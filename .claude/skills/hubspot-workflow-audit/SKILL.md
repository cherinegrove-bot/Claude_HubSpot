---
name: hubspot-workflow-audit
description: Audits a team's HubSpot workflows (e.g. CS Ops, Transitions, Marketing Services) from their real configuration. Has two modes. Weekly audit mode answers three questions for one team every Friday - were the tasks created, are they linked to the right company, and did anyone change the workflows (compared with the team's master rules file) - and produces a chat summary plus an interactive HTML page. Full map mode produces an Excel workbook (process overview, action map, workflow inventory, task and subtask logic, findings), an HTML summary page and a plain-English README. Use it whenever the user asks to audit, check, map, document, reverse-engineer or review a set of HubSpot workflows or the tasks they create, or asks for a "weekly audit", "weekly check", "workflow audit" or "workflow workbook" for a team, even if they don't name this skill.
---

# HubSpot Workflow Audit

Check what a set of HubSpot workflows **actually does**. The workflow configuration is the source of truth. Never describe an action from its name or from what it seems intended to do: describe only what the configuration says, and mark everything else.

This file is **general**. Everything specific to one team (queue, start date, business rules, task types, decisions, known issues, how its workflows should work) lives in that team's folder:

| File | What it holds |
|---|---|
| `audits/<team>-workflow-audit/team-rules.md` | The team's queue, start date, rules, task types, decisions, "Waiting on" items and known issues, in plain words, plus a `json` settings block at the end that the scripts read |
| `audits/<team>-workflow-audit/<Team>_Master_Rules.xlsx` | How every workflow of the team should work: one row per workflow, same columns for every team. The source of truth for "Did anyone change the workflows?" |

`<team>` is the team's short name, e.g. `cs-ops`. Every script takes it as `--team <team>`; nothing team-specific is written into the scripts.

## Hard rules (apply in both modes)

1. **Read only.** Never change anything in HubSpot.
2. **Report only. Never suggest deleting, editing, reassigning or completing any task, ticket, company or workflow.** Problems go in the report with evidence. People decide what to do.
3. **Never present an inference as a fact.** Label every finding (below).
4. **If you're unsure about a rule, ask the user. Don't guess.** Then write the answer into the team's `team-rules.md` (Decisions section and the settings block) so the next run doesn't have to ask.
5. **Stay inside the team's scope**: its queue and workflows, from its start date on. Never audit backwards.
6. **Raw HubSpot data stays in the scratchpad.** Never commit a work directory (`$WK`).
7. **Never rebuild the master rules file from the live workflows during an audit.** That would hide the very changes the audit is meant to catch. A row is updated only when the user confirms a change was planned.
8. **If the API returns 403, stop and tell the user.** Do not fall back to guessing from records without saying so.

## Evidence labels

| Label | Meaning |
|---|---|
| **VERIFIED (config)** | Read from the workflow configuration (Automation v4 API) |
| **VERIFIED (records)** | Read from HubSpot task / ticket / company records |
| **VERIFIED (screenshot)** | Seen in a screenshot the user supplied |
| **INFERENCE** | Logically derived; not directly visible. Say why. |
| **NEEDS VERIFICATION** | Cannot be determined. Say what would settle it. |

Never invent action names, conditions, owners, task names, timings or links between workflows.

## Setup (every session)

1. **Get the latest skill, scripts and team files.** They live in the repository on the shared branch, not in this file alone:
   ```bash
   git pull origin <the branch the user names>      # e.g. claude/kind-mayer-fwxvzk
   ls .claude/skills/hubspot-workflow-audit/scripts/   # fetch.py rules.py describe.py master.py weekly.py weekly_html.py build.py summary_html.py
   ls audits/<team>-workflow-audit/                    # team-rules.md and <Team>_Master_Rules.xlsx
   ```
   If the scripts are missing, stop and ask the user for the branch. If the team's two files are missing, the team isn't set up yet: see "Set up a new team".
2. **Requirements:**
   - Environment variable `HUBSPOT_ACCESS_TOKEN`: a private-app token with `automation`, read scopes for tickets, deals, companies, contacts and tasks, lists read, and all `*.sensitive.read` / `*.highly_sensitive.read` scopes. Without the sensitive scopes some workflows return `403 FLOW_ACCESS_DENIED` or are missing from the list.
   - Python packages `openpyxl` and `tzdata` (`pip install -q openpyxl tzdata` if an import fails). For screenshots of the HTML page: `playwright`, with Chromium at `/opt/pw-browsers`.
   - The scripts only **read** from HubSpot.

## Pick the mode

- **Weekly audit**: the default when the user says "run the audit", "weekly audit", "weekly check" or names a team. Runs every Friday.
- **Full map**: when the user asks for the workbook, or wants the whole set of workflows documented.

---

## Weekly audit mode

Everything it reports answers one of **three questions**:

1. **Were the tasks created?** For every facility (company) that should have got a task this week, did it get it? If not, why not?
2. **Are they linked to the right company?** Is every main task associated with the right company? Are subtasks kept off tickets (if the team's rules say so)?
3. **Did anyone change the workflows?** Is every workflow still the same as the master rules file? If not, what changed?

**Window:** the 7 days ending on the team's window end day (`window.ends_on`, e.g. Thursday); the report is for the next day (e.g. Friday). The window never starts before the team's start date. On a day other than the report day, the default is the window that contains today. `--from` / `--to` override it.

### 1. Confirm the run

Read the team's `team-rules.md`. Tell the user, in one short message:
- the team
- the window
- the queue
- the start date
- the number of workflows in the master rules file

Wait for a yes.

### 2. Fetch

```bash
SK=.claude/skills/hubspot-workflow-audit/scripts
WK=<scratchpad>/<team>-weekly-<date>      # raw HubSpot data: scratchpad only, never commit
python3 $SK/fetch.py --work $WK --weekly --team <team>       # [--from YYYY-MM-DD] [--to YYYY-MM-DD]
```

It saves to `$WK`:
- **Live settings** of every workflow in the master rules file.
- **Tasks created in the window:**
  - main tasks found through the team queue
  - subtasks found through their main task (subtasks may not carry the queue)
  - any task the team's workflows made **outside** the queue (found by workflow name)
- **Task associations** to companies and tickets.
- **Companies:** every live company, every company changed during the window, and every company a task is linked to. Each comes with **property history** for the properties the triggers, branches and team scope use.
- **List memberships** used by the workflows.

It ends by writing a `COMPLETE` marker. Check the output for `NOT RETURNED` lines.

### 3. Run the checks

```bash
python3 $SK/weekly.py --team <team> --work $WK        # writes $WK/results.json, prints the chat summary
python3 $SK/weekly_html.py --work $WK                 # writes audits/<team>-workflow-audit/weekly/<team>-weekly-audit-<report day>.html
```

`weekly.py` refuses to run if the fetch didn't finish, so a network error can never turn into a "no problems" report.

How each question is answered:

**Question 1: Were the tasks created?**
- **Grouping.** Tasks are grouped by **task type**, from the settings block. One task type made by several workflows, for example split by tier, counts as one type. A task's type comes from its workflow plus a title pattern.
- **Who should have it.** For each scheduled run of each workflow in the window, every company is checked against:
  - the team's company scope
  - the workflow's trigger, suppression and branches, **from the master rules file**
  - its property values **at the time of the run**, from property history

  Workflows with no schedule count as "should have" when a trigger property changed in the window and the company now qualifies. All of this is labelled INFERENCE: it is worked out, not seen.
- **What gets reported for each type:**
  - **Should have** and **did get**.
  - **Missing**, each with one reason, labelled:
    - a team-defined branch reason from `branch_reasons`
    - workflow off
    - went live this week
    - outside the team scope at the run (says which scope filter it failed)
    - unknown
  - **Shouldn't have**: a task for a company that didn't qualify when the task was created.
  - **Not due**: in-scope companies the workflow settings leave out, counted by reason.
- **Also checked:**
  - duplicates of a type for the same company on the same day
  - tasks from workflows the team expects to be off
  - tasks in the queue from workflows not in the master file
  - tasks from team workflows that aren't in the queue
  - tasks of a type for companies outside the scope, if a "Waiting on" item covers it
- **New facilities.** Companies whose status changed to the live value in the window. For each: the date it went live versus the go-live date (flagged when more than `max_days_apart` apart), and for each task type whether it got it, is missing it, isn't due yet (with the next run) or isn't due at all.

**Question 2: Are they linked to the right company?**
For every main task created in the window:
- **No company:** VERIFIED (records).
- **More than one company:** VERIFIED (records).
- **A company that doesn't qualify for that task type:** INFERENCE.
- **A ticket link,** only if the team's settings require one.

For every subtask: a ticket link is flagged if the team forbids it (`links.subtask_ticket_forbidden`).

**Question 3: Did anyone change the workflows?**
- **What's compared:** each live workflow against its row in the master rules file, using the master file's stored settings:
  - name, on/off
  - trigger, schedule, re-enrollment, suppression
  - branches, task actions (title, type, owner, due date, queue, associations, description fingerprint), other actions
  - queue, revision
- **How it's shown:** both sides are described the same way, so each difference reads "was → now". A revision change with no difference in the compared settings is reported as such.
- **Team exclusion rule:** if the team has one (`exclusion`), a workflow that gains or loses that list exclusion is flagged.
- A change isn't automatically wrong. The user decides whether it was planned.

### 4. Review before reporting

Open `$WK/results.json` and look over the top problems.
- **Spot-check two or three** "missing (unknown)" or "shouldn't have" cases against the facility's record or the workflow history in HubSpot.
- **If a pattern is really a known issue or a "Waiting on" item,** don't report it as new. Add a `branch_reasons` entry or a note to `team-rules.md` **only after the user agrees**.
- **Facilities whose Status changed to live after a run** but before the fetch count as "went live this week", not as missing.

### 5. Deliver

1. **Chat summary.** Short, in plain language:
   - the window
   - the number of facilities, tasks and workflows checked
   - one line per question ("all good" or how many problems)
   - the **5 most important problems**
   - **Waiting on \<decision owner\>**
   - known issues, mentioned once
2. **HTML page**, one self-contained file per report day, in `audits/<team>-workflow-audit/weekly/`.
   - **Tabs:** Summary, Tasks created, Company links, Workflow changes, Waiting on \<decision owner\>
   - **Tasks created** has a task-type dropdown showing should have, did get, missing (with reason) and shouldn't have. New facilities are on the same tab.
   - **Facility search** in the header shows every task a facility got this week, with type, due date, company link and any problems, plus the types it is missing.
   - **Colours:** from the team's `team-rules.md` (`page_colours`: `navy` for the title bar and headings, `grey` for table headers and labels, `red` for problems only, `white` for cards and tables, `background` for the page). Red marks problems only, never "all good" items.
   - **Content:** company names and record IDs only. No customer contact details.
3. **Send the HTML page to the user** with SendUserFile.
4. **Commit and push** the page only when the user wants it kept. Never commit `$WK`. A test run is not sent anywhere.
5. **Planned changes.** If the user confirms that a workflow change was planned, update the master rules file:
   ```bash
   python3 $SK/master.py update --team <team> --work $WK --ids <workflow id> --reason "<what was confirmed, by whom, when>"
   ```
   That replaces only those rows and logs the change in the Read Me sheet. `python3 $SK/master.py diff --team <team> --work $WK` shows differences without writing anything.

---

## Set up a new team

A new team only needs its two files. Do this with the user, one checkpoint at a time, and don't guess rules.

1. **Agree the workflows.**
   - `python3 $SK/fetch.py --work $WK --list` lists every workflow (ID, object, on/off, name).
   - Show the candidates and let the user confirm the exact list.
   - The API has no folder or queue-name endpoint, so the user confirms the queue **ID** too.
2. **Write `audits/<team>-workflow-audit/team-rules.md`.** Use the CS Ops file as the pattern for structure only; its rules are its own. In plain words, cover:
   - **Basics:** queue (name and ID), start date, window.
   - **Rules:** the team's numbered business rules.
   - **Task types:** name, the workflows that make it, when it's created, who should get it.
   - **Decisions so far.**
   - **Waiting on \<name\>.**
   - **Known issues.**

   Then the ```` ```json ```` settings block:

   | Key | Meaning |
   |---|---|
   | `team`, `team_name`, `decision_owner` | Short name (folder), display name, who decides open questions (names the "Waiting on" tab) |
   | `page_colours` | Colours of the weekly HTML page: `navy`, `grey`, `red` (problems only), `white`, `background` |
| `master_rules_file` | File name of the master rules workbook in the team folder |
   | `queue_name`, `queue_ids`, `start_date`, `window` | `window` = `{"ends_on": "Thursday", "days": 7}` |
   | `company_scope` | Filters on company properties using **internal** values, e.g. `{"property": "live", "operator": "IS_ANY_OF", "values": ["Yes"]}`; `{}`/omitted = all companies |
   | `went_live` | `status_property`, `live_value`, `go_live_date_property`, `max_days_apart` |
   | `links` | `main_task_company`, `main_task_ticket`, `subtask_ticket_forbidden` |
   | `exclusion` | Optional: `list_id` and `only_in_task_types` (the only task types whose workflows may exclude that list) |
   | `task_types` | `[{"name", "workflows": [ids], "title": regex on the lower-cased task title}]` |
   | `no_task_workflows`, `expected_off`, `not_readable` | Workflows that create nothing / are off on purpose / can't be read (with their known issue ID) |
   | `branch_reasons` | `[{"branch": regex on the branch path, e.g. "\"Branch A\" > \"Branch B\"", "kind": "missing" or "excluded", "reason", "label", "waiting_on"}]`: what to say when a company's path through the branches ends with no task |
   | `waiting_on` | `[{"id", "title", "detail", optional "duplicate_task_type", "task_types", "queue_move" (queue ID) or "company_ids"}]`. Problems for those companies, or tasks moved to that queue, are listed under the item instead of as new problems |
   | `known_issues` | `[{"id", "text", optional "label"}]`. Each is reported once, with this week's count of the tasks it covers |
   | `queue_names` | `{"<queue ID>": {"name", "label", "confirmed"}}`: queue names the user confirmed (the API can't return them) |
   | `known_queue_moves` | `[{"queue", "workflow", "known_issue", "waiting_on"}]`: a known workflow that moves the team's tasks to another queue; those tasks are reported as one known-issue line, not one problem per task |
3. **Build the master rules file once,** from a saved settings snapshot the user agrees is correct:
   ```bash
   python3 $SK/fetch.py --work $WK --ids <id> <id> ...           # snapshot of the agreed workflows
   python3 $SK/master.py build --team <team> --work $WK --purposes <purposes.json> --source-note "<where it came from>"
   ```
   - `purposes.json` maps workflow ID to a one-line purpose written from the settings. HubSpot's own descriptions are often wrong.
   - `master.py build` refuses to overwrite an existing file.
4. **Check the file against itself.** `master.py diff --team <team> --work $WK` must show no differences. Then show the user both files and wait for confirmation.

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
python3 $SK/fetch.py --work $WK --ids <id> <id> ... --team <team>     # --queue <ID> and --since <YYYY-MM-DD> override team-rules.md
```

`--team` reads the queue, start date and company scope from the team's `team-rules.md`. For a team without one, pass `--queue` and `--since`.

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
python3 $SK/build.py --work $WK --team <team> --out audits/<team>-workflow-audit/WLS_<Team>_Workflow_Audit.xlsx
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

`--template` keeps only the 5 core sheets (Process Overview, Detailed Action Map, Task & Subtask Logic, Workflow Inventory, Audit Findings).

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
- **the team's own rules, when its settings block defines them:**
  - subtask ticket links
  - an owner property, if one is set
  - the list exclusion (`exclusion`)
  - tasks from switched-off workflows
  - every Create task action in the queue

Overdue tasks and titles changed since creation are about how the team works, not whether the workflow works. Leave them out unless the user asks.

### 4. Review, don't just ship

Open the workbook (e.g. with openpyxl) and read the Audit Findings, the Process Overview and the Detailed Action Map. Then:

- **Check each auto finding against the configuration.** Suppress any that are wrong or noise by adding their keys to `suppress`.
- **Write team-specific findings** the generic checks can't make. For example:
  - the owner set at ticket creation and how it's changed later
  - a branch with a silent default
  - a check that runs after the stage it should gate
  - a task name that implies automation but is manual
  - individual records that went wrong
- **Each finding needs:**
  - classification: `Confirmed`, `Potential Issue`, `Needs Verification` or `No Issue Found` (no severity scores)
  - workflow, and action / step
  - the finding
  - evidence: config field / action ID / record IDs
  - why it matters
  - recommended verification

Save the result as `audits/<team>-workflow-audit/findings.json`:

```json
{"suppress": ["A14"],
 "findings": [{"classification": "Potential Issue", "workflow": "...", "action": "Step 3",
               "finding": "...", "evidence": "Config action 31 ...; ticket 123", "why": "...", "verify": "..."}],
 "process_notes": ["Optional lines for the Read Me sheet"],
 "top": [{"id": "F-03", "text": "...", "next": "..."}]}
```

Rebuild with `--findings audits/<team>-workflow-audit/findings.json`.

If the user supplies screenshots, add what they show as findings or process notes labelled **VERIFIED (screenshot)**.

### 5. Deliver

1. **Write `audits/<team>-workflow-audit/README.md`** in plain English. It should include:
   - the scope table (name, ID, object), queue and start date
   - the sources
   - **What actually happens**: record creation, enrollment, actions, branches, tasks/subtasks, hand-offs, completion, in numbered steps
   - **What WLS should verify / decide**: specific questions, each referencing a finding number
2. **Write the summary page.**
   - **Command:**
     ```bash
     python3 $SK/summary_html.py --workbook <xlsx> --findings <findings.json> --work $WK --team <team> --out audits/<team>-workflow-audit/<team>-audit-summary.html
     ```
     It reads only the workbook, `findings.json` and the saved fetch data; nothing is fetched.
   - **Sections:** header, headline numbers, top findings (from `"top"`), all findings, workflows, and a footer with the evidence labels and "Read only".
   - **Colours:** fixed in `summary_html.py`; it does not read the team's `page_colours` yet.
   - **Content:** no customer contact details.
3. **Commit** the workbook, `findings.json`, the README and the HTML page. Never commit `$WK`. Push to the session's branch, and **send the workbook and the HTML page to the user** (SendUserFile).
4. **Summarise in chat:**
   - what's in the workbook (sheet names and row counts)
   - the 5 to 7 most important findings, in plain language
   - what still needs verification and exactly what to send (e.g. "one subtask's settings screenshot")

Keep each team's audits in its own folder: `audits/<team>-workflow-audit/`.

## Things that will trip you up

- **Subtasks are not in the API.** Subtask titles, owners and due dates come only from records, or from screenshots. Say so.
- **Queue first, workflow name second.** Main tasks are found by queue; subtasks through their main task. The workflow name HubSpot stamps on each task (`hs_object_source_detail_1`) says which workflow made it.
- **Renamed workflows.** Tasks carry the workflow name **at the time they were made**, so a rename breaks the match:
  - The weekly fetch matches tasks against both the live name and the name in the master rules file.
  - The full-map fetch finds older names through task titles and saves them in `aliases.json` (INFERENCE; confirm them with the user).
- **Queue names can't be looked up through the API.** Only queue IDs exist on tasks (`hs_queue_membership_ids`). The user confirms which ID is which queue.
- **Scheduled re-checks.** Many company workflows re-check their trigger on a schedule (`enrollmentSchedule`: weekly days or days of the month, at a time in the portal's time zone) and re-enroll. A company that starts to qualify between runs may only get the task at the next run, so say "not yet, next run …", not "missing".
- **Branch order matters.** An If/then branch takes the **first** matching branch. Two branches that both match (e.g. "manager A is known", then "manager B is known") always send the record down the first.
- **Suppression** ("don't enroll if…") is stored at the top level of the workflow (`suppressionFilterBranch`), not in the trigger.
- **"Ticket status"** is HubSpot's label for `hs_pipeline_stage`. `hs_v2_date_entered_<stage>` holds the **latest** entry into that stage, so earlier entries are overwritten.
- **Filter-based triggers** ("Records meet custom conditions") are evaluated a few seconds after a change. A record that passes through a stage in under about 10 s may never enroll.
- **`actionExecutionIndex`** on a task counts every executed action, including branches. A gap means a non-task action ran there.
- **The time zone** is the account's (account-info API). Due dates are business days when the action's `daysOfWeek` is Mon to Fri.
