# Marketing Services: team rules for the weekly workflow audit

This file and `Marketing_Master_Rules.xlsx` hold everything specific to Marketing Services. The skill
(`.claude/skills/hubspot-workflow-audit/SKILL.md`) is general and reads them with `--team marketing`.

- **Last updated:** 2026-11-10
- **Edited by:** WLS (Cherine's team). Change this file only when a rule or decision changes.

## Basics

- **Queue:** Marketing Services (ID 13519272, confirmed by Cherine on 2026-10-06).
  - Main tasks are found through the queue.
  - Subtasks are found through their main task.
  - Manual tasks in this queue (e.g. "Marketing Request - ...") are not made by a workflow and are not checked.
- **Start date:** 2026-10-06. Nothing before this date is checked. Never audit backwards.
- **Window:** Friday to Thursday (7 days), as Cherine asked (2026-11-10). The run on Friday covers the previous Friday to that Thursday.
- **Workflows audited** (confirmed by Cherine, 2026-11-10):
  - Standalone Marketing | Monthly Performance Reviews | Marketing Services (UPDATED) (1892197644)
  - Improving Monthly Performance Reviews | Marketing Services (UPDATED) (1892196753)
  - At Risk Monthly Performance Reviews | Marketing Services (UPDATED) (1892165928)

## Rules

1. **Enrollment is manual.** Since 2026-11-07 the three workflows only enroll companies someone adds by hand (planned, Cherine, 2026-11-10). They no longer run on the 5th.
   - So the audit doesn't work out who *should* have got a review. "Were the tasks created?" checks only the tasks that were made: owner, queue, associations and subtasks.
2. Only **Live** companies get review tasks (Status = Live). A review task on a company that isn't Live is reported.
3. Every **main task** is associated with **exactly one company** and with that company's **Marketing ticket**.
4. **Subtasks must not be associated with a ticket.**
5. Every task the three workflows create is in the **Marketing Services queue** (13519272).

## Task types

The three workflows create the same task title. Each workflow counts as its own task type, told apart by the workflow that made the task.

| # | Task type | Made by (workflow ID) | When | Who should get it (from the workflow settings) |
|---|---|---|---|---|
| 1 | Standalone Marketing review | 1892197644 | Manual enrollment | The company's Marketing Portfolio Manager (Brock Hegr, Sarah Schlosberg or Mohammad Abudahab); no owner when it's "Not Assigned" |
| 2 | Improving review | 1892196753 | Manual enrollment | Same as above |
| 3 | At Risk review | 1892165928 | Manual enrollment | Same as above |

- **Task title:** "Marketing Performance Review", due 45 business days after creation at 08:00, in queue 13519272.
- **Subtasks seen in the records** (not in the workflow settings the API returns): Google Business Profile, Website Health & Optimization, Website Performance (GA4 & Search Console), HubSpot Marketing Card, Sparefoot (if active).

## Decisions so far

- **Manual enrollment** is planned (Cherine, 2026-11-10). Only created tasks are checked (rule 1).
- **Company scope:** Live only (Cherine, 2026-11-10). PPC Enrolled is not part of the scope.
- **Ticket association:** main tasks need both the company and its Marketing ticket (Cherine, 2026-11-10).
- **Task types:** one per workflow (Cherine, 2026-11-10).
- **demo Facility** (44541671248) is left out, as for CS Ops (Cherine, 2026-11-10).
- **Wrong company** (Question 2):
  - A main task with **no company** is flagged, VERIFIED (records).
  - A main task with **more than one company** is flagged, VERIFIED (records).
  - A main task linked to a company that **isn't Live** is flagged, INFERENCE.

## Waiting on Cherine

Report these once per run, in their own section, not as new problems every week.

None right now.

## Changes not yet confirmed

None. The master rules file is built from the live workflows of 2026-11-10 (revisions 21, 53 and 96).

## Known issues

None yet.

## Excluded companies

These companies are left out of every audit.

| Company ID | Name | Reason | Added |
|---|---|---|---|
| 44541671248 | demo Facility | demo facility | 2026-11-10 |

## HubSpot portal

Portal ID **45059701**. The weekly page uses it for the links that open workflows, companies and tasks in HubSpot.

## Queue names

HubSpot's API can't return queue names, only their IDs. These were confirmed by WLS in HubSpot:

| Queue ID | Name | Confirmed |
|---|---|---|
| 13519272 | Marketing Services | 2026-10-06 |

## Page colours

The weekly HTML page uses the WLS brand colours, as for CS Ops (Cherine, 2026-11-10):

| Colour | Hex | Used for |
|---|---|---|
| Navy | `#00173C` | Title bar and headings |
| Grey | `#646F79` | Table headers and labels |
| Red | `#E62222` | Problems only |
| White | `#FFFFFF` | Cards and tables |
| Light grey | `#F7F9FA` | Page background |

## Settings for the scripts

The scripts read this block. Keep it in step with the text above.
- `title` is a pattern matched against the task title, ignoring case and spacing.
- `company_scope` uses HubSpot's internal values.

```json
{
  "team": "marketing",
  "team_name": "Marketing Services",
  "decision_owner": "Cherine",
  "portal_id": "45059701",
  "page_colours": {
    "navy": "#00173C",
    "grey": "#646F79",
    "red": "#E62222",
    "white": "#FFFFFF",
    "background": "#F7F9FA"
  },
  "master_rules_file": "Marketing_Master_Rules.xlsx",
  "queue_name": "Marketing Services",
  "queue_ids": [
    "13519272"
  ],
  "start_date": "2026-10-06",
  "window": {
    "ends_on": "Thursday",
    "days": 7
  },
  "tier_property": "customer_tier",
  "tiers": [
    "Enterprise",
    "TIER 1",
    "TIER 2",
    "Tier 2 - L2",
    "TIER 3"
  ],
  "company_scope": {
    "description": "Live",
    "filters": [
      {
        "property": "live",
        "operator": "IS_ANY_OF",
        "values": [
          "Yes"
        ]
      }
    ]
  },
  "excluded_companies": [
    {
      "id": "44541671248",
      "name": "demo Facility",
      "reason": "demo facility",
      "added": "2026-11-10"
    }
  ],
  "links": {
    "main_task_company": true,
    "main_task_ticket": true,
    "subtask_ticket_forbidden": true
  },
  "task_types": [
    {
      "name": "Standalone Marketing review",
      "workflows": [
        "1892197644"
      ],
      "title": "^marketing performance review$"
    },
    {
      "name": "Improving review",
      "workflows": [
        "1892196753"
      ],
      "title": "^marketing performance review$"
    },
    {
      "name": "At Risk review",
      "workflows": [
        "1892165928"
      ],
      "title": "^marketing performance review$"
    }
  ],
  "no_task_workflows": [],
  "expected_off": [],
  "not_readable": [],
  "branch_reasons": [],
  "waiting_on": [],
  "known_issues": [],
  "queue_names": {
    "13519272": {
      "name": "Marketing Services",
      "label": "Marketing Services",
      "confirmed": "2026-10-06"
    }
  },
  "known_queue_moves": []
}
```
