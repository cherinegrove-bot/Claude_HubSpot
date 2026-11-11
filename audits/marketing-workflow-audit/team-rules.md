# Marketing Services: team rules for the weekly workflow audit

This file and `Marketing_Master_Rules.xlsx` hold everything specific to Marketing Services. The skill
(`.claude/skills/hubspot-workflow-audit/SKILL.md`) is general and reads them with `--team marketing`.

- **Last updated:** 2026-11-11
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

### Enrollment checks (because enrollment is manual)

Decided by Cherine on 2026-11-11. Each enrolled company is checked instead of "who should have had it":

6. **Right workflow.** At the time of the task, the company fits the workflow it was put in. These are the conditions the workflows used until 7 November:
   - **Standalone:** Live, PPC Enrolled = Yes, Standalone Services includes Marketing.
   - **Improving:** Live, PPC Enrolled = Yes, Trend to Goal = Improving, Customer Tier Enterprise, Tier 1 or Tier 2 - L1.
   - **At Risk:** Live, PPC Enrolled = Yes, Trend to Goal = At Risk, Customer Tier Enterprise, Tier 1, Tier 2 - L1, Tier 2 - L2 or Tier 3.
7. **Right owner.** The task's owner is the one the workflow's branches give for the company's Marketing Portfolio Manager (no owner for "Not Assigned").
8. **Right subtasks.** Every review has Google Business Profile, Website Health & Optimization, Website Performance (GA4 & Search Console) and HubSpot Marketing Card, plus Sparefoot (if active) only when SpareFoot (Y/N) = Yes.
9. **Not enrolled twice.** No company gets a review task within 45 days of another review task from any of the three workflows.
10. **Deleted tasks.** Review tasks and subtasks from the three workflows deleted during the window are listed (count, workflow, owner, when). HubSpot doesn't say who deleted them.
11. **Coverage.** Live companies with PPC Enrolled = Yes that have had no review task in the last 45 days are listed in two groups (Cherine, 2026-11-11): those that fit a review workflow today (with which one), and those that fit none (e.g. Trend to Goal On Track), shown for information.
    - Review tasks made before the start date count as a company's last review; they're used only for this date, never audited.
    - Deleted review tasks don't count as a review.
    - A company that's still in a workflow's 45-day wait isn't listed (rule 12), so the "fits a review workflow" group is exactly the companies that should have got the task and didn't.
12. **In the 45-day wait** (Cherine, 2026-11-11). Every path ends with a 45-day delay after the task, and HubSpot won't enroll a company again until it's out. The page lists, per workflow, every company in the wait now: the date it got the task (the action just above the delay), when the wait ends, and whether the task is open, completed or deleted. Labelled INFERENCE: HubSpot's API doesn't show enrollments, so this is worked out from the tasks.
    - A deleted task no longer shows its company. It's matched to a company only when that's unambiguous: same run and owner, and exactly as many companies that fitted the workflow then, weren't already in its wait and got no other task from that run. Otherwise it's shown as "not matched". Deleted tasks made before the start date are never matched.
    - A company can be in two workflows' waits at once (e.g. Improving on 5 October, At Risk on 5 November).
    - The fetch reads the team's tasks and deleted tasks from the 90 days before the window, so a run can tell who was already in a wait.
    - **Calendar** (Cherine, 2026-11-11): the day each workflow's wait ends is marked in its own colour, with the number of facilities: At Risk purple, Improving teal, Standalone magenta. Clicking the day lists the facilities.

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

| Item | Question | Asked |
|---|---|---|
| W-1 | **Were the 6 November deletions planned?** 192 tasks from the 5 November run were deleted on 6 November, 20:24 to 20:28 UTC: 34 review tasks (At Risk 21, Improving 13; Brock Hegr 24, Sarah Schlosberg 10) and 158 subtasks. Deleted tasks from that day are listed under this item, not as new problems. | 2026-11-10 |

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
  "waiting_on": [
    {
      "id": "W-1",
      "title": "Review tasks deleted on 6 November",
      "asked": "2026-11-10",
      "detail": "On 6 November between 20:24 and 20:28 UTC, 192 tasks from the 5 November run were deleted: 34 Marketing Performance Review tasks (At Risk 21, Improving 13; Brock Hegr 24, Sarah Schlosberg 10) and 158 subtasks. HubSpot doesn't say who deleted them or why. The workflows were switched to manual enrollment the next day.",
      "question": "Were the 6 November deletions planned?",
      "workflows": [
        "1892196753",
        "1892165928"
      ],
      "deleted_on": [
        "2026-11-06"
      ]
    }
  ],
  "known_issues": [],
  "queue_names": {
    "13519272": {
      "name": "Marketing Services",
      "label": "Marketing Services",
      "confirmed": "2026-10-06"
    }
  },
  "known_queue_moves": [],
  "manual_checks": {
    "task_types": [
      "Standalone Marketing review",
      "Improving review",
      "At Risk review"
    ],
    "fit": {
      "1892197644": {
        "short": "Standalone",
        "description": "Live, PPC Enrolled Yes, Standalone Services includes Marketing",
        "filters": [
          {
            "property": "live",
            "operator": "IS_ANY_OF",
            "values": [
              "Yes"
            ]
          },
          {
            "property": "ppc_ads__yes_no_",
            "operator": "IS_ANY_OF",
            "values": [
              "true"
            ]
          },
          {
            "property": "standalone_services",
            "operator": "IS_ANY_OF",
            "values": [
              "Marketing"
            ]
          }
        ]
      },
      "1892196753": {
        "short": "Improving",
        "description": "Live, PPC Enrolled Yes, Trend to Goal Improving, Tier Enterprise, Tier 1 or Tier 2 - L1",
        "filters": [
          {
            "property": "live",
            "operator": "IS_ANY_OF",
            "values": [
              "Yes"
            ]
          },
          {
            "property": "ppc_ads__yes_no_",
            "operator": "IS_ANY_OF",
            "values": [
              "true"
            ]
          },
          {
            "property": "trend_to_goal_",
            "operator": "IS_ANY_OF",
            "values": [
              "Improving"
            ]
          },
          {
            "property": "customer_tier",
            "operator": "IS_ANY_OF",
            "values": [
              "Enterprise",
              "TIER 1",
              "TIER 2"
            ]
          }
        ]
      },
      "1892165928": {
        "short": "At Risk",
        "description": "Live, PPC Enrolled Yes, Trend to Goal At Risk, Tier Enterprise, Tier 1, Tier 2 - L1, Tier 2 - L2 or Tier 3",
        "filters": [
          {
            "property": "live",
            "operator": "IS_ANY_OF",
            "values": [
              "Yes"
            ]
          },
          {
            "property": "ppc_ads__yes_no_",
            "operator": "IS_ANY_OF",
            "values": [
              "true"
            ]
          },
          {
            "property": "trend_to_goal_",
            "operator": "IS_ANY_OF",
            "values": [
              "At Risk"
            ]
          },
          {
            "property": "customer_tier",
            "operator": "IS_ANY_OF",
            "values": [
              "Enterprise",
              "TIER 1",
              "TIER 2",
              "Tier 2 - L2",
              "TIER 3"
            ]
          }
        ]
      }
    },
    "owner": true,
    "subtasks": {
      "required": [
        "Google Business Profile",
        "Website Health & Optimization",
        "Website Performance (GA4 & Search Console)",
        "HubSpot Marketing Card"
      ],
      "conditional": [
        {
          "title": "Sparefoot (if active)",
          "property": "sparefoot__y_n_",
          "values": [
            "true"
          ]
        }
      ]
    },
    "duplicate_days": 45,
    "deleted": true,
    "coverage": {
      "days": 45,
      "description": "Live, PPC Enrolled Yes",
      "filters": [
        {
          "property": "live",
          "operator": "IS_ANY_OF",
          "values": [
            "Yes"
          ]
        },
        {
          "property": "ppc_ads__yes_no_",
          "operator": "IS_ANY_OF",
          "values": [
            "true"
          ]
        }
      ]
    },
    "wait_days": 90
  },
  "manual_tasks_not_checked": true
}
```
