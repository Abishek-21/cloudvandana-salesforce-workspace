"""Local Salesforce CRUD application. Tokens stay in memory on the Python server."""
from __future__ import annotations

import base64
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
import hashlib
import hmac
import os
from pathlib import Path
import re
import secrets
from threading import RLock
import time
from typing import Any
from urllib.parse import urlencode, urlsplit

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict
from starlette.middleware.trustedhost import TrustedHostMiddleware
import httpx

ROOT = Path(__file__).resolve().parent.parent
OBJECT_FIELDS = {
    "Account": ["Id", "Name", "Type", "Industry", "Phone", "Website", "BillingCity", "BillingCountry", "Description"],
    "Opportunity": ["Id", "Name", "StageName", "CloseDate", "Amount", "AccountId", "Probability", "Type", "Description"],
    "Lead": ["Id", "FirstName", "LastName", "Company", "Email", "Phone", "Status", "Title", "Description"],
    "Contact": ["Id", "FirstName", "LastName", "AccountId", "Email", "Phone", "Title", "Department", "Description"],
    "Case": ["Id", "CaseNumber", "Subject", "Status", "Priority", "Origin", "ContactId", "AccountId", "Description", "SuppliedEmail"],
}
ID_RE = re.compile(r"[A-Za-z0-9]{15}(?:[A-Za-z0-9]{3})?\Z")
FIELD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")
SESSION_COOKIE = "cv_session"
LOGIN_COOKIE = "cv_login"
SESSION_SECONDS = 8 * 60 * 60


def salesforce_url(value: str) -> str:
    """Accept only HTTPS Salesforce hosts; never turn response data into an open proxy."""
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname
            or not parsed.hostname.endswith(".salesforce.com")
            or parsed.username or parsed.password or parsed.port not in (None, 443)
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise ValueError("Use an HTTPS Salesforce My Domain URL without a page path.")
    return value.rstrip("/")


def callback_address(value: str):
    """Allow localhost HTTP or one explicitly configured public HTTPS callback."""
    parsed = urlsplit(value)
    host = parsed.hostname or ""
    local = parsed.scheme == "http" and host in ("localhost", "127.0.0.1")
    public = (parsed.scheme == "https" and parsed.port in (None, 443)
              and "." in host and not host.endswith(".localhost")
              and all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", part)
                      for part in host.split("."))
              and not re.fullmatch(r"[0-9.]+", host))
    if (not (local or public) or parsed.path != "/auth/callback"
            or parsed.query or parsed.fragment or parsed.username or parsed.password):
        raise ValueError("Use a localhost HTTP or public HTTPS /auth/callback URL.")
    return parsed


@dataclass(frozen=True)
class Settings:
    login_url: str = ""
    client_id: str = ""
    client_secret: str = ""
    callback_url: str = "http://localhost:8008/auth/callback"
    api_version: str = ""

    @classmethod
    def read(cls):
        load_dotenv(ROOT / ".env")
        return cls(*(os.getenv(name, "").strip() for name in [
            "SALESFORCE_LOGIN_URL", "SALESFORCE_CLIENT_ID", "SALESFORCE_CLIENT_SECRET"
        ]), callback_url=os.getenv("SALESFORCE_CALLBACK_URL", "http://localhost:8008/auth/callback").strip(),
            api_version=os.getenv("SALESFORCE_API_VERSION", "").strip())

    def missing(self) -> list[str]:
        missing = [key for key, value in [
            ("SALESFORCE_LOGIN_URL", self.login_url), ("SALESFORCE_CLIENT_ID", self.client_id),
            ("SALESFORCE_CLIENT_SECRET", self.client_secret)
        ] if not value or "YOUR-DOMAIN" in value]
        if not missing:
            try:
                salesforce_url(self.login_url)
                callback_address(self.callback_url)
                if self.api_version and not re.fullmatch(r"\d{2,3}\.0", self.api_version):
                    raise ValueError("Invalid API version")
            except ValueError:
                missing.append("Valid My Domain, localhost HTTP or public HTTPS callback, and API version settings")
        return missing

    @property
    def origin(self):
        parsed = urlsplit(self.callback_url)
        return f"{parsed.scheme}://{parsed.netloc}"

    @property
    def secure_cookies(self):
        return urlsplit(self.callback_url).scheme == "https"


@dataclass
class Session:
    access_token: str
    refresh_token: str
    instance_url: str
    csrf: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    expires: float = field(default_factory=lambda: time.time() + SESSION_SECONDS)
    version: str = ""
    schemas: dict = field(default_factory=dict)
    lock: RLock = field(default_factory=RLock)


class Store:
    def __init__(self):
        self.sessions: dict[str, Session] = {}
        self.pending: dict[str, dict] = {}
        self.lock = RLock()

    def prune(self):
        now = time.time()
        with self.lock:
            self.sessions = {k: v for k, v in self.sessions.items() if v.expires > now}
            self.pending = {k: v for k, v in self.pending.items() if v["expires"] > now}


class RecordValues(BaseModel):
    model_config = ConfigDict(extra="forbid")
    values: dict[str, Any]


def create_app(settings: Settings | None = None, transport=None):
    cfg = settings or Settings.read()
    store = Store()
    http = httpx.Client(timeout=25, follow_redirects=False, trust_env=False, transport=transport)

    @asynccontextmanager
    async def lifespan(app):
        yield
        http.close()
        store.sessions.clear()
        store.pending.clear()

    app = FastAPI(title="Salesforce Workspace", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.store = store
    app.state.settings = cfg
    hosts = ["localhost", "127.0.0.1", "testserver"]
    try:
        hosts.append(callback_address(cfg.callback_url).hostname)
    except ValueError:
        pass
    # Render's assigned hostname is available before Salesforce is configured.
    # This lets the health check work during the first deploy without a wildcard.
    render_host = os.getenv("RENDER_EXTERNAL_HOSTNAME", "")
    if render_host:
        try:
            hosts.append(callback_address(f"https://{render_host}/auth/callback").hostname)
        except ValueError:
            pass
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)

    @app.middleware("http")
    async def headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return response

    @app.exception_handler(httpx.RequestError)
    async def network_error(request, exc):
        return JSONResponse(status_code=502, content={"detail": "Could not reach Salesforce. Check your connection and try again."})

    def session(request: Request) -> Session:
        store.prune()
        sid = request.cookies.get(SESSION_COOKIE, "")
        with store.lock:
            result = store.sessions.get(sid)
        if not result:
            raise HTTPException(401, "Please log in to Salesforce.")
        return result

    def mutation_session(request: Request, current: Session = Depends(session)):
        origin = request.headers.get("origin")
        if origin and origin != cfg.origin:
            raise HTTPException(403, "This request came from another website. Reload the application.")
        if not hmac.compare_digest(request.headers.get("x-csrf-token", ""), current.csrf):
            raise HTTPException(403, "Your form session changed. Reload the application and try again.")
        return current

    def require_object(name):
        if name not in OBJECT_FIELDS:
            raise HTTPException(404, "Choose one of the five supported Salesforce objects.")

    def api(current, method, path, **kwargs):
        if not path.startswith("/services/") or ".." in path:
            raise HTTPException(400, "Invalid Salesforce resource.")
        with current.lock:
            response = http.request(method, current.instance_url + path,
                                    headers={"Authorization": f"Bearer {current.access_token}"}, **kwargs)
            if response.status_code == 401 and current.refresh_token:
                refreshed = http.post(cfg.login_url + "/services/oauth2/token", data={
                    "grant_type": "refresh_token", "refresh_token": current.refresh_token,
                    "client_id": cfg.client_id, "client_secret": cfg.client_secret,
                })
                if refreshed.is_success:
                    data = refreshed.json()
                    current.access_token = data["access_token"]
                    current.refresh_token = data.get("refresh_token", current.refresh_token)
                    response = http.request(method, current.instance_url + path,
                                            headers={"Authorization": f"Bearer {current.access_token}"}, **kwargs)
            if response.status_code == 401:
                current.expires = 0
                raise HTTPException(401, "Your Salesforce session expired. Please log in again.")
            if response.is_error:
                try:
                    errors = response.json()
                    if not isinstance(errors, list):
                        errors = [errors]
                    detail = "; ".join(str(e.get("message", "Salesforce rejected this request.")) for e in errors if isinstance(e, dict))
                except ValueError:
                    detail = "Salesforce could not complete this operation. Please try again."
                raise HTTPException(response.status_code if response.status_code in (400, 403, 404, 409) else 502,
                                    detail or "Salesforce could not complete this operation.")
            return response.json() if response.content else None

    def version(current):
        if not current.version:
            if cfg.api_version:
                current.version = cfg.api_version
            else:
                versions = api(current, "GET", "/services/data/")
                current.version = max(versions, key=lambda item: float(item["version"]))["version"]
        return f"/services/data/v{current.version}"

    def schema(current, name):
        require_object(name)
        with current.lock:
            cached = current.schemas.get(name)
            if cached and cached[0] > time.time():
                return cached[1]
            raw = api(current, "GET", f"{version(current)}/sobjects/{name}/describe")
            if not raw.get("queryable"):
                raise HTTPException(403, f"Your Salesforce user cannot read {name} records.")
            available = {f["name"]: f for f in raw["fields"] if FIELD_RE.fullmatch(f["name"])}
            required = [f["name"] for f in available.values()
                        if f.get("createable") and not f.get("nillable") and not f.get("defaultedOnCreate")]
            names = [n for n in OBJECT_FIELDS[name] if n in available]
            for n in required:
                if n not in names:
                    if len(names) == 10:
                        removable = next((v for v in reversed(names) if v not in required and v != "Id"), None)
                        if not removable:
                            raise HTTPException(422, "This org requires more fields than the assignment's 10-field limit. Review its custom requirements.")
                        names.remove(removable)
                    names.append(n)
            if len(names) < 5:
                raise HTTPException(403, "Your user has access to fewer than five configured fields. Review Salesforce field permissions.")
            fields = []
            for n in names:
                f = available[n]
                fields.append({"name": n, "label": f["label"], "type": f["type"],
                               "createable": bool(f.get("createable")), "updateable": bool(f.get("updateable")),
                               "required": n in required, "nillable": bool(f.get("nillable")),
                               "length": f.get("length", 0), "scale": f.get("scale", 0),
                               "default": f.get("defaultValue"),
                               "referenceTo": f.get("referenceTo", []),
                               "options": [{"value": p["value"], "label": p["label"], "default": p.get("defaultValue", False)}
                                           for p in f.get("picklistValues", []) if p.get("active")]})
            result = {"name": name, "label": raw.get("label", name), "pluralLabel": raw.get("labelPlural", name),
                      "createable": bool(raw.get("createable")), "updateable": bool(raw.get("updateable")),
                      "deletable": bool(raw.get("deletable")), "keyPrefix": raw.get("keyPrefix"), "fields": fields}
            current.schemas[name] = (time.time() + 120, result)
            return result

    def record_id(value, meta):
        if not ID_RE.fullmatch(value) or (meta.get("keyPrefix") and not value.startswith(meta["keyPrefix"])):
            raise HTTPException(400, "Invalid record ID for this object.")
        return value

    def values_for(payload, meta, create):
        capability = "createable" if create else "updateable"
        if not meta[capability]:
            raise HTTPException(403, "Your Salesforce user does not have permission for this operation.")
        allowed = {f["name"]: f for f in meta["fields"] if f[capability]}
        if not payload.values:
            raise HTTPException(422, "Enter at least one field value.")
        unknown = set(payload.values) - set(allowed)
        if unknown:
            raise HTTPException(422, "Some fields are not editable: " + ", ".join(sorted(unknown)))
        if any(isinstance(v, (dict, list)) for v in payload.values.values()):
            raise HTTPException(422, "Fields must contain individual values.")
        if create:
            missing = [f["label"] for f in allowed.values() if f["required"] and payload.values.get(f["name"]) in (None, "")]
            if missing:
                raise HTTPException(422, "Complete required fields: " + ", ".join(missing))
        return payload.values

    @app.get("/healthz")
    def health():
        return {"status": "ok"}

    @app.get("/api/session")
    def session_info(request: Request):
        store.prune()
        current = store.sessions.get(request.cookies.get(SESSION_COOKIE, ""))
        return {"authenticated": bool(current), "configured": not cfg.missing(), "missing": cfg.missing(),
                "csrfToken": current.csrf if current else None,
                "org": urlsplit(current.instance_url).hostname if current else None}

    @app.get("/auth/login")
    def login(request: Request):
        if cfg.missing():
            return RedirectResponse("/?auth_error=configuration", status_code=303)
        # Start on the public host so the login cookie and callback share a host.
        if cfg.secure_cookies and request.url.hostname != urlsplit(cfg.callback_url).hostname:
            return RedirectResponse(cfg.origin + "/auth/login", status_code=303)
        store.prune()
        state, verifier, nonce = (secrets.token_urlsafe(48) for _ in range(3))
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        with store.lock:
            store.pending[state] = {"verifier": verifier, "nonce": nonce, "expires": time.time() + 600}
        url = cfg.login_url + "/services/oauth2/authorize?" + urlencode({
            "response_type": "code", "client_id": cfg.client_id, "redirect_uri": cfg.callback_url,
            "scope": "api refresh_token", "state": state, "code_challenge": challenge, "code_challenge_method": "S256",
        })
        response = RedirectResponse(url, status_code=303)
        response.set_cookie(LOGIN_COOKIE, nonce, httponly=True, secure=cfg.secure_cookies, samesite="lax", max_age=600)
        return response

    @app.get("/auth/callback")
    def callback(request: Request, state: str = "", code: str = "", error: str = ""):
        store.prune()
        with store.lock:
            pending = store.pending.pop(state, None)
        if not pending or not hmac.compare_digest(pending["nonce"], request.cookies.get(LOGIN_COOKIE, "")):
            raise HTTPException(400, "Invalid or expired login request. Start Salesforce login again.")
        if error or not code:
            response = RedirectResponse("/?auth_error=cancelled", status_code=303)
            response.delete_cookie(LOGIN_COOKIE, secure=cfg.secure_cookies, httponly=True, samesite="lax")
            return response
        token = http.post(cfg.login_url + "/services/oauth2/token", data={
            "grant_type": "authorization_code", "code": code, "client_id": cfg.client_id,
            "client_secret": cfg.client_secret, "redirect_uri": cfg.callback_url, "code_verifier": pending["verifier"],
        })
        if not token.is_success:
            response = RedirectResponse("/?auth_error=exchange", status_code=303)
            response.delete_cookie(LOGIN_COOKIE, secure=cfg.secure_cookies, httponly=True, samesite="lax")
            return response
        try:
            data = token.json()
            connected = Session(access_token=data["access_token"], refresh_token=data.get("refresh_token", ""),
                                instance_url=salesforce_url(data["instance_url"]))
        except (ValueError, KeyError):
            raise HTTPException(502, "Salesforce returned an invalid login response. Start login again.")
        sid = secrets.token_urlsafe(48)
        with store.lock:
            old = request.cookies.get(SESSION_COOKIE)
            if old:
                store.sessions.pop(old, None)
            store.sessions[sid] = connected
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(SESSION_COOKIE, sid, httponly=True, secure=cfg.secure_cookies, samesite="lax", max_age=SESSION_SECONDS)
        response.delete_cookie(LOGIN_COOKIE, secure=cfg.secure_cookies, httponly=True, samesite="lax")
        return response

    @app.post("/auth/logout")
    def logout(request: Request, current=Depends(mutation_session)):
        with store.lock:
            store.sessions.pop(request.cookies.get(SESSION_COOKIE, ""), None)
        try:
            http.post(cfg.login_url + "/services/oauth2/revoke", data={"token": current.refresh_token or current.access_token})
        except httpx.RequestError:
            pass
        response = JSONResponse({"success": True})
        response.delete_cookie(SESSION_COOKIE, secure=cfg.secure_cookies, httponly=True, samesite="lax")
        return response

    @app.get("/api/objects")
    def objects(current=Depends(session)):
        return {"objects": list(OBJECT_FIELDS)}

    @app.get("/api/objects/{name}/schema")
    def object_schema(name: str, current=Depends(session)):
        return schema(current, name)

    @app.get("/api/objects/{name}/records")
    def records(name: str, after: str = "", current=Depends(session)):
        meta = schema(current, name)
        where = f" WHERE Id > '{record_id(after, meta)}'" if after else ""
        fields = ",".join(f["name"] for f in meta["fields"])
        query = f"SELECT {fields} FROM {name}{where} ORDER BY Id ASC LIMIT 20"
        result = api(current, "GET", version(current) + "/query", params={"q": query})
        rows = [{k: v for k, v in r.items() if k != "attributes"} for r in result["records"]]
        return {"records": rows, "nextCursor": rows[-1]["Id"] if len(rows) == 20 else None}

    @app.get("/api/objects/{name}/records/{rid}")
    def read_record(name: str, rid: str, current=Depends(session)):
        meta = schema(current, name)
        fields = ",".join(f["name"] for f in meta["fields"])
        result = api(current, "GET", f"{version(current)}/sobjects/{name}/{record_id(rid, meta)}", params={"fields": fields})
        return {k: v for k, v in result.items() if k != "attributes"}

    @app.post("/api/objects/{name}/records", status_code=201)
    def create_record(name: str, payload: RecordValues, current=Depends(mutation_session)):
        meta = schema(current, name)
        return api(current, "POST", f"{version(current)}/sobjects/{name}", json=values_for(payload, meta, True))

    @app.patch("/api/objects/{name}/records/{rid}")
    def update_record(name: str, rid: str, payload: RecordValues, current=Depends(mutation_session)):
        meta = schema(current, name)
        api(current, "PATCH", f"{version(current)}/sobjects/{name}/{record_id(rid, meta)}", json=values_for(payload, meta, False))
        return {"success": True, "id": rid}

    @app.delete("/api/objects/{name}/records/{rid}")
    def delete_record(name: str, rid: str, current=Depends(mutation_session)):
        meta = schema(current, name)
        if not meta["deletable"]:
            raise HTTPException(403, "Your Salesforce user cannot delete these records.")
        api(current, "DELETE", f"{version(current)}/sobjects/{name}/{record_id(rid, meta)}")
        return {"success": True, "id": rid}

    if (ROOT / "dist").is_dir():
        app.mount("/", StaticFiles(directory=ROOT / "dist", html=True), name="frontend")
    else:
        @app.get("/")
        def not_built():
            return JSONResponse(status_code=503, content={"detail": "Build the frontend with npm run build, then restart the server."})
    return app


app = create_app()
