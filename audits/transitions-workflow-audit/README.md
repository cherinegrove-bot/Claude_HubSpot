# WLS Transitions Workflow Audit (observed-behaviour build)

Workbook: `WLS_Transitions_Workflow_Audit.xlsx`. Data as of 2026-10-02, HubSpot portal 45059701.

**Scope (8 workflows):**
1. Closed Won | Create Ticket in INITIAL SETUP - UNASSIGNED (1670039203)
2. Transitions - Transition Kickoff Tasks (+SubTask)
3. Transitions - Pre Launch Setup Tasks (+SubTask)
4. Transitions - Launch Readiness Tasks (+SubTask)
5. Transitions - Go Live Execution Tasks (+SubTask)
6. Transitions - Final Sign Off Tasks (+SubTask)
7. Transitions - 30-Day Monitoring (+SubTask)
8. Transitions - TRANSITION COMPLETE (+SubTask)

## Important limitation

HubSpot's Automation API will not return the configuration of any of these 8 workflows.
- Workflow 1670039203 returns `403 FLOW_ACCESS_DENIED`.
- The 7 (+SubTask) workflows are missing from the API's workflow list altogether.

That was still true after every sensitive read scope and the write scopes were added to the private app.

The workbook is therefore built from the records the workflows create. HubSpot stamps every workflow-created task with three things:
- the workflow name
- the enrollment ID
- the action execution index

That shows **what** each workflow did, **in what order**, **for which ticket** and **when**. It does **not** show:
- triggers
- re-enrollment
- suppression
- branch conditions
- delays
- actions that create no record
- the exact HubSpot action labels

Every statement in the workbook is labelled **VERIFIED (records)**, **INFERENCE** or **NEEDS VERIFICATION**.

## What actually happens?

1. **Ticket creation.** The Closed Won workflow has created 171 Onboarding Pipeline tickets (2025-07-14 to 2026-10-01). Each one is created in stage **UNASSIGNED**, and the ticket name is usually the deal name. The deal trigger itself can't be seen.
2. **Waiting.** None of the 7 Transitions workflows fires in UNASSIGNED, On Hold or Website Only. Nothing observed moves the ticket out of UNASSIGNED, so the move to Transition Kickoff appears to be manual (INFERENCE).
3. **Stage entry triggers each workflow.** Every one of the 101 enrollments started 4–25 seconds after the ticket entered the matching stage (INFERENCE: the trigger is "ticket enters stage"):

   | Stage entered | Workflow that runs |
   |---|---|
   | Transition Kickoff | Kickoff |
   | Pre-Launch Setup | Pre Launch |
   | Launch Readiness | Launch Readiness |
   | Go-Live Execution | Go Live |
   | Final Signoff | Final Sign Off |
   | Post 30-Day Monitoring | 30-Day |
   | Transition Completed | TRANSITION COMPLETE |

4. **Task actions.** Each workflow runs a short series of task-creating actions, with no delays between them. Each action creates one **parent task** plus its **subtasks**.
   - Parents are owned either by the **ticket owner** ("Ticket Owner/PM" parents) or by a **fixed named person** (Bryn, Mo'men, Mike, Ilse, Hunter, Ryan, Aseel, Brock).
   - **Subtasks have no owner**, except in TRANSITION COMPLETE.
   - Due dates are a fixed number of business days after creation, at 08:00 ET.
   - The full lists are in *Task & Subtask Logic*.
5. **Handoffs between workflows.** The only link between the 7 workflows is the ticket's stage. Completing tasks does not move the stage; timing data and the subtask text "move manually" both point to manual moves.
6. **Two other workflows act on these tasks** (their configuration was readable):
   - **Set task queue** puts the two "BOG" subtasks into the *BOG - Run and Sustain* queue.
   - **Set OM and SM overdue tasks to Deferred** can defer overdue parents owned by OM/SM team members.
7. **Completion.** Moving the ticket to Transition Completed, which is a closed stage, creates one final PM task, due the same day.

## What should WLS verify?

- For all 8 workflows: the enrollment trigger, the re-enrollment setting, the suppression lists, and whether there are branches, delays or non-task actions. The gaps at Pre-Launch #6–#7 prove that at least some non-task actions exist.
- The exact action type and settings of each task action, especially:
  - the subtask **owner** (empty in 6 of 7 workflows)
  - the due-date rule
  - the association settings (some tasks are ticket-only)
- Why Spencerport (48042783912) entered Kickoff and got no Kickoff tasks (F-07). It's possible suppression or "unenroll" settings exist.
- Why one Pre-Launch enrollment (Stow Pros, 2026-08-31) created only one of five parent tasks (F-08).
- Whether Pre-Launch's new "Marketing | Create Marketing Proposal" task (#8) duplicates the "Marketing Proposal Task" workflow (F-09).
- Whether open subtasks are meant to stay open when the parent is completed (95 open now), and whether anything should close out tasks from earlier stages (F-03, F-04).
- Whether the TRANSITION COMPLETE check is meant to run *after* the ticket is closed (F-16).
- Whether onboarding BOG subtasks belong in the BOG Run & Sustain queue, and whether Transitions tasks should be auto-deferred (F-25, F-26).
- Whether the 79 Closed Won tickets linked to 2 deals, and the 18 companies with more than one onboarding ticket, are intended (F-22).
- Who moves tickets from UNASSIGNED into Transition Kickoff, and between later stages (F-20, F-23).
- That the legacy non-subtask Transitions workflows are switched off. They stopped creating tasks 2026-08-11 to 08-18 (F-06).

## Re-running

The `scripts/` folder pulls the data with `HUBSPOT_ACCESS_TOKEN` and rebuilds the workbook. Run them in this order from a scratch directory:

1. `pull.py`
2. `pull2.py`
3. `pull3.py`
4. `analyze.py`
5. `model.py`
6. `build.py`

The scripts need `openpyxl` and `tzdata`. The raw JSON they produce contains customer data and is deliberately not committed.

The Read Me summary counts are COUNTIF formulas that Excel calculates when the file is opened. LibreOffice could not run in this environment to pre-calculate them.
