# Salesforce Workspace

CloudVandana Associate Software Engineer assignment for Abishek Budhiraja.

A local React application with a Python/FastAPI backend. Salesforce remains the source of truth: the app uses Salesforce REST APIs and the signed-in user's permissions. No custom Apex or LWC deployment is required for these standard-object operations.

## Assignment requirements

- [x] Log in through an External Client App using OAuth authorization code + PKCE.
- [x] Select Account, Opportunity, Lead, Contact or Case from one dropdown.
- [x] Display 5–10 fields for the selected object, respecting available metadata.
- [x] Create, view, update and delete records through this application.
- [x] Load records in pages of 20 and load the next page when scrolling to the end.
- [x] Run on a local server and document reviewer access.
- [x] Complete live-org verification for all five objects.
- [ ] Send the repository link and updated resume after final submission review.

Live verification was completed on 6 November 2026. See [VERIFICATION.md](VERIFICATION.md) for the scope, evidence and cleanup. Sending the application is a separate final step.

## Local setup

Verified environment: Python 3.13 and Node.js 22.17. The frontend needs a Node version supported by the locked Vite release.

1. Open this folder in VS Code.
2. Create a Python environment: `python3 -m venv .venv`.
3. Install the backend: `.venv/bin/python -m pip install -r requirements.lock.txt`.
4. Install frontend packages: `npm ci`.
5. Copy `.env.example` to `.env` and complete the Salesforce settings locally.
6. Run `sh run-local.sh` and open **http://localhost:8008**.

The interface can be previewed without credentials. Salesforce operations require a configured External Client App and successful consent. Restart the server after changing `.env`.

## Salesforce setup

The app's OAuth authorization is separate from signing VS Code/Salesforce CLI into an org.

In the Developer Org's Setup, create a **local External Client App**:

- Name: `CloudVandana Salesforce Workspace`.
- Callback URL: `http://localhost:8008/auth/callback` (must match `.env` exactly).
- Enable OAuth with `api` and `refresh_token` / `offline_access` scopes.
- Enable the authorization code / web server flow and require PKCE.
- Require the consumer secret for the web server flow and refresh token flow.
- Allow the intended Developer Org user to authorize the application under its OAuth policies.
- Obtain the consumer key and secret and enter them in the local `.env` file.

Use the org's My Domain URL for `SALESFORCE_LOGIN_URL`. Do not use a Lightning page URL, a sandbox belonging to an employer, or a production org. Do not commit `.env` or authorization files. Log in and grant consent in the browser yourself.

If connecting the CLI as well, use Salesforce's documented `sf org login web` flow for your org and the applicable External Client App settings. The CLI's default callback (`http://localhost:1717/OauthRedirect`) is different from this app's callback. Do not substitute a CLI access token for the app's login flow.

## Local hosting and review

`localhost` is reachable only on the computer running this application. A reviewer cannot open your Mac's localhost from their computer. The PDF says both "free online server" and "local server"; confirm whether they want to run the repository themselves, view a live demonstration, or receive an externally reachable hosted link. No public deployment or tunnel is configured without resolving that requirement.

## Implementation

`src/main.jsx` contains the React interface and metadata-driven record dialog. `backend/main.py` contains OAuth, session management, validation and REST API routes. `tests/` contains fake Salesforce responses and automated tests; the real application does not import these test fixtures.

- Salesforce describes each object so forms use its field labels, field types, active picklist values, required fields and edit permissions.
- Each object has a configured selection of nine or ten fields. Required custom fields are added by replacing optional fields within the ten-field limit. If the org cannot satisfy that limit, the app shows an error instead of silently dropping required fields.
- Records use `ORDER BY Id ASC LIMIT 20` and an ID cursor. This avoids an ever-growing SOQL OFFSET. After a create, the new record is shown first; Reload restores the server's ID order. IDs are de-duplicated between pages.
- Write requests carry a CSRF token. OAuth uses a browser-bound state value, a one-use authorization code and PKCE.
- Access and refresh tokens stay in process memory. The browser receives only an opaque HttpOnly session cookie and a CSRF token. Restarting the server clears sessions. Run one local worker.
- The backend discovers a supported REST API version from the connected org unless an explicit version is configured.
- New records stay visible after creation. The save path distinguishes a successful write from a failed subsequent read, preventing an accidental duplicate retry.

## Tests and demo

Run `.venv/bin/python -m pytest -q` for backend tests and `npm run build` for the frontend build. The exact installed Python versions are captured in `requirements.lock.txt`; `requirements.txt` records the direct dependency ranges.

For a demonstration: sign in, choose each object, open a record, create a clearly identified sample, edit it, then delete only that sample. To demonstrate pagination, use an object with more than 20 records and scroll the table to the end. A manual "Load next 20 records" button is also available.

## Known boundaries

This is a single-machine assessment application, not a multi-worker production service. Sessions are intentionally not persisted. Custom validation rules, duplicate rules, dependent picklists and record-type restrictions remain enforced by Salesforce; errors are shown to the user. Reference fields accept Salesforce record IDs rather than providing a separate lookup-search component. Read-only fields are available in the table and view dialog but excluded from create/edit forms.

Account fields: Id, Name, Type, Industry, Phone, Website, BillingCity, BillingCountry, Description. Opportunity: Id, Name, StageName, CloseDate, Amount, AccountId, Probability, Type, Description. Lead: Id, FirstName, LastName, Company, Email, Phone, Status, Title, Description. Contact: Id, FirstName, LastName, AccountId, Email, Phone, Title, Department, Description. Case: Id, CaseNumber, Subject, Status, Priority, Origin, ContactId, AccountId, Description, SuppliedEmail.

Automated tests use fake Salesforce responses. They do not replace the live-org verification documented separately.

## References

- Salesforce web server OAuth flow: https://help.salesforce.com/s/articleView?id=sf.remoteaccess_oauth_web_server_flow.htm&type=5
- Salesforce REST API: https://developer.salesforce.com/docs/platform/api-rest/guide/intro_rest.html
- Salesforce CLI authorization: https://developer.salesforce.com/docs/platform/sfdx-dev/guide/sfdx-dev-auth-eca.html
