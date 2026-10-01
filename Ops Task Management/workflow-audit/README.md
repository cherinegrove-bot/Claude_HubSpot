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
| 2. API validation (`npm run api-check`) | Done: 22 of 24 folder workflows readable (see below) |
| 3. Data model | Done (`src/model/workflowRecord.js`, filled by `src/audit/normalise.js`) |
| 4. Audit engine | Done (`src/audit/`), runs offline from the raw bundle |
| 5. UI | Not started |
| 6. Report generator | Done: 9-section Markdown report plus the audited spreadsheet |
| 7. Testing | Unit tests for the client, document parser and audit engine (synthetic data) |

Two folder workflows can't be read through the API and are flagged for manual
review in every report: **Create Tasks | Respond to reviews at Storage Reach**
(a User-object workflow; `GET /automation/v4/flows/1682571075` returns 404) and
**R+S - Reminders: Respond within 1 day to external emails** (not in the v4 or
v3 workflow lists).

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

# 1. Fetch everything from HubSpot once (GET only) into output/raw-<time>/bundle.json
npm run fetch-raw -- --doc "input/Phase 3 Task Management.xlsx"

# 2. Run the audit offline from the latest bundle (no HubSpot calls)
npm run audit -- --doc "input/Phase 3 Task Management.xlsx"
```

`npm run audit` writes to `output/audit-<time>/`:

- `report.md`: the report in 9 sections (Executive Summary, Workflow
  Inventory, Workflow Mapping, Suppression / Exclusion Analysis, Relationships /
  Dependencies, Documentation vs Actual HubSpot, Missing / Additional
  Workflows, Notable Configuration Differences, Items Requiring Human Review),
  with each finding labelled FACT, DOCUMENTED, DIFFERENCE or REVIEW.
- `<spreadsheet> - Audited.xlsx`: the original sheet with its 8 columns
  untouched, audit columns added from column I onwards, and sheets for
  HubSpot-only tasks, workflows, suppression and review items.
- `audit.json`: the normalised workflows and comparison, for debugging.

### How the audit reads a workflow

- Branches are walked from `startActionId`. HubSpot list branches are
  first-match: a company goes down the first branch it qualifies for, and
  companies matching none take the "otherwise" path or, if there is none,
  leave the workflow. So an "OM is known" branch placed before "SM is known"
  means the SM path only runs when the OM is blank. The audit reports this.
- Every create-task action is recorded with the path that reaches it. That
  path gives the tier(s), SOA or non-SOA, the assignee (OM/SM property or a
  named user) and the due rule.
- Spreadsheet rows are matched to tasks by title, then checked per tier and
  role. T1 maps to HubSpot `TIER 1`, T2 to `TIER 2` (Tier 2 - L1) and
  `Tier 2 - L2`, and T3 to `TIER 3`. A role ending in "-SOA" means SOA
  companies only.

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
src/model/workflowRecord.js    normalised workflow record
src/audit/filters.js           filter trees: plain English, exclusions, overlap
src/audit/normalise.js         flow → record; branch walk; create-task paths
src/audit/suppression.js       suppression / exclusion analysis
src/audit/compare.js           spreadsheet rows vs HubSpot tasks
src/audit/report.js            9-section Markdown report
src/audit/spreadsheet.js       audited copy of the WLS spreadsheet
scripts/fetch-raw.js           fetch the raw HubSpot bundle (GET only)
scripts/audit.js               run the audit offline from the bundle
src/redact.js                  token redaction
test/                          unit tests (synthetic data only)
```
