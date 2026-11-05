# Understanding and demonstrating the application

## Start with what you already know

Your integration experience maps directly to this project:

| Familiar concept | Where it appears here |
| --- | --- |
| An API request in Postman or MuleSoft | Python sends HTTP requests to Salesforce with `httpx`. |
| A Salesforce object and its fields | The app asks Salesforce for the object's describe metadata. |
| SOQL | The record-list endpoint builds a restricted query for one of five allowed objects. |
| Salesforce Flows / business rules | Salesforce still enforces validation, permissions, defaults and duplicate rules when an API changes a record. |
| Separating API responsibilities | React handles the interface; Python handles authentication, validation and communication with Salesforce. |
| Testing an integration | Backend tests use controlled fake API responses, followed by real-org browser tests. |

## Follow one read request

1. The user chooses `Account` in the dropdown.
2. React requests the object's schema and its first page of records from Python.
3. Python describes Account to learn labels, types, picklists, required fields and permissions.
4. Python sends a Salesforce REST query selecting the configured fields, ordered by ID, with a limit of 20.
5. React renders the returned columns and records.
6. At the end of the scroll area, React asks for the next page using the last returned record ID.

The next query adds `WHERE Id > '<last ID>'`. The backend validates the ID and only permits five object names and fields from its metadata. A browser cannot send an arbitrary SOQL query through this app.

## Understand the Salesforce login

1. The login button sends the browser to the Python login endpoint.
2. Python generates an unpredictable state value and a PKCE verifier/challenge.
3. Salesforce handles sign-in and consent. The app never asks for a Salesforce password.
4. Salesforce redirects to the registered localhost callback with a short-lived authorization code.
5. Python checks the browser-bound state and exchanges the code using the client secret and PKCE verifier.
6. Python keeps the access/refresh tokens in memory. The browser gets an opaque session cookie.

The CLI login and the web application's login are separate. A CLI access token does not demonstrate the assignment's External Client App OAuth flow.

## Understand one write request

The create/edit dialog is built from the same schema as the table. Read-only fields are not editable. When submitting, the application reads the actual form controls, validates editable field names and required values, and sends a Salesforce REST create or update request.

If Salesforce rejects a value, its error is shown in the form. A successful write is not retried just because a subsequent read failed. Delete has a confirmation dialog showing the specific record's name and ID.

## A five-minute demo

1. Open `http://localhost:8008` and use **Log in to Salesforce**.
2. Explain that the access token remains in Python, not browser local storage.
3. Select each of the five objects and point out the changing fields and picklists.
4. Create one clearly named demo record. Open its view dialog, update its description, and read back the change.
5. Delete only that demo record using the confirmation dialog.
6. With more than 20 available records, reload to show the first 20, then scroll down to load the next page.
7. Show the tests and verification notes, including the cleanup of the approved test data.

Do not delete existing practice records as part of the demonstration. The original live verification used specifically approved disposable records.

## Questions to practise answering

- Why are the client secret and access token kept in the backend?
- What does PKCE protect, and why also check OAuth state?
- How does Salesforce describe metadata change the forms?
- Why does the application display read-only IDs but exclude them from edit requests?
- Why use an ID cursor rather than increasing OFFSET indefinitely?
- What happens when a user's Salesforce session expires?
- What is covered by the fake-response tests, and what required real-org verification?
- Why can another person not open your computer's localhost address from their own computer?

Explain the implementation in your own words and be clear about any parts you are still learning.
