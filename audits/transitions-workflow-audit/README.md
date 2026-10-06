# WLS Transitions Workflow Audit

- **Workbook:** `WLS_Transitions_Workflow_Audit.xlsx`
- **Data as of:** 2026-10-02
- **HubSpot portal:** 45059701

## Scope (13 workflows)

| # | Workflow | ID | Object |
|---|---|---|---|
| 1 | Closed Won \| Create Ticket in INITIAL SETUP - UNASSIGNED | 1670039203 | Deal |
| 2 | Transitions - Transition Kickoff Tasks (+SubTask) | 1866384267 | Ticket |
| 3 | Transitions - Pre Launch Setup Tasks (+SubTask) | 1866658899 | Ticket |
| 4 | Transitions - Launch Readiness Tasks (+SubTask) | 1866664080 | Ticket |
| 5 | Transitions - Go Live Execution Tasks (+SubTask) | 1866664222 | Ticket |
| 6 | Transitions - Final Sign Off Tasks (+SubTask) | 1866664327 | Ticket |
| 7 | Transitions - 30-Day Monitoring (+SubTask) | 1866659765 | Ticket |
| 8 | Transitions - TRANSITION COMPLETE (+SubTask) | 1867929348 | Ticket |
| 9 | Transition Kickoff Tasks > Pre Launch Setup Tasks (task complete) | 1699704693 | Task |
| 10 | Transition Pre Launch Setup Tasks > Launch Readiness Tasks (task complete) | 1699666189 | Task |
| 11 | Transition Launch Readiness Tasks > Go Live Execution Tasks (task complete) | 1699704743 | Task |
| 12 | Transition Go-Live Execution tasks > Final Signoff tasks (task complete) | 1699730300 | Task |
| 13 | Transition Final Signoff tasks > 30 Day monitoring task (task complete) | 1699702705 | Task |

## Sources

- **Workflow settings (source of truth):** read from the HubSpot Automation v4 API on 2026-10-02 and marked *VERIFIED (config)*. That covers every trigger, re-enrollment/unenrollment setting and action.
- **Subtasks:** the API does not return them. Subtask titles, owners and due dates come from the tasks the workflows created (*VERIFIED (records)*). For Kickoff Step 1 they were also checked against a screenshot.
- **Cross-check:** task and ticket records are used to confirm the settings against what actually happened (counts, owners, due dates, timing).

## What actually happens

1. **The ticket is created.** A deal reaching *Closed won* (White Label Storage SALES pipeline) triggers the Closed Won workflow. It creates one ticket:
   - name = the deal's name
   - stage = **UNASSIGNED** (Onboarding Pipeline)
   - owner = Elizabeth Airey
   - linked to the deal, the deal's contacts and the deal's companies (company label "Transitions")

   Re-enrollment is off, so each deal gets one ticket.
2. **The ticket waits in UNASSIGNED.** None of the 13 workflows moves it to Transition Kickoff; a person has to.
3. **Each stage triggers its workflow.** Whenever *Ticket status* equals the stage, the matching (+SubTask) workflow enrolls the ticket. Each workflow then creates its parent tasks back to back, with no delays. Their subtasks have no owner. Owners are either the **ticket owner** ("Ticket Owner/PM" tasks) or a **fixed person** (Mo'men, Bryn, Mike, Ilse, Hunter, Ryan, Aseel).

   | Stage | Parent tasks | Due (business days, 08:00) |
   |---|---|---|
   | Kickoff | 3 | 7 |
   | Pre-Launch | 5 | 6 |
   | Launch Readiness | 5 | 6 |
   | Go-Live | 5 | 1 |
   | Final Sign-Off | 6 | 4 |
   | 30-Day Monitoring | 2 | 30 |
   | Transition Complete | 1 | 0 |

4. **Pre-Launch has one branch.** If an associated company has *PPC Ads = Yes*, it also creates "Marketing | Create Marketing Proposal" for that company's Marketing Portfolio Manager. The choices are Brock, Sarah or Mohammad; anyone else goes to Brock.
5. **Moving to the next stage is meant to be automatic, but no longer is.** The five "(task complete)" workflows move the ticket on when a task with a specific old title is completed (e.g. "TRANSITION KICKOFF: PM - FINAL SIGN OFF"). They only act if the ticket is still in that stage. Those titles came from the **legacy** workflows, and the (+SubTask) workflows never create them, so **for the new process every stage move is manual** (F-01). Since 2026-08-20 the advance workflows have only fired on 41 leftover legacy tasks.
6. **Two moves were never automated:** UNASSIGNED → Kickoff, and Post 30-Day Monitoring → Transition Completed (F-02).
7. **The final check runs after the ticket is closed.** Entering Transition Completed (a closed stage) creates one final PM task, due the same day (F-18).

## What WLS should verify / decide

- **F-01:** which (+SubTask) task should trigger each automatic stage move. Then either update the five advance workflows' title filters or retire them.
- **F-02:** who owns the UNASSIGNED → Kickoff and 30-Day → Completed moves.
- **F-04:** re-enrollment is off everywhere, so a ticket sent back to a stage gets no new tasks. Is that intended?
- **F-05, F-06, F-25:** subtask owner settings. One subtask screenshot would confirm whether "no owner" is a setting.
- **F-07, F-08:** whether parents and stages should wait for subtasks to be complete. There are 95 open subtasks under completed parents, and many overdue tasks.
- **F-10, F-11:** contact and company associations.
  - The "Transition" contact label is almost never used, so tasks rarely link to a contact.
  - Some actions don't link the company at all.
- **F-12, F-13:**
  - The task owners that are fixed people (hard-coded).
  - How the ticket owner changes from Elizabeth Airey to the PM before Kickoff starts.
- **F-14:** why 79 tickets are linked to 2 deals.
- **F-15:** the Pre-Launch proposal fallback to Brock, and which company it reads when a ticket has several.
- **F-16, F-17, F-24:** three individual tickets: Stow Pros, Spencerport, and company 38502110732.

## Re-running

The scripts in `scripts/` read `HUBSPOT_ACCESS_TOKEN`. Run them from a scratch directory in this order:

1. `pull_configs.py`
2. `pull.py`
3. `pull2.py`
4. `pull3.py`
5. `analyze.py`
6. `model.py`
7. `build.py`

They need `openpyxl` and `tzdata`. The raw JSON they produce contains customer data and is not committed.

The Read Me sheet's summary counts are COUNTIF formulas that Excel calculates when the file is opened.
