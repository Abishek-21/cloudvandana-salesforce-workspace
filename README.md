# Salesforce Workspace

[Live app](https://cloudvandana-abishek-budhiraja.onrender.com)

CloudVandana Associate Software Engineer assignment, built with React, FastAPI and Salesforce REST APIs.

The app supports create, view, edit and delete for Accounts, Opportunities, Leads, Contacts and Cases. Forms use Salesforce metadata for field labels, types and picklists. Records load 20 at a time, with the next page loaded on scroll.

Use the reviewer login supplied separately. The free Render service may take about a minute to wake up.

## Run locally

Tested with Python 3.13 and Node.js 22.

```sh
git clone https://github.com/Abishek-21/cloudvandana-salesforce-workspace.git
cd cloudvandana-salesforce-workspace
cp .env.example .env
```

Create a Salesforce External Client App with Local distribution. Enable the OAuth web server flow with PKCE, select `api` and `refresh_token` / `offline_access`, and require the consumer secret for the web server and refresh-token flows.

Register `http://localhost:8008/auth/callback` as its local callback, then fill in `.env`:

```dotenv
SALESFORCE_LOGIN_URL=https://YOUR-DOMAIN.my.salesforce.com
SALESFORCE_CLIENT_ID=your_consumer_key
SALESFORCE_CLIENT_SECRET=your_consumer_secret
SALESFORCE_CALLBACK_URL=http://localhost:8008/auth/callback
```

`SALESFORCE_API_VERSION` can stay blank to discover the org's supported version. The `.env` file is excluded from Git.

```sh
sh run-local.sh
```

This installs missing dependencies, builds React and starts the app at http://localhost:8008. Stop with Control+C and restart after changing `.env`.

## Hosting

The live app runs on Render independently of the local computer. To deploy a copy, create a Docker Web Service using the Free plan and `/healthz` as the health check. `render.yaml` contains the service template.

Set the four Salesforce environment variables in Render. Use the deployed HTTPS address followed by `/auth/callback` for `SALESFORCE_CALLBACK_URL`, and register the same URL in Salesforce. The current callback is:

```text
https://cloudvandana-abishek-budhiraja.onrender.com/auth/callback
```

The Docker image serves React through FastAPI on Render's `PORT`. The current service uses **Manual Deploy → Deploy latest commit** after pushing to GitHub.

For return to the app after logout, set **Setup → Session Settings → Logout Page Settings → Logout URL** to the app's home address. This is an org-wide setting. Logout also ends the Salesforce browser session and signs out other tabs using that org.

## Tests

After local setup:

```sh
.venv/bin/python -m pytest -q
npm run build
```

The last check passed 33 backend tests and the frontend build. CRUD was also checked through the hosted app with the reviewer account; the temporary records were deleted afterwards.

## Limitations

- Sessions are stored in memory, so a server restart requires another login. Salesforce keeps the records.
- The backend runs with one worker.
- Lookup fields take Salesforce record IDs; lookup search is not included.
- Salesforce permissions and business rules still apply to all operations.
