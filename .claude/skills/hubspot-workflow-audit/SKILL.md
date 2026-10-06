---
name: hubspot-workflow-audit
description: Audits a team's HubSpot workflows (e.g. Marketing, Transitions, C-Ops) from their real configuration and produces an Excel workbook. The workbook covers the process overview, a detailed action map, the workflow inventory, task and subtask logic, workflow connections, audit findings and evidence sheets. It cross-checks every setting against the tasks and tickets the workflows actually created. Use it whenever the user asks to audit, map, document, reverse-engineer or review a set of HubSpot workflows, or asks for a "workflow audit" / "workflow workbook" for a team, even if they don't name this skill.
---

# HubSpot Workflow Audit

Reverse-engineer what a set of HubSpot workflows **actually does**, then audit it. The workflow configuration is the source of truth. Never describe an action from its name or from what it seems intended to do: describe only what the configuration says, and mark everything else.

## Evidence labels (use them in every sheet and every chat summary)

| Label | Meaning |
|---|---|
| **VERIFIED (config)** | Read from the workflow configuration (Automation v4 API) |
| **VERIFIED (records)** | Read from HubSpot task / ticket / deal records |
| **VERIFIED (screenshot)** | Seen in a screenshot the user supplied |
| **INFERENCE** | Logically derived; not directly visible. Say why. |
| **NEEDS VERIFICATION** | Cannot be determined. Say what would settle it. |

Never present an inference as a fact. Never invent action names, conditions, owners, task names, timings or links between workflows.

## Requirements

- Environment variable `HUBSPOT_ACCESS_TOKEN`: a private-app token with the following scopes. Without the sensitive scopes, ticket and deal workflows return `403 FLOW_ACCESS_DENIED` or are missing from the list.
  - `automation`
  - read (and write) scopes for tickets, deals, companies and contacts
  - all `*.sensitive.read` and `*.highly_sensitive.read` scopes
- Python packages `openpyxl` and `tzdata`. Install them with `pip install -q openpyxl tzdata` if an import fails.
- The scripts are in `.claude/skills/hubspot-workflow-audit/scripts/`. They only **read** from HubSpot; they never change anything.

## Procedure

### 1. Agree the scope with the user. Do this first; do not guess.

Ask which team the audit is for (e.g. Marketing / Transitions / C-Ops). Then list the candidate workflows:

```bash
SK=.claude/skills/hubspot-workflow-audit/scripts
WK=<scratchpad>/<team>-audit          # raw data contains customer data: keep it in the scratchpad, never commit it
python3 $SK/fetch.py --work $WK --list | grep -i "<team keyword>"
```

Show the user the matching workflows as a table: ID, object, ON/off, name. Ask them to confirm the exact list.

- **Add or remove only what they say.** If you spot related workflows (for example ones that move a stage, set an owner, or are triggered by these workflows' tasks), *suggest* them and let the user decide.
- **Their decision is final.** In the Transitions audit the user first excluded the stage-move workflows, then included them.

### 2. Fetch

```bash
python3 $SK/fetch.py --work $WK --ids <id> <id> ...      # or --name-filter "<regex>" once the user has confirmed what it matches
```

The script saves the following to `$WK`:
- the configuration of each workflow
- the tasks each workflow created (matched by the workflow name HubSpot stamps on each task) and their associations
- the tickets involved, with their stage-entry dates
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
| Read Me | Sources, evidence labels, scope, live count of findings by classification |
| Process Overview | Order of events: trigger → each action / branch → hand-off to the next workflow |
| Detailed Action Map | One row per trigger, action, branch, go-to and end. Each row has what it does, the exact configuration, the branch path, and the records check (counts, owner and due-date match) |
| Workflow Inventory | One row per workflow: trigger, re-enrollment, suppression, number and type of actions, related workflows |
| Task & Subtask Logic | Each Create task action from the configuration, plus every subtask observed in the records (subtasks are **not** in the API) |
| Workflow Connections | Where one workflow writes a property or creates a task that another workflow's trigger or condition reads |
| Audit Findings | Automatic checks plus your reviewed findings |
| Evidence sheets | Enrollments (timing per run); Missed Enrollments (tickets that entered a trigger stage with no tasks); Stage Moves (task-completion → stage-change timing) |

The automatic checks are:
- denied / OFF workflows
- re-enrollment and suppression
- subtasks not in the API
- unowned subtasks
- open subtasks under completed parents
- overdue tasks
- fixed-user owners, including deactivated users
- association label copies that rarely match
- association differences between actions
- **task-title triggers that no in-scope workflow creates** (broken hand-offs)
- trigger stages nothing in scope moves into
- actions never executed
- titles changed since creation
- missed enrollments
- dependencies stated only in task notes
- partial enrollments
- tasks with no associations
- due dates that differ from the configured rule

### 4. Review, don't just ship

Open the workbook (e.g. with openpyxl) and read the Audit Findings, the Process Overview and the Detailed Action Map. Then:

- **Check each auto finding against the configuration.** Suppress any that are wrong or noise by adding their keys to `suppress`.
- **Write team-specific findings** the generic checks can't make. Examples from the Transitions audit:
  - the owner set at ticket creation and how it's changed later
  - a branch with a silent default
  - a check that runs after the stage it should gate
  - a task name that implies automation but is manual
  - individual tickets that went wrong
- **Each finding needs:** classification (`Confirmed`, `Potential Issue`, `Needs Verification` or `No Issue Found`; no severity scores), workflow, action / step, finding, evidence (config field / action ID / record IDs), why it matters, and recommended verification.

Save the result as `audits/<team>-workflow-audit/findings.json`:

```json
{"suppress": ["A14"],
 "findings": [{"classification": "Potential Issue", "workflow": "…", "action": "Step 3",
               "finding": "…", "evidence": "Config action 31 …; ticket 123", "why": "…", "verify": "…"}],
 "process_notes": ["Optional lines for the Read Me sheet"]}
```

Rebuild with `--findings audits/<team>-workflow-audit/findings.json`.

If the user supplies screenshots, add what they show as findings or process notes labelled **VERIFIED (screenshot)**.

### 5. Deliver

1. **Write `audits/<team>-workflow-audit/README.md`** in plain English. It should include:
   - the scope table (name, ID, object)
   - the sources
   - **What actually happens**: ticket/record creation → enrollment → actions → branches → tasks/subtasks → hand-offs → completion, in numbered steps
   - **What WLS should verify / decide**: specific questions, each referencing a finding number
2. **Commit** the workbook, `findings.json` and the README. Never commit `$WK`. Push to the session's branch, and **send the workbook to the user** (SendUserFile).
3. **Summarise in chat:**
   - what's in the workbook (sheet names and row counts)
   - the 5–7 most important findings, in plain language
   - what still needs verification and exactly what to send (e.g. "one subtask's settings screenshot")

Keep the three team audits in separate folders, e.g. `audits/marketing-workflow-audit/`, `audits/transitions-workflow-audit/`, `audits/c-ops-workflow-audit/`.

## Things that will trip you up

- **Subtasks are not in the API.** Subtask titles, owners and due dates come only from records, or from screenshots. Say so.
- **Records are matched by workflow name.** Tasks created before a workflow was renamed carry the old name and are missed. If a workflow's records look thin compared with its age, ask whether it was renamed.
- **"Ticket status"** is HubSpot's label for `hs_pipeline_stage`. `hs_v2_date_entered_<stage>` holds the **latest** entry into that stage, so earlier entries are overwritten.
- **Filter-based triggers** ("Records meet custom conditions") are evaluated a few seconds after a change. A record that passes through a stage in under about 10 s may never enroll.
- **`actionExecutionIndex`** on a task counts every executed action, including branches. A gap means a non-task action ran there.
- **Several actions with the same task title** (e.g. one per branch) can't be told apart in the records when the owner is also the same. The build flags these as shared.
- **The time zone** is the account's (account-info API). Due dates are business days when the action's `daysOfWeek` is Mon–Fri.
- **If the API starts returning 403 again,** stop and tell the user. Don't fall back to inferring logic from records without saying so, and label everything that comes from records alone.
