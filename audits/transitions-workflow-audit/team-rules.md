# Transitions: team rules for the weekly workflow audit

This file and `Transitions_Master_Rules.xlsx` hold everything specific to Transitions. The skill
(`.claude/skills/hubspot-workflow-audit/SKILL.md`) is general and reads them with `--team transitions`.

- **Last updated:** 2026-10-13
- **Edited by:** WLS (Cherine's team). Change this file only when a rule or decision changes.
- **Based on:** the Transitions full map audit, v3 (`WLS_Transitions_Workflow_Audit_v3.xlsx`, 2026-10-06).

## Basics

- **Queue:** Transitions (ID 13519270), confirmed by Cherine on 2026-10-06.
  - Main tasks are found through the queue.
  - Subtasks are found through their main task, because subtasks may not carry the queue.
- **Start date:** 2026-10-06. Nothing before this date is checked. Never audit backwards.
- **Window:** Friday to Thursday (7 days), the same as CS Ops. The run on Friday covers the previous Friday to that Thursday (e.g. the run on Fri 16 Oct covers Fri 9 Oct to Thu 15 Oct).
- **Workflows:** 8, agreed with Cherine on 2026-10-13:

| Workflow | ID | Object | What it does |
|---|---|---|---|
| Closed Won \| Create Ticket in INITIAL SETUP - UNASSIGNED | 1670039203 | Deal | Creates the onboarding ticket. No tasks. |
| Transitions - Transition Kickoff Tasks (+SubTask) | 1866384267 | Ticket | Tasks when the ticket enters Transition Kickoff |
| Transitions - Pre Launch Setup Tasks (+SubTask) | 1866658899 | Ticket | Tasks when the ticket enters Pre-Launch Setup, plus the marketing proposal |
| Transitions - Launch Readiness Tasks (+SubTask) | 1866664080 | Ticket | Tasks when the ticket enters Launch Readiness |
| Transitions - Go Live Execution Tasks (+SubTask) | 1866664222 | Ticket | Tasks when the ticket enters Go-Live Execution |
| Transitions - Final Sign Off Tasks (+SubTask) | 1866664327 | Ticket | Tasks when the ticket enters Final Signoff |
| Transitions - 30-Day Monitoring (+SubTask) | 1866659765 | Ticket | Tasks when the ticket enters Post 30-Day Monitoring (OM/SM) |
| Transitions - TRANSITION COMPLETE (+SubTask) | 1867929348 | Ticket | Task when the ticket enters Transition Completed |

The 5 stage-move workflows ("... (task complete)") and "Transitions | PM = Ticket Owner" are not part of this audit (Cherine, 2026-10-13).

## How "who should get a task" works for Transitions

Transitions workflows don't run on a schedule. Each one starts when a **ticket** in the Onboarding Pipeline enters its stage. So, for each week:

1. **Who should have it:** every Onboarding Pipeline ticket that entered the workflow's stage during the week (from the ticket's stage history). VERIFIED (records) for the stage move; INFERENCE that the workflow should have enrolled it.
2. **Re-enrollment is off** on all 7 task workflows. A ticket that had already entered that stage before (since the workflow was created) gets nothing new; that's "not expected", not missing.
3. **The facility** is the ticket's company with the "Transitions" label, else its Primary company. The weekly page lists results by facility. A ticket with no company is reported as its own problem.
4. **Did it get it:** the ticket got every task the stage creates. If it got only some, it's "partial", and the missing task titles are named.

## Rules

1. Each stage's tasks go to every ticket that enters that stage in the Onboarding Pipeline (see above). There is no company filter: the ticket's stage decides, because onboarding facilities aren't live yet.
2. Every Create task action uses the Transitions queue (13519270).
3. Main tasks are linked to the **ticket** and to exactly **one company**.
   - Subtasks must **not** be linked to the ticket.
4. Tasks that shouldn't exist (a ticket that didn't enter the stage, or a second set for the same ticket) are reported.

## Task types

One type per stage, plus the marketing proposal. "Tasks" is the number of Create task actions every ticket gets at that stage (from the master rules file).

| # | Task type | Made by (workflow ID) | When | Tasks | Who should get it |
|---|---|---|---|---|---|
| 1 | Transition Kickoff | 1866384267 | Ticket enters Transition Kickoff | 3 | Every Onboarding ticket |
| 2 | Pre-Launch Setup | 1866658899 | Ticket enters Pre-Launch Setup | 5 | Every Onboarding ticket |
| 3 | Marketing Proposal | 1866658899 | Same run as Pre-Launch Setup | 1 | Only if an associated company has PPC Enrolled = Yes |
| 4 | Launch Readiness | 1866664080 | Ticket enters Launch Readiness | 5 | Every Onboarding ticket |
| 5 | Go-Live Execution | 1866664222 | Ticket enters Go-Live Execution | 5 | Every Onboarding ticket |
| 6 | Final Sign-Off | 1866664327 | Ticket enters Final Signoff | 6 | Every Onboarding ticket |
| 7 | 30-Day Monitoring | 1866659765 | Ticket enters Post 30-Day Monitoring (OM/SM) | 2 | Every Onboarding ticket |
| 8 | Transition Complete | 1867929348 | Ticket enters Transition Completed | 1 | Every Onboarding ticket |

**Not a task type:** Closed Won | Create Ticket in INITIAL SETUP - UNASSIGNED (1670039203) creates the ticket, not tasks. It's only checked for changes (question 3).

## Decisions so far

All agreed with Cherine on 2026-10-13:
- **Option A:** question 1 is worked out from tickets entering stages, not from company schedules.
- **Facility of a ticket:** the "Transitions" company, else the Primary company.
- **Task types:** one per stage, plus Marketing Proposal. A ticket missing some of a stage's tasks is "partial".
- **Company scope:** none. The ticket's stage decides.
- **Links:** main task to the ticket and exactly one company; subtasks not linked to the ticket.
- **Went live this week:** shown, using Status = Live and the go-live date, flagged when more than 7 days apart.
- **Excluded companies:** demo Facility (44541671248), the same as CS Ops.
- **Page colours:** the WLS brand colours, the same as CS Ops.

## Waiting on Cherine

Report these once per run, in their own section, not as new problems every week.

| Item | Question | Asked |
|---|---|---|
| W-1 (F-13) | The 4 "Marketing \| Create Marketing Proposal" actions put the task in the Transitions queue, although it's assigned to a marketing manager. Should it sit there? | 2026-10-06 |
| W-2 (F-15) | "Transition \| 30 - DAY MONITORING \| Subtask - Automated" is an ordinary task for the ticket owner. Is it meant to be manual? | 2026-10-06 |
| W-3 (F-11) | The proposal checks PPC on any linked company, but takes the portfolio manager from the earliest "Transitions" company (anything else goes to Brock Hegr). Should both come from the same company? | 2026-10-06 |

## Known issues

Report each once, as a known issue, with this week's count where it applies.

- **F-05:** "Transition | FINAL SIGN-OFF | Subtask - Mike" (Final Sign Off, action 20) is set up without a company link, so it is always flagged under question 2. Reported here once a week instead.
- **F-09:** new tickets are created owned by Elizabeth Airey (owner 81929768), a deactivated user. Every "Ticket Owner/PM" task follows the ticket owner.
- **F-10:** tasks copy only contacts with the "Transition" label, but the Closed Won workflow links contacts without a label, so tasks probably get no contact.
- **F-12:** the Transition Complete check is created after the ticket reaches Transition Completed, which is a closed stage, due the same day.

## Excluded companies

| Company ID | Name | Reason | Added |
|---|---|---|---|
| 44541671248 | demo Facility | demo facility | 2026-10-13 |

## HubSpot portal

Portal ID **45059701**. The weekly page uses it for the links that open workflows, companies and tasks in HubSpot.

## Queue names

HubSpot's API can't return queue names, only their IDs. Confirmed by WLS in HubSpot:

| Queue ID | Name | Confirmed |
|---|---|---|
| 13519270 | Transitions | 2026-10-06 |

## Page colours

The WLS brand colours, the same as CS Ops: navy `#00173C` (title bar and headings), grey `#646F79` (table headers and labels), red `#E62222` (problems only), white `#FFFFFF` (cards and tables), light grey `#F7F9FA` (page background).

## Settings for the scripts

The scripts read this block. Keep it in step with the text above.
- `title` is a pattern matched against the task title, ignoring case and spacing.
- `ticket_facility` says how a ticket-triggered workflow is audited: the pipelines its tickets are in, and which company is the ticket's facility.

```json
{
  "team": "transitions",
  "team_name": "Transitions",
  "decision_owner": "Cherine",
  "portal_id": "45059701",
  "page_colours": {
    "navy": "#00173C",
    "grey": "#646F79",
    "red": "#E62222",
    "white": "#FFFFFF",
    "background": "#F7F9FA"
  },
  "master_rules_file": "Transitions_Master_Rules.xlsx",
  "queue_name": "Transitions",
  "queue_ids": [
    "13519270"
  ],
  "start_date": "2026-10-06",
  "window": {
    "ends_on": "Thursday",
    "days": 7
  },
  "company_scope": {},
  "ticket_facility": {
    "pipelines": [
      "751582029"
    ],
    "company_label": "Transitions",
    "fallback_label": "Primary"
  },
  "excluded_companies": [
    {
      "id": "44541671248",
      "name": "demo Facility",
      "reason": "demo facility",
      "added": "2026-10-13"
    }
  ],
  "went_live": {
    "status_property": "live",
    "live_value": "Yes",
    "go_live_date_property": "go_live_date",
    "max_days_apart": 7
  },
  "links": {
    "main_task_company": true,
    "main_task_ticket": true,
    "subtask_ticket_forbidden": true
  },
  "task_types": [
    {
      "name": "Transition Kickoff",
      "workflows": [
        "1866384267"
      ],
      "title": "transition kick-?off"
    },
    {
      "name": "Pre-Launch Setup",
      "workflows": [
        "1866658899"
      ],
      "title": "pre[ -]?launch set ?up"
    },
    {
      "name": "Marketing Proposal",
      "workflows": [
        "1866658899"
      ],
      "title": "marketing proposal"
    },
    {
      "name": "Launch Readiness",
      "workflows": [
        "1866664080"
      ],
      "title": "launch readiness"
    },
    {
      "name": "Go-Live Execution",
      "workflows": [
        "1866664222"
      ],
      "title": "go-?live execution"
    },
    {
      "name": "Final Sign-Off",
      "workflows": [
        "1866664327"
      ],
      "title": "final sign-?off"
    },
    {
      "name": "30-Day Monitoring",
      "workflows": [
        "1866659765"
      ],
      "title": "30 ?- ?day monitoring"
    },
    {
      "name": "Transition Complete",
      "workflows": [
        "1867929348"
      ],
      "title": "transition complete"
    }
  ],
  "tier_property": null,
  "tiers": [],
  "no_task_workflows": [
    "1670039203"
  ],
  "expected_off": [],
  "not_readable": [],
  "branch_reasons": [],
  "waiting_on": [
    {
      "id": "W-1",
      "title": "Marketing proposal tasks in the Transitions queue (F-13)",
      "asked": "2026-10-06",
      "detail": "The 4 \"Marketing | Create Marketing Proposal\" actions in Pre Launch Setup put the task in the Transitions queue, although it is assigned to Brock Hegr, Sarah Schlosberg or Mohammad Abudahab.",
      "question": "Should marketing proposal tasks sit in the Transitions queue?",
      "workflows": [
        "1866658899"
      ]
    },
    {
      "id": "W-2",
      "title": "\"Automated\" 30-Day Monitoring task (F-15)",
      "asked": "2026-10-06",
      "detail": "\"Transition | 30 - DAY MONITORING | Subtask - Automated\" is an ordinary to-do for the ticket owner; nothing in the workflow automates it.",
      "question": "Is this task meant to be done by hand by the PM?",
      "workflows": [
        "1866659765"
      ]
    },
    {
      "id": "W-3",
      "title": "Which company the proposal's portfolio manager comes from (F-11)",
      "asked": "2026-10-06",
      "detail": "Pre Launch Setup checks PPC Enrolled on any company linked to the ticket, but reads Marketing Portfolio Manager from the earliest-created company with the \"Transitions\" label. Any other value, or none, sends the proposal to Brock Hegr.",
      "question": "Should the PPC check and the portfolio manager come from the same company, and is Brock Hegr the right default?",
      "workflows": [
        "1866658899"
      ]
    }
  ],
  "changes_not_confirmed": [],
  "queue_names": {
    "13519270": {
      "name": "Transitions",
      "label": "confirmed by WLS",
      "confirmed": "2026-10-06"
    }
  },
  "known_queue_moves": [],
  "known_issues": [
    {
      "id": "F-05",
      "text": "\"Transition | FINAL SIGN-OFF | Subtask - Mike\" (Final Sign Off, action 20) is set up without a company link, so it never has a company.",
      "link_titles": [
        "final sign-?off \\| subtask - mike"
      ]
    },
    {
      "id": "F-09",
      "text": "New tickets are created owned by Elizabeth Airey (owner 81929768), a deactivated user. Every \"Ticket Owner/PM\" task follows the ticket owner."
    },
    {
      "id": "F-10",
      "text": "Tasks copy only contacts with the \"Transition\" label, but the Closed Won workflow links contacts without a label, so tasks probably get no contact."
    },
    {
      "id": "F-12",
      "text": "The Transition Complete check is created after the ticket reaches Transition Completed (a closed stage), due the same day."
    }
  ],
  "closed": [],
  "workflow_summaries": {},
  "old_workflow_names": {}
}
```
