# CS Ops: team rules for the weekly workflow audit

This file and `CS_Ops_Master_Rules.xlsx` hold everything specific to CS Ops. The skill
(`.claude/skills/hubspot-workflow-audit/SKILL.md`) is general and reads them with `--team cs-ops`.

- **Last updated:** 2026-10-07
- **Edited by:** WLS (Cherine's team). Change this file only when a rule or decision changes.

## Basics

- **Queue:** Ops Tasks (ID 13519269).
  - Main tasks are found through the queue.
  - Subtasks are found through their main task, because subtasks may not carry the queue.
- **Start date:** 2026-10-06. Nothing before this date is checked. Never audit backwards.
- **Window:** last Friday to this Thursday (7 days). The audit runs every Friday.

## Rules

1. Only facilities that are **live** and **full management** get tasks.
   - Live means Status = Live.
   - Full management means Full Management Type is either value below. Both are used in the workflow filters today:
     - "Full management (Excl Call center)"
     - "Full management (Incl Call center)" (internal value `Full TPM`)
2. Only the **Rate Review** workflows keep the segment exclusion (list 4291 "Exclude from Ops tasks").
   - It was removed from the other workflows on 2026-10-06.
3. Main tasks are associated with the **company**. That's enough for CS Ops; no ticket link is needed.
   - Subtasks must **not** be associated with a ticket.
4. Tasks that were switched off as duplicates should not be created.

## Task types

One task type can be made by several workflows, for example split by tier. Each row below counts as one type. "When" is the workflow's scheduled re-check, in the portal's time zone (US/Eastern). SOA facilities are companies whose name starts with "SOA - ".

| # | Task type | Made by (workflow ID) | When | Who should get it (from the workflow settings) |
|---|---|---|---|---|
| 1 | Rate Review - Execution | 1682542430 (ENT, Tier 1, Tier 2.1); 1868006300 (Tier 2.2, Tier 3) | Day 2 & 17, 10:00 / day 15, 10:00 | All tiers, not SOA, not on list 4291 |
| 2 | Update Customer Sentiment | 1682559152 (Ent, Tier 1, Tier 2.1); 1868006311 (Tier 2.2, Tier 3) | Day 10, 17:00 / day 25, 17:00 | All tiers, not SOA |
| 3 | Send Monthly Marketing Report to Owner | 1682548292 | Day 6, 10:00 | All tiers, not SOA, PPC Enrolled is not No |
| 4 | Bi-Weekly Call | 1682560327 (Month End Call) | Day 10 & 20, 10:00 | Enterprise, Tier 1, Tier 2 - L1, Tier 2 - L2; not SOA |
| 5 | Monthly Status Call | 1682560327 (Month End Call) | Day 10 & 20, 10:00 | Tier 3; not SOA |
| 6 | Weekly Call: First 90 days | 1838565644; also 1838568062 for Tier 2/3 (see Waiting on Cherine) | Mondays, 10:00 | Go-live date in the last 91 days, not SOA, not Pinetop Self Storage |
| 7 | Weekly KPI Review: First 90 days | 1838568062 | Mondays, 10:00 | Enterprise and Tier 1, go-live date in the last 91 days, not SOA |
| 8 | Review Facility Contacts | 1838568063 | Day 25, 17:00 | All tiers, not SOA |
| 9 | Unsold Unit, Towing, SCRA | 1838565797 | Day 1, 10:00 | All tiers, not SOA |
| 10 | Playbook Review/Maintenance | 1682549352 | Day 15, 17:00 | All tiers, including SOA |
| 11 | BOG Weekly Walkthrough + BOG Performance Status | 1682559061 (SOA get "Execute/Review Checklist") | Mondays, 00:00 | All tiers, including SOA |
| 12 | Execute Monthly Walk Through | 1688833555 | Day 1, 00:00 | SOA only |
| 13 | Facility Performance Monitoring and Escalation | 1688976731 | Day 1, 00:00 | All tiers, not SOA |
| 14 | AI Lien Process | 1688964146 | Day 1, 00:00 | Enterprise and SOA only |
| 15 | BOG Oversight | 1770960918 | Wednesdays, 10:00 | Enterprise and Tier 1 |
| 16 | NPS Detractor Recovery Actions | 1770961042 | No schedule: when NPS Customer Service Score drops below 6 | All tiers, not SOA |

**Not task types:**
- `R+S - Reminders: Respond within 1 day to external emails` (1689020435) creates nothing (known issue F-05, Waiting on Cherine 4).
- The 5 switched-off workflows (see Known issues): any task they create counts as one that shouldn't exist.

## Decisions so far

- "Bi-Weekly Call" and Tier 3's "Monthly Status Call" are **two separate task types** until Cherine says otherwise.
- **SOA facilities:**
  - If the workflow settings leave them out, report it as "excluded by rule", labelled VERIFIED (config).
  - If not, label it INFERENCE and add it to Waiting on Cherine.
- **Full management:** both values listed under rule 1 count (confirmed 2026-10-07).
- **Became live this week:** use the date Status changed to Live, with the go-live date as a cross-check.
  - Flag any facility where the two are more than 7 days apart.
- **First-90-days tasks for facilities that aren't live:** flag as a Potential Issue under rule 1, and add to Waiting on Cherine.
- **Tier 1 SM gap:** facilities caught by it are shown as **missing**, with the reason "Tier 1 SM gap (Waiting on Cherine)".
  - Not "excluded by rule": there's no confirmed rule yet.
  - Not "unknown": we know why.
- **Tier 2 - L1 SM gap:** in Update Customer Sentiment (Ent, Tier 1, Tier 2.1) the "Tier 2 - L1 SM" branch ends with no task. Facilities caught by it are shown as **missing**, with the reason "Tier 2 - L1 SM gap (Waiting on Cherine)" (decided 2026-10-07).
- **Duplicate Weekly Call tasks** (from both the Weekly calls and Weekly KPI workflows) go under Waiting on Cherine, not as a broken rule 4.
- **No SM or OM on the facility:** a facility that should get a task but whose OM/SM branch matches neither is shown as missing, with the reason "no SM or OM on the facility", labelled VERIFIED (records).
- **Wrong company** (Question 2):
  - A main task with **no company** is flagged, VERIFIED (records).
  - A main task with **more than one company** is flagged, VERIFIED (records).
  - A main task linked to a company that **doesn't qualify** for that task type is flagged, INFERENCE.

## Waiting on Cherine

Report these once per run, in their own section, not as new problems every week.

1. **Tier 1 SM gap.**
   - In 7 workflows the "T1 SM" branch ends with no task: Facility Performance, Weekly KPI, Weekly calls, Update Customer Sentiment Ent/T1/T2.1, Month End Call, Confirm contacts and BOG Oversight.
   - So a Tier 1 facility with an SM but no OM gets none of those tasks.
2. **Weekly KPI workflow making "Weekly Call" tasks.**
   - Its Tier 2 - L1, Tier 2 - L2 and Tier 3 branches create "Weekly Call: First 90 days Live", the same task the Weekly calls workflow makes.
   - Is this a duplicate?
3. **First-90-days tasks before a facility is live.**
   - The two first-90-days workflows check the go-live date, not Status = Live.
   - Should they create tasks before a facility is live?
4. **R+S - Reminders: should it create a task?**
   - `R+S - Reminders: Respond within 1 day to external emails` (1689020435) only branches and waits; it creates nothing (F-05).
5. **Tier 2 - L1 SM gap.**
   - In Update Customer Sentiment (Ent, Tier 1, Tier 2.1) the "Tier 2 - L1 SM" branch ends with no task.
   - So a Tier 2 - L1 facility with an SM but no OM gets no Update Customer Sentiment task.

## Changes not yet confirmed

The weekly audit found these differences from the master rules file. They stay "change, not yet confirmed" until WLS confirms whether they were planned; the master rules file is not updated until then.

| Workflow | Change | First seen | Status |
|---|---|---|---|
| Create Tasks \| Weekly KPI review to owner for first 90 days (1838568062) | Switched OFF (revision 28 -> 29, 2026-10-07 13:15 UTC) | 2026-10-07 | Checking with Cherine |
| Create Tasks \| Weekly calls first 90 days after go live (1838565644) | Revision 39 -> 41 (2026-10-07 13:15 UTC); no change in the compared settings | 2026-10-07 | Checking with Cherine |

## Known issues

Report each once, as a known issue.

- **F-03:** in 13 workflows the OM branch is checked before the SM branch, so tasks go to the OM when both exist. Cherine is deciding the fix.
- **F-05:** `R+S - Reminders: Respond within 1 day to external emails` (1689020435) creates no tasks. It only branches and waits, then loops back. Flagged by the 2026-10-06 full-map audit.
- **F-08:** "Create Tasks | Respond to reviews at Storage Reach" didn't come back from the API. It's a User workflow, which may be why.
- **5 workflows are switched off.** That's expected unless WLS says otherwise:
  - 1774165521 OM | RISK within the first 90 days
  - 1697631666 Create Tasks | Storage Reach
  - 1682549368 Create Tasks | Prepare Rate Review
  - 1682101413 Create Tasks | Prepare Month End Report
  - 1682545542 Create Tasks | Playbook Review/Maintenance T1 OM

## Settings for the scripts

The scripts read this block. Keep it in step with the text above.
- `title` is a pattern matched against the task title, ignoring case and spacing.
- `company_scope` uses HubSpot's internal values.

```json
{
  "team": "cs-ops",
  "team_name": "CS Ops",
  "decision_owner": "Cherine",
  "master_rules_file": "CS_Ops_Master_Rules.xlsx",
  "queue_name": "Ops Tasks",
  "queue_ids": ["13519269"],
  "start_date": "2026-10-06",
  "window": {"ends_on": "Thursday", "days": 7},
  "company_scope": {
    "description": "Live, full management",
    "filters": [
      {"property": "live", "operator": "IS_ANY_OF", "values": ["Yes"]},
      {"property": "mgt_type", "operator": "IS_ANY_OF", "values": ["Full management (Excl Call center)", "Full TPM"]}
    ]
  },
  "went_live": {"status_property": "live", "live_value": "Yes", "go_live_date_property": "go_live_date", "max_days_apart": 7},
  "links": {"main_task_company": true, "main_task_ticket": false, "subtask_ticket_forbidden": true},
  "exclusion": {"list_id": "4291", "only_in_task_types": ["Rate Review - Execution"]},
  "task_types": [
    {"name": "Rate Review - Execution", "workflows": ["1682542430", "1868006300"], "title": "rate review"},
    {"name": "Update Customer Sentiment", "workflows": ["1682559152", "1868006311"], "title": "customer sentiment"},
    {"name": "Send Monthly Marketing Report to Owner", "workflows": ["1682548292"], "title": "marketing report"},
    {"name": "Bi-Weekly Call", "workflows": ["1682560327"], "title": "bi-?weekly call"},
    {"name": "Monthly Status Call", "workflows": ["1682560327"], "title": "monthly sta\\w*s call"},
    {"name": "Weekly Call: First 90 days", "workflows": ["1838565644", "1838568062"], "title": "weekly call"},
    {"name": "Weekly KPI Review: First 90 days", "workflows": ["1838568062"], "title": "kpi review"},
    {"name": "Review Facility Contacts", "workflows": ["1838568063"], "title": "facility contacts"},
    {"name": "Unsold Unit, Towing, SCRA", "workflows": ["1838565797"], "title": "unsold unit"},
    {"name": "Playbook Review/Maintenance", "workflows": ["1682549352"], "title": "playbook"},
    {"name": "BOG Weekly Walkthrough + BOG Performance Status", "workflows": ["1682559061"], "title": "bog weekly|execute/review checklist"},
    {"name": "Execute Monthly Walk Through", "workflows": ["1688833555"], "title": "monthly walk ?through"},
    {"name": "Facility Performance Monitoring and Escalation", "workflows": ["1688976731"], "title": "facility performance"},
    {"name": "AI Lien Process", "workflows": ["1688964146"], "title": "ai lien"},
    {"name": "BOG Oversight", "workflows": ["1770960918"], "title": "bog oversight"},
    {"name": "NPS Detractor Recovery Actions", "workflows": ["1770961042"], "title": "nps detractor"}
  ],
  "no_task_workflows": ["1689020435"],
  "expected_off": ["1774165521", "1697631666", "1682549368", "1682101413", "1682545542"],
  "not_readable": [{"name": "Create Tasks | Respond to reviews at Storage Reach", "known_issue": "F-08"}],
  "branch_reasons": [
    {"branch": "^\"SOA\"", "kind": "excluded", "reason": "excluded by rule: SOA facility", "label": "VERIFIED (config)"},
    {"branch": "> \"(T1|Tier 1) SM\"$", "kind": "missing", "reason": "Tier 1 SM gap (Waiting on Cherine)", "label": "VERIFIED (config)", "waiting_on": "W-1"},
    {"branch": "> \"Tier 2 - L1 SM\"$", "kind": "missing", "reason": "Tier 2 - L1 SM gap (Waiting on Cherine)", "label": "VERIFIED (config)", "waiting_on": "W-5"},
    {"branch": "^\"[^\"]+\" > None met$", "kind": "missing", "reason": "no SM or OM on the facility", "label": "VERIFIED (records)"}
  ],
  "waiting_on": [
    {"id": "W-1", "title": "Tier 1 SM gap", "detail": "In 7 workflows the T1 SM branch ends with no task, so a Tier 1 facility with an SM but no OM gets none of those tasks."},
    {"id": "W-2", "title": "Weekly KPI workflow making Weekly Call tasks", "detail": "Its Tier 2 - L1, Tier 2 - L2 and Tier 3 branches create the same Weekly Call task as the Weekly calls workflow. Duplicates found are listed here, not as a broken rule.", "duplicate_task_type": "Weekly Call: First 90 days"},
    {"id": "W-3", "title": "First-90-days tasks before a facility is live", "detail": "The first-90-days workflows check the go-live date, not Status = Live. Tasks for facilities that aren't live are flagged as a Potential Issue under rule 1.", "task_types": ["Weekly Call: First 90 days", "Weekly KPI Review: First 90 days"]},
    {"id": "W-4", "title": "R+S - Reminders: should it create a task?", "detail": "R+S - Reminders: Respond within 1 day to external emails (1689020435) only branches and waits; it creates nothing (known issue F-05)."},
    {"id": "W-5", "title": "Tier 2 - L1 SM gap", "detail": "In Update Customer Sentiment (Ent, Tier 1, Tier 2.1) the Tier 2 - L1 SM branch ends with no task, so a Tier 2 - L1 facility with an SM but no OM gets no Update Customer Sentiment task."}
  ],
  "changes_not_confirmed": [
    {"workflow": "1838568062", "what": "switched off", "first_seen": "2026-10-07", "status": "checking with Cherine"},
    {"workflow": "1838565644", "what": "revision 39 -> 41, no change in the compared settings", "first_seen": "2026-10-07", "status": "checking with Cherine"}
  ],
  "known_issues": [
    {"id": "F-03", "text": "In 13 workflows the OM branch is checked before the SM branch, so tasks go to the OM when both exist. Cherine is deciding the fix."},
    {"id": "F-05", "text": "R+S - Reminders: Respond within 1 day to external emails (1689020435) creates no tasks: it only branches and waits, then loops back."},
    {"id": "F-08", "text": "\"Create Tasks | Respond to reviews at Storage Reach\" didn't come back from the API. It's a User workflow, which may be why."},
    {"id": "OFF-5", "text": "5 workflows are switched off. That's expected unless WLS says otherwise."}
  ]
}
```
