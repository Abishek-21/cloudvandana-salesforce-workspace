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
- Confirm the review method if the recipient expects to access the applicant's machine remotely: a localhost address is local to the computer running the app. The README supports a reviewer running their own copy with their own Developer Org and External Client App.
