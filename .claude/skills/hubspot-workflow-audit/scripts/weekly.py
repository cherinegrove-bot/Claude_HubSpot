#!/usr/bin/env python3
"""Weekly audit for one team: answers the three questions from data fetch.py --weekly saved.

  1. Were the tasks created?          per task type: should have / did get / missing (with reason) / shouldn't have,
                                       plus new facilities (became live this week)
  2. Are they linked to the right company?   main task -> company; subtask -> no ticket (per team settings)
  3. Did anyone change the workflows?        live settings vs the team's master rules file

Usage:
  python3 weekly.py --team cs-ops --work DIR            # writes DIR/results.json and prints the chat summary

Who "should have" a task is worked out from the MASTER RULES FILE settings (not the live workflows) and the team
rules in team-rules.md, using each company's property values at the time of the scheduled run (from property
history). Everything the team decides lives in team-rules.md; nothing team-specific is in this script.
"""
import argparse, collections, datetime as dt, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rules, describe, master

ap = argparse.ArgumentParser()
ap.add_argument('--team', required=True)
ap.add_argument('--work', required=True)
A = ap.parse_args()
W = lambda n, d=None: json.load(open(os.path.join(A.work, n))) if os.path.exists(os.path.join(A.work, n)) else d
if not os.path.exists(os.path.join(A.work, 'COMPLETE')):
    sys.exit(f'STOP: {A.work} is incomplete (fetch.py --weekly did not finish). Re-run the fetch - no report was produced.')
SCOPE = W('scope.json', {})
if SCOPE.get('mode') != 'weekly':
    sys.exit(f'STOP: {A.work} was not made by fetch.py --weekly.')
TEAM_NAME, TEAM = rules.load_team(A.team)
if not TEAM:
    sys.exit(f'STOP: no team-rules.md for "{A.team}".')
describe.init(A.work)
M, _ = master.read_master(os.path.join(TEAM['_dir'], TEAM['master_rules_file']))
LIVE = W('configs.json', {})
DENIED = W('denied.json', [])
TASKS = W('tasks.json', [])
TASSOC = W('task_assoc.json', {})
# Companies the team excludes from every audit (e.g. demo records): dropped here, so they are in no scope, count, search or calendar.
EXCLUDED = {str(x['id']): x for x in (TEAM.get('excluded_companies') or [])}
COMP = {c['id']: c for c in W('companies.json', []) if c['id'] not in EXCLUDED}
EXCLUDED_TASKS = 0
for _tid, _a in TASSOC.items():
    _cs = _a.get('companies') or []
    if any(x['id'] in EXCLUDED for x in _cs):
        _a['companies'] = [x for x in _cs if x['id'] not in EXCLUDED]
        if not _a['companies']:
            _a['_only_excluded'] = True
LISTS = W('lists.json', {})
LIST_NAMES = W('list_names.json', {})
ACCT = W('account.json', {})
QHIST = W('queue_history.json', {})
MOVERS = W('queue_movers.json', [])
from zoneinfo import ZoneInfo
TZ = ZoneInfo(ACCT.get('timeZone') or 'UTC')
P = rules.parse_date
FIRST, LAST = [dt.date.fromisoformat(x) for x in SCOPE['window']]
T0, T1 = [P(x) for x in SCOPE['window_utc']]
NOW = P(SCOPE['fetched_at'])
QIDS = set(SCOPE.get('queue_ids') or [])
OWNER = TEAM.get('decision_owner', 'the team lead')
TYPES = TEAM.get('task_types', [])
TYPE_NAMES = [t['name'] for t in TYPES]
EXPECTED_OFF = set(TEAM.get('expected_off', []))
WAIT = {w['id']: w for w in TEAM.get('waiting_on', [])}
GOLIVE = TEAM.get('went_live') or {}
local = lambda x: x.astimezone(TZ)
fmt_dt = lambda x: local(x).strftime('%Y-%m-%d %H:%M')
cname = lambda cid: (COMP.get(cid, {}).get('properties', {}).get('name') or f'company {cid}')
wfname = lambda w: (M.get(w, {}).get('row', {}).get('Workflow Name') or LIVE.get(w, {}).get('name') or str(w))
PROBLEMS = []


def problem(q, kind, text, label, cls='Confirmed', type_=None, cid=None, task=None, workflow=None, reason=None, group=None, source=None, extra=None):
    PROBLEMS.append({**(extra or {}), 'q': q, 'kind': kind, 'text': text, 'label': label, 'class': cls, 'type': type_, 'company_id': cid,
                     'company': cname(cid) if cid else None, 'task_id': task, 'workflow': workflow, 'reason': reason, 'group': group or kind,
                     'source': source or (wfname(workflow) if workflow else None)})


# ------------------------------------------------------------------ tasks in the window
def task_row(t):
    p = t['properties']
    comps = [x['id'] for x in TASSOC.get(t['id'], {}).get('companies', [])]
    tix = [x['id'] for x in TASSOC.get(t['id'], {}).get('tickets', [])]
    flow = t.get('_flow')
    return {'id': t['id'], 'title': (p.get('hs_task_subject') or '').strip(), 'flow': flow, 'source': p.get('hs_object_source_detail_1') or p.get('hs_object_source'),
            'created': P(p['hs_createdate']), 'due': P(p.get('hs_timestamp')), 'sub': p.get('hs_task_is_sub_task') == 'true',
            'parent': p.get('hs_task_parent_task_id'), 'companies': comps, 'tickets': tix,
            'queues': [q for q in (p.get('hs_queue_membership_ids') or '').split(';') if q],
            'in_queue': bool(set((p.get('hs_queue_membership_ids') or '').split(';')) & QIDS),
            'type': rules.task_type_of(TEAM, flow, p.get('hs_task_subject')) if flow in M else None, 'problems': []}


ROWS = [task_row(t) for t in TASKS if T0 <= P(t['properties']['hs_createdate']) < T1]
EXCLUDED_TASKS = sum(1 for r in ROWS if TASSOC.get(r['id'], {}).get('_only_excluded'))
ROWS = [r for r in ROWS if not TASSOC.get(r['id'], {}).get('_only_excluded')]      # tasks linked only to an excluded company are not checked
MAIN = [r for r in ROWS if not r['sub']]
SUBS = [r for r in ROWS if r['sub']]


def moved_by(r):
    """If a task was created in the team queue and later put in another queue by automation, say so,
    and name the task workflow whose action sets that queue (when exactly one does)."""
    hist = sorted(QHIST.get(r['id'], []), key=lambda h: h['timestamp'])
    if not hist:
        return None
    first, last = hist[0], hist[-1]
    if first.get('value') not in QIDS or last.get('value') in QIDS:
        return None
    m = [x for x in MOVERS if x['queue'] == last.get('value')]
    who = f'workflow "{m[0]["name"]}" ({m[0]["id"]}, {"ON" if m[0]["enabled"] else "off"}) sets queue {last["value"]} in action {m[0]["actionId"]}' if len(m) == 1 else \
          (f'{len(m)} task workflows set queue {last["value"]}' if m else 'no task workflow found that sets this queue')
    secs = (P(last['timestamp']) - P(first['timestamp'])).total_seconds()
    qn = (TEAM.get('queue_names') or {}).get(last.get('value'))
    if qn:
        who += f'; queue {last["value"]} is "{qn["name"]}" ({qn.get("label", "VERIFIED (screenshot)")})'
    return {'text': f'It was created in {TEAM.get("queue_name")}, then moved to queue {last["value"]} by automation ({last.get("sourceType")}) {secs:.0f} s later; {who}.',
            'workflow': m[0]['id'] if len(m) == 1 else None, 'workflow_name': m[0]['name'] if len(m) == 1 else None, 'queue': last['value']}


# ------------------------------------------------------------------ who should get what
def scope_reason(props):
    """Why a company is outside the team scope, in words built from the team's scope filters."""
    out = []
    for f in (TEAM.get('company_scope') or {}).get('filters', []):
        ok = rules.eval_filter({'filterType': 'PROPERTY', 'property': f['property'], 'operation': {'operator': f['operator'], 'values': f.get('values')}}, props)
        if ok is False:
            lbl = describe.plabel(f['property'])
            out.append(f'{lbl} is {describe.pval(f["property"], props.get(f["property"])) or "empty"}')
    return '; '.join(out) or 'outside the team scope'


def _when_ok(conds, props):
    """All conditions of a branch reason hold for these company values, e.g. {"property": "site_manager", "is": "known"}."""
    for c in conds or []:
        v = props.get(c['property'])
        has = v not in (None, '')
        if c.get('is') == 'known' and not has:
            return False
        if c.get('is') == 'unknown' and has:
            return False
        if 'starts_with' in c and not str(v or '').startswith(c['starts_with']):
            return False
    return True


def branch_reason(path, props=None, wid=None):
    """First team branch reason whose branch pattern, workflows and conditions all match."""
    for b in TEAM.get('branch_reasons', []):
        if b.get('workflows') and str(wid) not in b['workflows']:
            continue
        if re.search(b['branch'], path or '') and _when_ok(b.get('when'), props or {}):
            return b
    return None


def evaluate(cid, wid, when, type_name):
    """Would this company get this task type from this workflow at `when`, by the master settings?
    Returns dict(state, reason, label, path). state: expected | missing_reason | not_expected | out_of_scope | unknown."""
    c = COMP.get(cid)
    cfg = M.get(wid, {}).get('cfg')
    if not c or not cfg:
        return {'state': 'unknown', 'reason': 'no data', 'label': 'NEEDS VERIFICATION'}
    props = rules.props_at(c, when)
    sc = rules.in_scope(props, TEAM)
    if sc is False:
        return {'state': 'out_of_scope', 'reason': scope_reason(props), 'label': 'VERIFIED (records)'}
    trig = cfg.get('enrollmentCriteria', {}).get('listFilterBranch')
    if trig:
        ok = rules.eval_branch(trig, props, LISTS)
        if ok is None:
            return {'state': 'unknown', 'reason': "the workflow's trigger could not be checked from the data", 'label': 'NEEDS VERIFICATION'}
        if not ok:
            return {'state': 'not_expected', 'reason': "doesn't meet the workflow trigger", 'label': 'VERIFIED (config)'}
    elif cfg.get('enrollmentCriteria', {}).get('type') != 'LIST_BASED':
        return {'state': 'unknown', 'reason': 'event or manual trigger', 'label': 'NEEDS VERIFICATION'}
    sup = rules.suppression(cfg)
    if sup:
        s = rules.eval_branch(sup, props, LISTS)
        if s:
            lst = ', '.join(f'list {l} "{LIST_NAMES.get(l, "")}"' for l in rules.referenced_lists({'s': sup}))
            return {'state': 'not_expected', 'reason': f'excluded by rule: on {lst or "the suppression"}', 'label': 'VERIFIED (config)', 'excluded': True}
    outcome, action, path = rules.task_path(cfg, props, LISTS)
    if outcome is None:
        return {'state': 'unknown', 'reason': f'branch could not be checked ({path})', 'label': 'NEEDS VERIFICATION'}
    if outcome == 'task':
        t = rules.task_type_of(TEAM, wid, action.get('fields', {}).get('subject'))
        if t == type_name:
            return {'state': 'expected', 'path': path, 'label': 'INFERENCE'}
        return {'state': 'not_expected', 'reason': f'gets "{t or action.get("fields", {}).get("subject")}" instead ({path})', 'label': 'VERIFIED (config)'}
    b = branch_reason(path, props, wid)
    if b and b.get('kind') == 'missing':
        return {'state': 'missing_reason', 'reason': b['reason'], 'label': b.get('label', 'VERIFIED (config)'), 'path': path, 'waiting_on': b.get('waiting_on')}
    if b:
        return {'state': 'not_expected', 'reason': b['reason'], 'label': b.get('label', 'VERIFIED (config)'), 'path': path, 'excluded': True}
    where = 'no branch matched at the first check' if path in ('', 'None met') else f'branch {path} has no task'
    return {'state': 'not_expected', 'reason': f'by the workflow settings: {where}', 'label': 'VERIFIED (config)', 'path': path}


def trigger_props(cfg):
    return set(rules.referenced_props(cfg))


def changed_in_window(c, props):
    for k in props:
        for h in (c.get('propertiesWithHistory') or {}).get(k, []) or []:
            ts = P(h.get('timestamp'))
            if ts and T0 <= ts < T1:
                return ts
    return None


def went_live(c):
    """(moment Status changed to the live value inside the window, or None)."""
    sp, lv = GOLIVE.get('status_property', 'live'), GOLIVE.get('live_value', 'Yes')
    hist = sorted((c.get('propertiesWithHistory') or {}).get(sp, []) or [], key=lambda h: h['timestamp'])
    prev = None
    for h in hist:
        ts = P(h['timestamp'])
        if h.get('value') == lv and prev != lv and T0 <= ts < T1:
            return ts
        prev = h.get('value')
    return None


# ------------------------------------------------------------------ Question 1
TYPE_RESULTS = []
TASKS_BY_TYPE_CO = collections.defaultdict(list)
for r in MAIN:
    if r['type']:
        for cid in r['companies'] or [None]:
            TASKS_BY_TYPE_CO[(r['type'], cid)].append(r)
LIVE_NOW = {cid for cid, c in COMP.items() if rules.in_scope(c.get('properties', {}), TEAM)}

for tt in TYPES:
    name = tt['name']
    runs, notes = [], []
    should, missing, shouldnt, not_exp = {}, {}, {}, collections.Counter()
    for wid in tt['workflows']:
        mc = M.get(wid, {}).get('cfg')
        if not mc:
            notes.append(f'{wfname(wid)} is not in the master rules file.')
            continue
        live = LIVE.get(wid)
        sched = rules.schedule_runs(mc, FIRST, LAST, TZ, NOW)
        off_now = live is not None and not live.get('isEnabled') and mc.get('isEnabled')
        if not mc.get('isEnabled'):
            continue
        if sched is None:          # no schedule: enrolls when a company newly meets the trigger
            tp = trigger_props(mc)
            for cid, c in COMP.items():
                ts = changed_in_window(c, tp)
                if not ts:
                    continue
                e = evaluate(cid, wid, NOW, name)
                if e['state'] in ('expected', 'missing_reason'):
                    should.setdefault(cid, {'wf': wid, 'run': ts, 'eval': e})
            runs.append({'workflow': wid, 'name': wfname(wid), 'when': 'when a company newly meets the trigger', 'off': off_now})
            continue
        for run in sched:
            runs.append({'workflow': wid, 'name': wfname(wid), 'when': fmt_dt(run), 'at': run.isoformat(), 'off': off_now})
            for cid in COMP:
                e = evaluate(cid, wid, run, name)
                if e['state'] in ('expected', 'missing_reason'):
                    should.setdefault(cid, {'wf': wid, 'run': run, 'eval': e, 'off': off_now})
                elif e['state'] == 'not_expected' and cid in LIVE_NOW:
                    not_exp[e['reason']] += 1
    got = {cid for (n, cid) in TASKS_BY_TYPE_CO if n == name and cid}
    for cid, s in should.items():
        if cid in got:
            continue
        e = s['eval']
        if e['state'] == 'missing_reason':
            missing[cid] = {'reason': e['reason'], 'label': e['label'], 'waiting_on': e.get('waiting_on'), 'workflow': s['wf'], 'run': fmt_dt(s['run'])}
        elif s.get('off'):
            missing[cid] = {'reason': 'workflow off', 'label': 'VERIFIED (config)', 'workflow': s['wf'], 'run': fmt_dt(s['run'])}
        else:
            missing[cid] = {'reason': 'unknown', 'label': 'INFERENCE', 'workflow': s['wf'], 'run': fmt_dt(s['run'])}
    # companies that qualify now but did not at the run (became live / full management after it)
    if any(x.get('at') for x in runs):
        for cid in LIVE_NOW - set(should) - got:
            wid = next((w for w in tt['workflows'] if M.get(w, {}).get('cfg', {}).get('isEnabled')), None)
            if not wid:
                continue
            e = evaluate(cid, wid, NOW, name)
            if e['state'] in ('expected', 'missing_reason'):
                gl = went_live(COMP[cid])
                first_run = next((P(x['at']) for x in runs if x.get('at')), NOW)
                missing[cid] = {'reason': 'went live this week' if gl else f'outside the team scope at the run ({scope_reason(rules.props_at(COMP[cid], first_run))})', 'label': 'VERIFIED (records)',
                                'workflow': wid, 'run': 'after the run' + (f' (live since {fmt_dt(gl)})' if gl else '')}
    for cid in got:
        for r in TASKS_BY_TYPE_CO[(name, cid)]:
            if cid in should:
                continue
            e = evaluate(cid, r['flow'], r['created'], name)
            if e['state'] in ('expected', 'missing_reason'):
                continue
            shouldnt[cid] = {'reason': e.get('reason'), 'label': e.get('label'), 'task': r['id'], 'workflow': r['flow'], 'created': fmt_dt(r['created'])}
    # problems
    for cid, m in missing.items():
        if m['reason'] == 'went live this week':
            continue                                                # shown under New facilities
        problem(1, 'missing', f'{cname(cid)} did not get "{name}" ({m["reason"]}).', m['label'], 'Potential Issue' if m['reason'] == 'unknown' else 'Confirmed',
                name, cid, None, m['workflow'], m['reason'], group=f'missing:{name}:{m["reason"]}')
    for cid, s in shouldnt.items():
        problem(1, 'shouldnt', f'{cname(cid)} got "{name}" but should not have ({s["reason"]}).', s['label'], 'Potential Issue', name, cid, s['task'], s['workflow'], s['reason'],
                group=f'shouldnt:{name}:{s["reason"]}')
    TYPE_RESULTS.append({'name': name, 'workflows': [{'id': w, 'name': wfname(w), 'on_master': M.get(w, {}).get('cfg', {}).get('isEnabled'),
                                                       'on_live': (LIVE.get(w) or {}).get('isEnabled')} for w in tt['workflows']],
                         'runs': runs, 'notes': notes,
                         'should': sorted(should, key=cname), 'got': sorted(got, key=cname),
                         'missing': {cid: missing[cid] for cid in sorted(missing, key=cname)},
                         'shouldnt': {cid: shouldnt[cid] for cid in sorted(shouldnt, key=cname)},
                         'not_expected': dict(not_exp.most_common()),
                         'tasks': [r['id'] for r in MAIN if r['type'] == name]})

# other task-level checks (Question 1)
DUPES, W3 = [], []
by_day = collections.defaultdict(list)
for r in MAIN:
    if r['type']:
        for cid in r['companies']:
            by_day[(r['type'], cid, local(r['created']).date())].append(r)
dup_type = {w.get('duplicate_task_type'): wid for wid, w in WAIT.items() if w.get('duplicate_task_type')}
for (tname, cid, day), rs in by_day.items():
    if len(rs) < 2:
        continue
    flows = sorted({r['flow'] for r in rs})
    entry = {'type': tname, 'company_id': cid, 'company': cname(cid), 'day': day.isoformat(), 'tasks': [r['id'] for r in rs], 'workflows': [wfname(f) for f in flows]}
    if tname in dup_type and len(flows) > 1:
        entry['waiting_on'] = dup_type[tname]
        DUPES.append(entry)
    else:
        problem(1, 'duplicate', f'{cname(cid)} got "{tname}" {len(rs)} times on {day} (rule 4: duplicates should not be created).', 'VERIFIED (records)', 'Potential Issue', tname, cid, rs[0]['id'],
                flows[0], group=f'duplicate:{tname}')
w3 = next((w for w in WAIT.values() if w.get('task_types')), None)
for r in MAIN:
    if w3 and r['type'] in w3['task_types']:
        for cid in r['companies']:
            if cid in COMP and rules.in_scope(rules.props_at(COMP[cid], r['created']), TEAM) is False:
                W3.append({'type': r['type'], 'company_id': cid, 'company': cname(cid), 'task': r['id'], 'reason': scope_reason(rules.props_at(COMP[cid], r['created']))})
                problem(1, 'not_live_90', f'{cname(cid)} got "{r["type"]}" while {scope_reason(rules.props_at(COMP[cid], r["created"]))} (rule 1; {w3["id"]}).', 'VERIFIED (records)', 'Potential Issue',
                        r['type'], cid, r['id'], r['flow'], group=f'not_live_90:{r["type"]}')
for r in MAIN:
    if r['flow'] in EXPECTED_OFF:
        problem(1, 'off_task', f'Task "{r["title"]}" was created by {wfname(r["flow"])}, which is switched off as a duplicate (rule 4).', 'VERIFIED (records)', 'Confirmed',
                None, (r['companies'] or [None])[0], r['id'], r['flow'], group=f'off_task:{r["flow"]}')
    elif r['flow'] is None:
        problem(1, 'unknown_source', f'Task "{r["title"]}" in the queue comes from "{r["source"]}", which is not in the master rules file.', 'NEEDS VERIFICATION', 'Needs Verification',
                None, (r['companies'] or [None])[0], r['id'], None, group=f'unknown_source:{r["source"]}')
    elif r['flow'] in M and QIDS and not r['in_queue']:
        cq = sorted({str(a.get('fields', {}).get('queue_id')) for a in M[r['flow']]['cfg'].get('actions', []) if describe.akind(a) == '0-3'})
        mv = moved_by(r)
        problem(1, 'not_in_queue', f'Task "{r["title"]}" from {wfname(r["flow"])} is in queue {", ".join(r["queues"]) or "none"}, not {TEAM.get("queue_name")} '
                f'({", ".join(sorted(QIDS))}); the workflow settings say queue {", ".join(cq)}.' + (f' {mv["text"]}' if mv else ''),
                'VERIFIED (records)' + (' + VERIFIED (config)' if mv and mv.get('workflow') else ''), 'Confirmed',
                r['type'], (r['companies'] or [None])[0], r['id'], r['flow'], reason=f'in queue {", ".join(r["queues"]) or "none"}',
                group=f'not_in_queue:{r["flow"]}:{",".join(r["queues"])}', extra={'moved_by': mv})
    elif r['flow'] in M and not r['type'] and M[r['flow']]['cfg'].get('isEnabled'):
        problem(1, 'unknown_type', f'Task "{r["title"]}" from {wfname(r["flow"])} does not match any task type in team-rules.md.', 'VERIFIED (records)', 'Needs Verification',
                None, (r['companies'] or [None])[0], r['id'], r['flow'], group=f'unknown_type:{r["flow"]}')
KNOWN_NR = collections.Counter(r['source'] for r in MAIN if isinstance(r['flow'], str) and r['flow'].startswith('not_readable'))

# new facilities
NEW = []
for cid, c in COMP.items():
    gl = went_live(c)
    if not gl or cid not in LIVE_NOW:
        continue
    gld = c['properties'].get(GOLIVE.get('go_live_date_property', 'go_live_date'))
    gap = None
    if gld:
        gap = abs((local(gl).date() - dt.date.fromisoformat(gld[:10])).days)
    types = []
    for tr in TYPE_RESULTS:
        if cid in tr['got']:
            st = 'got it'
        elif cid in tr['missing']:
            st = 'missing: ' + tr['missing'][cid]['reason']
        else:
            wid = next((w for w in next(t for t in TYPES if t['name'] == tr['name'])['workflows'] if M.get(w, {}).get('cfg', {}).get('isEnabled')), None)
            e = evaluate(cid, wid, NOW, tr['name']) if wid else {'state': 'not_expected', 'reason': 'workflow switched off'}
            if e['state'] in ('expected', 'missing_reason'):
                nxt = None
                for w in next(t for t in TYPES if t['name'] == tr['name'])['workflows']:
                    mc = M.get(w, {}).get('cfg') or {}
                    if mc.get('isEnabled') and mc.get('enrollmentSchedule'):
                        rs = rules.schedule_runs(mc, LAST + dt.timedelta(days=1), LAST + dt.timedelta(days=62), TZ)
                        if rs:
                            nxt = min(nxt or rs[0], rs[0])
                st = 'not yet' + (f': next run {fmt_dt(nxt)}' if nxt else ' (no schedule: when the trigger is met)')
            else:
                st = 'not for this facility: ' + e.get('reason', '')
        types.append({'type': tr['name'], 'status': st})
    NEW.append({'company_id': cid, 'company': cname(cid), 'went_live': fmt_dt(gl), 'go_live_date': gld, 'days_apart': gap,
                'flag': gap is not None and gap > int(GOLIVE.get('max_days_apart', 7)), 'types': types})
    if gap is not None and gap > int(GOLIVE.get('max_days_apart', 7)):
        problem(1, 'golive_gap', f'{cname(cid)}: Status changed to Live on {local(gl).date()} but the go-live date is {gld} ({gap} days apart).', 'VERIFIED (records)', 'Potential Issue',
                None, cid, group='golive_gap')
NEW.sort(key=lambda x: x['company'])

# ------------------------------------------------------------------ Question 2
links = TEAM.get('links') or {}
LINK_ROWS = []
for r in MAIN:
    st, label = 'ok', 'VERIFIED (records)'
    if links.get('main_task_company', True):
        if not r['companies']:
            st = 'no company'
        elif len(r['companies']) > 1:
            st = f'{len(r["companies"])} companies'
        elif r['type']:
            cid = r['companies'][0]
            tr = next(t for t in TYPE_RESULTS if t['name'] == r['type'])
            if cid in tr['shouldnt']:
                st, label = "company doesn't qualify", 'INFERENCE'
    if st == 'ok' and links.get('main_task_ticket') and not r['tickets']:
        st = 'no ticket'
    r['link'] = st
    if st != 'ok':
        note = ' (from known issue ' + next((n.get('known_issue', '') for n in TEAM.get('not_readable', []) if n['name'] == r['source']), '') + ')' if isinstance(r['flow'], str) and r['flow'].startswith('not_readable') else ''
        problem(2, 'link', f'Task "{r["title"]}" ({r["id"]}): {st}{note}.', label, 'Confirmed' if label.startswith('VERIFIED') else 'Potential Issue', r['type'],
                (r['companies'] or [None])[0], r['id'], r['flow'] if r['flow'] in M else None, st, group=f'link:{st}:{r["source"]}',
                source=(wfname(r['flow']) if r['flow'] in M else r['source']) + note,
                extra={'nr_issue': r['flow'].split(':', 1)[1], 'known_issue': r['flow'].split(':', 1)[1]} if isinstance(r['flow'], str) and r['flow'].startswith('not_readable:') else None)
    r['known'] = r['flow'].split(':', 1)[1] if isinstance(r['flow'], str) and r['flow'].startswith('not_readable:') and st != 'ok' else None
    LINK_ROWS.append({'task': r['id'], 'title': r['title'], 'type': r['type'], 'workflow': wfname(r['flow']) if r['flow'] in M else r['source'],
                      'workflow_id': r['flow'] if r['flow'] in M else None,
                      'companies': [{'id': c, 'name': cname(c)} for c in r['companies']], 'status': st, 'label': label, 'known': r.get('known')})
SUB_ROWS = []
for r in SUBS:
    bad = links.get('subtask_ticket_forbidden') and r['tickets']
    SUB_ROWS.append({'task': r['id'], 'title': r['title'], 'parent': r['parent'], 'tickets': r['tickets'], 'status': 'linked to a ticket' if bad else 'ok'})
    if bad:
        problem(2, 'subtask_ticket', f'Subtask "{r["title"]}" ({r["id"]}) is associated with ticket {", ".join(r["tickets"])}.', 'VERIFIED (records)', 'Confirmed',
                None, None, r['id'], r['flow'], group='subtask_ticket')

# ------------------------------------------------------------------ Question 3
CHANGES = []
excl = TEAM.get('exclusion') or {}
excl_wfs = set(rules.load_team(A.team)[1]['rules'].get('exclusion_only_in_workflows') or [])
for wid, e in sorted(M.items(), key=lambda x: wfname(x[0]).lower()):
    live = LIVE.get(wid)
    if not live:
        err = next((d['error'] for d in DENIED if d['id'] == wid), 'not returned')
        CHANGES.append({'workflow': wid, 'name': wfname(wid), 'status': 'not returned by the API', 'diffs': [], 'label': 'NEEDS VERIFICATION', 'error': err[:200]})
        problem(3, 'not_returned', f'{wfname(wid)} ({wid}) was not returned by the API.', 'NEEDS VERIFICATION', 'Needs Verification', workflow=wid, group='not_returned')
        continue
    diffs = master.compare(e['cfg'], live, TEAM) if e.get('cfg') else []
    only_rev = diffs and all(d['column'] == 'Revision' for d in diffs)
    rule2 = None
    if excl.get('list_id'):
        has = excl['list_id'] in json.dumps(rules.suppression(live) or {}) or any(l[0] == excl['list_id'] and l[1] == 'NOT_IN_LIST' for l in rules.list_filters(live))
        if live.get('isEnabled') and has and wid not in excl_wfs:
            rule2 = f'now excludes list {excl["list_id"]}, which only {", ".join(excl.get("only_in_task_types", []))} workflows should (rule 2)'
        if live.get('isEnabled') and not has and wid in excl_wfs:
            rule2 = f'no longer excludes list {excl["list_id"]} (rule 2 says it should)'
    pend = next((c for c in TEAM.get('changes_not_confirmed', []) if c['workflow'] == wid), None)
    CHANGES.append({'workflow': wid, 'name': wfname(wid), 'status': 'change, not yet confirmed' if diffs else 'same', 'diffs': diffs, 'label': 'VERIFIED (config)',
                    'pending': pend,
                    'revision': [e['row'].get('Revision'), str(live.get('revisionId'))], 'updated': (live.get('updatedAt') or '')[:16].replace('T', ' ') + ' UTC',
                    'only_revision': bool(only_rev), 'rule2': rule2})
    if diffs:
        what = 'only the revision number changed (no change found in the compared settings)' if only_rev else ', '.join(d['column'] for d in diffs) + ' changed'
        known = f' Change, not yet confirmed (first seen {pend["first_seen"]}; {pend["status"]}).' if pend else ' Change, not yet confirmed.'
        problem(3, 'changed', f'{wfname(wid)}: {what}.{known}', 'VERIFIED (config)', 'Needs Verification', workflow=wid, group=f'changed:{wid}',
                extra={'pending': bool(pend)})
    if rule2:
        problem(3, 'rule2', f'{wfname(wid)} {rule2}.', 'VERIFIED (config)', 'Confirmed', workflow=wid, group=f'rule2:{wid}')

# ------------------------------------------------------------------ known issues and open decisions: one line each, not one problem per task
FOLDED = collections.defaultdict(list)
known_moves = {m['queue']: m for m in TEAM.get('known_queue_moves', [])}
ROW_BY_ID = {r['id']: r for r in ROWS}


def known_move(p):
    """The team's known queue move that covers this problem (same queue, and created on or before the cut-off date if one is set)."""
    m = known_moves.get((p.get('moved_by') or {}).get('queue'))
    if not m:
        return None
    r = ROW_BY_ID.get(p.get('task_id'))
    if m.get('created_on_or_before') and (not r or local(r['created']).date().isoformat() > m['created_on_or_before']):
        return None
    return m
wait_cos = {cid: wid for wid, w in WAIT.items() for cid in w.get('company_ids', [])}
keep = []
for p in PROBLEMS:
    km = known_move(p) if p['kind'] == 'not_in_queue' else None
    if km:
        FOLDED[('known', km['known_issue'])].append(p)
        if km.get('waiting_on'):
            FOLDED[('wait', km['waiting_on'])].append(p)
    elif p['kind'] == 'link' and p.get('nr_issue'):
        FOLDED[('known', p['nr_issue'])].append(p)
    elif p.get('company_id') in wait_cos:
        FOLDED[('wait', wait_cos[p['company_id']])].append(p)
    else:
        keep.append(p)
PROBLEMS[:] = keep
for tr in TYPE_RESULTS:                       # same facilities in the task-type view: mark them as waiting, not as new problems
    for cid, m in tr['missing'].items():
        if cid in wait_cos:
            m['reason'] += f' (Waiting on {OWNER}: {wait_cos[cid]})'
            m['waiting_on'] = wait_cos[cid]


KNOWN_DAYS = collections.defaultdict(int)          # (local date, task type, known issue) -> tasks, for the Overview calendar
for (kind, kid), ps in FOLDED.items():
    if kind == 'known':
        for p in ps:
            r = ROW_BY_ID.get(p.get('task_id'))
            if r and r.get('type'):
                KNOWN_DAYS[(local(r['created']).date().isoformat(), r['type'], kid)] += 1


def folded_text(ps):
    by = collections.Counter(re.sub(r' \(from known issue [^)]*\)', '', p.get('source') or wfname(p.get('workflow'))) for p in ps)
    kinds = {p['kind'] for p in ps}
    what = 'moved out of the ' + TEAM.get('queue_name', 'team') + ' queue' if kinds == {'not_in_queue'} else 'not linked to any company' if kinds == {'link'} else 'affected'
    return f'{len(ps)} task(s) {what} (' + '; '.join(f'{k}: {v}' for k, v in by.most_common()) + ').'


# ------------------------------------------------------------------ summary
q_counts = {q: len([p for p in PROBLEMS if p['q'] == q]) for q in (1, 2, 3)}
groups = collections.OrderedDict()
for p in PROBLEMS:
    groups.setdefault(p['group'], []).append(p)
WEIGHT = {'missing': 4, 'link': 5, 'subtask_ticket': 5, 'rule2': 5, 'off_task': 5, 'changed': 4, 'not_in_queue': 5, 'shouldnt': 3, 'duplicate': 3,
          'not_returned': 3, 'unknown_source': 2, 'unknown_type': 2, 'not_live_90': 2, 'golive_gap': 1}


def headline(g, ps):
    p = ps[0]
    n = len(ps)
    k = p['kind']
    if k == 'missing':
        r = p['reason']
        return f'{n} facilit{"y" if n == 1 else "ies"} did not get "{p["type"]}" — reason: {r}.'
    if k == 'shouldnt':
        return f'{n} facilit{"y" if n == 1 else "ies"} got "{p["type"]}" but should not have ({p["reason"]}).'
    if k == 'link':
        return f'{n} main task{"s" if n > 1 else ""} from {p["source"]}: {p["reason"]}.'
    if k == 'not_in_queue':
        mv = p.get('moved_by') or {}
        return (f'{n} task{"s" if n > 1 else ""} from {p["source"]} {"are" if n > 1 else "is"} {p["reason"]}, not the {TEAM.get("queue_name")} queue'
                + (f': created in {TEAM.get("queue_name")}, then moved by the workflow "{mv["workflow_name"]}" ({mv["workflow"]}).' if mv.get('workflow') else
                   f': created in {TEAM.get("queue_name")}, then moved by automation; no current task workflow sets that queue (the one that did may have been deleted).' if mv else
                   ', although the workflow settings say ' + TEAM.get('queue_name', '') + '.'))
    if n == 1:
        return p['text']
    return f'{n} × {p["text"]}'


def score(ps):
    p = ps[0]
    s = WEIGHT.get(p['kind'], 1) + min(len(ps), 50) / 25
    if p['kind'] == 'missing' and p.get('reason') in ('unknown', 'workflow off'):
        s += 3                                        # tasks nobody can explain go first
    if p.get('pending'):
        s -= 2                                        # already seen, waiting on confirmation
    if 'Waiting on' in (p.get('reason') or ''):
        s -= 3                                        # already with the decision owner
    return s


ranked = sorted(groups.items(), key=lambda kv: -score(kv[1]))
TOP = [{'text': headline(g, ps), 'label': ps[0]['label'], 'q': ps[0]['q'], 'count': len(ps)} for g, ps in ranked[:5]]

in_scope_count = len(LIVE_NOW)
waiting = []
for wid_, w in WAIT.items():
    item = dict(w)
    if w.get('duplicate_task_type'):
        item['found'] = [d for d in DUPES if d.get('waiting_on') == wid_]
    elif w.get('task_types'):
        item['found'] = W3
    else:
        item['found'] = [{'type': tr['name'], 'company_id': cid, 'company': cname(cid), 'reason': m['reason']} for tr in TYPE_RESULTS for cid, m in tr['missing'].items()
                         if m.get('waiting_on') == wid_ and cid not in wait_cos]
    fp = FOLDED.get(('wait', wid_), [])
    if w.get('queue_move') and fp:
        qn = ((TEAM.get('queue_names') or {}).get(w['queue_move']) or {}).get('name')
        item['found'] = item.get('found', []) + [{'type': p.get('type'), 'company_id': p.get('company_id'), 'company': p.get('company'), 'task': p.get('task_id'),
                                                  'reason': f'moved to queue {w["queue_move"]}' + (f' "{qn}"' if qn else '') + f' by {(p.get("moved_by") or {}).get("workflow_name", "another workflow")}'}
                                                 for p in fp]
        item['summary'] = '; '.join(f'{n} task(s) from {src} moved to queue {w["queue_move"]}' + (f' "{qn}"' if qn else '')
                                    for src, n in collections.Counter(p.get('source') for p in fp).most_common())
    elif fp:
        item['found'] = item.get('found', []) + [{'type': p.get('type'), 'company_id': p.get('company_id'), 'company': p.get('company'), 'reason': p['text']} for p in fp]
    waiting.append(item)
known = list(TEAM.get('known_issues', []))
if KNOWN_NR:
    for k in known:
        for n in TEAM.get('not_readable', []):
            if n.get('known_issue') == k['id'] and n['name'] in KNOWN_NR:
                k = dict(k)
                k['this_week'] = f'{KNOWN_NR[n["name"]]} task(s) from it were created.'
                known[known.index(next(x for x in known if x['id'] == n['known_issue']))] = k
for i, k in enumerate(known):
    fp = FOLDED.get(('known', k['id']))
    if fp:
        k = dict(k)
        k['this_week'] = ((k.get('this_week') or '') + ' ' + folded_text(fp)).strip()
        known[i] = k
off_state = [{'id': w, 'name': wfname(w), 'live': 'ON' if (LIVE.get(w) or {}).get('isEnabled') else 'OFF'} for w in EXPECTED_OFF]

# Schedules for the Overview calendar: when each task type's workflows are set to run, from the MASTER RULES FILE.
SCHEDULES = []
for tt in TYPES:
    for wid in tt['workflows']:
        mc = (M.get(wid) or {}).get('cfg') or {}
        if not mc.get('isEnabled'):
            continue
        sc = mc.get('enrollmentSchedule') or {}
        t = sc.get('timeOfDay', {})
        live = LIVE.get(wid)
        SCHEDULES.append({'type': tt['name'], 'workflow': wid, 'workflow_name': wfname(wid),
                          'kind': {'MONTHLY_SPECIFIC_DAYS': 'monthly', 'WEEKLY': 'weekly', 'DAILY': 'daily'}.get(sc.get('type'), 'trigger'),
                          'days': sc.get('daysOfMonth') or [d.upper() for d in sc.get('daysOfWeek', [])],
                          'time': f'{t.get("hour", 0):02d}:{t.get("minute", 0):02d}' if sc else '',
                          'off_now': bool(live is not None and not live.get('isEnabled'))})

# "Switched off" tab: every master-file workflow that is off in the master rules file or in HubSpot now.
# Summaries come from team-rules.md (written from the master rules file); a summary written for an older revision is flagged.
SUMS = TEAM.get('workflow_summaries') or {}
SWITCHED_OFF = []
for wid, e in M.items():
    mon = bool((e.get('cfg') or {}).get('isEnabled'))
    live = LIVE.get(wid)
    lon = None if live is None else bool(live.get('isEnabled'))
    if mon and lon is not False:
        continue
    if not mon and lon is False:
        status = 'off_expected'
    elif not mon and lon:
        status = 'on_now'          # off in the master rules file, switched on in HubSpot
    elif not mon:
        status = 'not_returned'
    else:
        status = 'off_now'         # on in the master rules file, switched off in HubSpot
    sm = SUMS.get(wid) or {}
    rev = str((e.get('cfg') or {}).get('revisionId') or e['row'].get('Revision') or '')
    SWITCHED_OFF.append({'workflow': wid, 'name': wfname(wid), 'status': status, 'summary': sm.get('summary'),
                         'summary_stale': bool(sm) and str(sm.get('written_for_revision')) != rev, 'summary_revision': sm.get('written_for_revision'),
                         'master_revision': rev, 'live_revision': str((live or {}).get('revisionId') or ''),
                         'last_edited': ((live or {}).get('updatedAt') or (e.get('cfg') or {}).get('updatedAt') or '')[:16].replace('T', ' ') + ' UTC'})
SWITCHED_OFF.sort(key=lambda x: (x['status'] == 'off_expected', x['name'].lower()))

RESULT = {
    'team': TEAM_NAME, 'team_slug': rules.team_slug(A.team), 'decision_owner': OWNER, 'portal': str(ACCT.get('portalId', '')), 'queue': TEAM.get('queue_name'), 'queue_ids': sorted(QIDS),
    'window': [FIRST.isoformat(), LAST.isoformat()], 'report_day': rules.report_day(TEAM, LAST).isoformat(), 'time_zone': ACCT.get('timeZone'),
    'fetched_at': fmt_dt(NOW), 'start_date': TEAM.get('start_date'),
    'excluded_companies': [{'id': k, 'name': v.get('name'), 'reason': v.get('reason')} for k, v in EXCLUDED.items()],
    'excluded_tasks': EXCLUDED_TASKS,
    'counts': {'facilities_in_scope': in_scope_count, 'main_tasks': len(MAIN), 'subtasks': len(SUBS), 'workflows': len(M),
               'q1': q_counts[1], 'q2': q_counts[2], 'q3': q_counts[3]},
    'top': TOP, 'types': TYPE_RESULTS, 'new_facilities': NEW, 'links': LINK_ROWS, 'subtasks': SUB_ROWS, 'changes': CHANGES,
    'schedules': SCHEDULES, 'switched_off': SWITCHED_OFF, 'known_days': [{'date': d, 'type': t, 'known_issue': k, 'tasks': n} for (d, t, k), n in sorted(KNOWN_DAYS.items())],
    'waiting_on': waiting, 'known_issues': known, 'expected_off': off_state, 'problems': PROBLEMS,
    'companies': {cid: cname(cid) for cid in {x for tr in TYPE_RESULTS for x in tr['should'] + tr['got'] + list(tr['missing']) + list(tr['shouldnt'])} | {c for r in MAIN for c in r['companies']} | LIVE_NOW},
    'tasks': [{'id': r['id'], 'title': r['title'], 'type': r['type'], 'workflow': wfname(r['flow']) if r['flow'] in M else r['source'],
               'workflow_id': r['flow'] if r['flow'] in M else None, 'created': fmt_dt(r['created']),
               'due': fmt_dt(r['due']) if r['due'] else '', 'companies': r['companies'], 'link': r.get('link'), 'in_queue': r['in_queue']} for r in MAIN],
}
json.dump(RESULT, open(os.path.join(A.work, 'results.json'), 'w'), indent=1, default=str)

line = lambda n, what: 'all good' if n == 0 else f'{n} problem{"s" if n > 1 else ""} found'
print(f'## {TEAM_NAME} weekly audit — {FIRST} to {LAST}' + (' (window shortened by the start date)' if FIRST.isoformat() == TEAM.get('start_date') else ''))
if EXCLUDED:
    print(f'Excluded from the audit: ' + '; '.join(f'{v.get("name") or k} ({k}): {v.get("reason")}' for k, v in EXCLUDED.items()) + (f' ({EXCLUDED_TASKS} task(s) linked only to them not checked)' if EXCLUDED_TASKS else ''))
print(f'Checked {in_scope_count} companies in scope ({(TEAM.get("company_scope") or {}).get("description", "all companies")}), {len(MAIN)} main tasks and {len(SUBS)} subtasks created in the window, and {len(M)} workflows.\n')
print(f'1. **Were the tasks created?** {line(q_counts[1], "")}' + (f' ({len(NEW)} new facilit{"y" if len(NEW) == 1 else "ies"} this week)' if NEW else ''))
print(f'2. **Are they linked to the right company?** {line(q_counts[2], "")}')
print(f'3. **Did anyone change the workflows?** ' + ('no changes' if not q_counts[3] else f'{sum(1 for c in CHANGES if c["status"] != "same")} workflow(s) differ from the master rules file'))
if TOP:
    print('\n**Top problems**')
    for i, t in enumerate(TOP, 1):
        print(f'{i}. {t["text"]} [{t["label"]}]')
print('\n**Known issues** (reported once)')
for k in known:
    print(f'- {k["id"]}: {k["text"]}' + (f' This week: {k["this_week"]}' if k.get('this_week') else ''))
print(f'\n**Waiting on {OWNER}**')
for w in waiting:
    print(f'- {w["id"]} {w["title"]}' + (f' — this week: ' + (w.get('summary') or '; '.join(f.get('reason') or f.get('company') or '' for f in w['found'][:3])) if w.get('found') else ''))
print(f'\nresults: {os.path.join(A.work, "results.json")}')
