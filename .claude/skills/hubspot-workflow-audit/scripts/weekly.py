#!/usr/bin/env python3
"""Weekly check: for one team, answer two questions per workflow and print a short problem list.

  1. Did the right companies go in?  Companies that meet the team's company scope AND the workflow's own
     enrollment filter, but have no task from that workflow at any date.
  2. Did the tasks come out right?   For tasks in the team queue created on/after the start date: every
     unconditional task present, in the queue, assigned to the right person, plus the team rules.

Usage: python3 weekly.py --work DIR --team "CS Ops" [--json out.json]
Report only - this script never changes anything and never recommends changes.
"""
import argparse, collections, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rules

ap = argparse.ArgumentParser()
ap.add_argument('--work', required=True)
ap.add_argument('--team', required=True)
ap.add_argument('--json')
A = ap.parse_args()
W = lambda n, d=None: json.load(open(os.path.join(A.work, n))) if os.path.exists(os.path.join(A.work, n)) else d

if not os.path.exists(os.path.join(A.work, 'COMPLETE')):
    sys.exit(f'STOP: {A.work} is incomplete (fetch.py did not finish). Re-run fetch.py - no results were produced.')
TEAM_NAME, TEAM = rules.load_team(A.team)
SCOPE = W('scope.json', {})
CFG = W('configs.json', {})
TASKS = W('tasks.json', [])
HIST = W('history_tasks.json', [])
TASSOC = W('task_assoc.json', {})
COMPANIES = {c['id']: c for c in W('companies.json', [])}
LISTS = W('lists.json', {})
OWN = {str(o['id']): ((o.get('firstName', '') + ' ' + o.get('lastName', '')).strip() or o.get('email')) for o in W('owners.json', [])}
TICKETS = {t['id']: t for t in W('tickets.json', [])}
R = (TEAM or {}).get('rules', {}) or {}
QIDS = set(SCOPE.get('queue_ids') or [])
SINCE = SCOPE.get('since')
problems, notes = [], []


def add(cid, wf, problem, label):
    c = COMPANIES.get(cid, {}).get('properties', {})
    problems.append({'company_id': cid or '-', 'company': c.get('name', '-') if cid else '-', 'workflow': wf, 'problem': problem, 'label': label})


def companies_of(t):
    return [x['id'] for x in TASSOC.get(t['id'], {}).get('companies', [])]


def tickets_of(t):
    return [x['id'] for x in TASSOC.get(t['id'], {}).get('tickets', [])]


if not TEAM:
    notes.append(f'Team "{A.team}" is not in teams.json - only generic checks were run.')
if not QIDS:
    notes.append('NEEDS VERIFICATION: no queue ID is known for this team (teams.json queue_ids is empty and no in-scope Create task action sets a queue). '
                 'Tasks were matched by workflow name, and the "in the queue" check was skipped.')
ALIASES = W('aliases.json', {})
if ALIASES:
    notes.append('Old workflow names were counted as the same workflow (renames detected from task titles - INFERENCE; confirm): ' +
                 '; '.join(f'{CFG[w]["name"]} <- {", ".join(n)}' for w, n in ALIASES.items() if w in CFG))
if not SINCE:
    notes.append('NEEDS VERIFICATION: no start date - every task date is in scope.')

hist_by_flow = collections.defaultdict(list)
for t in HIST:
    hist_by_flow[t['_flow']].append(t)
scope_tasks = [t for t in TASKS if not SINCE or t['properties']['hs_createdate'][:10] >= SINCE]
in_scope_companies = {cid for cid, c in COMPANIES.items() if rules.in_scope(c['properties'], TEAM) is not False}
checked = set()

for wid, c in CFG.items():
    name = c['name']
    e = c.get('enrollmentCriteria', {})
    # ---------- Q1: did the right companies go in?
    if c.get('objectTypeId') == '0-2' and c.get('isEnabled'):
        enrolled = {cid for t in hist_by_flow[wid] for cid in companies_of(t)}
        _, delay_first = rules.linear_task_actions(c)
        unknown = 0
        if e.get('type') == 'LIST_BASED':
            for cid in sorted(in_scope_companies):
                checked.add(cid)
                props = COMPANIES[cid]['properties']
                ok = rules.eval_branch(e.get('listFilterBranch'), props, LISTS)
                if ok is None:
                    unknown += 1
                    continue
                if not ok or cid in enrolled:
                    continue
                expect, delayed = rules.expected_task(c, props, LISTS)
                if expect is None:
                    unknown += 1
                elif expect:
                    add(cid, name, 'Meets the team scope and this workflow\'s enrollment filter, and its branch path ends in a task, but it has no task from this workflow (any date, old workflow names included).' +
                        (' A delay sits before the task, so it may still be waiting.' if delayed else ''),
                        'INFERENCE' if delayed else 'VERIFIED (config + records)')
            if unknown:
                notes.append(f'NEEDS VERIFICATION: {name} - {unknown} companies could not be checked because the filter uses dates, associations or lists that could not be read.')
        else:
            notes.append(f'NEEDS VERIFICATION: {name} - trigger type {e.get("type")} cannot be checked against company data (only filter-based triggers can).')
    # ---------- Q2: did the tasks come out right?
    mine = [t for t in scope_tasks if t.get('_flow') == wid]
    if not mine:
        continue
    lin, _ = rules.linear_task_actions(c)
    titles_cfg = {rules.norm(x['fields'].get('subject')) for x in c.get('actions', []) if (x.get('actionTypeId') == '0-3')}
    actions_by_title = {rules.norm(x['fields'].get('subject')): x for x in c.get('actions', []) if x.get('actionTypeId') == '0-3'}
    enr = collections.defaultdict(list)
    for t in mine:
        m = (t['properties'].get('hs_object_source_id') or '').split(';')[0]
        enr[m].append(t)
    for k, ts in enr.items():
        cids = sorted({cid for t in ts for cid in companies_of(t)})
        cid = cids[0] if cids else None
        checked.update(cids)
        parents = [t for t in ts if t['properties'].get('hs_task_is_sub_task') != 'true']
        got = {rules.norm(t['properties']['hs_task_subject']) for t in parents}
        for a in lin:
            if rules.norm(a['fields'].get('subject')) not in got:
                add(cid, name, f'Task "{a["fields"].get("subject", "").strip()}" is missing (it runs for every enrolled record).', 'VERIFIED (config + records)')
        for t in ts:
            p = t['properties']
            title = (p.get('hs_task_subject') or '').strip()
            sub = p.get('hs_task_is_sub_task') == 'true'
            if QIDS and not sub and not (set((p.get('hs_queue_membership_ids') or '').split(';')) & QIDS):
                add(cid, name, f'Task "{title}" is not in the team queue.', 'VERIFIED (records)')
            if sub and R.get('subtasks_not_on_ticket') and tickets_of(t):
                add(cid, name, f'Subtask "{title}" is associated with ticket {tickets_of(t)[0]} (subtasks must not be).', 'VERIFIED (records)')
            if sub:
                continue
            a = actions_by_title.get(rules.norm(title))
            if not a:
                if R.get('flag_tasks_from_off_or_removed_actions'):
                    add(cid, name, f'Task "{title}" does not match any Create task action in the current workflow (removed or turned-off action?).', 'VERIFIED (config + records)')
                continue
            kind, val = rules.owner_spec(a['fields'])
            owner = p.get('hubspot_owner_id')
            if kind == 'static' and owner != val:
                add(cid, name, f'Task "{title}" is owned by {OWN.get(owner, owner or "nobody")}; the action assigns {OWN.get(val, val)}.', 'VERIFIED (config + records)')
            if kind == 'property':
                rec = COMPANIES.get(cid, {}).get('properties', {}) if c.get('objectTypeId') == '0-2' else TICKETS.get((tickets_of(t) or [None])[0], {}).get('properties', {})
                want = rec.get(val)
                if want and owner != want:
                    add(cid, name, f'Task "{title}" is owned by {OWN.get(owner, owner or "nobody")}; the record\'s {val} is now {OWN.get(want, want)} (it may have changed after the task was created).', 'INFERENCE')
                if R.get('owner_property') and val != R['owner_property']:
                    add(cid, name, f'Task "{title}" is assigned from {val}; the team rule says {R["owner_property"]}.', 'VERIFIED (config)')
            if R.get('owner_property') and kind == 'static':
                add(cid, name, f'Task "{title}" goes to a fixed user; the team rule says {R["owner_property"]}.', 'VERIFIED (config)')
    # ---------- team rule: exclusion only where allowed
    if R.get('exclusion_only_in'):
        excl = [l for l in rules.list_filters(c) if l[1] == 'NOT_IN_LIST']
        allowed = R['exclusion_only_in'].lower() in name.lower()
        if excl and not allowed:
            add(None, name, f'Has a list exclusion (list {", ".join(x[0] for x in excl)}); the team rule says only "{R["exclusion_only_in"]}" workflows should.', 'VERIFIED (config)')
        if allowed and not excl:
            add(None, name, f'No list exclusion found; the team rule says "{R["exclusion_only_in"]}" workflows should have one.', 'VERIFIED (config)')

# tasks in the queue from workflows outside scope / switched off
if R.get('flag_tasks_from_off_or_removed_actions') and QIDS:
    for t in scope_tasks:
        p = t['properties']
        if p.get('hs_task_is_sub_task') == 'true':
            continue
        if t.get('_flow') is None or not CFG.get(t['_flow'], {}).get('isEnabled', True):
            cids = companies_of(t)
            add(cids[0] if cids else None, p.get('hs_object_source_detail_1') or p.get('hs_object_source') or '-',
                f'Task "{(p.get("hs_task_subject") or "").strip()}" is in the queue but comes from a workflow that is switched off or not part of this team\'s workflows.', 'VERIFIED (records)')

# ---------- output
seen, uniq = set(), []
for p in problems:
    key = (p['company_id'], p['workflow'], p['problem'])
    if key not in seen:
        seen.add(key)
        uniq.append(p)
print(f'## Weekly check - {TEAM_NAME}  (queue: {", ".join(QIDS) or "unknown"}; start date: {SINCE or "none"}; scope: {((TEAM or {}).get("company_scope") or {}).get("description", "all companies")})\n')
if uniq:
    print('| Company ID | Company name | Workflow | Problem | Evidence label |\n|---|---|---|---|---|')
    for p in uniq:
        print(f'| {p["company_id"]} | {p["company"]} | {p["workflow"]} | {p["problem"]} | {p["label"]} |', flush=True)
print(f'\n{len(checked)} companies checked, {len(uniq)} problems found.' if uniq else f'\n{len(checked)} companies checked, no problems found.')
for n in notes:
    print('- ' + n)
if A.json:
    json.dump({'problems': uniq, 'notes': notes, 'companies_checked': len(checked)}, open(A.json, 'w'), indent=1)
