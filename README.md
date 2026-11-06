# Salesforce Workspace

My submission for the CloudVandana Associate Software Engineer assignment.

[Open the application](https://sanitary-motive-skipper.ngrok-free.dev) - available while the local server and ngrok are running. Salesforce sign-in with an authorized user in the configured org is required.

This app connects to a Salesforce Developer Org and lets you manage Accounts, Opportunities, Leads, Contacts and Cases from one screen. It uses React for the frontend and Python with FastAPI for the backend. Records are read from and saved directly to Salesforce through its REST API.

## Features

- Sign in to Salesforce using OAuth 2.0 through an External Client App.
- Switch between the five objects using a dropdown.
- View records and create, edit or delete them.
- Display 9 fields for each object and 10 for Case, with form labels and field settings taken from Salesforce.
- Load 20 records initially, then load the next 20 when scrolling to the bottom. There is also a button to load more.
- Show Salesforce validation errors and respect the signed-in user's permissions.

## Run locally

The app was tested on macOS with Python 3.13 and Node.js 22.17. You will also need a Salesforce Developer Org and an External Client App configured as described below.

```sh
git clone https://github.com/Abishek-21/cloudvandana-salesforce-workspace.git
cd cloudvandana-salesforce-workspace
cp .env.example .env
```

Fill in the Salesforce settings in `.env`, then run:

```sh
sh run-local.sh
```

The script creates a Python environment, installs missing dependencies, builds the frontend and starts the server. Open [http://localhost:8008](http://localhost:8008), then sign in to Salesforce.

Use `Control+C` to stop the server. Restart it after changing `.env`.

## Connect Salesforce

In your Developer Org's Setup, create a local **External Client App** with these settings:

| Setting | Value |
| --- | --- |
| App name | CloudVandana Salesforce Workspace |
| Callback URL | `http://localhost:8008/auth/callback` |
| OAuth scopes | `api` and `refresh_token` / `offline_access` |
| Flow | Authorization code / web server flow with PKCE |
| Consumer secret | Required for the web server and refresh token flows |

Allow your user to authorize the app in its OAuth policies. Copy the consumer key and secret into `.env`:

```dotenv
SALESFORCE_LOGIN_URL=https://YOUR-DOMAIN.my.salesforce.com
SALESFORCE_CLIENT_ID=your_consumer_key
SALESFORCE_CLIENT_SECRET=your_consumer_secret
SALESFORCE_CALLBACK_URL=http://localhost:8008/auth/callback
SALESFORCE_API_VERSION=
```

Use your org's My Domain URL for the login URL. Leaving the API version blank lets the backend discover it from Salesforce. The callback URL must match the External Client App exactly.

The `.env` file is excluded from Git. Keep the consumer secret there, on the backend. Salesforce CLI login is not required to run this app.

## Remote review

For review without keeping a local computer running, the repository includes a `Dockerfile` and Render Blueprint (`render.yaml`). Create a free Docker Web Service on Render using this repository. Set the four Salesforce environment variables in Render, using the service's public HTTPS URL followed by `/auth/callback` for the callback. Register that exact callback in the Salesforce External Client App. Use `/healthz` for the health check.

The image builds React and serves it from the Python backend. It binds to Render's `PORT` on `0.0.0.0`, runs as a non-root user and excludes local credentials from its build context. Credentials are supplied through the hosting environment, not the Dockerfile or Git.

Render's free service sleeps after inactivity and wakes on a visit. Waking may take about a minute. In-memory login sessions clear after a restart or sleep, so users sign in again; records remain in Salesforce. Each browser still needs an authorized Salesforce login in the configured org.

### Local tunnel alternative

The local app can also be reached through an ngrok HTTPS tunnel. Install ngrok, connect your account, then set `SALESFORCE_CALLBACK_URL` to your assigned public domain followed by `/auth/callback`. Register that same URL in the Salesforce External Client App.

With those settings in place, run:

```sh
sh run-review.sh
```

This builds the frontend, starts the local backend and forwards its port through ngrok. Keep the terminal open and the computer awake and connected. Control+C stops both processes. Stop an existing server on port 8008 before using this launcher.

The public hostname is explicitly allowed by the backend. HTTPS login uses Secure, HttpOnly session cookies, and write requests must use the configured public origin. Request inspection is disabled in the tunnel command. Each browser signs in separately; sharing the link does not share a Salesforce session. Reviewers need an authorized user in the configured org.

Ngrok's free plan displays a visitor notice before opening the app. The link is available while the local server and tunnel are running.

## How it works

The React frontend calls the FastAPI backend, which handles login and sends requests to Salesforce. Access and refresh tokens stay on the server; the browser uses a session cookie. OAuth uses PKCE and a state check, and record changes require a CSRF token.

The backend reads Salesforce object metadata to get field labels, types, picklist values and required fields. If an org has extra required fields, it replaces optional fields while keeping the form within the assignment's ten-field limit.

Pagination uses the last record's ID to fetch the next 20 records. Newly created records appear at the top so they are easy to find. Reloading restores the normal ID order.

| File | Purpose |
| --- | --- |
| `src/main.jsx` | Object selector, records table and forms |
| `src/styles.css` | Page layout and styling |
| `backend/main.py` | OAuth, sessions and Salesforce API calls |
| `tests/` | Backend tests with mock Salesforce responses |
| `run-local.sh` | Local setup and startup script |

## Testing

```sh
.venv/bin/python -m pytest -q
npm run build
```

On 6 November 2026, all 25 backend tests passed, including public HTTPS OAuth, secure cookies, host validation, origin checks and the cloud health endpoint. The frontend production build passed. Live checks in the Developer Org passed for login, create, view, update and delete across all five objects. Pagination was checked with 35 Account records. All 29 temporary records created for testing were deleted afterwards.

The public ngrok link was also checked for OAuth login, all five object views, record details and pagination reaching the end of the available records.

More details are in [VERIFICATION.md](VERIFICATION.md).

## Current limitations

- The app supports local running, ngrok access and cloud deployment. The plain localhost link only works on the computer running the server. A free cloud service may have a cold start after inactivity.
- Sessions are stored in memory, so restarting the server requires signing in again. The app runs with one backend worker.
- Lookup fields accept Salesforce record IDs. A lookup search is not included yet.
- Salesforce handles custom validation rules, duplicate rules, dependent picklists and record-type restrictions. Any errors are shown in the form.

## Documentation used

- [Salesforce OAuth web server flow](https://help.salesforce.com/s/articleView?id=sf.remoteaccess_oauth_web_server_flow.htm&type=5)
- [Salesforce REST API](https://developer.salesforce.com/docs/platform/api-rest/guide/intro_rest.html)

Abishek Budhiraja
