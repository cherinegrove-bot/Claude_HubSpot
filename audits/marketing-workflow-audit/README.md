# WLS Marketing Workflow Audit (full map)

- **Workbook:** `WLS_Marketing_Workflow_Audit.xlsx`. It has 5 sheets with the same columns and styling as the Transitions audit:

  | Sheet | Rows |
  |---|---|
  | Process Overview | 60 |
  | Detailed Action Map | 89 |
  | Task & Subtask Logic | 24 |
  | Workflow Inventory | 3 |
  | Audit Findings | 16 |

- **Summary page:** `marketing-audit-summary.html`, a one-page overview that opens in any browser. It has the headline numbers, top findings, all findings and workflows.
- **Data as of:** 2026-10-06. All three workflows were last edited that day; the latest edit was at 15:18 UTC.
- **HubSpot portal:** 45059701
- **Read-only:** nothing in HubSpot was changed.

## Scope

The list of workflows was confirmed by WLS.

| Workflow | ID | Object | On |
|---|---|---|---|
| Standalone Marketing \| Monthly Performance Reviews \| Marketing Services (UPDATED) | 1892197644 | Company | ON |
| Improving Monthly Performance Reviews \| Marketing Services (UPDATED) | 1892196753 | Company | ON |
| At Risk Monthly Performance Reviews \| Marketing Services (UPDATED) | 1892165928 | Company | ON |

**Team settings:**
- **Queue:** Marketing Services. Every Create task action uses queue ID 13519272. That this ID is the Marketing Services queue still needs confirming (F-13).
- **Start date:** 2026-10-06. Only tasks created on or after this date are checked.
- **Companies:** no team-wide company scope. Each workflow's own trigger decides who enrolls.

## Sources

- **Workflow settings (source of truth):** read from the HubSpot Automation v4 API.
- **Records used to cross-check:**
  - tasks in queue 13519272 since 2026-10-06. There are none yet: the workflows next run on 5 November.
  - the current properties of 502 companies: Status, PPC Enrolled, Customer Tier, Trend to Goal, Standalone Services, SpareFoot, Marketing Portfolio Manager
  - the tasks each workflow has created at any date, used only to spot companies that qualify but never got a task
- **Labels in the workbook:** every statement is marked VERIFIED (config), VERIFIED (records), INFERENCE or NEEDS VERIFICATION.
- **Purpose / Observed Function** in the Workflow Inventory is HubSpot's own description of the workflow. It hasn't been checked against the configuration (see F-10).

## What actually happens

1. **Enrollment.** All three workflows are company-based, with filter-based triggers. Every one requires Status = Live and PPC Enrolled = Yes. In addition:
   - **Standalone:** Standalone Services includes Marketing.
   - **Improving:** Trend to Goal = Improving and Customer Tier is Enterprise, Tier 1 or Tier 2 - L1.
   - **At Risk:** Trend to Goal = At Risk and Customer Tier is Enterprise, Tier 1, Tier 2 - L1, Tier 2 - L2 or Tier 3.

   None of them has a suppression list. Matching companies today: Standalone 7, Improving 18, At Risk 69. One company matches both Standalone and At Risk (F-08).
2. **Schedule and re-enrollment.** Each workflow re-checks companies on the **5th of every month at 00:00** and has re-enrollment on (F-01).
3. **Branch 1: SpareFoot (Y/N)** (action 2), true or false. There is no default path. Both paths lead to identical steps (F-03).
4. **Branch 2: Marketing Portfolio Manager.** The paths are Brock Hegr, Sarah Schlosberg, Mohammad Abudahab and "Not Assigned". Any other value goes to the "Not Assigned" path, except in Standalone's SpareFoot = false branch, which has no default (F-07).
5. **Task.** Each path creates one task, "Marketing Performance Review" (To-do, no priority):
   - **Owner:** a fixed user, Brock, Sarah or Mohammad (F-02). The "Not Assigned" path leaves it unowned (F-04).
   - **Queue:** 13519272 on all 24 Create task actions (F-14).
   - **Due:** 45 business days after creation, at 08:00 (F-06).
   - **Links:** to the company, and to the company's "Marketing" ticket (a copy of the company-to-ticket "Marketing" association).
   - **Body:** says the task has subtasks for Berat (Google Business Profile, SpareFoot, website content), and that Mohammad handles Google Ads on a separate task.
6. **Subtasks.** These aren't in the workflow API, so their titles, owners and ticket links can't be read from the configuration. No task has been created since the start date, so the records can't show them yet either (F-12).
7. **End.** Every path ends with a **45-day Delay**, then the workflow ends. A company is still in the workflow at the next monthly run, so it likely can't re-enroll until the month after (F-05, INFERENCE).
8. **Hand-offs.** None of the three writes a property or creates a task that another in-scope workflow listens for.

## Marketing rules

| Rule | Result | Finding |
|---|---|---|
| Every Create task action uses the Marketing Services queue | **Holds** for all 24 actions (queue 13519272). That this ID is Marketing Services still needs confirming | F-14, F-13 |
| Subtasks are not linked to the ticket | **Can't be checked yet.** Subtasks aren't in the API, and there are no tasks in the queue since 2026-10-06. The main task is linked to the ticket by design | F-12 |
| No tasks from switched-off workflows, no same-day duplicates | **Holds** (no tasks since the start date) | F-15, F-16 |

## What WLS should verify / decide

- **F-05:** is the 45-day Delay at the end of every path meant to space reviews out to every other month? If reviews should be monthly, this conflicts with the 5th-of-the-month schedule. Check one October company's workflow history after the 5 November run.
- **F-06:** is "45 business days" the intended due date for a monthly review?
- **F-04:** who picks up the unowned review tasks for companies whose Portfolio Manager is "Not Assigned" or empty (12 At Risk companies today)?
- **F-08:** should a Standalone Marketing company (e.g. Climate Smart Self Storage, 31201467651) also get the At Risk or Improving review?
- **F-09:** check the workflow history of A Affordable Storage Waxahachie (48889029662, Improving) and Climate Smart Self Storage (31201467651, At Risk). Both qualify today but have no task.
- **F-03 / F-07:** what is the SpareFoot branch meant to change? Should Standalone action 16 default to the "Not Assigned" task, like action 15?
- **F-11:** should Tier 2 - L2 and Tier 3 companies with Trend to Goal = Improving get a review? There are 15 today.
- **F-12:** send a screenshot of one Create task action's subtask settings, or re-run this audit after 5 November, to check that subtasks aren't linked to the ticket.
- **F-13:** confirm that queue ID 13519272 is "Marketing Services". It will then be recorded in `teams.json`.
- **F-10:** Standalone's HubSpot description says "for at-risk customers". It was copied from At Risk.
