# Company / Ticket Target Go-Live Date Validation

Workflow custom code action that checks whether a Company's **Target Go-Live
Date** matches the **Target Go Live Date** on its associated Ticket in the
**Onboarding Pipeline**.

## What it does

1. Reads the enrolled Company's `target_golive_date` property.
2. Finds all Tickets associated with the Company.
3. Filters those tickets down to the ones in the Onboarding Pipeline
   (`hs_pipeline` = `751582029`). If more than one is found, the most
   recently created onboarding ticket is used.
4. Compares the company's date to the ticket's `target_go_live_date`
   (calendar-date comparison, so timezone/timestamp formatting doesn't cause
   false mismatches).
5. Returns output fields the workflow can branch on.

## Output fields

| Field | Type | Values |
|---|---|---|
| `validationResult` | Enumeration/String | `MATCH`, `MISMATCH`, `MISSING_DATE`, `NO_ONBOARDING_TICKET_FOUND`, `NO_TICKET_ASSOCIATED` |
| `datesMatch` | Boolean | `true` only when `validationResult` is `MATCH` |
| `companyGoLiveDate` | String (`YYYY-MM-DD`) | Company's target go-live date, or `null` |
| `ticketGoLiveDate` | String (`YYYY-MM-DD`) | Onboarding ticket's target go-live date, or `null` |
| `onboardingTicketId` | String | Record ID of the onboarding ticket used, or `null` |

Use an IF/THEN branch on `validationResult` (or `datesMatch`) after this
action to route the workflow, e.g. notify the deal/onboarding owner on
`MISMATCH`, or handle `NO_ONBOARDING_TICKET_FOUND` separately.

## Setup in HubSpot

1. **Workflow**: Create (or open) a Company-based workflow, enrollment
   trigger of your choice (e.g. re-enrollment on `target_golive_date`
   change, or "Ticket property changed" via a companion workflow).
2. **Add action → Custom code**, language **Node.js 20.x**.
3. Paste in `src/index.js`.
4. **Add dependency**: `@hubspot/api-client` (see `package.json`).
5. **Add a secret** named `PRIVATE_APP_ACCESS_TOKEN`, pointing at a Private
   App token with these scopes:
   - `crm.objects.companies.read`
   - `crm.objects.tickets.read`
   - `crm.schemas.tickets.read` (association scopes may also be required
     depending on your portal's association permissions setup)
6. **Set output fields** to match the table above (types: String, Boolean,
   String, String, String).
7. Add an **IF/THEN branch** action after this step, branching on
   `validationResult` or `datesMatch`.

## Notes / assumptions specific to this portal

- Onboarding Pipeline ID: `751582029` (label "Onboarding Pipeline").
- Company property: `target_golive_date` ("Target Go-Live Date").
- Ticket property: `target_go_live_date` ("Target Go Live Date").

If any of these internal names or the pipeline ID change in the portal,
update the constants at the top of `src/index.js` accordingly.
