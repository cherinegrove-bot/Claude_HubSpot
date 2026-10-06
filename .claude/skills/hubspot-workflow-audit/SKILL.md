---
name: hubspot-workflow-audit
description: Audits a team's HubSpot workflows (e.g. Marketing, Transitions, CS Ops) from their real configuration. Has two modes. Weekly check mode answers two questions for one team's task queue (did every company that should enroll actually enroll, and were its tasks created and assigned correctly) and returns a short problem list. Full map mode produces an Excel workbook (process overview, action map, workflow inventory, task and subtask logic, workflow connections, findings and evidence sheets). Use it whenever the user asks to audit, check, map, document, reverse-engineer or review a set of HubSpot workflows or the tasks they create, or asks for a "weekly check", "workflow audit" or "workflow workbook" for a team, even if they don't name this skill.
---

# HubSpot Workflow Audit

Check what a set of HubSpot workflows **actually does**. The workflow configuration is the source of truth. Never describe an action from its name or from what it seems intended to do: describe only what the configuration says, and mark everything else.

## Hard rules (apply in both modes)

1. **Report only. Never suggest deleting, editing, reassigning or completing any task, ticket, company or workflow.** Problems go in the report with evidence. The user decides what to do.
2. **Stay inside the agreed scope.** Only look at tasks in the team's task queue, created on or after the start date. Anything outside that is not part of the audit, so do not mention it.
3. **Never present an inference as a fact.** Use the evidence labels below.
4. **If the API returns 403, stop and tell the user.** Do not fall back to guessing from records without saying so.

## Evidence labels (use them in every sheet and every chat summary)

| Label | Meaning |
|---|---|
| **VERIFIED (config)** | Read from the workflow configuration (Automation v4 API) |
| **VERIFIED (records)** | Read from HubSpot task / ticket / company records |
| **VERIFIED (screenshot)** | Seen in a screenshot the user supplied |
| **INFERENCE** | Logically derived; not directly visible. Say why. |
| **NEEDS VERIFICATION** | Cannot be determined. Say what would settle it. |

Never invent action names, conditions, owners, task names, timings or links between workflows.

## Team settings

Each team has its own queue and rules. The machine-readable copy of this table is `teams.json` (in this skill's folder): the scripts read the queue, start date, company scope and team rules from it. **Keep the two in step** when a team's rules change.

**Queue names can't be looked up through the API** (no public queue endpoint; the task Queue property only holds numeric IDs). So the scripts work with queue **IDs**:
- If `teams.json` lists `queue_ids` for the team, those are used.
- If it doesn't, the scripts use the queue ID(s) the team's Create task actions set in their configuration (`queue_id`), and say so. Confirm with the user that this ID is the queue named in the table, then add it to `teams.json`.
- If neither exists, the "in the queue" check is skipped and tasks are matched by workflow name. The report says so as NEEDS VERIFICATION.

| Team | Queue name | Start date | Companies in scope | Team-specific rules |
|---|---|---|---|---|
| CS Ops | `Ops Tasks` | 2026-10-06 | Live, full management | Tasks go to the SM, even if the facility has an OM. Only the Rate Review workflow has the segment exclusion. Tasks that were turned off as duplicates must not appear. |
| Transitions | `Transitions` | Ask the user | Agree with the user before the first run | None yet |
| Marketing | `Marketing Services` | Ask the user | Agree with the user before the first run | None yet |

Rules for every team: subtasks created on or after the start date must **not** be associated with the ticket. Only main tasks are.

Start date: the date the queue was added to the team's workflows (see the table). Ask the user if it isn't filled in. Tasks created before it are ignored, because they were made before the queues and subtask changes existed.

## Requirements

- Environment variable `HUBSPOT_ACCESS_TOKEN`: a private-app token with these scopes. Without the sensitive scopes, ticket and deal workflows return `403 FLOW_ACCESS_DENIED` or are missing from the list.
  - `automation`
  - read (and write) scopes for tickets, deals, companies and contacts
  - read access to tasks (NEEDS VERIFICATION: confirm the exact scope name in the private app settings)
  - all `*.sensitive.read` and `*.highly_sensitive.read` scopes
- Python packages `openpyxl` and `tzdata`. Install them with `pip install -q openpyxl tzdata` if an import fails.
- The scripts are in `.claude/skills/hubspot-workflow-audit/scripts/`. They only **read** from HubSpot; they never change anything.
- Queue property on tasks: `hs_queue_membership_ids`, label "Queue" (VERIFIED: property metadata). It holds queue IDs, not names.

## Pick the mode

- **Weekly check**: the default when the user says "run the audit", "weekly check" or names a team. Short, focused, no workbook.
- **Full map**: when the user asks for the workbook, or after the team's workflows have changed and the map is out of date.

---

## Weekly check mode

### 1. Confirm the run

Tell the user, in one short message, the team, queue name, start date and company rules you will use. Wait for a yes.

### 2. Fetch

```bash
SK=.claude/skills/hubspot-workflow-audit/scripts
WK=<scratchpad>/<team>-weekly      # contains customer data: keep it in the scratchpad, never commit it
python3 $SK/fetch.py --work $WK --name-filter "<confirmed regex>" --team "<Team>"     # --queue <ID> and --since <YYYY-MM-DD> override teams.json
```

### 3. Run the checks

```bash
python3 $SK/weekly.py --work $WK --team "<Team>"
```

Both `weekly.py` and `build.py` refuse to run if the fetch didn't finish (no `COMPLETE` marker in `$WK`), so a network error can never turn into a "no problems" report.

It answers two questions per workflow:

1. **Did the right companies go in?** Lists every company that meets the team's company scope **and** the workflow's own enrollment filter, **and** whose branch path (worked out from its current properties) ends in a task, but has no task from that workflow at any date. Companies whose filters can't be evaluated (association filters, unreadable lists, unsupported operators) are counted in a NEEDS VERIFICATION note, never reported as problems.
2. **Did the tasks come out right?** For each enrolled company: is every task there, in the queue, assigned to the right person? Plus the team-specific rules from the table above.

### 4. Report

Reply in chat with a short table, one row per problem:

| Company ID | Company name | Workflow | Problem | Evidence label |
|---|---|---|---|---|

Then one line: "X companies checked, Y problems found." If there are no problems, say so in one line. No workbook, no README, no commit.

---

## Full map mode

### 1. Agree the scope with the user. Do this first; do not guess.

Ask which team the audit is for. Then list the candidate workflows:

```bash
python3 $SK/fetch.py --work $WK --list | grep -i "<team keyword>"
```

Show the user the matching workflows as a table: ID, object, ON/off, name. Ask them to confirm the exact list.

- **Add or remove only what they say.** If you spot related workflows (for example ones that move a stage, set an owner, or are triggered by these workflows' tasks), *suggest* them and let the user decide.
- **Their decision is final.**

### 2. Fetch

```bash
python3 $SK/fetch.py --work $WK --ids <id> <id> ... --team "<Team>"     # --queue <ID> and --since <YYYY-MM-DD> override teams.json
```

The script saves the following to `$WK`:
- the configuration of each workflow
- the tasks each workflow created, in the queue and on or after the start date, and their associations
- the tickets and companies involved, with their stage-entry dates
- tasks whose exact title a workflow watches
- reference data: owners, pipelines, association labels, property labels

Check the output for `DENIED` lines. If any workflow is denied:
1. Tell the user which ones, and the exact error.
2. Recheck the token's scopes. Use `POST /oauth/v2/private-apps/get/access-token-info` with `{"tokenKey": "<token>"}`, and never print the token.
3. Note that scope changes can take a while to apply.
4. Offer screenshots as a fallback. Ask for the canvas, the trigger, the trigger's Settings tab (re-enroll / unenroll), every action's edit panel, and the workflow URL.

Do not build findings for workflows you could not read.

### 3. Build the first pass

```bash
python3 $SK/build.py --work $WK --team "<Team>" --out audits/<team>-workflow-audit/WLS_<Team>_Workflow_Audit.xlsx
```

It prints counts and the **auto-finding keys** (A03, A12-<id>, ...). The workbook contains these sheets:

| Sheet | Contents |
|---|---|
| Read Me | Sources, evidence labels, scope, queue, start date, live count of findings by classification |
| Process Overview | Order of events: trigger, then each action / branch, then hand-off to the next workflow |
| Detailed Action Map | One row per trigger, action, branch, go-to and end, with what it does, the exact configuration, the branch path, and the records check |
| Workflow Inventory | One row per workflow: trigger, re-enrollment, suppression, number and type of actions, related workflows |
| Task & Subtask Logic | Each Create task action from the configuration, plus every subtask observed in the records (subtasks are **not** in the API) |
| Workflow Connections | Where one workflow writes a property or creates a task that another workflow's trigger or condition reads |
| Audit Findings | Automatic checks plus your reviewed findings |
| Evidence sheets | Enrollments (timing per run); Missed Enrollments (companies and tickets that should have enrolled but have no tasks); Stage Moves (task-completion to stage-change timing) |

The automatic checks are:
- denied / OFF workflows
- re-enrollment and suppression
- subtasks not in the API
- unowned subtasks
- open subtasks under completed parents
- fixed-user owners, including deactivated users
- association label copies that rarely match
- association differences between actions
- **task-title triggers that no in-scope workflow creates** (broken hand-offs)
- trigger stages nothing in scope moves into
- actions never executed
- missed enrollments (companies and tickets)
- dependencies stated only in task notes
- partial enrollments
- tasks with no associations
- due dates that differ from the configured rule
- **team rules from the Team settings table** (subtask ticket links, SM vs OM owner, segment exclusion only on Rate Review, turned-off tasks still appearing)

Overdue tasks and titles changed since creation are about how the team works, not whether the workflow works. Leave them out unless the user asks.

### 4. Review, don't just ship

Open the workbook (e.g. with openpyxl) and read the Audit Findings, the Process Overview and the Detailed Action Map. Then:

- **Check each auto finding against the configuration.** Suppress any that are wrong or noise by adding their keys to `suppress`.
- **Write team-specific findings** the generic checks can't make. For example: the owner set at ticket creation and how it's changed later; a branch with a silent default; a check that runs after the stage it should gate; a task name that implies automation but is manual; individual records that went wrong.
- **Each finding needs:** classification (`Confirmed`, `Potential Issue`, `Needs Verification` or `No Issue Found`; no severity scores), workflow, action / step, finding, evidence (config field / action ID / record IDs), why it matters, and recommended verification.

Save the result as `audits/<team>-workflow-audit/findings.json`:

```json
{"suppress": ["A14"],
 "findings": [{"classification": "Potential Issue", "workflow": "...", "action": "Step 3",
               "finding": "...", "evidence": "Config action 31 ...; ticket 123", "why": "...", "verify": "..."}],
 "process_notes": ["Optional lines for the Read Me sheet"]}
```

Rebuild with `--findings audits/<team>-workflow-audit/findings.json`.

If the user supplies screenshots, add what they show as findings or process notes labelled **VERIFIED (screenshot)**.

### 5. Deliver

1. **Write `audits/<team>-workflow-audit/README.md`** in plain English. It should include:
   - the scope table (name, ID, object), queue and start date
   - the sources
   - **What actually happens**: record creation, enrollment, actions, branches, tasks/subtasks, hand-offs, completion, in numbered steps
   - **What WLS should verify / decide**: specific questions, each referencing a finding number
2. **Commit** the workbook, `findings.json` and the README. Never commit `$WK`. Push to the session's branch, and **send the workbook to the user** (SendUserFile).
3. **Summarise in chat:**
   - what's in the workbook (sheet names and row counts)
   - the 5 to 7 most important findings, in plain language
   - what still needs verification and exactly what to send (e.g. "one subtask's settings screenshot")

Keep the three team audits in separate folders: `audits/marketing-workflow-audit/`, `audits/transitions-workflow-audit/`, `audits/cs-ops-workflow-audit/`.

## Things that will trip you up

- **Subtasks are not in the API.** Subtask titles, owners and due dates come only from records, or from screenshots. Say so.
- **Queue first, workflow name second.** Tasks are found by queue. The workflow name HubSpot stamps on each task is still used to say which workflow made it.
- **Renamed workflows.** Tasks made before a rename carry the old workflow name. `fetch.py` finds candidate old names automatically: it looks up tasks with the same titles whose workflow name no longer exists, and counts them as the same workflow (saved in `aliases.json`). The weekly report lists these as INFERENCE; confirm them with the user. Example: "Create Tasks | Rate Review - Execution" is the old name of both Rate Review workflows.
- **Old tasks are out of scope.** Anything created before the start date has no queue and may still have old subtask links. Do not report it.
- **"Ticket status"** is HubSpot's label for `hs_pipeline_stage`. `hs_v2_date_entered_<stage>` holds the **latest** entry into that stage, so earlier entries are overwritten.
- **Filter-based triggers** ("Records meet custom conditions") are evaluated a few seconds after a change. A record that passes through a stage in under about 10 s may never enroll.
- **`actionExecutionIndex`** on a task counts every executed action, including branches. A gap means a non-task action ran there.
- **Several actions with the same task title** (e.g. one per branch) can't be told apart in the records when the owner is also the same. The build flags these as shared.
- **The time zone** is the account's (account-info API). Due dates are business days when the action's `daysOfWeek` is Mon to Fri.
