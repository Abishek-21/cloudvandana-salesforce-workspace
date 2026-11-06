# Verification record

Date: 6 November 2026 (India time).

## Local build and automated checks

- Production frontend build completed successfully using Vite 7.3.7.
- 15 backend tests passed. One dependency deprecation warning concerns Starlette's future test-client transport migration; it did not affect these results.
- Tests cover unauthorized requests, OAuth state/PKCE, callback replay and browser binding, all five objects, field limits, pagination, CRUD, object/ID allowlists, required fields, CSRF/origin validation, Salesforce permission/validation errors, token refresh, logout and expired sessions.
- Browser console: no warnings or errors in the final live view.

## Live Developer Org checks

The actual React interface completed OAuth login through the assignment's local External Client App. The org's normal consent and identity verification steps were completed with the user's approval.

| Object | Create | Read in view dialog | Update and read back | Delete |
| --- | --- | --- | --- | --- |
| Account | Passed | Passed | Passed | Passed |
| Opportunity | Passed | Passed | Passed | Passed |
| Lead | Passed | Passed | Passed | Passed |
| Contact | Passed | Passed | Passed | Passed |
| Case | Passed | Passed | Passed | Passed |

The Opportunity close-date test exposed a form submission issue during automated browser entry. The implementation now reads actual submitted controls, and date controls preserve their values across changes to other fields. The live create and update were repeated successfully after the fix.

Lookups were verified by linking the temporary Opportunity and Contact to a temporary Account, then linking the temporary Case to that Account and Contact.

## Pagination

- Live Account test: 35 records were available (10 existing, 25 approved temporary records).
- Reload displayed 20 records initially.
- Scrolling to the end displayed all 35 records.
- All 35 displayed IDs were unique.
- An isolated fake-data browser check also exercised 20, 40 and 45 displayed records across three pages. The fake server is not part of the real application.

## Cleanup and privacy

Only records labelled `CV Assignment QA 2026-11-06` and created for this test were changed or deleted. The user explicitly approved 25 temporary Accounts and one temporary record for each of the other four objects.

All 29 approved temporary records were deleted after verification. Related Case, Contact, Opportunity and Lead records were deleted before the temporary Accounts. Each confirmation dialog was checked against its recorded created ID. A fresh Account load showed the original 10 records and no temporary Account rows.

No existing practice records were edited or deleted. Deletion used normal Salesforce soft delete, not permanent purge.

The local `.env` file is ignored by Git and is readable only by the local account. Consumer credentials and access/refresh tokens are excluded from source and frontend assets. Tokens remain in the server process, not in browser local storage or source files.

## Remaining handoff steps

- Provide the Git repository URL with the final application.
- Include the updated resume when submitting.
- Arrange an authorized Salesforce user for interactive reviewer access, or demonstrate the app while signed in. Sessions are private to each browser; the public URL does not share the applicant's session.

## Public HTTPS review link

On 6 November 2026, remote access was configured at `https://sanitary-motive-skipper.ngrok-free.dev`, forwarding to the local server on port 8008. The user approved registering the exact public `/auth/callback` URL in the Salesforce External Client App, and Salesforce confirmed the save. Existing OAuth scopes were retained.

- Local and public HTTP checks returned 200.
- OAuth login completed through the public address and returned to a connected workspace.
- Account, Opportunity, Lead, Contact and Case metadata and record views loaded successfully.
- An Account detail dialog loaded successfully.
- Contact and Case each initially displayed 20 records. Scrolling requested the next page and correctly displayed the end-of-records state with 20 total records.
- No new records were created or changed during these public-link checks. The earlier live CRUD results above cover record mutations.
- The final browser view had no captured console warnings or errors.
- All 24 automated backend tests passed, including new public-host OAuth, Secure/HttpOnly cookies, canonical login, host validation, origin enforcement and invalid callback checks.
- Both launch scripts passed shell syntax checks.

The public hostname is explicitly allowed. Cookies are Secure for the HTTPS callback. The ngrok command disables request inspection, and tokens remain in the backend. The public link requires the local server, tunnel and internet connection to remain active.
