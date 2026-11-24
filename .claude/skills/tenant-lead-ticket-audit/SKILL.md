---
name: tenant-lead-ticket-audit
description: Daily audit that checks whether Tenant Leads pipeline tickets were created correctly for new Tenant contacts at the in-scope facilities, based on contact Source (Internet Website = no ticket, anything else = ticket). Use when asked to run, rerun or schedule the tenant lead ticket audit, or to check for missed / incorrect Tenant Lead tickets.
---

# Tenant Lead Ticket Audit (daily)

Checks the ticket-creation rule run by workflow
https://app.hubspot.com/workflows/45059701/platform/flow/1930587141/edit/actions/3/list-branch
(portal 45059701).

Goals:
1. Tickets are **not created incorrectly** (Internet Website leads must not get one).
2. Tickets are **not missed** (every other source must get one).

Rule went live **2026-11-20**. Never audit a day before 2026-11-20 (SAST);
if asked to, say so and stop.

## Audit window

The previous calendar day in **SAST (Africa/Johannesburg, UTC+2, no DST)**,
unless the user names a different day.
Day D in SAST = `D-1 22:00:00 UTC` (inclusive) to `D 22:00:00 UTC` (exclusive).
Example: auditing 2026-11-20 SAST → createdate >= `2026-11-19 22:00:00` and
< `2026-11-20 22:00:00` (UTC).

## Step 1: population (contacts)

Contacts that match the "new tenant lead" criteria AND were created in the window:

| UI criterion | Internal property | Filter |
|---|---|---|
| Contact Type is any of Tenant | `contact_type` | `= 'Tenant'` |
| software source is known | `software_source` | `IS NOT NULL` |
| Lead status is any of New | `hs_lead_status` | `= 'NEW'` |
| last synced at is known | `last_synced_at` | `IS NOT NULL` |
| Lifecycle stage is any of Lead | `lifecyclestage` | `= 'lead'` |
| (new contact) | `createdate` | inside the audit window |
| In-scope facility | `facility_tag` | IN the list below (exact match) |

The list's rolling "last synced at updated in last 1 day" criterion is replaced
by the createdate window, so a re-sync of an old contact does not pull it back in.

Note: lead status / lifecycle stage may have moved on since creation (e.g. a rep
already worked the lead). Run Step 1 a second time **without** the
`hs_lead_status` and `lifecyclestage` filters and list any extra contacts in a
separate "Criteria changed since creation" section, still evaluated against the rule.

In-scope facility tags (18):
```
f__space_station_storage
f__prime_vault_self_storage
f__space_station_salisbury
f__cache_plus_storage
f__demo_facility
f__safe_storage
f__meadowood_self_storage
f__moore_storage_of_delaware
f__hillside_storage
f__secureloc_self_storage
f__nobull_storage_arrow_way
f__patriot_state_storage
f__big_brown_storage_llc
f__honeycrisp_self_storage_lawrence
f__securely_storage
f__iron_mountain_storage
f__mendon_secure_storage
f__raymond_clinton_mini_storage
```

Properties to pull: `hs_object_id, firstname, lastname, email, facility_tag,
source, software_source, createdate, last_synced_at, hs_lead_status, lifecyclestage`.
Page through all results; check `total` and never report on a partial set.

## Step 2: tickets

For each contact, find associated tickets with `hs_pipeline = '753749611'`
(**Tenant Leads**) and `createdate >= contact createdate - 5 minutes`.
Tickets in other pipelines (e.g. Support Pipeline `0`) do not count.

Only tickets **created by the workflow** count for the rule. For every Tenant
Leads ticket found, read `hs_object_source_label` and `hs_object_source_detail_1`.
Workflow tickets have `hs_object_source_label = AUTOMATION_PLATFORM` and
`hs_object_source_detail_1` starting "CS - When a Tenant Lead Comes in Create a
Ticket", with subject "New Tenant Lead: <name> - <facility>".
Tenant Leads tickets from any other source (e.g. `CONVERSATIONS` chat/inbox,
`CRM_UI`) do NOT count as created or incorrect. List them in an informational
"Other Tenant Leads tickets (not from the workflow)" section only.

Working query shape (HubSpot SQL via `query_crm_data`):
```sql
SELECT hs_object_id, firstname, lastname, facility_tag, source, createdate,
       TICKET.hs_object_id, TICKET.hs_pipeline, TICKET.createdate
FROM CONTACT
WHERE contact_type = 'Tenant' AND hs_lead_status = 'NEW' AND lifecyclestage = 'lead'
  AND software_source IS NOT NULL AND last_synced_at IS NOT NULL
  AND createdate >= '<start UTC>' AND createdate < '<end UTC>'
  AND facility_tag IN (<18 tags>)
```
That join returns only contacts that have some ticket, so contacts missing from
it must be checked individually (search TICKET with `associatedWith` the contact
and `hs_pipeline = 753749611`) before being called "no ticket".

## Step 3: classify

`isWebsite` = `source` trimmed and lower-cased equals `internet website`
(exact; "Internet StorEdge Website", "Web - Company Website" etc. are NOT website).
Blank source → not website (ticket expected), but flag it.

| isWebsite | Workflow ticket in Tenant Leads? | Result |
|---|---|---|
| yes | none | ✅ CORRECT – no ticket |
| no | ≥1 | ✅ CORRECT – ticket created |
| yes | ≥1 | ❌ INCORRECT TICKET (should not exist) |
| no | none | ❌ MISSED TICKET |
| no | ≥2 | ⚠️ DUPLICATE TICKETS (also list) |

## Step 4: report

**Always update the same report page; never create a new one.**
Fixed report URL: https://claude.ai/artifact/XA7aoyFKu2RQHPs8VnemWK
1. Read it first with the Artifact tool (`action: "read"`, that `url`).
2. Rebuild the page from what comes back: keep the `<title>Tenant Lead Ticket Audit</title>`
   and the page styling, replace the report body with today's results, and add
   one row at the top of the **Run history** table (day audited, contacts,
   correct, missed, incorrect, duplicates), keeping all earlier rows.
3. Publish with `url` set to that same link (no `icon`). If the publish is
   refused with a newer version, merge into that version and publish again.
   Never publish without `url`, as that creates a new link.

Keep exceptions from earlier days listed in an "Open exception from an earlier day"
section until the user says they are resolved, and move the previous latest
day's contacts into the collapsed "Earlier days" list.

If the page has a `<section id="today-prelim">` (an on-demand partial-day check),
remove it on the next scheduled run; the full-day result replaces it.

The report body contains:
- Summary tiles: contacts audited, correct, missed tickets, incorrect tickets, duplicates.
- **Exceptions first**: Missed tickets, Incorrect tickets, Duplicates, Criteria
  changed, Blank source. Each row: contact name + clickable link
  `https://app.hubspot.com/contacts/45059701/record/0-1/<contactId>`, facility
  tag, source, created (SAST), ticket link(s)
  `https://app.hubspot.com/contacts/45059701/record/0-5/<ticketId>`.
- Breakdown by facility tag (count, website, non-website, tickets).
- Full list of compliant contacts (collapsed).
If there are zero exceptions, say so clearly at the top. Do not modify any
HubSpot records; this audit is read-only.
