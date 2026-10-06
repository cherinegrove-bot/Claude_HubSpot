# WLS CS Ops Workflow Audit (full map)

- **Workbook:** `WLS_CS_Ops_Workflow_Audit.xlsx`. It has 5 sheets with the same columns and styling as the Transitions audit:

  | Sheet | Rows |
  |---|---|
  | Process Overview | 239 |
  | Detailed Action Map | 490 |
  | Task & Subtask Logic | 126 |
  | Workflow Inventory | 23 |
  | Audit Findings | 13 |

- **Data as of:** 2026-10-06
- **HubSpot portal:** 45059701
- **Read-only:** nothing in HubSpot was changed.

## Scope

The list of workflows was confirmed by WLS. HubSpot's API doesn't return workflow folders, so folder 451664132163 couldn't be read directly.

| Workflow | ID | On |
|---|---|---|
| T1 SM SOA \| R+S - Execute Monthly Walk Through - BOG | 1688833555 | ON |
| R+S - Reminders: Respond within 1 day to external emails | 1689020435 | ON |
| R+S - Facility Performance Monitoring and Escalation | 1688976731 | ON |
| R+S - BOG Weekly Walkthrough + BOG Performance Status | 1682559061 | ON |
| R+S - AI Lien Process | 1688964146 | ON |
| OM \| RISK within the first 90 days | 1774165521 | off |
| Create Tasks \| Weekly KPI review to owner for first 90 days | 1838568062 | ON |
| Create Tasks \| Weekly calls first 90 days after go live | 1838565644 | ON |
| Create Tasks \| Update Customer Sentiment \|Tier 2.2, Tier 3 | 1868006311 | ON |
| Create Tasks \| Update Customer Sentiment \| Ent, Tier 1, Tier 2.1 | 1682559152 | ON |
| Create Tasks \| Storage Reach | 1697631666 | off |
| Create Tasks \| Send Monthly Marketing Report Owner | 1682548292 | ON |
| Create Tasks \| Review Tow and Unsold Auctions report, action as needed | 1838565797 | ON |
| Create Tasks \| Rate Review - Execution Tier 2.2 and Tier 3 | 1868006300 | ON |
| Create Tasks \| Rate Review - Execution ENT, Tier 1 and Tier 2.1 | 1682542430 | ON |
| Create Tasks \| Prepare Rate Review | 1682549368 | off |
| Create Tasks \| Prepare Month End Report | 1682101413 | off |
| Create Tasks \| Playbook Review/Maintenance | 1682549352 | ON |
| Create Tasks \| Playbook Review/Maintenance T1 OM | 1682545542 | off |
| Create Tasks \| Month End Call | 1682560327 | ON |
| Create Tasks \| Confirm contacts on facility are correct | 1838568063 | ON |
| Create Tasks \| BOG Oversight Ent and T1 | 1770960918 | ON |
| Create Tasks \| NPS Detractor Recovery Actions | 1770961042 | ON |
| Create Tasks \| Respond to reviews at Storage Reach | not found | - |

**Team settings:**
- **Queue:** 13519269, assumed to be "Ops Tasks", because the API doesn't return queue names
- **Start date:** 2026-10-06
- **Companies:** Live with full management (252 companies)

## Sources

- **Workflow settings (source of truth):** read from the HubSpot Automation v4 API.
- **Records used to cross-check:**
  - the tasks each workflow created, including tasks created under a workflow's old name before it was renamed
  - the 150 tasks in queue 13519269 since 2026-10-06
  - the properties of the companies in scope
  - the members of list 4291
- **Labels in the workbook:** every statement is marked VERIFIED (config), VERIFIED (records), INFERENCE or NEEDS VERIFICATION.

## What actually happens

1. **Enrollment.** All switched-on workflows are company-based, with filter-based triggers. They typically check status Live, full management, a customer tier and, for some, a go-live date range. Most also **re-check on a schedule**, weekly or on set days of the month (e.g. Rate Review ENT on the 2nd and 17th at 10:00), and they re-enroll.
2. **Exclusions.** Only the two Rate Review workflows now suppress list 4291, "Exclude from Ops tasks". Until today, 17 switched-on workflows did (F-04).
3. **Branches.** A first branch splits by customer tier, and companies whose name starts with "SOA - " get no task. A second branch splits by **OM or SM**: if the Operations Manager is known, the OM branch runs first.
4. **Tasks.**
   - **Owner:** taken from the company's Operations Manager or Site Manager property, depending on the branch.
   - **Queue:** every Create task action in the switched-on workflows uses queue 13519269.
   - **Subtasks:** none are created.
5. **Today's run.** Send Monthly Marketing Report Owner ran at 10:00 and created 150 tasks: 102 went to the SM and 48 to the OM (F-03).
6. **R+S - Reminders** creates nothing: it only branches, waits a day and loops back (F-05).

## CS Ops rules

| Rule | Result | Finding |
|---|---|---|
| Tasks go to the SM even if the facility has an OM | **Broken.** In 13 workflows the OM branch comes first; 48 of today's tasks went to the OM | F-03 |
| Only Rate Review has the segment exclusion | **Holds now.** The exclusion was removed from 15 workflows today | F-09, F-04 |
| Subtasks are not linked to the ticket | **Holds.** No subtasks are created at all | F-13 |
| Every Create task action uses the Ops Tasks queue | **Holds** for all switched-on workflows; 4 switched-off workflows have no queue | F-10 |
| Tasks turned off as duplicates are not created | **Holds.** Nothing has been created by a switched-off workflow since 2026-10-06, and no same-day duplicates | F-11, F-12 |

## What WLS should verify / decide

- **F-03:** confirm the SM rule applies to every tier. If it does, the OM-first branches in 13 workflows conflict with it.
- **F-07:**
  - There are 96 company–workflow pairs where the company qualifies but has never had a task. Check a few in HubSpot's workflow history. A company that qualified after the last scheduled run only shows up after the next one.
  - The 83 pairs for companies on list 4291 are explained by the exclusion that was in place until today.
- **F-04:** confirm the 89 companies on "Exclude from Ops tasks" should now receive these tasks.
- **F-05:** confirm whether the R+S Reminders actions were removed on purpose today.
- **F-08:** "Create Tasks \| Respond to reviews at Storage Reach" can't be found. Was it deleted or renamed? Its tasks were last created on 2026-09-30.
