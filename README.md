# Salesforce Workspace

My submission for the CloudVandana Associate Software Engineer assignment.

**Live app:** [cloudvandana-abishek-budhiraja.onrender.com](https://cloudvandana-abishek-budhiraja.onrender.com)

The app is hosted on Render and works independently of my computer. The free service sleeps after inactivity, so the first visit can take about a minute to load. Salesforce sign-in with an authorized user in the configured Developer Org is required.

## About the app

This app lets you manage Accounts, Opportunities, Leads, Contacts and Cases from one screen. I used React for the interface and Python with FastAPI for the backend. The backend connects to Salesforce through its REST API, and Salesforce stores the records.

You can:

- Sign in through a Salesforce External Client App using OAuth 2.0 with PKCE.
- Switch between the five objects using a dropdown.
- View, create, edit and delete records.
- See nine fields per object and ten for Case, with labels, types and picklist values taken from Salesforce metadata.
- Load 20 records initially, then load the next page when scrolling to the bottom. A load-more button is also available.
- See validation errors returned by Salesforce. The signed-in user's permissions apply to every operation.

## Using the hosted app

Open the live link, click **Log in to Salesforce**, and sign in as an authorized user in the connected org. Once connected, choose an object to view its records.

Each browser has its own session. The public link does not share my login, and an account in a different Salesforce org cannot automatically access this configured org. Review access needs to be arranged separately.

The server keeps access and refresh tokens in memory. A restart or an idle shutdown clears login sessions, so users sign in again. This does not remove records from Salesforce.

## How it works

React sends requests to FastAPI. The backend handles OAuth, reads object metadata, validates requests and calls Salesforce. Consumer credentials and tokens stay on the backend; the browser uses an HttpOnly session cookie, marked Secure for HTTPS. Write requests also require a CSRF token and check the request origin.

Forms use Salesforce metadata for field labels, types, active picklist values, required fields and edit permissions. Extra required fields can replace optional fields within the ten-field limit. If an org's requirements cannot fit within that limit, the app shows an error.

Pagination uses `ORDER BY Id ASC LIMIT 20`. The next request adds `WHERE Id > '<last record ID>'`. Newly created records appear at the top; reloading restores the normal ID order. Duplicate IDs are removed between pages.

## Project files

| File or folder | Purpose |
| --- | --- |
| `src/main.jsx` | Object dropdown, records table, forms and pagination |
| `src/styles.css` | Layout and styling |
| `backend/main.py` | OAuth, sessions, metadata, validation and Salesforce API calls |
| `tests/` | Backend tests with mock Salesforce responses |
| `Dockerfile` | Builds React and packages the Python server |
| `.dockerignore` | Keeps local credentials and unnecessary files out of the build context |
| `render.yaml` | Free Render service template and environment variable names |
| `.env.example` | Local configuration template |
| `run-local.sh` | Local setup and startup script |
| `run-review.sh` | Optional local ngrok launcher; not used by the hosted app |
| `VERIFICATION.md` | Detailed test and deployment results |
| `WALKTHROUGH.md` | Request flows and demo notes |

## Salesforce configuration

To run your own copy, use your own Developer Org and create an **External Client App** in Setup:

| Setting | Value |
| --- | --- |
| App name | CloudVandana Salesforce Workspace, or a name of your choice |
| Distribution | Local |
| OAuth scopes | `api` and `refresh_token` / `offline_access` |
| Authentication | Authorization code / web server flow with PKCE |
| Consumer secret | Required for the web server and refresh token flows |
| Callback for local development | `http://localhost:8008/auth/callback` |
| Callback for a cloud deployment | Your service's HTTPS URL followed by `/auth/callback` |

Allow the intended org user to authorize the app under its OAuth policies. The callback registered in Salesforce must exactly match `SALESFORCE_CALLBACK_URL` for that deployment. The current hosted app uses:

```text
https://cloudvandana-abishek-budhiraja.onrender.com/auth/callback
```

These are the backend settings:

```dotenv
SALESFORCE_LOGIN_URL=https://YOUR-DOMAIN.my.salesforce.com
SALESFORCE_CLIENT_ID=your_consumer_key
SALESFORCE_CLIENT_SECRET=your_consumer_secret
SALESFORCE_CALLBACK_URL=http://localhost:8008/auth/callback
SALESFORCE_API_VERSION=
```

Use your org's My Domain URL for `SALESFORCE_LOGIN_URL`. Leaving the API version blank lets the backend discover it. Use the cloud callback instead of localhost when deploying to Render.

For local development, put these settings in `.env`. For Render, put them in the service's environment settings. The `.env` file is excluded from Git. Salesforce CLI login is not required.

## Run locally

Tested with Python 3.13 and Node.js 22.17 on macOS. Configure the Salesforce app above with the localhost callback, then run:

```sh
git clone https://github.com/Abishek-21/cloudvandana-salesforce-workspace.git
cd cloudvandana-salesforce-workspace
cp .env.example .env
```

Fill in `.env` with your own connection settings, then start the app:

```sh
sh run-local.sh
```

The script creates a Python environment if needed, installs missing dependencies, builds React and starts FastAPI at [http://localhost:8008](http://localhost:8008). Keep that terminal open while developing. Control+C stops the server. Restart after changing `.env`.

## Deploy your own copy to Render

1. Create a **Web Service** from this repository, using the **Docker** runtime.
2. Select the **Free** compute plan and set the health check path to `/healthz`. The included `render.yaml` provides the equivalent Blueprint template.
3. Set the four required Salesforce environment variables from the configuration section. Use your own service's HTTPS callback URL.
4. Register that exact callback in your Salesforce External Client App.
5. Deploy and test Salesforce login through the cloud URL.

The Docker image builds the frontend and serves it through FastAPI. It runs as a non-root user and listens on `0.0.0.0` using Render's `PORT`. The app uses one backend worker because sessions are stored in process memory.

For the current service, code updates are deployed through **Manual Deploy → Deploy latest commit** in Render after pushing to GitHub. No local server or ngrok process is needed for the Render deployment.

## Testing

After setting up the local dependencies:

```sh
.venv/bin/python -m pytest -q
npm run build
```

On 6 November 2026, all 26 backend tests and the frontend production build passed. Testing covered OAuth state and PKCE, sessions, permissions, validation, CRUD, pagination, CSRF, HTTPS cookies, allowed hosts and cloud health checks.

Real-org CRUD was verified for all five objects, and the temporary test records were removed afterwards. Render built and deployed the Docker image successfully. Cloud login, all five object views, record details and pagination end-of-records handling were checked after the local server and ngrok were stopped.

See [VERIFICATION.md](VERIFICATION.md) for the full results.

## Limitations

- The free Render instance has a wake-up delay after inactivity.
- Sessions are cleared on restart or shutdown, and the app runs with one backend worker.
- Lookup fields accept Salesforce record IDs; lookup search is not included.
- Salesforce enforces custom validation rules, duplicate rules, dependent picklists and record-type restrictions. Errors are shown in the form.

## Documentation used

- [Salesforce OAuth web server flow](https://help.salesforce.com/s/articleView?id=sf.remoteaccess_oauth_web_server_flow.htm&type=5)
- [Salesforce REST API](https://developer.salesforce.com/docs/platform/api-rest/guide/intro_rest.html)
- [Render Docker deployment](https://render.com/docs/docker)
- [Render free-service limits](https://render.com/docs/free)

Abishek Budhiraja
