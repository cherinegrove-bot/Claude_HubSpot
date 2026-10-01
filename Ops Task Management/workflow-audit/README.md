# WLS HubSpot Workflow Audit (read-only)

Audits the workflows in the WLS HubSpot folder **C-Ops - Task Management**
(24 workflows), maps their logic with particular attention to suppression,
exclusion and unenrollment, and compares them with the Ops task management
spreadsheet.

**This tool is read-only.** It never activates, deactivates, edits or
deletes workflows, and never changes properties or records.

## Status

| Phase | State |
|---|---|
| 1. Inspect repo | Done |
| 2. API validation (`npm run api-check`) | Built; waiting on credential and network access |
| 3. Data model | Draft (`src/model/workflowRecord.js`); finalised after Phase 2 shows real data |
| 4. Audit engine | Not started |
| 5. UI | Not started (built after Phase 2 works) |
| 6. Report generator | Not started |
| 7. Testing | Unit tests for the read-only client and document parser |

## How read-only is enforced

HubSpot's `automation` scope grants write access as well as read, so the
token alone can't guarantee read-only. `src/hubspot/readOnlyClient.js` only
sends `GET` requests, and only to an allowlist of read endpoints. Anything
else throws before a network request is made. `test/readOnlyClient.test.js`
covers this.

## HubSpot credential

The token is read from the `HUBSPOT_ACCESS_TOKEN` environment variable. It
must never be committed, pasted into source code, or shared in chat.

1. In HubSpot: **Settings → Integrations → Private Apps** (may be shown as
   Legacy Apps). Create an app named e.g. *WLS Workflow Audit – Read Only*.
2. Grant the scopes below and copy the access token.
3. Store it as a secret where you run the tool:
   - **Claude Code on the web:** cloud environment menu in the session title
     bar → **Edit** → API credentials / environment variables →
     `HUBSPOT_ACCESS_TOKEN`. Also allow network access to `api.hubapi.com`.
     Start a new session afterwards.
   - **GitHub Codespaces:** repository **Settings → Secrets and variables →
     Codespaces** → `HUBSPOT_ACCESS_TOKEN`.
   - **Local machine:** `cp .env.example .env` and fill in the value. `.env`
     is git-ignored.

### Required scopes

| Scope | Used for |
|---|---|
| `automation` | Reading workflow definitions (no read-only variant exists) |
| `crm.lists.read` | Resolving suppression/enrollment list IDs to names and criteria |
| `crm.schemas.contacts.read`, `crm.schemas.companies.read`, `crm.schemas.deals.read`, `crm.schemas.tickets.read` | Resolving property names and pipelines |
| `crm.objects.owners.read` | Resolving task assignees / owners |
| `settings.users.read` (optional) | Resolving users a task is assigned to |
| `content` (optional) | Names of marketing emails referenced by actions |

## Usage

Requires Node.js 22+.

```bash
npm install
npm test

# The WLS documentation stays out of git: put it in input/ (git-ignored).
npm run parse-doc -- "input/Phase 3 Task Management.xlsx"

# Phase 2 API validation (GET requests only)
npm run api-check -- --all --doc "input/Phase 3 Task Management.xlsx"
```

Everything written by the tool (raw API responses, parsed document, reports,
audit logs) goes to `output/`, which is git-ignored. Tokens are redacted from
anything written or printed.

### Audit scope

`config/audit-scope.json` holds the folder name and expected count. HubSpot's
public API may not expose folder membership (Phase 2 confirms this), so list
the folder's workflow IDs or names there, copied from the HubSpot folder
view. The API check reports any IDs or names it can't find, and whether the
total matches the expected 24.

## Layout

```
config/audit-scope.json        folder name, expected count, workflow IDs/names
scripts/api-check.js           Phase 2 read-only API validation
scripts/parse-doc.js           parse the WLS spreadsheet
src/hubspot/readOnlyClient.js  GET-only, allowlisted HubSpot client
src/docs/parseTaskSpec.js      spreadsheet parser and documentation checks
src/model/workflowRecord.js    normalised workflow record (draft)
src/redact.js                  token redaction
test/                          unit tests (synthetic data only)
```
