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

## The Transitions process (Cherine, 2026-10-20)

This is how onboarding really works. Use it in every run.

1. **Sales moves the deal to Closed won.** The Closed Won workflow (1670039203) creates the onboarding ticket in UNASSIGNED. It doesn't add a company **on purpose**: the facility doesn't exist yet.
2. **The onboarding team sends the intake form.** When it's completed, the Create Facility workflow (1852542804) creates the company (the facility).
3. **Ilsa (Ilse Modene in HubSpot) associates that company with the ticket by hand, before the ticket moves to Pre-Launch Setup** (Cherine, 2026-10-20). The ticket is created without a company and can still be without one during Transition Kickoff; that's by design. From Pre-Launch Setup on, it must have its company.
4. **If a ticket moves to Pre-Launch Setup or a later stage before its company is associated**, that stage's tasks get no company. That's a **team process issue, not a workflow fault**. It is reported under its own heading, "Process issues for the Transitions team", with the ticket, the stage, when it moved (and who moved it), and when the company was linked. Those tasks are not reported again under question 2.
   - How the audit knows when the company was associated: the ticket's "Number of Associated Companies" (`hs_num_associated_companies`) history, the first time it goes above 0 (VERIFIED (records)). Who moved the ticket comes from the ticket status history.

## How "who should get a task" works for Transitions

Transitions workflows don't run on a schedule. Each one starts when a **ticket** in the Onboarding Pipeline enters its stage. So, for each week:

1. **Who should have it:** every Onboarding Pipeline ticket that entered the workflow's stage during the week (from the ticket's stage history). VERIFIED (records) for the stage move; INFERENCE that the workflow should have enrolled it.
2. **Re-enrollment is off** on all 7 task workflows. A ticket that had already entered that stage before (since the workflow was created) gets nothing new; that's "not expected", not missing.
3. **The facility** is the ticket's company with the "Transitions" label, else its Primary company. The weekly page lists results by facility. A ticket with no company is reported as its own problem.
4. **Did it get it:** the ticket got every task the stage creates. If it got only some, it's "partial", and the missing task titles are named.

## Rules

1. Each stage's tasks go to every ticket that enters that stage in the Onboarding Pipeline (see above). There is no company filter: the ticket's stage decides, because onboarding facilities aren't live yet.
2. Every Create task action uses the Transitions queue (13519270).
3. **Main tasks and subtasks** (Cherine, 2026-10-13; subtask part changed 2026-10-16):
   - **Main tasks** are the tasks the workflows create, including every task named "... | Subtask - [person]" (e.g. "Transition | TRANSITION KICK-OFF | Subtask - Bryn"). Despite the word "Subtask" in the name, these are main tasks. Each must be linked to the **ticket** and to exactly **one company**.
   - **Checklist subtasks** are only the real checklist items inside a task (HubSpot's "Is subtask" = true, with a parent task). They **share their main task's links**, including the ticket: HubSpot copies them automatically. This is accepted, by design (2026-10-16, closes W-5 and SUB-1). The audit flags a subtask only if its links (companies or ticket) **differ** from its main task's. Exception (Cherine, 2026-10-23): if **only one of the two has a company** (the subtask or its main task), that's fine and not flagged. Only different companies on both, or a different ticket, are flagged.
4. Tasks that shouldn't exist (a ticket that didn't enter the stage, or a second set for the same ticket) are reported.
5. **Every Closed Won deal gets an onboarding ticket** (Cherine, 2026-10-13). Every deal in the White Label Storage SALES pipeline that moved to Closed won in the window must have a ticket in the Onboarding Pipeline. Any deal without one is reported under question 1, with a link to the deal. VERIFIED (records): the deal's "Date entered Closed won" and its ticket links.
6. **The company is associated before the ticket moves to Pre-Launch Setup** (Cherine, 2026-10-20). A ticket that reaches Pre-Launch Setup or a later stage before its company is associated is a process issue for the Transitions team (see "The Transitions process", step 4), not a workflow fault.
7. **Kickoff tasks without a company are fine, by design** (Cherine, 2026-10-20). Transition Kickoff tasks, and their checklist subtasks, can be created before the company is associated, so they may have none. They are not reported as problems; each run lists them under "By design, not problems" with this reason.

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

**Not a task type:** Closed Won | Create Ticket in INITIAL SETUP - UNASSIGNED (1670039203) creates the ticket, not tasks. It's checked by rule 5 (every Closed Won deal got an onboarding ticket) and for changes (question 3).

## Decisions so far

All agreed with Cherine on 2026-10-13:
- **Option A:** question 1 is worked out from tickets entering stages, not from company schedules.
- **Facility of a ticket:** the "Transitions" company, else the Primary company.
- **Task types:** one per stage, plus Marketing Proposal. A ticket missing some of a stage's tasks is "partial".
- **Company scope:** none. The ticket's stage decides.
- **Links:** main task to the ticket and exactly one company; checklist subtasks share their main task's links (changed 2026-10-16, was "not linked to the ticket"). "Subtask - [person]" tasks are main tasks (rule 3).
- **Went live this week:** shown, using Status = Live and the go-live date, flagged when more than 7 days apart.
  - Checked on 2026-10-13: this is the same property as CS Ops. Company property `live` (label "Status"); Live is the internal value `Yes`. The go-live date is `go_live_date` (label "Actual Go-Live Date").
- **Closed Won deals:** every deal that moved to Closed won (White Label Storage SALES) in the window must have an Onboarding Pipeline ticket (rule 5).
- **Finish Line Self Storage, 3 Kickoff tasks with no company (12 Oct): by design, not a problem** (corrected 2026-10-20, Cherine; replaces the earlier notes). Ilse Modene moved the ticket to Transition Kickoff at 2:35 PM (US Eastern) on 12 Oct; the Kickoff workflow created its tasks seconds later, while the ticket had no company; she linked Finish Line Self Storage to the ticket 24 seconds after the move (VERIFIED (records): ticket status history and "Number of Associated Companies" history; Cherine said about a minute). That's before Pre-Launch Setup, so the process was followed, and Kickoff tasks without a company are by design (rule 7). Not caused by W-4. Cherine linked the company to the 3 main tasks by hand on 2026-10-15; their 17 checklist subtasks still have no company, which is also fine at Kickoff. W-7 (why the hand fix didn't reach the subtasks) was closed as done and resolved on 2026-10-20.
- **Owensville Storage, Pre-Launch tasks created late (20 Oct): already dealt with** (Cherine, 2026-10-30). The ticket passed through Pre-Launch Setup in 6 seconds on 14 Oct, so the workflow skipped it; the Pre-Launch tasks and the Marketing Proposal were created on 20 Oct to make up for it. Listed under "Already dealt with" (setting `handled`), not as problems.
- **Excluded companies:** demo Facility (44541671248), the same as CS Ops.
- **Closed Won adds no company, by design** (Cherine, 2026-10-20; was W-4): the facility doesn't exist yet when the deal closes. The 8 Oct edit was planned.
- **The onboarding team links the company before the ticket moves to Pre-Launch Setup** (Cherine, 2026-10-20; was W-6): "By design. The company must be linked by the onboarding team before the ticket moves on. Cherine is raising it with Ilsa." The deadline is Pre-Launch Setup: a Kickoff ticket may not have its company yet (rule 7). A ticket that reaches Pre-Launch Setup or later without it is a process issue (rule 6), not a workflow problem.
- **A subtask and its main task only need the company on one of them** (Cherine, 2026-10-23). A subtask with no company when its main task has one is fine, and so is a subtask with the company when its main task has none (e.g. Rindge Self Storage, Final Sign-Off; the main task's missing company is known issue F-05). Not flagged under question 2. Still flagged: both have a company but different ones, or a different ticket.
- **Checklist subtasks share their main task's links** (2026-10-16; was W-5 / SUB-1): accepted, by design. Subtasks linked to the ticket are not a problem. Only a subtask whose links differ from its main task's is flagged (question 2). Cherine has been told and may ask to revisit it.
- **Marketing Proposal routing is by design** (Cherine, 2026-10-15; was W-3 / F-11): the PPC check looks at any company linked to the ticket; the proposal goes to the Marketing Portfolio Manager of the first-created "Transitions" company; Brock Hegr is the correct default when that manager is empty or someone else. Keep the workflow as it is. **Never flag this** in a weekly run: the check only looks at whether the proposal was created when PPC Enrolled = Yes, not who it went to.
- **"Subtask - Automated" (30-Day Monitoring) is by design** (Cherine, 2026-10-15; was W-2 / F-15): the CSAT survey goes out automatically when the ticket enters Post 30-Day Monitoring, and this task tells the ticket owner it was sent. "Automated" refers to the survey, not the task. Not a problem. Survey name to be confirmed.
- **Marketing Proposal tasks stay in the Transitions queue** (Cherine, 2026-10-14; was W-1 / F-13): queues track tasks by process, not by team, and the proposal is part of the Transitions process. Not a problem.
- **Page colours:** the WLS brand colours, the same as CS Ops.

## Waiting on Cherine

Report these once per run, in their own section, not as new problems every week.

None right now.

### Closed (answered by Cherine)

| Item | Answer |
|---|---|
| W-1 (F-13). Should the Marketing Proposal tasks sit in the Transitions queue? | Yes: the Marketing Proposal tasks stay in the Transitions queue. Queues track tasks by process, not by team, and the proposal is part of the Transitions process (Cherine, 2026-10-14). Closed 2026-10-15. |
| W-2 (F-15). Is "Transition \| 30 - DAY MONITORING \| Subtask - Automated" meant to be done by hand by the PM? | By design (Cherine, 2026-10-15). The CSAT survey is sent automatically by a feedback survey when the ticket enters Post 30-Day Monitoring (survey name to be confirmed). The "Subtask - Automated" task is created at the same time so the ticket owner can see it was sent: "Automated" refers to the survey, not the task. In HubSpot: the workflow "Send Transitions CSAT" (1700009377, ON) adds the contacts of a ticket in Post 30-Day Monitoring to the list "Send Transitions Survey" (1889) (VERIFIED (config)); that the survey sends to this list is INFERENCE. Closed 2026-10-15. |
| W-3 (F-11). Should the proposal's PPC check and portfolio manager come from the same company, and is Brock Hegr the right default? | By design, keep the workflow as it is (Cherine, 2026-10-15). The PPC check looks at any company linked to the ticket, and the proposal goes to the Marketing Portfolio Manager of the first-created "Transitions" company. That's how WLS wants it. Brock Hegr is the correct default when the portfolio manager is empty or someone else. Not flagged in future runs. Closed 2026-10-15. |
| W-5 and known issue SUB-1. Checklist subtasks always get the ticket link, because they copy the main task. Accept it, or look for another way? | Accepted, by design (2026-10-16). Checklist subtasks belong to their main task, so they share the main task's links, including the ticket. HubSpot does this automatically. Cherine has been told and can ask to look for another way (the client didn't like seeing subtasks on the ticket before). Closed 2026-10-16. |
| W-4. The Closed Won workflow no longer copies the deal's companies onto the ticket (edited 8 Oct). Was that on purpose? | By design. The Closed Won workflow doesn't add a company on purpose: when the deal closes, the facility doesn't exist yet. It is created later by Create Facility from the intake form, and the onboarding team links it to the ticket by hand (Cherine, 2026-10-20). The 8 Oct edit (revision 13 -> 14) was planned; the master rules file now holds revision 14. Closed 2026-10-20. |
| W-6. Should the facility always be linked before a ticket moves to Kickoff, or should something link it automatically? | By design. The company must be linked by the onboarding team before the ticket moves on. Cherine is raising it with Ilsa. (Cherine, 2026-10-20). Clarified 2026-10-20: the deadline is Pre-Launch Setup; Kickoff tasks without a company are by design. Closed 2026-10-20. |
| W-7. When a company is added by hand to a main task, HubSpot updates its checklist subtasks but doesn't add the company to them. Why, and how should subtasks get the company? | Done and resolved (closed by WLS on 2026-10-20). No further action. Note: Finish Line's Kickoff checklist subtasks without a company are by design anyway (rule 7). Closed 2026-10-20. |

## Changes not yet confirmed

None. The Closed Won edit of 2026-10-08 (revision 13 -> 14, it no longer copies the deal's companies onto the ticket) was planned (Cherine, 2026-10-20, W-4); the master rules file was updated the same day.

## Known issues

Report each once, as a known issue, with this week's count where it applies.

- **F-05:** "Transition | FINAL SIGN-OFF | Subtask - Mike" (Final Sign Off, action 20) is set up without a company association, so it is always flagged under question 2. Reported here once a week instead.
- **F-09:** new tickets are created owned by Elizabeth Airey (owner 81929768), a deactivated user. Every "Ticket Owner/PM" task follows the ticket owner. On 22 Oct 2026 the Kickoff task for SSU Storage - Shenandoah (ticket 49916242185) was created, assigned to her, then deleted (VERIFIED (screenshot) of the workflow action log, 2026-10-30). The audit reports such a task under F-09 as "created, then deleted", not as missing (setting `deleted_tasks`).
- **F-10:** tasks copy only contacts with the "Transition" label, but the Closed Won workflow associates contacts without a label, so tasks probably get no contact.
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
- `record_checks` lists records that must get a record from a workflow: here, deals that entered Closed won (pipeline 79187488, stage 150102819) must have a ticket in the Onboarding Pipeline (751582029).

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
  "record_checks": [
    {
      "name": "Closed Won deal got an onboarding ticket",
      "workflow": "1670039203",
      "object": "deals",
      "object_label": "deal",
      "object_type_id": "0-3",
      "pipeline": "79187488",
      "pipeline_property": "pipeline",
      "stage": "150102819",
      "stage_label": "Closed won (White Label Storage SALES)",
      "creates": "tickets",
      "creates_label": "onboarding ticket",
      "created_in_pipelines": [
        "751582029"
      ]
    }
  ],
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
    "subtask_ticket_forbidden": false,
    "subtask_links_match_parent": true,
    "subtask_company_ok_if_one_has": true
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
  "waiting_on": [],
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
      "text": "\"Transition | FINAL SIGN-OFF | Subtask - Mike\" (Final Sign Off, action 20) is set up without a company association, so it never has a company.",
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
      "text": "Tasks copy only contacts with the \"Transition\" label, but the Closed Won workflow associates contacts without a label, so tasks probably get no contact."
    },
    {
      "id": "F-12",
      "text": "The Transition Complete check is created after the ticket reaches Transition Completed (a closed stage), due the same day."
    }
  ],
  "closed": [
    {
      "id": "W-7",
      "closed": "2026-10-20",
      "answered": "2026-10-20",
      "answer": "Done and resolved (closed by WLS on 2026-10-20). No further action. Note: Finish Line's Kickoff checklist subtasks without a company are by design anyway (rule 7)."
    },
    {
      "id": "W-4",
      "closed": "2026-10-20",
      "answered": "2026-10-20",
      "answer": "By design. The Closed Won workflow doesn't add a company on purpose: when the deal closes, the facility doesn't exist yet. It is created later by Create Facility from the intake form, and the onboarding team links it to the ticket by hand (Cherine, 2026-10-20). The 8 Oct edit (revision 13 -> 14) was planned; the master rules file now holds revision 14."
    },
    {
      "id": "W-6",
      "closed": "2026-10-20",
      "answered": "2026-10-20",
      "answer": "By design. The company must be linked by the onboarding team before the ticket moves on. Cherine is raising it with Ilsa.",
      "clarified": "2026-10-20: the deadline is Pre-Launch Setup; Kickoff tasks without a company are by design."
    },
    {
      "id": "W-5",
      "closed": "2026-10-16",
      "answered": "2026-10-16",
      "answer": "Accepted, by design (2026-10-16). Checklist subtasks belong to their main task, so they share the main task's links, including the ticket. HubSpot does this automatically. Cherine has been told and can ask to look for another way (the client didn't like seeing subtasks on the ticket before).",
      "also_closes": "SUB-1"
    },
    {
      "id": "W-3",
      "closed": "2026-10-15",
      "answered": "2026-10-15",
      "answer": "By design, keep the workflow as it is (Cherine, 2026-10-15). The PPC check looks at any company linked to the ticket, and the proposal goes to the Marketing Portfolio Manager of the first-created \"Transitions\" company. That's how WLS wants it. Brock Hegr is the correct default when the portfolio manager is empty or someone else. Not flagged in future runs.",
      "do_not_flag": true
    },
    {
      "id": "W-2",
      "closed": "2026-10-15",
      "answered": "2026-10-15",
      "answer": "By design (Cherine, 2026-10-15). The CSAT survey is sent automatically by a feedback survey when the ticket enters Post 30-Day Monitoring (survey name to be confirmed). The \"Subtask - Automated\" task is created at the same time so the ticket owner can see it was sent: \"Automated\" refers to the survey, not the task. In HubSpot: the workflow \"Send Transitions CSAT\" (1700009377, ON) adds the contacts of a ticket in Post 30-Day Monitoring to the list \"Send Transitions Survey\" (1889) (VERIFIED (config)); that the survey sends to this list is INFERENCE.",
      "to_confirm": "the feedback survey's name"
    },
    {
      "id": "W-1",
      "closed": "2026-10-15",
      "answered": "2026-10-14",
      "answer": "Yes: the Marketing Proposal tasks stay in the Transitions queue. Queues track tasks by process, not by team, and the proposal is part of the Transitions process (Cherine, 2026-10-14)."
    }
  ],
  "workflow_summaries": {},
  "old_workflow_names": {},
  "handled": [
    {
      "ticket": "47886783564",
      "task_types": ["Pre-Launch Setup", "Marketing Proposal"],
      "handled": "week of 2026-10-19",
      "note": "Owensville passed through Pre-Launch Setup in 6 seconds on 14 Oct, so the workflow skipped it; the Pre-Launch tasks and the Marketing Proposal were created late on 20 Oct to make up for it. Dealt with the week of 19 Oct (Cherine, 2026-10-30)."
    }
  ],
  "deleted_tasks": [
    {
      "ticket": "49916242185",
      "task_type": "Transition Kickoff",
      "titles": ["Transition | TRANSITION KICK-OFF"],
      "known_issue": "F-09",
      "label": "VERIFIED (screenshot)",
      "note": "The workflow log shows it was created and assigned to Elizabeth Airey (deactivated); it no longer exists in HubSpot. Confirmed by Cherine from the action log on 2026-10-30."
    }
  ],
  "fixed_by_hand": [
    {
      "task_ids": [
        "118385086549",
        "118386967348",
        "118384322086"
      ],
      "problem": "no company",
      "fixed": "2026-10-15",
      "note": "Finish Line Self Storage linked to the 3 Kickoff tasks by Cherine; checked in HubSpot on 2026-10-15 (VERIFIED (records)).",
      "ticket": "49234797065",
      "company": "59101446751"
    }
  ],
  "process_issues": {
    "company_before_stage": true,
    "heading": "Process issues for the Transitions team",
    "note": "A ticket moved to a stage before its first company link (hs_num_associated_companies > 0): that stage's tasks got no company. Team process issue, not a workflow fault (Cherine, 2026-10-20).",
    "stages": [
      "1094530722",
      "1094530723",
      "1094493506",
      "1094493507",
      "1102485356",
      "1094530724"
    ],
    "stages_note": "Pre-Launch Setup and every later stage of the Onboarding Pipeline (the company must be associated before Pre-Launch Setup)."
  },
  "by_design_no_company": [
    {
      "task_types": [
        "Transition Kickoff"
      ],
      "reason": "The ticket gets its company by hand before Pre-Launch Setup, so Kickoff tasks (and their checklist subtasks) can be created before it's associated.",
      "decided": "2026-10-20",
      "by": "Cherine"
    }
  ]
}
```
