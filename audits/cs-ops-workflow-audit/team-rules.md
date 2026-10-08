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
- `R+S - Reminders: Respond within 1 day to external emails` (1689020435) was deleted on 2026-10-08.
- The 5 switched-off workflows (see Known issues): any task they create counts as one that shouldn't exist.

## Decisions so far

- "Bi-Weekly Call" and Tier 3's "Monthly Status Call" are **two separate task types** until Cherine says otherwise.
- **SOA facilities:**
  - If the workflow settings leave them out, report it as "excluded by rule", labelled VERIFIED (config).
  - If not, label it INFERENCE and add it to Waiting on Cherine.
  - Since 2026-10-08 most workflows no longer have an empty "SOA" branch. SOA facilities are still left out by the tier branches ("Company name doesn't contain exactly SOA"), so this stays "excluded by rule".
- **Full management:** both values listed under rule 1 count (confirmed 2026-10-07).
- **Became live this week:** use the date Status changed to Live, with the go-live date as a cross-check.
  - Flag any facility where the two are more than 7 days apart.
- **First-90-days tasks for facilities that aren't live:** flag as a Potential Issue under rule 1, and add to Waiting on Cherine.
- **Tier 1 SM gap:** a Tier 1 facility with an SM but no OM, in a workflow that gives Tier 1 tasks only to the OM, is shown as **missing**, with the reason "Tier 1 SM gap (Waiting on Cherine)".
  - Not "excluded by rule": there's no confirmed rule yet.
  - Not "unknown": we know why.
  - Not "no SM or OM on the facility": the facility has an SM.
- **Tier 2 - L1 facilities with no OM in Update Customer Sentiment (Ent, Tier 1, Tier 2.1):** they get no task. Cherine confirmed on 2026-10-08 that this is fine, so it's reported as "excluded by rule", not as missing.
- **Duplicate Weekly Call tasks** (from both the Weekly calls and Weekly KPI workflows) go under Waiting on Cherine item 2, not as new problems or a broken rule 4.
- **No SM or OM on the facility:** a facility that should get a task but has neither an SM nor an OM is shown as missing, with the reason "no SM or OM on the facility", labelled VERIFIED (records).
- **Wrong company** (Question 2):
  - A main task with **no company** is flagged, VERIFIED (records).
  - A main task with **more than one company** is flagged, VERIFIED (records).
  - A main task linked to a company that **doesn't qualify** for that task type is flagged, INFERENCE.

## Waiting on Cherine

Report these once per run, in their own section, not as new problems every week.

1. **Tier 1 SM gap.**
   - In 7 workflows, Tier 1 tasks go only to the OM: Facility Performance, Weekly KPI, Weekly calls, Update Customer Sentiment Ent/T1/T2.1, Month End Call, Confirm contacts and BOG Oversight.
   - The empty "T1 SM" branches were deleted on 2026-10-08, but that doesn't add a task: a Tier 1 facility with an SM and no OM now matches no branch and still gets none of those tasks.
   - Are Tier 1 tasks meant to go only to the OM?
2. **Weekly KPI review is on and creates duplicate Weekly Call tasks. Should it be off?**
   - It was switched off on 2026-10-07 and back on on 2026-10-08 (08:12 UTC). Its Tier 2 - L1, Tier 2 - L2 and Tier 3 branches create "Weekly Call: First 90 days Live", the same task the Weekly calls workflow makes.
   - Duplicate Weekly Call tasks are listed under this item, not as new problems.
3. **First-90-days tasks before a facility is live.**
   - The two first-90-days workflows check the go-live date, not Status = Live.
   - Should they create tasks before a facility is live?
7. **demo Facility (44541671248): test record?**
   - Live, Full TPM, Tier 2 - L1, with no SM and no OM, so it gets no tasks from the OM/SM branches.
   - Should it be excluded from the audit?

### Closed (answered by Cherine, 2026-10-08)

| Item | Answer |
|---|---|
| 4. R+S - Reminders: should it create a task? | Workflow deleted. Known issue F-05 closed too. |
| 5. Tier 2 - L1 SM gap (Update Customer Sentiment) | Fine, no action. Reported as "excluded by rule" from now on. |
| 6. Set task queue moves BOG tasks to BOG - Run and Sustain | Workflow deleted. BOG tasks should now stay in Ops Tasks. The 52 tasks it moved on 2026-10-07 stay in BOG - Run and Sustain (known issue BOG-Q, fixed, no action needed). |
| Weekly KPI review switched off (change of 2026-10-07) | It's on again. The switch-off was not marked as planned and the master rules file still records it as on. See item 2. |
| Weekly calls revision 39 -> 41 (change of 2026-10-07) | Planned. Master rules file updated on 2026-10-08. |
| Empty branches in CS Ops workflows | 47 branches with nothing under them, plus Storage Reach's "Enterprise" branch (it held only empty branches), deleted on purpose. Master rules file updated on 2026-10-08, one log line per workflow. |

## Changes not yet confirmed

None. The live workflows matched the master rules file after the 2026-10-08 update.

## Known issues

Report each once, as a known issue.

- **F-03:** in 13 workflows the OM branch is checked before the SM branch, so tasks go to the OM when both exist. Cherine is deciding the fix.
- **BOG-Q (fixed, no action needed):** the 52 BOG Oversight tasks created on 2026-10-07 are still in queue 9999918 "BOG - Run and Sustain": moved by Set task queue before it was deleted, no action needed (WLS, 2026-10-08). Reported once, as a known issue that's already fixed. Only tasks created on or before 2026-10-07 are covered; a BOG task moved after that is a new problem.
- **F-08:** "Create Tasks | Respond to reviews at Storage Reach" didn't come back from the API. It's a User workflow, which may be why. Its tasks are in Ops Tasks but are not linked to any company. The audit reports this as one line, with the week's count, not one problem per task.
- **5 workflows are switched off.** That's expected unless WLS says otherwise:
  - 1774165521 OM | RISK within the first 90 days
  - 1697631666 Create Tasks | Storage Reach
  - 1682549368 Create Tasks | Prepare Rate Review
  - 1682101413 Create Tasks | Prepare Month End Report
  - 1682545542 Create Tasks | Playbook Review/Maintenance T1 OM

## HubSpot portal

Portal ID **45059701**. The weekly page uses it for the links that open workflows, companies and tasks in HubSpot.

## Queue names

HubSpot's API can't return queue names, only their IDs. These were confirmed by WLS in HubSpot:

| Queue ID | Name | Confirmed |
|---|---|---|
| 13519269 | Ops Tasks | 2026-10-06 |
| 9999918 | BOG - Run and Sustain | 2026-10-07 (seen in a task's queue history). CS Ops tasks should no longer go there: "Set task queue" was deleted on 2026-10-08. |

## Page colours

The weekly HTML page uses the WLS brand colours (set 2026-10-07):

| Colour | Hex | Used for |
|---|---|---|
| Navy | `#00173C` | Title bar and headings |
| Grey | `#646F79` | Table headers and labels |
| Red | `#E62222` | Problems only |
| White | `#FFFFFF` | Cards and tables |
| Light grey | `#F7F9FA` | Page background |

No green: rows and items that are fine are shown in the normal colours.

## Settings for the scripts

The scripts read this block. Keep it in step with the text above.
- `title` is a pattern matched against the task title, ignoring case and spacing.
- `company_scope` uses HubSpot's internal values.

```json
{
  "team": "cs-ops",
  "team_name": "CS Ops",
  "decision_owner": "Cherine",
  "portal_id": "45059701",
  "page_colours": {
    "navy": "#00173C",
    "grey": "#646F79",
    "red": "#E62222",
    "white": "#FFFFFF",
    "background": "#F7F9FA"
  },
  "master_rules_file": "CS_Ops_Master_Rules.xlsx",
  "queue_name": "Ops Tasks",
  "queue_ids": [
    "13519269"
  ],
  "start_date": "2026-10-06",
  "window": {
    "ends_on": "Thursday",
    "days": 7
  },
  "company_scope": {
    "description": "Live, full management",
    "filters": [
      {
        "property": "live",
        "operator": "IS_ANY_OF",
        "values": [
          "Yes"
        ]
      },
      {
        "property": "mgt_type",
        "operator": "IS_ANY_OF",
        "values": [
          "Full management (Excl Call center)",
          "Full TPM"
        ]
      }
    ]
  },
  "went_live": {
    "status_property": "live",
    "live_value": "Yes",
    "go_live_date_property": "go_live_date",
    "max_days_apart": 7
  },
  "links": {
    "main_task_company": true,
    "main_task_ticket": false,
    "subtask_ticket_forbidden": true
  },
  "exclusion": {
    "list_id": "4291",
    "only_in_task_types": [
      "Rate Review - Execution"
    ]
  },
  "task_types": [
    {
      "name": "Rate Review - Execution",
      "workflows": [
        "1682542430",
        "1868006300"
      ],
      "title": "rate review"
    },
    {
      "name": "Update Customer Sentiment",
      "workflows": [
        "1682559152",
        "1868006311"
      ],
      "title": "customer sentiment"
    },
    {
      "name": "Send Monthly Marketing Report to Owner",
      "workflows": [
        "1682548292"
      ],
      "title": "marketing report"
    },
    {
      "name": "Bi-Weekly Call",
      "workflows": [
        "1682560327"
      ],
      "title": "bi-?weekly call"
    },
    {
      "name": "Monthly Status Call",
      "workflows": [
        "1682560327"
      ],
      "title": "monthly sta\\w*s call"
    },
    {
      "name": "Weekly Call: First 90 days",
      "workflows": [
        "1838565644",
        "1838568062"
      ],
      "title": "weekly call"
    },
    {
      "name": "Weekly KPI Review: First 90 days",
      "workflows": [
        "1838568062"
      ],
      "title": "kpi review"
    },
    {
      "name": "Review Facility Contacts",
      "workflows": [
        "1838568063"
      ],
      "title": "facility contacts"
    },
    {
      "name": "Unsold Unit, Towing, SCRA",
      "workflows": [
        "1838565797"
      ],
      "title": "unsold unit"
    },
    {
      "name": "Playbook Review/Maintenance",
      "workflows": [
        "1682549352"
      ],
      "title": "playbook"
    },
    {
      "name": "BOG Weekly Walkthrough + BOG Performance Status",
      "workflows": [
        "1682559061"
      ],
      "title": "bog weekly|execute/review checklist"
    },
    {
      "name": "Execute Monthly Walk Through",
      "workflows": [
        "1688833555"
      ],
      "title": "monthly walk ?through"
    },
    {
      "name": "Facility Performance Monitoring and Escalation",
      "workflows": [
        "1688976731"
      ],
      "title": "facility performance"
    },
    {
      "name": "AI Lien Process",
      "workflows": [
        "1688964146"
      ],
      "title": "ai lien"
    },
    {
      "name": "BOG Oversight",
      "workflows": [
        "1770960918"
      ],
      "title": "bog oversight"
    },
    {
      "name": "NPS Detractor Recovery Actions",
      "workflows": [
        "1770961042"
      ],
      "title": "nps detractor"
    }
  ],
  "no_task_workflows": [],
  "expected_off": [
    "1774165521",
    "1697631666",
    "1682549368",
    "1682101413",
    "1682545542"
  ],
  "not_readable": [
    {
      "name": "Create Tasks | Respond to reviews at Storage Reach",
      "known_issue": "F-08"
    }
  ],
  "branch_reasons": [
    {
      "branch": "^None met$",
      "when": [
        {
          "property": "name",
          "starts_with": "SOA - "
        }
      ],
      "kind": "excluded",
      "reason": "excluded by rule: SOA facility",
      "label": "VERIFIED (config)"
    },
    {
      "branch": "^\"SOA\"",
      "kind": "excluded",
      "reason": "excluded by rule: SOA facility",
      "label": "VERIFIED (config)"
    },
    {
      "branch": "^\"Tier 2 - L1\" > (None met|\"Tier 2 - L1 SM\")$",
      "workflows": [
        "1682559152"
      ],
      "when": [
        {
          "property": "operations_manager",
          "is": "unknown"
        }
      ],
      "kind": "excluded",
      "reason": "excluded by rule: Tier 2 - L1 with no OM gets no Update Customer Sentiment task (Cherine, 2026-10-08)",
      "label": "VERIFIED (config)"
    },
    {
      "branch": "^\"(T1|Tier 1)\" > (None met|\"(T1|Tier 1) SM\")$",
      "when": [
        {
          "property": "site_manager",
          "is": "known"
        }
      ],
      "kind": "missing",
      "reason": "Tier 1 SM gap (Waiting on Cherine)",
      "label": "VERIFIED (config)",
      "waiting_on": "W-1"
    },
    {
      "branch": "^\"[^\"]+\" > None met$",
      "when": [
        {
          "property": "site_manager",
          "is": "unknown"
        },
        {
          "property": "operations_manager",
          "is": "unknown"
        }
      ],
      "kind": "missing",
      "reason": "no SM or OM on the facility",
      "label": "VERIFIED (records)"
    }
  ],
  "waiting_on": [
    {
      "id": "W-1",
      "title": "Tier 1 SM gap",
      "detail": "In 7 workflows Tier 1 tasks go only to the OM. The empty T1 SM branches were deleted on 2026-10-08, but a Tier 1 facility with an SM and no OM still gets none of those tasks. Are Tier 1 tasks meant to go only to the OM?"
    },
    {
      "id": "W-2",
      "title": "Weekly KPI review is on and creates duplicate Weekly Call tasks. Should it be off?",
      "detail": "Its Tier 2 - L1, Tier 2 - L2 and Tier 3 branches create the same Weekly Call task as the Weekly calls workflow. It was switched off on 2026-10-07 and back on on 2026-10-08. Duplicates found are listed here, not as new problems.",
      "duplicate_task_type": "Weekly Call: First 90 days"
    },
    {
      "id": "W-3",
      "title": "First-90-days tasks before a facility is live",
      "detail": "The first-90-days workflows check the go-live date, not Status = Live. Tasks for facilities that aren't live are flagged as a Potential Issue under rule 1.",
      "task_types": [
        "Weekly Call: First 90 days",
        "Weekly KPI Review: First 90 days"
      ]
    },
    {
      "id": "W-7",
      "title": "demo Facility (44541671248): test record?",
      "detail": "Live, Full TPM, Tier 2 - L1, with no SM and no OM. Should it be excluded from the audit? Until then, anything the audit finds for it is listed here, not as a problem.",
      "company_ids": [
        "44541671248"
      ]
    }
  ],
  "changes_not_confirmed": [],
  "queue_names": {
    "13519269": {
      "name": "Ops Tasks",
      "label": "confirmed by WLS",
      "confirmed": "2026-10-06"
    },
    "9999918": {
      "name": "BOG - Run and Sustain",
      "label": "VERIFIED (screenshot)",
      "confirmed": "2026-10-07"
    }
  },
  "known_queue_moves": [
    {
      "queue": "9999918",
      "created_on_or_before": "2026-10-07",
      "known_issue": "BOG-Q"
    }
  ],
  "known_issues": [
    {
      "id": "F-03",
      "text": "In 13 workflows the OM branch is checked before the SM branch, so tasks go to the OM when both exist. Cherine is deciding the fix."
    },
    {
      "id": "BOG-Q",
      "status": "fixed",
      "text": "BOG Oversight tasks from 2026-10-07 in BOG - Run and Sustain: moved by Set task queue before it was deleted, no action needed.",
      "label": "VERIFIED (records); queue name VERIFIED (screenshot)"
    },
    {
      "id": "F-08",
      "text": "\"Create Tasks | Respond to reviews at Storage Reach\" didn't come back from the API. It's a User workflow, which may be why. Its tasks are in Ops Tasks but are not linked to any company.",
      "no_company_tasks": true
    },
    {
      "id": "OFF-5",
      "text": "5 workflows are switched off. That's expected unless WLS says otherwise."
    }
  ],
  "closed": [
    {
      "id": "W-4",
      "closed": "2026-10-08",
      "answer": "R+S - Reminders deleted (also closes F-05)"
    },
    {
      "id": "W-5",
      "closed": "2026-10-08",
      "answer": "Tier 2 - L1 SM gap in Update Customer Sentiment: fine, no action"
    },
    {
      "id": "W-6",
      "closed": "2026-10-08",
      "answer": "Set task queue deleted; BOG tasks stay in Ops Tasks (also closes BOG-Q)"
    }
  ]
}
```
