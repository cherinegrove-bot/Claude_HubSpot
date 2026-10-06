# WLS Transitions Workflow Audit, version 3

- **Workbook:** `WLS_Transitions_Workflow_Audit_v3.xlsx` (5 sheets: Process Overview, Detailed Action Map, Task & Subtask Logic, Workflow Inventory, Audit Findings)
- **Summary page:** `transitions-audit-summary.html` (open in any browser)
- **Findings source:** `findings.json`
- **Data as of:** 2026-10-06. Version 3 re-read only the Go-Live Execution workflow (1866664222) after its queue was fixed; everything else is the version 2 data.
- **HubSpot portal:** 45059701
- **Previous versions:** `WLS_Transitions_Workflow_Audit_v2.xlsx` with `README_v2.md` (2026-10-06, before the Go-Live queue fix), and `WLS_Transitions_Workflow_Audit.xlsx` with `README.md` (2026-10-02, 13 workflows), are kept unchanged.
- **Changes in version 3:** F-08 (Go-Live Execution queue) is now No Issue Found, and F-13 records that all 31 task actions use the Transitions queue. All other findings and finding numbers are the same as in version 2.

Read only: nothing in HubSpot was changed. This audit reports what it finds; what to do about it is WLS's decision.

## Scope (8 workflows, agreed 2026-10-06)

| # | Workflow | ID | Object | Status on 2026-10-06 |
|---|---|---|---|---|
| 1 | Closed Won \| Create Ticket in INITIAL SETUP - UNASSIGNED | 1670039203 | Deal | ON |
| 2 | Transitions - Transition Kickoff Tasks (+SubTask) | 1866384267 | Ticket | ON |
| 3 | Transitions - Pre Launch Setup Tasks (+SubTask) | 1866658899 | Ticket | ON |
| 4 | Transitions - Launch Readiness Tasks (+SubTask) | 1866664080 | Ticket | ON |
| 5 | Transitions - Go Live Execution Tasks (+SubTask) | 1866664222 | Ticket | ON |
| 6 | Transitions - Final Sign Off Tasks (+SubTask) | 1866664327 | Ticket | ON |
| 7 | Transitions - 30-Day Monitoring (+SubTask) | 1866659765 | Ticket | ON |
| 8 | Transitions - TRANSITION COMPLETE (+SubTask) | 1867929348 | Ticket | ON |

- **Queue:** Transitions, ID `13519270` (confirmed by WLS on 2026-10-06 and recorded in `teams.json`).
- **Start date:** 2026-10-06. Only tasks in the queue created on or after this date are in scope. None existed yet when the audit ran (F-16).
- **Not in scope:** the 5 stage-advance (task complete) workflows. Moving tickets between stages was therefore not checked.
- **Team checks added for this run:**
  1. Every Create task action uses the Transitions queue (F-08, F-13).
  2. Subtasks are not linked to the ticket; only main tasks are (F-14).

## Sources

- **Workflow settings (source of truth):** read from the HubSpot Automation v4 API on 2026-10-06 and marked *VERIFIED (config)*. Go-Live Execution (1866664222) was read again later that day, at revision 60, after WLS set its queue. This covers each workflow's trigger, re-enrollment setting, actions, branches, owners, due dates, queues and associations.
- **Reference data:** owners (including deactivated users), pipelines and stages, and association labels, read from the HubSpot API.
- **Task records:** searched in the queue from 2026-10-06 onward. There were 0 tasks, so no finding is based on task records yet.
- **Subtasks:** the API does not return subtask settings. Nothing in this version describes a subtask's title, owner or due date.

Evidence labels used throughout: VERIFIED (config), VERIFIED (records), VERIFIED (screenshot), INFERENCE (with the reason), NEEDS VERIFICATION (with what would settle it).

## What actually happens

1. **The ticket is created.** When a deal reaches *Closed won* (White Label Storage SALES pipeline), the Closed Won workflow creates one ticket:
   - name = the deal name
   - stage = **UNASSIGNED** (Onboarding Pipeline)
   - owner = Elizabeth Airey (owner ID 81929768), who is deactivated in HubSpot (F-09)

   The ticket is linked to the deal, to the deal's contacts (no label) and to the deal's companies (label "Transitions"). Re-enrollment is off, so each deal gets one ticket.
2. **The ticket waits in UNASSIGNED.** None of the 8 workflows moves a ticket from one stage to the next (F-06). A person, or automation outside this scope, does it.
3. **Each stage creates its tasks.** Each Transitions workflow enrolls a ticket in the Onboarding Pipeline when its status becomes that workflow's stage. It then creates all of its tasks at once, with no delays and no waits (F-07). Re-enrollment is off everywhere (F-01).

   | Stage | Tasks | Due (business days, 08:00) | Queue |
   |---|---|---|---|
   | Transition Kickoff | 3: ticket owner, Mo'men, Bryn | 7 | 13519270 |
   | Pre-Launch Setup | 5: ticket owner, Mike, Mo'men, Bryn, Ilse; plus 1 marketing proposal if PPC (step 4) | 6 (proposal 3) | 13519270 |
   | Launch Readiness | 5: Mo'men, Hunter, ticket owner, Bryn, Ryan | 6 | 13519270 |
   | Go-Live Execution | 5: Ryan, Bryn, ticket owner, Mo'men, Mike | 1 | 13519270 (fixed 2026-10-06, F-08) |
   | Final Signoff | 6: Mo'men, Bryn, Mike, ticket owner, Aseel, Ilse | 4 | 13519270 |
   | Post 30-Day Monitoring (OM/SM) | 2: both to the ticket owner, one titled "Automated" (F-15) | 30 | 13519270 |
   | Transition Completed (a closed stage) | 1: ticket owner | 0, same day (F-12) | 13519270 |

4. **The marketing proposal branch (Pre-Launch Setup).** The workflow checks whether any associated company has PPC Enrolled = Yes. If none does, no proposal task is created. If one does, it reads Marketing Portfolio Manager from the earliest-created company with the "Transitions" label:
   - Brock Hegr, Sarah Schlosberg or Mohammad Abudahab: the proposal task goes to that person.
   - Any other value, or no value: it goes to Brock Hegr (F-11).
5. **Owners.**
   - "Ticket Owner/PM" tasks, the main Kickoff task and the Pre-Launch "Subtask" task go to the ticket owner at the time the task is created.
   - All other tasks go to the fixed named person on the action (F-02).
6. **Associations.**
   - Every task is linked to the ticket (correct for main tasks).
   - Tasks also copy the ticket's companies, and the ticket's contacts that have the "Transition" label. Some actions leave out the contact or the company (F-03 to F-05).
   - Because the ticket's contacts are added without that label, tasks probably get no contact (F-10).
7. **Subtasks.** Every workflow is named "(+SubTask)", but subtask settings are not visible in the API. Whether subtasks are linked to the ticket can only be checked from records or screenshots (F-14).
8. **Completion.** The last task is created when the ticket enters *Transition Completed*, which HubSpot treats as a closed stage (F-12).

## What WLS should verify / decide

1. Should the 4 marketing proposal tasks sit in the Transitions queue? (F-13)
2. Done: the 5 Go-Live Execution tasks now use the Transitions queue. The weekly check will confirm that new tasks land there. (F-08)
3. Are subtasks linked to the ticket? Send one subtask settings screenshot per workflow, or wait for the weekly check after the first enrollment. (F-14)
4. What changes the ticket owner from Elizabeth Airey (deactivated) to the real PM, and does it happen before Kickoff? (F-09)
5. Do Transitions tickets' contacts carry the "Transition" association label? (F-10)
6. Should the PPC check and the portfolio manager come from the same company? Is Brock Hegr the intended default? (F-11)
7. Should the final Transition Complete check run before the ticket is closed? (F-12)
8. Is "30 - DAY MONITORING | Subtask - Automated" meant to be a manual task for the PM? (F-15)
9. Who moves tickets between stages, now that the stage-advance workflows are outside this audit? (F-06)
10. Rerun the weekly check once tickets have entered Transitions stages after 2026-10-06, so the tasks can be checked against this configuration. (F-16)
