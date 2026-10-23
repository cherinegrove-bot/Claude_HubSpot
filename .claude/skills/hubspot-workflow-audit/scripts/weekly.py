#!/usr/bin/env python3
"""Weekly audit for one team: answers the three questions from data fetch.py --weekly saved.

  1. Were the tasks created?          per task type: should have / did get / missing (with reason) / shouldn't have,
                                       plus new facilities (became live this week)
  2. Are they associated with the right company?   main task -> company; subtask -> no ticket (per team settings)
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
# Workflows whose own trigger decides who should get them, instead of the team's company scope (team-rules.md).
SCOPE_EXEMPT = {str(x) for x in ((TEAM.get('scope_exempt_workflows') or {}).get('workflows') or [])}
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
# Ticket-triggered workflows (team-rules.md "ticket_facility"): who should get a task comes from tickets entering the
# trigger stage, and each ticket is shown under its facility (the company with the team's label, else the Primary one).
TF = TEAM.get('ticket_facility') or {}
TICKETS = {t['id']: t for t in W('weekly_tickets.json', [])}
TCO = W('ticket_companies.json', {})
STAGES = {s['id']: s for p in (W('pipelines.json', {}) or {}).get('tickets', []) for s in p['stages']}


def is_ticket_wf(wid):
    return bool(TF) and ((M.get(wid) or {}).get('cfg') or {}).get('objectTypeId') == '0-5'


def facility_of(tid):
    cs = [c for c in TCO.get(tid, []) if c['id'] not in EXCLUDED]
    for lbl in (TF.get('company_label'), TF.get('fallback_label')):
        hit = [c['id'] for c in cs if lbl and lbl in (c.get('labels') or [])]
        if hit:
            return hit[0]
    return cs[0]['id'] if cs else None


def ticket_open(tid):
    return (STAGES.get((TICKETS.get(tid) or {}).get('properties', {}).get('hs_pipeline_stage')) or {}).get('metadata', {}).get('isClosed') != 'true'
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
# A test run may look back past the start date. Runs and tasks before it go to their own section ("before_start" in team-rules.md).
BEFORE = TEAM.get('before_start') or {}
CUTOFF = dt.date.fromisoformat(TEAM['start_date']) if SCOPE.get('ignore_start_date') and TEAM.get('start_date') else None
if CUTOFF and CUTOFF <= FIRST:
    CUTOFF = None
SECTION = 'main'
OWNER = TEAM.get('decision_owner', 'the team lead')
TYPES = TEAM.get('task_types', [])
TYPE_NAMES = [t['name'] for t in TYPES]
EXPECTED_OFF = set(TEAM.get('expected_off', []))
WAIT = {w['id']: w for w in TEAM.get('waiting_on', [])}
GOLIVE = TEAM.get('went_live') or {}
local = lambda x: x.astimezone(TZ)
fmt_dt = lambda x: local(x).strftime('%Y-%m-%d %H:%M')
cname = lambda cid: (COMP.get(cid, {}).get('properties', {}).get('name') or f'company {cid}')
ALL_FLOWS = {str(f['id']): f for f in W('all_flows.json', [])}       # every workflow the API lists (names for links outside the master file)
wfname = lambda w: (M.get(w, {}).get('row', {}).get('Workflow Name') or LIVE.get(w, {}).get('name') or ALL_FLOWS.get(str(w), {}).get('name') or str(w))
# tasks a person fixed by hand after the run (team-rules.md "fixed_by_hand"): still this week's problem, shown as fixed
FIXED = {t: f for f in (TEAM.get('fixed_by_hand') or []) for t in f.get('task_ids', [])}
PROBLEMS = []


PRE_PROBLEMS = []


def problem(q, kind, text, label, cls='Confirmed', type_=None, cid=None, task=None, workflow=None, reason=None, group=None, source=None, extra=None):
    (PRE_PROBLEMS if SECTION == 'before_start' else PROBLEMS).append({**(extra or {}), 'section': SECTION, 'q': q, 'kind': kind, 'text': text, 'label': label, 'class': cls, 'type': type_, 'company_id': cid,
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


def resolve_alias(r):
    """A task made under an old workflow name that several current workflows used to share."""
    old = r['flow'][len('alias:'):]
    cands = [w for w in (TEAM.get('old_workflow_names') or {}).get(old, []) if w in M]
    by_title = [w for w in cands if rules.task_type_of(TEAM, w, r['title'])] or cands
    pick = by_title[0] if by_title else None
    if len(by_title) > 1 and r['companies'] and r['companies'][0] in COMP:
        props = rules.props_at(COMP[r['companies'][0]], r['created'])
        fit = [w for w in by_title if rules.eval_branch(M[w]['cfg'].get('enrollmentCriteria', {}).get('listFilterBranch'), props, LISTS)]
        pick = (fit or by_title)[0]
    r['flow'], r['old_name'] = pick, old
    r['type'] = rules.task_type_of(TEAM, pick, r['title']) if pick else None
    return r


ROWS = [task_row(t) for t in TASKS if T0 <= P(t['properties']['hs_createdate']) < T1]
ROWS = [resolve_alias(r) if isinstance(r['flow'], str) and r['flow'].startswith('alias:') else r for r in ROWS]
EXCLUDED_TASKS = sum(1 for r in ROWS if TASSOC.get(r['id'], {}).get('_only_excluded'))
ROWS = [r for r in ROWS if not TASSOC.get(r['id'], {}).get('_only_excluded')]      # tasks linked only to an excluded company are not checked
for r in ROWS:
    r['before_start'] = bool(CUTOFF and local(r['created']).date() < CUTOFF)
PRE_MAIN = [r for r in ROWS if not r['sub'] and r['before_start']]
MAIN = [r for r in ROWS if not r['sub'] and not r['before_start']]
SUBS = [r for r in ROWS if r['sub'] and not r['before_start']]


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
        if 'starts_with' in c and not str(v or '').strip().lower().startswith(c['starts_with'].strip().lower()):
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


def evaluate(cid, wid, when, type_name, pre=False):
    """Would this company get this task type from this workflow at `when`, by the master settings?
    Returns dict(state, reason, label, path). state: expected | missing_reason | not_expected | out_of_scope | unknown."""
    c = COMP.get(cid)
    cfg = M.get(wid, {}).get('cfg')
    if not c or not cfg:
        return {'state': 'unknown', 'reason': 'no data', 'label': 'NEEDS VERIFICATION'}
    props = rules.props_at(c, when)
    sc = None if str(wid) in SCOPE_EXEMPT else rules.in_scope(props, TEAM)     # exempt workflows: their own trigger decides
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


def changed_in_window(c, props, first=None, last=None):
    """When one of these properties changed between two dates (default: the whole window)."""
    t0 = dt.datetime(first.year, first.month, first.day, tzinfo=TZ) if first else T0
    t1 = dt.datetime(last.year, last.month, last.day, tzinfo=TZ) + dt.timedelta(days=1) if last else T1
    for k in props:
        for h in (c.get('propertiesWithHistory') or {}).get(k, []) or []:
            ts = P(h.get('timestamp'))
            if ts and t0 <= ts < t1:
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
LIVE_NOW = {cid for cid, c in COMP.items() if rules.in_scope(c.get('properties', {}), TEAM)}
if TF and TYPES and all(is_ticket_wf(w) for t in TYPES for w in t['workflows']):
    # a ticket team: the facilities in scope are those with an open ticket in the team's pipelines
    LIVE_NOW = {f for f in (facility_of(t) for t in TICKETS if ticket_open(t)) if f and f in COMP}


def ticket_runs(wid, name, t0, t1):
    """Tickets that entered the trigger of a ticket-triggered workflow between t0 and t1, by the MASTER settings.
    One entry per ticket (its first qualifying entry in the period): state expected / not_expected / unknown,
    with the task titles its path reaches for this task type."""
    cfg = M[wid]['cfg']
    trig = cfg.get('enrollmentCriteria', {}).get('listFilterBranch')
    reenroll = cfg.get('enrollmentCriteria', {}).get('shouldReEnroll')
    born = P((LIVE.get(wid) or {}).get('createdAt') or '') or None
    tt = next(t for t in TYPES if t['name'] == name)
    out = []
    for tid, t in TICKETS.items():
        entries = rules.stage_entries(t)
        hits = [ts for ts, _ in entries if rules.eval_branch(trig, rules.props_at(t, ts), LISTS)]
        now = [ts for ts in hits if t0 <= ts < t1]
        if not now:
            continue
        at = now[0]
        stage = (STAGES.get(rules.props_at(t, at).get('hs_pipeline_stage')) or {}).get('label', 'the trigger stage')
        e = {'ticket': tid, 'subject': t['properties'].get('subject') or f'ticket {tid}', 'facility': facility_of(tid), 'at': at, 'stage': stage}
        nxt = next((ts for ts, _ in entries if ts > at), None)
        e['left_after'] = (nxt - at).total_seconds() if nxt else None
        before = [ts for ts in hits if ts < at and (born is None or ts >= born)]
        if before and not reenroll:
            out.append({**e, 'state': 'not_expected', 'reason': f'already entered {stage} on {local(before[-1]).date()}; re-enrollment is off', 'label': 'VERIFIED (config)'})
            continue
        comps = [rules.props_at(COMP[c['id']], at) for c in TCO.get(tid, []) if c['id'] in COMP]
        acts, path, certain = rules.reached_tasks(cfg, rules.props_at(t, at), comps, LISTS)
        titles = sorted({rules.norm(a.get('fields', {}).get('subject')) for a in acts if re.search(tt['title'], rules.norm(a.get('fields', {}).get('subject')), re.I)})
        if not certain:
            out.append({**e, 'state': 'unknown', 'reason': f'branch could not be checked ({path})', 'label': 'NEEDS VERIFICATION', 'titles': titles})
        elif titles:
            out.append({**e, 'state': 'expected', 'label': 'INFERENCE', 'titles': titles, 'path': path})
        else:
            out.append({**e, 'state': 'not_expected', 'reason': 'by the workflow settings: no ' + name + ' task on its path' + (f' ({path})' if path else ''), 'label': 'VERIFIED (config)'})
    return out


TICKET_DAYS = []      # calendar events for ticket teams: tickets created, and tickets entering a stage (with the result)


def ticket_type_results(tt, first, last, rows):
    """Question 1 for a task type made by ticket-triggered workflows: tickets that entered the stage this period
    should have every task the stage creates; shown by facility."""
    name = tt['name']
    t0 = dt.datetime(first.year, first.month, first.day, tzinfo=TZ)
    t1 = dt.datetime(last.year, last.month, last.day, tzinfo=TZ) + dt.timedelta(days=1)
    runs, notes = [], []
    should, got, missing, shouldnt, not_exp = {}, set(), {}, {}, collections.Counter()
    mine = [r for r in rows if r['type'] == name]
    by_ticket = collections.defaultdict(list)
    for r in mine:
        for x in r['tickets']:
            by_ticket[x].append(r)
    seen_tickets = set()
    for wid in tt['workflows']:
        mc = M.get(wid, {}).get('cfg')
        if not mc:
            notes.append(f'{wfname(wid)} is not in the master rules file.')
            continue
        live = LIVE.get(wid)
        off_now = live is not None and not live.get('isEnabled') and mc.get('isEnabled')
        if not mc.get('isEnabled'):
            continue
        runs.append({'workflow': wid, 'name': wfname(wid), 'when': 'when a ticket enters its stage', 'off': off_now})
        for e in ticket_runs(wid, name, t0, t1):
            tid, fac = e['ticket'], e['facility']
            if e['state'] == 'not_expected':
                not_exp[e['reason'].split(' on 20')[0] if 'already entered' in e['reason'] else e['reason']] += 1
                seen_tickets.add(tid)
                continue
            if e['state'] == 'unknown':
                not_exp['could not be checked: ' + e['reason']] += 1
                problem(1, 'unknown_branch', f'Ticket "{e["subject"]}" ({tid}) entered {e["stage"]} on {fmt_dt(e["at"])}: whether it should get "{name}" could not be worked out ({e["reason"]}).',
                        'NEEDS VERIFICATION', 'Needs Verification', name, fac, None, wid, group=f'unknown_branch:{name}')
                continue
            seen_tickets.add(tid)
            if not fac:
                problem(1, 'no_facility', f'Ticket "{e["subject"]}" ({tid}) entered {e["stage"]} on {fmt_dt(e["at"])} but is not associated with any company, so it has no facility.',
                        'VERIFIED (records)', 'Confirmed', name, None, None, wid, 'ticket has no company', group=f'no_facility:{name}')
                continue
            got_titles = {rules.norm(r['title']) for r in by_ticket.get(tid, [])}
            have = set()
            for gt in got_titles:                       # each task counts for the longest configured title it starts with
                m = max((x for x in e['titles'] if gt.startswith(x)), key=len, default=None)
                if m:
                    have.add(m)
            lack = [x for x in e['titles'] if x not in have]
            should.setdefault(fac, {'wf': wid, 'run': e['at'], 'ticket': tid})
            TICKET_DAYS.append({'date': local(e['at']).date().isoformat(), 'time': local(e['at']).strftime('%H:%M'), 'kind': 'stage', 'type': name,
                                'at_iso': e['at'].isoformat(), 'stage': e['stage'],
                                'workflow': wid, 'workflow_name': wfname(wid), 'ticket': tid, 'ticket_name': e['subject'], 'company_id': fac,
                                'status': 'ok' if not lack else 'bad', 'detail': 'all tasks created' if not lack else
                                (f'got {len(have)} of {len(e["titles"])} tasks' if have else 'no tasks created')})
            if not lack:
                got.add(fac)
                continue
            if have:
                missing[fac] = {'reason': f'partial: ticket {tid} got {len(have)} of {len(e["titles"])} tasks; missing ' + ', '.join(f'"{x}"' for x in lack),
                                'label': 'VERIFIED (records)', 'workflow': wid, 'run': fmt_dt(e['at']), 'ticket': tid}
            elif e.get('left_after') is not None and e['left_after'] < 60:
                nxt_stage = (STAGES.get(rules.value_at(TICKETS[tid]['propertiesWithHistory'].get('hs_pipeline_stage'), e['at'] + dt.timedelta(seconds=e['left_after']))) or {}).get('label', 'the next stage')
                missing[fac] = {'reason': f'passed through: ticket {tid} entered {e["stage"]} on {fmt_dt(e["at"])} and moved to {nxt_stage} {e["left_after"]:.0f} seconds later, '
                                          f'so the workflow probably never enrolled it (HubSpot checks the trigger a few seconds after a change); none of its {len(e["titles"])} tasks were created',
                                'label': 'VERIFIED (records) + INFERENCE', 'workflow': wid, 'run': fmt_dt(e['at']), 'ticket': tid}
            elif off_now:
                missing[fac] = {'reason': 'workflow off', 'label': 'VERIFIED (config)', 'workflow': wid, 'run': fmt_dt(e['at']), 'ticket': tid}
            else:
                missing[fac] = {'reason': f'unknown: ticket {tid} entered {e["stage"]} on {fmt_dt(e["at"])} and got none of its {len(e["titles"])} tasks',
                                'label': 'INFERENCE', 'workflow': wid, 'run': fmt_dt(e['at']), 'ticket': tid}
    # tasks of this type that no ticket explains: judged per task, using ALL its tickets (a task can also carry an extra
    # ticket, e.g. a support ticket linked later, which is not a reason to flag it)
    pipes = set(TF.get('pipelines') or [])
    for r in mine:
        tix = r['tickets']
        if not tix or any(x in seen_tickets for x in tix):
            continue
        team_tix = [x for x in tix if (TICKETS.get(x) or {}).get('properties', {}).get('hs_pipeline') in pipes] if pipes else tix
        trig = (M.get(r['flow'], {}).get('cfg') or {}).get('enrollmentCriteria', {}).get('listFilterBranch')
        if any([ts for ts, _ in rules.stage_entries(TICKETS[x]) if ts <= r['created'] and (r['created'] - ts).total_seconds() < 86400
                and rules.eval_branch(trig, rules.props_at(TICKETS[x], ts), LISTS)] for x in team_tix if x in TICKETS):
            continue                                # its ticket entered the stage just before the period; created by that run
        tid = (team_tix or tix)[0]
        t = TICKETS.get(tid)
        fac = facility_of(tid) or (r['companies'] or [None])[0]
        tp = (t or {}).get('properties', {})
        if not team_tix and t:
            made = P(tp.get('createdate'))
            reason = (f'the task is associated only with a ticket in another pipeline' + (f', created {fmt_dt(made)}' + (', after the task' if made and made > r['created'] else '') if made else '')
                      + '; it was probably associated by hand later')
        else:
            reason = 'its ticket did not enter the stage before this task was created' if t else f'its ticket {tid} is not in the team pipeline'
        shouldnt[fac or tid] = {'reason': reason + f' (ticket {tid})', 'label': 'INFERENCE', 'task': r['id'], 'workflow': r['flow'], 'created': fmt_dt(r['created'])}
    for cid, m in missing.items():
        problem(1, 'missing', f'{cname(cid)} did not get "{name}" ({m["reason"]}).', m['label'], 'Potential Issue' if m['reason'].startswith('unknown') else 'Confirmed',
                name, cid, None, m['workflow'], m['reason'].split(':')[0], group=f'missing:{name}:{m["reason"].split(":")[0]}')
    for cid, s in shouldnt.items():
        problem(1, 'shouldnt', f'{cname(cid)} got "{name}" but should not have ({s["reason"]}).', s['label'], 'Potential Issue', name, cid, s['task'], s['workflow'], s['reason'],
                group=f'shouldnt:{name}')
    return {'name': name, 'workflows': [{'id': w, 'name': wfname(w), 'on_master': M.get(w, {}).get('cfg', {}).get('isEnabled'),
                                         'on_live': (LIVE.get(w) or {}).get('isEnabled')} for w in tt['workflows']],
            'runs': runs, 'notes': notes, 'should': sorted(should, key=cname), 'got': sorted(got, key=cname),
            'missing': {cid: missing[cid] for cid in sorted(missing, key=cname)},
            'shouldnt': {cid: shouldnt[cid] for cid in sorted(shouldnt, key=cname)},
            'not_expected': dict(not_exp.most_common()), 'tasks': [r['id'] for r in mine]}


def type_results(first, last, rows, pre=False):
    """Question 1 per task type, for the runs between two dates and the tasks made in that period."""
    out = []
    by_co = collections.defaultdict(list)
    for r in rows:
        if r['type']:
            for cid in r['companies'] or [None]:
                by_co[(r['type'], cid)].append(r)
    for tt in TYPES:
        name = tt['name']
        if tt['workflows'] and all(is_ticket_wf(w) for w in tt['workflows']):
            out.append(ticket_type_results(tt, first, last, rows))     # before the start date too (its own section, no queue check)
            continue
        runs, notes = [], []
        should, missing, shouldnt, not_exp = {}, {}, {}, collections.Counter()
        for wid in tt['workflows']:
            mc = M.get(wid, {}).get('cfg')
            if not mc:
                notes.append(f'{wfname(wid)} is not in the master rules file.')
                continue
            live = LIVE.get(wid)
            sched = rules.schedule_runs(mc, first, last, TZ, NOW)
            off_now = live is not None and not live.get('isEnabled') and mc.get('isEnabled')
            if not mc.get('isEnabled'):
                continue
            if sched is None:          # no schedule: enrolls when a company newly meets the trigger
                tp = trigger_props(mc)
                for cid, c in COMP.items():
                    ts = changed_in_window(c, tp, first, last)
                    if not ts:
                        continue
                    e = evaluate(cid, wid, NOW, name, pre)
                    if e['state'] in ('expected', 'missing_reason'):
                        should.setdefault(cid, {'wf': wid, 'run': ts, 'eval': e})
                runs.append({'workflow': wid, 'name': wfname(wid), 'when': 'when a company newly meets the trigger', 'off': off_now})
                continue
            for run in sched:
                runs.append({'workflow': wid, 'name': wfname(wid), 'when': fmt_dt(run), 'at': run.isoformat(), 'off': off_now})
                for cid in COMP:
                    e = evaluate(cid, wid, run, name, pre)
                    if e['state'] in ('expected', 'missing_reason'):
                        should.setdefault(cid, {'wf': wid, 'run': run, 'eval': e, 'off': off_now})
                    elif e['state'] == 'not_expected' and cid in LIVE_NOW:
                        not_exp[e['reason']] += 1
        got = {cid for (n, cid) in by_co if n == name and cid}
        pre_lists = {c for lid in BEFORE.get('excluded_lists', []) for c in LISTS.get(str(lid), [])} if pre else set()
        for cid, s in should.items():
            if cid in got:
                continue
            e = s['eval']
            cov = next((c for c in BEFORE.get('covered_by', []) if pre and c['type'] == name and cid in COVERED.get(c['covered_by_type'], set())), None)
            if cov:                              # got the task type that replaced it under the old settings: shown, not flagged
                missing[cid] = {'reason': cov['reason'], 'label': 'VERIFIED (records)', 'workflow': s['wf'], 'run': fmt_dt(s['run']), 'not_flagged': True}
                continue
            gap = next((g for g in BEFORE.get('old_settings_gaps', []) if pre and g['type'] == name and
                        rules.props_at(COMP[cid], s['run']).get(TEAM.get('tier_property')) in g.get('tiers', [])), None)
            if gap:                              # the old settings didn't give this tier the task (decided by the user): shown, not flagged
                missing[cid] = {'reason': gap['reason'], 'label': gap.get('label', 'VERIFIED (records)'), 'workflow': s['wf'], 'run': fmt_dt(s['run']), 'not_flagged': True}
                continue
            if cid in pre_lists:                 # the old settings may have excluded it: shown, not flagged
                missing[cid] = {'reason': 'probably excluded at the time: ' + BEFORE.get('excluded_reason', 'on an excluded list'), 'label': 'INFERENCE',
                                'workflow': s['wf'], 'run': fmt_dt(s['run']), 'not_flagged': True}
                continue
            if e['state'] == 'missing_reason':
                missing[cid] = {'reason': e['reason'], 'label': e['label'], 'waiting_on': e.get('waiting_on'), 'workflow': s['wf'], 'run': fmt_dt(s['run'])}
            elif s.get('off'):
                missing[cid] = {'reason': 'workflow off', 'label': 'VERIFIED (config)', 'workflow': s['wf'], 'run': fmt_dt(s['run'])}
            else:
                missing[cid] = {'reason': 'unknown', 'label': 'INFERENCE', 'workflow': s['wf'], 'run': fmt_dt(s['run'])}
        # companies that qualify now but did not at the run (became live / full management after it)
        if any(x.get('at') for x in runs) and not pre:
            for cid in LIVE_NOW - set(should) - got:
                wid = next((w for w in tt['workflows'] if M.get(w, {}).get('cfg', {}).get('isEnabled')), None)
                if not wid:
                    continue
                e = evaluate(cid, wid, NOW, name, pre)
                if e['state'] in ('expected', 'missing_reason'):
                    gl = went_live(COMP[cid])
                    first_run = next((P(x['at']) for x in runs if x.get('at')), NOW)
                    missing[cid] = {'reason': 'went live this week' if gl else f'outside the team scope at the run ({scope_reason(rules.props_at(COMP[cid], first_run))})', 'label': 'VERIFIED (records)',
                                    'workflow': wid, 'run': 'after the run' + (f' (live since {fmt_dt(gl)})' if gl else '')}
        for cid in got:
            for r in by_co[(name, cid)]:
                if cid in should:
                    continue
                e = evaluate(cid, r['flow'], r['created'], name, pre)
                if e['state'] in ('expected', 'missing_reason'):
                    continue
                shouldnt[cid] = {'reason': e.get('reason'), 'label': e.get('label'), 'task': r['id'], 'workflow': r['flow'], 'created': fmt_dt(r['created'])}
        # problems
        for cid, m in missing.items():
            if m['reason'] == 'went live this week' or m.get('not_flagged'):
                continue                                                # shown under New facilities
            problem(1, 'missing', f'{cname(cid)} did not get "{name}" ({m["reason"]}).', m['label'], 'Potential Issue' if m['reason'] == 'unknown' else 'Confirmed',
                    name, cid, None, m['workflow'], m['reason'], group=f'missing:{name}:{m["reason"]}')
        for cid, s in shouldnt.items():
            if pre:
                continue                                                # made under the old settings: shown, not flagged
            problem(1, 'shouldnt', f'{cname(cid)} got "{name}" but should not have ({s["reason"]}).', s['label'], 'Potential Issue', name, cid, s['task'], s['workflow'], s['reason'],
                    group=f'shouldnt:{name}:{s["reason"]}')
        out.append({'name': name, 'workflows': [{'id': w, 'name': wfname(w), 'on_master': M.get(w, {}).get('cfg', {}).get('isEnabled'),
                                                           'on_live': (LIVE.get(w) or {}).get('isEnabled')} for w in tt['workflows']],
                             'runs': runs, 'notes': notes,
                             'should': sorted(should, key=cname), 'got': sorted(got, key=cname),
                             'missing': {cid: missing[cid] for cid in sorted(missing, key=cname)},
                             'shouldnt': {cid: shouldnt[cid] for cid in sorted(shouldnt, key=cname)},
                             'not_expected': dict(not_exp.most_common()),
                             'tasks': [r['id'] for r in rows if r['type'] == name]})
    return out


COVERED = collections.defaultdict(set)     # task type -> facilities that got it anywhere in the window (for "covered_by")
for r in MAIN + PRE_MAIN:
    if r['type']:
        COVERED[r['type']] |= set(r['companies'])
# ------------------------------------------------------------------ process issues (ticket teams)
# A ticket moved to a stage before its first company was linked, so that stage's tasks got no company. The team's
# process says the company is linked first (team-rules.md), so this is reported as a team process issue, not a workflow fault.
PROC_STAGES = {(STAGES.get(x) or {}).get('label') for x in ((TEAM.get('process_issues') or {}).get('stages') or [])} - {None}
# task types whose tasks may have no company by design (team-rules.md "by_design_no_company"): not problems, listed with the reason
BYD = {t: b for b in (TEAM.get('by_design_no_company') or []) for t in b.get('task_types', [])}
BY_DESIGN = collections.OrderedDict()


def by_design_note(r, sub=False):
    tid = (r['tickets'] or [None])[0]
    k = (tid, r['type'])
    e = BY_DESIGN.setdefault(k, {'type': r['type'], 'ticket': tid, 'ticket_name': (TICKETS.get(tid) or {}).get('properties', {}).get('subject') or (f'ticket {tid}' if tid else ''),
                                 'company_id': facility_of(tid) if tid else None, 'tasks': 0, 'subtasks': 0, 'reason': BYD[r['type']]['reason'],
                                 'fixed_by_hand': None})
    e['subtasks' if sub else 'tasks'] += 1
    if not sub and r['id'] in FIXED:
        e['fixed_by_hand'] = FIXED[r['id']].get('fixed')


USERS = {str(o.get('userId')): (o.get('firstName', '') + ' ' + o.get('lastName', '')).strip() for o in W('owners.json', []) if o.get('userId')}
PROC, PROC_TASKS = [], set()


def first_link(t):
    for h in sorted((t.get('propertiesWithHistory') or {}).get('hs_num_associated_companies') or [], key=lambda h: h['timestamp']):
        try:
            if float(h.get('value') or 0) > 0:
                return P(h['timestamp'])
        except ValueError:
            pass
    return None


def moved_by_whom(t, at):
    for h in (t.get('propertiesWithHistory') or {}).get('hs_pipeline_stage') or []:
        if P(h['timestamp']) == at:
            m = re.match(r'userId:(\d+)', h.get('sourceId') or '')
            if m:
                return USERS.get(m.group(1), f'user {m.group(1)}')
            return 'a workflow' if h.get('sourceType') == 'AUTOMATION_PLATFORM' else (h.get('sourceType') or '').lower().replace('_', ' ') or None
    return None


def build_process_issues():
    if not TF or not (TEAM.get('process_issues') or {}).get('company_before_stage'):
        return
    done = {x['key'] for x in PROC}
    for e in TICKET_DAYS:
        if e['kind'] != 'stage' or not e.get('at_iso') or (PROC_STAGES and e.get('stage') not in PROC_STAGES):
            continue
        key = (e['ticket'], e['type'], e['at_iso'])
        t = TICKETS.get(e['ticket'])
        if key in done or not t:
            continue
        at = P(e['at_iso'])
        linked = first_link(t)
        if linked is not None and linked <= at:
            continue
        run = [r for r in ROWS if not r['sub'] and e['ticket'] in r['tickets'] and r['type'] == e['type'] and 0 <= (r['created'] - at).total_seconds() < 600]
        if not run:
            continue
        subs = [r for r in ROWS if r['sub'] and r['parent'] in {x['id'] for x in run}]
        PROC_TASKS.update(x['id'] for x in run + subs)
        fixed = [x for x in run if x['id'] in FIXED]
        PROC.append({'key': key, 'ticket': e['ticket'], 'ticket_name': e['ticket_name'], 'company_id': e['company_id'] or facility_of(e['ticket']),
                     'stage': e.get('stage'), 'type': e['type'], 'moved': fmt_dt(at), 'moved_by': moved_by_whom(t, at),
                     'linked': fmt_dt(linked) if linked else None, 'seconds_after': round((linked - at).total_seconds()) if linked else None,
                     'tasks': len(run), 'tasks_without_company': sum(1 for x in run if not x['companies']),
                     'subtasks': len(subs), 'subtasks_without_company': sum(1 for x in subs if not x['companies']),
                     'fixed_by_hand': fixed[0]['id'] in FIXED and FIXED[fixed[0]['id']].get('fixed') if fixed else None,
                     'section': 'before_start' if CUTOFF and local(at).date() < CUTOFF else 'main', 'label': 'VERIFIED (records)'})
        e['status'] = 'process'
        e['detail'] = f'moved before the company was associated ({"associated " + fmt_dt(linked) if linked else "no company associated yet"}): its tasks got no company'


MAIN_FIRST = CUTOFF or FIRST
TYPE_RESULTS = type_results(MAIN_FIRST, LAST, MAIN)
PRE_TYPES = []
PRE_KNOWN_LINKS = collections.Counter()
if CUTOFF:
    SECTION = 'before_start'
    PRE_TYPES = type_results(FIRST, CUTOFF - dt.timedelta(days=1), PRE_MAIN, pre=True)
    build_process_issues()
    for r in PRE_MAIN:                       # a real problem even under the old settings: a task with no company
        if isinstance(r['flow'], str) and r['flow'].startswith('not_readable') or r['id'] in PROC_TASKS:
            continue                         # counted under its known issue / the process issues instead
        if r['type'] in BYD and not r['companies']:
            by_design_note(r)
            continue
        if not r['companies']:
            problem(2, 'link', f'Task "{r["title"]}" ({r["id"]}): no company.', 'VERIFIED (records)', 'Confirmed', r['type'], None, r['id'], r['flow'] if r['flow'] in M else None,
                    'no company', group=f'link:no company:{r["source"]}', source=wfname(r['flow']) if r['flow'] in M else r['source'])
    _kt = {x: k['id'] for k in TEAM.get('known_issues', []) for x in k.get('link_titles', [])}
    PRE_KNOWN_LINKS = collections.Counter()
    for p_ in list(PRE_PROBLEMS):              # a known issue before the start date too: one line, not one problem per task
        r_ = next((r for r in PRE_MAIN if r['id'] == p_.get('task_id')), None)
        k_ = next((kid for x, kid in _kt.items() if r_ and re.search(x, rules.norm(r_['title']), re.I)), None) if p_['kind'] == 'link' else None
        if k_:
            PRE_KNOWN_LINKS[k_] += 1
            PRE_PROBLEMS.remove(p_)
    SECTION = 'main'

# other task-level checks (Question 1)
# records that should have got a record from a workflow (team-rules.md "record_checks"), e.g. Closed Won deal -> onboarding ticket
RECORD_CHECKS = []
for rc in W('record_checks.json', []):
    c = rc['check']
    keep = set(c.get('created_in_pipelines') or [])
    made = {m['id']: m for m in rc['created'] if not keep or m['properties'].get('hs_pipeline') in keep}
    rows_ = []
    for rec in rc['records']:
        p = rec['properties']
        at = P(p.get(f'hs_v2_date_entered_{c["stage"]}'))
        mine = [x['id'] for x in rc['links'].get(rec['id'], []) if x['id'] in made]
        nm = p.get('dealname') or p.get('subject') or p.get('name') or f'record {rec["id"]}'
        rows_.append({'id': rec['id'], 'name': nm, 'entered': fmt_dt(at) if at else '', 'created': mine, 'status': 'ok' if mine else 'none'})
        if not mine:
            problem(1, 'record_missing', f'{c["object"][:-1].capitalize()} "{nm}" ({rec["id"]}) moved to {c.get("stage_label", "the stage")} on {fmt_dt(at) if at else "?"} '
                    f'but has no {c.get("creates_label", c["creates"][:-1])}.', 'VERIFIED (records)', 'Confirmed', c['name'], None, None, c.get('workflow'),
                    f'no {c.get("creates_label", c["creates"][:-1])}', group=f'record_missing:{c["name"]}',
                    extra={'record': {'id': rec['id'], 'name': nm, 'object_type': c.get('object_type_id', '0-3'), 'entered': fmt_dt(at) if at else ''},
                           'check_name': c['name'], 'creates_label': c.get('creates_label'), 'object_label': c.get('object_label', c['object'][:-1])})
    RECORD_CHECKS.append({'name': c['name'], 'workflow': c.get('workflow'), 'workflow_name': wfname(c.get('workflow')) if c.get('workflow') else '',
                          'creates_label': c.get('creates_label'), 'object_type': c.get('object_type_id', '0-3'), 'records': rows_})

DUPES, W3 = [], []
by_day = collections.defaultdict(list)
TICKET_TYPES = {t['name'] for t in TYPES if t['workflows'] and all(is_ticket_wf(w) for w in t['workflows'])}
for r in MAIN:
    if r['type'] in TICKET_TYPES:      # a stage makes several tasks per ticket: a duplicate is the same task twice on the same ticket
        for tid in r['tickets']:
            by_day[(r['type'], facility_of(tid) or (r['companies'] or [None])[0], local(r['created']).date(), tid, rules.norm(r['title']))].append(r)
    elif r['type']:
        for cid in r['companies']:
            by_day[(r['type'], cid, local(r['created']).date())].append(r)
dup_type = {w.get('duplicate_task_type'): wid for wid, w in WAIT.items() if w.get('duplicate_task_type')}
for (tname, cid, day, *_), rs in by_day.items():
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
        elif tr['name'] in TICKET_TYPES:
            st = 'not yet (no schedule: when its ticket enters the stage)'
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
build_process_issues()
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
    fx = FIXED.get(r['id'])
    if r['type'] in BYD and (st == 'no company' or (fx and st == 'ok')):
        by_design_note(r)                     # e.g. Kickoff tasks before the company is linked: by design
        st, fx = 'ok', None
    if fx and st == 'ok':                     # fine now, because a person fixed it after the workflow ran
        st = f'{fx.get("problem", "problem")} when created; fixed by hand on {fx["fixed"]}'
        label = 'VERIFIED (records)'
        r['fixed'] = fx
    r['link'] = st
    if st != 'ok' and r['id'] in PROC_TASKS:
        r['link'] = st = 'process issue: ' + st          # reported under the team's process issues, not as a link problem
    elif st != 'ok':
        note = ' (from known issue ' + next((n.get('known_issue', '') for n in TEAM.get('not_readable', []) if n['name'] == r['source']), '') + ')' if isinstance(r['flow'], str) and r['flow'].startswith('not_readable') else ''
        problem(2, 'link', f'Task "{r["title"]}" ({r["id"]}): {st}{note}.', label, 'Confirmed' if label.startswith('VERIFIED') else 'Potential Issue', r['type'],
                (r['companies'] or [None])[0], r['id'], r['flow'] if r['flow'] in M else None, st, group=f'link:{st}:{r["source"]}',
                source=(wfname(r['flow']) if r['flow'] in M else r['source']) + note,
                extra={**({'nr_issue': r['flow'].split(':', 1)[1], 'known_issue': r['flow'].split(':', 1)[1]} if isinstance(r['flow'], str) and r['flow'].startswith('not_readable:') else {}),
                       **({'fixed': r['fixed']['fixed'], 'fixed_note': r['fixed'].get('note', ''), 'problem_was': r['fixed'].get('problem')} if r.get('fixed') else {})} or None)
    r['known'] = r['flow'].split(':', 1)[1] if isinstance(r['flow'], str) and r['flow'].startswith('not_readable:') and st != 'ok' else None
    LINK_ROWS.append({'task': r['id'], 'title': r['title'], 'type': r['type'], 'workflow': wfname(r['flow']) if r['flow'] in M else r['source'],
                      'workflow_id': r['flow'] if r['flow'] in M else None,
                      'companies': [{'id': c, 'name': cname(c)} for c in r['companies']], 'status': st, 'label': label, 'known': r.get('known')})
# calendar (ticket teams): a stage entry whose tasks have a link problem (not a known issue) is a problem day too
_known_titles = [x for k in TEAM.get('known_issues', []) for x in k.get('link_titles', [])]
for e in TICKET_DAYS:
    if e['kind'] != 'stage' or e.get('status') == 'process':
        continue
    bad = [r for r in MAIN if e['ticket'] in r['tickets'] and r['type'] == e['type'] and r.get('link') not in (None, 'ok')
           and not any(re.search(x, rules.norm(r['title']), re.I) for x in _known_titles)]
    fixed = [r for r in bad if r.get('fixed')]
    if fixed and len(fixed) == len(bad):
        e['status'] = 'fixed'
        e['detail'] += f'; {len(fixed)} task{"s" if len(fixed) > 1 else ""} had {fixed[0]["fixed"].get("problem", "a problem")} when created, fixed by hand on {fixed[0]["fixed"]["fixed"]}'
        continue
    if bad:
        e['status'] = 'bad'
        e['detail'] += f'; {len(bad)} task{"s" if len(bad) > 1 else ""} with an association problem (' + ', '.join(sorted({r["link"] for r in bad})) + ')'
for e in TICKET_DAYS:                       # by-design gaps are noted on the day, without making it a problem day
    b_ = BY_DESIGN.get((e['ticket'], e['type'])) if e['kind'] == 'stage' else None
    if b_ and e.get('status') == 'ok':
        e['detail'] += f'; {b_["tasks"]} created without a company, by design'
SUB_ROWS = []
PARENTS = {t['id']: task_row(t) for t in TASKS}              # main tasks of the window's subtasks (fetched with them)
for r in SUBS:
    bad = links.get('subtask_ticket_forbidden') and r['tickets']
    diff = None
    if links.get('subtask_links_match_parent'):              # subtasks share their main task's links; flag only a difference
        par = PARENTS.get(r['parent'])
        if par is None:
            diff = 'main task not found'
        else:
            parts = []
            tname = lambda x: (TICKETS.get(x) or {}).get('properties', {}).get('subject') or f'ticket {x}'
            for what, a_, b_, nm in (('Company', r['companies'], par['companies'], cname), ('Ticket', r['tickets'], par['tickets'], tname)):
                if what == 'Company' and (not a_ or not b_) and links.get('subtask_company_ok_if_one_has'):
                    continue                   # only one of the two has a company, which is enough (team setting)
                if set(a_) != set(b_):
                    parts.append(f'{what}: subtask has {", ".join(nm(x) for x in sorted(a_)) or "none"}, main task has {", ".join(nm(x) for x in sorted(b_)) or "none"}')
            diff = '; '.join(parts) or None
    par_ = PARENTS.get(r['parent']) or {}
    if diff and par_.get('type') in BYD and not r['companies'] and set(r['tickets']) == set(par_.get('tickets') or []):
        by_design_note({**r, 'type': par_['type'], 'tickets': r['tickets'] or par_.get('tickets') or []}, sub=True)
        diff = None                            # only the company is missing, at a stage where that's by design
    st = 'associated with a ticket' if bad else (f'associations differ from its main task ({diff})' if diff else 'ok')
    if r['id'] in PROC_TASKS and st != 'ok':
        SUB_ROWS.append({'task': r['id'], 'title': r['title'], 'parent': r['parent'], 'tickets': r['tickets'], 'status': 'process issue: ' + st})
        continue
    SUB_ROWS.append({'task': r['id'], 'title': r['title'], 'parent': r['parent'], 'tickets': r['tickets'], 'status': st})
    if bad:
        problem(2, 'subtask_ticket', f'Subtask "{r["title"]}" ({r["id"]}) is associated with ticket {", ".join(r["tickets"])}.', 'VERIFIED (records)', 'Confirmed',
                None, None, r['id'], r['flow'], group='subtask_ticket')
    elif diff:
        par = PARENTS.get(r['parent']) or {}
        problem(2, 'subtask_links', f'Subtask "{r["title"]}" ({r["id"]}) has different associations from its main task "{par.get("title", r["parent"])}" ({diff}).',
                'VERIFIED (records)', 'Confirmed', par.get('type'), (r['companies'] or par.get('companies') or [None])[0], r['id'], r['flow'] or par.get('flow'),
                diff, group=f'subtask_links:{par.get("flow") or r["flow"]}')

# ------------------------------------------------------------------ Question 3
def _short(seg):
    """One setting part in a few words: arrows, no "(all)", links read "A → B, copied from C"."""
    seg = re.sub(r'^links: ', '', seg.strip()).replace(' -> ', ' → ').replace(' (all)', '')
    seg = seg.replace(": copied from the enrolled record's ", ', copied from ').replace(': the enrolled record', ' = the enrolled record')
    return seg


def _parts(line):
    """(where, [parts]) for one action line: '(start): Create record - create a Ticket; set ...; links: ...'."""
    line = re.sub(r'^\(start\):\s*', '', line.strip())
    m = re.match(r'^(.*?"[^"]*")\s*\|\s*(.*)$', line)          # a task action: "Title" | type ... | owner ...
    if m:
        return m.group(1), [x for x in m.group(2).split(' | ') if x.strip()]
    sep = ' | ' if ' | ' in line else '; '
    ps = [x for x in line.split(sep) if x.strip()]
    head = re.sub(r'^(.*?) - create a (\w+)$', r'\1 (\2)', ps[0]) if ps else line
    rest = []
    for x in ps[1:]:
        rest += [y for y in (x[len('set '):].split('; ') if x.startswith('set ') else [x])]
    return head, rest


def change_rows(diffs):
    """Each difference as short rows: {what, where, detail} (multi-line settings) or {what, was, now}."""
    out = []
    for d in diffs:
        col = d['column']
        if col == 'Revision':
            continue
        if col in master.MULTILINE:
            old = [l for l in (d['was'] or '').split('\n') if l and l not in ('(nothing)', 'same lines, different order')]
            new = [l for l in (d['now'] or '').split('\n') if l and l != '(removed)']
            if d['was'] == 'same lines, different order':
                out.append({'what': f'{col}: order changed', 'where': '', 'detail': ''})
                continue
            o = {h: r for h, r in map(_parts, old)}
            n = {h: r for h, r in map(_parts, new)}
            for h in o:
                if h in n:
                    link = lambda x: '→' in _short(x)
                    key = lambda x: _short(x).split(' = ')[0] if ' = ' in x else _short(x).split(' ')[0]
                    gone = [x for x in o[h] if x not in n[h]]
                    came = [x for x in n[h] if x not in o[h]]
                    for x in list(gone):              # same setting, new value: one "was -> now" row
                        y = next((y for y in came if not link(x) and not link(y) and key(y) == key(x)), None)
                        if y:
                            val = lambda z: _short(z)[len(key(z)):].lstrip(' =') or _short(z)
                            if key(x) == 'description':
                                out.append({'what': 'Description text changed', 'where': h, 'detail': ''})
                            else:
                                out.append({'what': key(x).capitalize() + ' changed', 'where': h, 'was': val(x), 'now': val(y)})
                            gone.remove(x); came.remove(y)
                    for x in gone:
                        out.append({'what': ('Link' if link(x) else 'Setting') + ' removed', 'where': h, 'detail': _short(x)})
                    for x in came:
                        out.append({'what': ('Link' if link(x) else 'Setting') + ' added', 'where': h, 'detail': _short(x)})
                else:
                    out.append({'what': 'Action removed', 'where': h, 'detail': ''})
            for h in n:
                if h not in o:
                    out.append({'what': 'Action added', 'where': h, 'detail': ''})
        else:
            out.append({'what': f'{col} changed', 'was': d['was'], 'now': d['now']})
    return out


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
                    'only_revision': bool(only_rev), 'rule2': rule2, 'rows': change_rows(diffs)})
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
SUB_KNOWN = next((k['id'] for k in TEAM.get('known_issues', []) if k.get('subtask_ticket')), None)    # known issue covering subtasks linked to the ticket


def link_known(p):
    """The team's known issue that covers a link problem by task title (known_issues[].link_titles), if any."""
    t = rules.norm((ROW_BY_ID.get(p.get('task_id')) or {}).get('title'))
    return next((k['id'] for k in TEAM.get('known_issues', []) if any(re.search(x, t, re.I) for x in k.get('link_titles', []))), None)
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
    elif p['kind'] == 'link' and link_known(p):
        FOLDED[('known', link_known(p))].append(p)
    elif p['kind'] == 'subtask_ticket' and SUB_KNOWN:
        FOLDED[('known', SUB_KNOWN)].append(p)
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
    what = 'moved out of the ' + TEAM.get('queue_name', 'team') + ' queue' if kinds == {'not_in_queue'} else 'not associated with any company' if kinds == {'link'} else \
        'subtasks linked to the ticket' if kinds == {'subtask_ticket'} else 'affected'
    if kinds == {'subtask_ticket'}:
        return f'{len(ps)} {what} (' + '; '.join(f'{k}: {v}' for k, v in by.most_common()) + ').'
    return f'{len(ps)} task(s) {what} (' + '; '.join(f'{k}: {v}' for k, v in by.most_common()) + ').'


# ------------------------------------------------------------------ summary
q_counts = {q: len([p for p in PROBLEMS if p['q'] == q]) for q in (1, 2, 3)}
groups = collections.OrderedDict()
for p in PROBLEMS:
    groups.setdefault(p['group'], []).append(p)
WEIGHT = {'subtask_links': 4, 'record_missing': 5, 'missing': 4, 'link': 5, 'subtask_ticket': 5, 'rule2': 5, 'off_task': 5, 'changed': 4, 'not_in_queue': 5, 'shouldnt': 3, 'duplicate': 3,
          'not_returned': 3, 'unknown_source': 2, 'unknown_type': 2, 'not_live_90': 2, 'golive_gap': 1}


def headline(g, ps):
    p = ps[0]
    n = len(ps)
    k = p['kind']
    if k == 'missing':
        r = p['reason']
        return f'{n} facilit{"y" if n == 1 else "ies"} did not get "{p["type"]}" — reason: {r}.'
    if k == 'subtask_links':
        return f'{n} subtask{"s" if n > 1 else ""} with different associations from {"their" if n > 1 else "its"} main task ({p["source"]}).'
    if k == 'subtask_ticket':
        src = collections.Counter(x.get('source') for x in ps)
        return f'{n} subtask{"s" if n > 1 else ""} linked to a ticket, which the team rules forbid (' + '; '.join(f'{k_}: {v}' for k_, v in src.most_common()) + ').'
    if k == 'record_missing':
        return f'{n} record{"s" if n > 1 else ""} with no {p.get("creates_label") or "record"} ({p["type"]}): ' + ', '.join(f'{x["record"]["name"]} ({x["record"]["id"]})' for x in ps[:5]) + ('…' if n > 5 else '') + '.'
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
    # the workflows a question is about, by name, with whether each is switched on now (live, else master rules file)
    item['workflow_list'] = [{'id': x, 'name': wfname(x),
                              'on': bool((LIVE.get(x) or (M.get(x) or {}).get('cfg') or ALL_FLOWS.get(str(x)) or {}).get('isEnabled'))} for x in w.get('workflows', [])]
    if w.get('duplicate_task_type'):
        item['found'] = [d for d in DUPES if d.get('waiting_on') == wid_]
    elif w.get('task_types'):
        item['found'] = W3
    else:
        item['found'] = [{'type': tr['name'], 'company_id': cid, 'company': cname(cid), 'reason': m['reason']} for tr in TYPE_RESULTS for cid, m in tr['missing'].items()
                         if m.get('waiting_on') == wid_ and cid not in wait_cos]
    kw = [k for k in TEAM.get('known_issues', []) if k.get('waiting_on') == wid_ and FOLDED.get(('known', k['id']))]
    if kw:                                   # a known issue tied to this question: show its weekly count on the card
        item['affected_text'] = '; '.join(folded_text(FOLDED[('known', k['id'])]).split(' (')[0] + ' this week' for k in kw)
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

# Task list for the Overview (under the calendar): one entry per task type, from the MASTER RULES FILE, so it matches the calendar.
# For each workflow that makes the type: how often, which tiers reach a Create task action for it, and who it's assigned to.
TIER_PROP = TEAM.get('tier_property')
TIER_ALL = TEAM.get('tiers') or list(((describe.PROPS.get('companies') or {}).get(TIER_PROP) or {}).get('options', {}))
OWNER_SHORT = TEAM.get('owner_short') or {}
ORD = lambda n: f'{n}{"th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")}'


def _and_list(xs):
    xs = list(xs)
    return ', '.join(xs[:-1]) + ' and ' + xs[-1] if len(xs) > 1 else (xs[0] if xs else '')


def _freq(cfg):
    sc = cfg.get('enrollmentSchedule') or {}
    t = sc.get('timeOfDay', {})
    at = f', {t.get("hour", 0):02d}:{t.get("minute", 0):02d}' if sc else ''
    if sc.get('type') == 'MONTHLY_SPECIFIC_DAYS':
        return f'Monthly on the {_and_list(ORD(d) for d in sorted(sc.get("daysOfMonth", [])))}{at}'
    if sc.get('type') == 'WEEKLY':
        return f'Weekly on {_and_list(d.capitalize() for d in sc.get("daysOfWeek", []))}{at}'
    if sc.get('type') == 'DAILY':
        return f'Daily{at}'
    return 'When triggered'


def _kind(cfg):
    return {'MONTHLY_SPECIFIC_DAYS': 'monthly', 'WEEKLY': 'weekly', 'DAILY': 'daily'}.get((cfg.get('enrollmentSchedule') or {}).get('type'), 'trigger')


def _conds(fb, tiers, notes):
    """Narrow the tier set by a filter branch (AND of filters, OR of sub-branches) and note name and list conditions."""
    if not fb:
        return tiers
    subs = [f for f in fb.get('filters', [])]
    for f in subs:
        op = f.get('operation', {})
        o, vals = op.get('operator'), [str(v) for v in (op.get('values') or ([op['value']] if 'value' in op else []))]
        if TIER_PROP and f.get('property') == TIER_PROP:
            if o in ('IS_ANY_OF', 'IS_EQUAL_TO'):
                tiers = [x for x in tiers if x in vals]
            elif o in ('IS_NONE_OF', 'IS_NOT_EQUAL_TO'):
                tiers = [x for x in tiers if x not in vals]
        elif f.get('property') == 'name' and vals:
            v = re.sub(r'[\s\-]+$', '', vals[0])
            notes.add(f'not {v}' if o in ('DOES_NOT_CONTAIN', 'DOES_NOT_CONTAIN_EXACTLY', 'IS_NOT_EQUAL_TO') else f'{v} only')
        elif f.get('filterType') == 'IN_LIST' and f.get('operator') == 'NOT_IN_LIST':
            notes.add(f'not on list "{describe.LIST_NAMES.get(str(f.get("listId")), f.get("listId"))}"')
    kids = fb.get('filterBranches', [])
    if kids and fb.get('filterBranchType') == 'OR':
        got = []
        for b in kids:
            n2 = set()
            got += [x for x in _conds(b, tiers, n2) if x not in got]
            notes |= n2 if len(kids) == 1 else set()
        tiers = [x for x in tiers if x in got]
    else:
        for b in kids:
            tiers = _conds(b, tiers, notes)
    return tiers


def _who(f):
    kind, v = rules.owner_spec(f)
    if kind == 'property':
        return OWNER_SHORT.get(v) or describe.plabel(v)
    if kind == 'static':
        return describe.OWN.get(str(v), f'user {v}')
    return 'No owner'


def task_list_entry(tt):
    groups = []
    for wid in tt['workflows']:
        mc = (M.get(wid) or {}).get('cfg')
        if not mc:
            continue
        notes = set()
        base = _conds(mc.get('enrollmentCriteria', {}).get('listFilterBranch'), list(TIER_ALL), notes)
        acts = {a['actionId']: a for a in mc.get('actions', [])}
        per = {}                                       # (tier, conditions on the path) -> owners in branch order
        def visit(aid, tiers, nts, seen):
            while aid and aid in acts and aid not in seen:
                seen = seen | {aid}
                a = acts[aid]
                k = describe.akind(a)
                if k == 'LIST_BRANCH':
                    for b in a.get('listBranches', []):
                        n2 = set(nts)
                        t2 = _conds(b.get('filterBranch'), tiers, n2)
                        visit(b.get('connection', {}).get('nextActionId'), t2, frozenset(n2), seen)
                    if a.get('defaultBranch'):
                        visit(a['defaultBranch'].get('nextActionId'), tiers, nts, seen)
                    return
                if k in ('STATIC_BRANCH', 'AB_TEST_BRANCH'):
                    for b in a.get('staticBranches', []) + ([a['defaultBranch']] if a.get('defaultBranch') else []):
                        visit((b.get('connection') or b).get('nextActionId'), tiers, nts, seen)
                    return
                if k == '0-3' and re.search(tt['title'], rules.norm(a.get('fields', {}).get('subject')), re.I):
                    w = _who(a.get('fields', {}))
                    for x in (tiers if TIER_ALL else ['*']):
                        lst = per.setdefault((x, tuple(sorted(nts))), [])
                        if w not in lst:
                            lst.append(w)
                aid = a.get('connection', {}).get('nextActionId')
        visit(mc.get('startActionId'), base, frozenset(notes), frozenset())
        by = {}
        for (x, nts), ws in per.items():
            by.setdefault((', else '.join(ws), nts), []).append(x)
        opts = ((describe.PROPS.get('companies') or {}).get(TIER_PROP) or {}).get('options', {})
        order = {x: i for i, x in enumerate(TIER_ALL or ['*'])}
        for (who, nts), ts in sorted(by.items(), key=lambda kv: (min(order.get(x, 99) for x in kv[1]), kv[0][1])):
            ts = sorted(set(ts), key=lambda x: order.get(x, 99))
            tiers = 'All tiers' if (not TIER_ALL or set(ts) == set(TIER_ALL)) else ', '.join(opts.get(x, x) for x in ts)
            groups.append({'workflow': wid, 'workflow_name': wfname(wid), 'frequency': _freq(mc), 'kind': _kind(mc), 'trigger': describe.trigger_text(mc) if not mc.get('enrollmentSchedule') else '',
                           'tiers': tiers, 'tier_list': [opts.get(x, x) for x in ts] if TIER_ALL else [], 'notes': list(nts), 'who': who, 'off': not mc.get('isEnabled')})
        if not by:
            groups.append({'workflow': wid, 'workflow_name': wfname(wid), 'frequency': _freq(mc), 'kind': _kind(mc), 'trigger': '', 'tiers': 'No task action found', 'tier_list': [], 'notes': [], 'who': '', 'off': not mc.get('isEnabled')})
    return {'type': tt['name'], 'groups': groups}


TASK_LIST = [task_list_entry(tt) for tt in TYPES]
TIER_COLUMNS = [(((describe.PROPS.get('companies') or {}).get(TIER_PROP) or {}).get('options', {})).get(x, x) for x in TIER_ALL]

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

PRE_KNOWN = collections.Counter(r['source'] for r in PRE_MAIN if isinstance(r['flow'], str) and r['flow'].startswith('not_readable'))
BEFORE_START = None
if CUTOFF:
    BEFORE_START = {
        'title': BEFORE.get('title') or f'Made before {CUTOFF.isoformat()}', 'note': BEFORE.get('note', ''),
        'window': [FIRST.isoformat(), (CUTOFF - dt.timedelta(days=1)).isoformat()], 'cutoff': CUTOFF.isoformat(),
        'main_tasks': len(PRE_MAIN), 'types': PRE_TYPES, 'problems': PRE_PROBLEMS,
        'not_flagged': sum(len(t['shouldnt']) for t in PRE_TYPES),
        'known': [f'{n} task(s) from "{src}" (known issue {next((x.get("known_issue", "") for x in TEAM.get("not_readable", []) if x["name"] == src), "")})' for src, n in PRE_KNOWN.items()]
                 + [f'{n} task(s) with no company (known issue {k})' for k, n in PRE_KNOWN_LINKS.items()],
        'tasks_by_workflow': dict(collections.Counter(wfname(r['flow']) if r['flow'] in M else r['source'] for r in PRE_MAIN)),
        'old_names': dict(collections.Counter(r['old_name'] for r in PRE_MAIN + MAIN if r.get('old_name'))),
    }

if TF:
    rc_wf = next((c.get('workflow') for c in TEAM.get('record_checks') or []), None)
    for tid, t in TICKETS.items():
        if TF.get('pipelines') and t['properties'].get('hs_pipeline') not in TF['pipelines']:
            continue                          # e.g. a ticket in another pipeline that a task was linked to by hand
        cd = P(t['properties'].get('createdate'))
        if not cd or local(cd).date() > LAST or local(cd).date() < FIRST or (not CUTOFF and TEAM.get('start_date') and local(cd).date().isoformat() < TEAM['start_date']):
            continue
        fac = facility_of(tid)
        TICKET_DAYS.append({'date': local(cd).date().isoformat(), 'time': local(cd).strftime('%H:%M'), 'kind': 'created', 'type': 'New onboarding ticket',
                            'workflow': rc_wf, 'workflow_name': wfname(rc_wf) if rc_wf else '', 'ticket': tid,
                            'ticket_name': t['properties'].get('subject') or f'ticket {tid}', 'company_id': fac,
                            'status': 'ok' if fac or (TEAM.get('process_issues') or {}).get('company_before_stage') else 'bad',
                            'detail': 'ticket created' if fac else ('ticket created; no company yet, which is expected until it moves to the stage where the company is required'
                                                                    if (TEAM.get('process_issues') or {}).get('company_before_stage') else 'ticket created, no company linked now')})
    TICKET_DAYS.sort(key=lambda x: (x['date'], x['time']))

RESULT = {
    'team': TEAM_NAME, 'team_slug': rules.team_slug(A.team), 'decision_owner': OWNER, 'portal': str(ACCT.get('portalId', '')), 'queue': TEAM.get('queue_name'), 'queue_ids': sorted(QIDS),
    'window': [FIRST.isoformat(), LAST.isoformat()], 'report_day': rules.report_day(TEAM, LAST).isoformat(), 'time_zone': ACCT.get('timeZone'),
    'fetched_at': fmt_dt(NOW), 'start_date': TEAM.get('start_date'),
    'excluded_companies': [{'id': k, 'name': v.get('name'), 'reason': v.get('reason')} for k, v in EXCLUDED.items()],
    'excluded_tasks': EXCLUDED_TASKS,
    'counts': {'facilities_in_scope': in_scope_count, 'main_tasks': len(MAIN), 'subtasks': len(SUBS), 'workflows': len(M),
               'q1': q_counts[1], 'q2': q_counts[2], 'q3': q_counts[3]},
    'top': TOP, 'types': TYPE_RESULTS, 'record_checks': RECORD_CHECKS, 'ticket_days': TICKET_DAYS,
    'process_issues': [{k: v for k, v in x.items() if k != 'key'} for x in PROC], 'by_design': list(BY_DESIGN.values()), 'process_heading': f'Process issues for the {TEAM_NAME} team', 'process_stages_note': (TEAM.get('process_issues') or {}).get('stages_note'), 'new_facilities': NEW, 'links': LINK_ROWS, 'subtasks': SUB_ROWS, 'changes': CHANGES,
    'schedules': SCHEDULES, 'task_list': TASK_LIST, 'tier_columns': TIER_COLUMNS, 'switched_off': SWITCHED_OFF, 'before_start': BEFORE_START, 'known_days': [{'date': d, 'type': t, 'known_issue': k, 'tasks': n} for (d, t, k), n in sorted(KNOWN_DAYS.items())],
    'waiting_on': waiting, 'known_issues': known, 'expected_off': off_state, 'problems': PROBLEMS,
    'companies': {cid: cname(cid) for cid in {x for tr in TYPE_RESULTS + PRE_TYPES for x in tr['should'] + tr['got'] + list(tr['missing']) + list(tr['shouldnt'])} | {c for r in MAIN + PRE_MAIN for c in r['companies']} | LIVE_NOW | {e['company_id'] for e in TICKET_DAYS if e['company_id']}},
    'tasks': [{'id': r['id'], 'title': r['title'], 'type': r['type'], 'workflow': wfname(r['flow']) if r['flow'] in M else r['source'],
               'workflow_id': r['flow'] if r['flow'] in M else None, 'created': fmt_dt(r['created']),
               'due': fmt_dt(r['due']) if r['due'] else '', 'companies': r['companies'], 'link': r.get('link'), 'in_queue': r['in_queue'],
               'before_start': r['before_start']} for r in MAIN + PRE_MAIN],
}
json.dump(RESULT, open(os.path.join(A.work, 'results.json'), 'w'), indent=1, default=str)

line = lambda n, what: 'all good' if n == 0 else f'{n} problem{"s" if n > 1 else ""} found'
print(f'## {TEAM_NAME} weekly audit — {FIRST} to {LAST}' + (' (window shortened by the start date)' if FIRST.isoformat() == TEAM.get('start_date') else ''))
if EXCLUDED:
    print(f'Excluded from the audit: ' + '; '.join(f'{v.get("name") or k} ({k}): {v.get("reason")}' for k, v in EXCLUDED.items()) + (f' ({EXCLUDED_TASKS} task(s) linked only to them not checked)' if EXCLUDED_TASKS else ''))
print(f'Checked {in_scope_count} ' + ('facilities with an open ticket in the team pipeline' if TF and TICKET_TYPES == set(TYPE_NAMES) else f'companies in scope ({(TEAM.get("company_scope") or {}).get("description", "all companies")})') + f', {len(MAIN)} main tasks and {len(SUBS)} subtasks created in the window, and {len(M)} workflows.\n')
print(f'1. **Were the tasks created?** {line(q_counts[1], "")}' + (f' ({len(NEW)} new facilit{"y" if len(NEW) == 1 else "ies"} this week)' if NEW else ''))
for rc_ in RECORD_CHECKS:
    nm_ = sum(1 for r_ in rc_['records'] if r_['status'] != 'ok')
    print(f'   - {rc_["name"]}: {len(rc_["records"])} checked, ' + ('all good' if not nm_ else f'{nm_} without one'))
print(f'2. **Are they associated with the right company?** {line(q_counts[2], "")}')
print(f'3. **Did anyone change the workflows?** ' + ('no changes' if not q_counts[3] else f'{sum(1 for c in CHANGES if c["status"] != "same")} workflow(s) differ from the master rules file'))
if TOP:
    print('\n**Top problems**')
    for i, t in enumerate(TOP, 1):
        print(f'{i}. {t["text"]} [{t["label"]}]')
if TF and (TEAM.get('process_issues') or {}).get('company_before_stage'):
    print(f'\n**Process issues for the {TEAM_NAME} team** (a ticket moved to a stage before its company was associated)')
    if not PROC:
        print('- None')
    for x in PROC:
        print(f'- {x["ticket_name"]} (ticket {x["ticket"]}): moved to {x["stage"]} on {x["moved"]}' + (f' by {x["moved_by"]}' if x['moved_by'] else '')
              + (f'; company associated {x["linked"]} ({x["seconds_after"]} s later)' if x['linked'] else '; no company associated yet')
              + f'. {x["tasks_without_company"]} of {x["tasks"]} tasks and {x["subtasks_without_company"]} of {x["subtasks"]} subtasks have no company'
              + (f'; main tasks fixed by hand on {x["fixed_by_hand"]}' if x['fixed_by_hand'] else '') + (' (before the start date)' if x['section'] == 'before_start' else '') + '. [VERIFIED (records)]')
if BY_DESIGN:
    print('\n**By design, not problems**')
    for x in BY_DESIGN.values():
        print(f'- {x["type"]}: {x["ticket_name"]} (ticket {x["ticket"]}): {x["tasks"]} task(s) and {x["subtasks"]} subtask(s) created without a company. Why: {x["reason"]}'
              + (f' (main tasks were also given the company by hand on {x["fixed_by_hand"]})' if x['fixed_by_hand'] else ''))
print('\n**Known issues** (reported once)')
for k in known:
    print(f'- {k["id"]}: {k["text"]}' + (f' This week: {k["this_week"]}' if k.get('this_week') else ''))
if BEFORE_START:
    pm = [p for p in PRE_PROBLEMS]
    print(f'\n**{BEFORE_START["title"]}** ({BEFORE_START["window"][0]} to {BEFORE_START["window"][1]}): {len(PRE_MAIN)} main tasks found through their workflows; '
          + (f'{len(pm)} real problem(s).' if pm else 'no real problems.') + (f' {BEFORE_START["not_flagged"]} task(s) made under the old settings shown but not flagged.' if BEFORE_START['not_flagged'] else ''))
    for t in PRE_TYPES:
        if t['runs']:
            fl = [m for m in t['missing'].values() if not m.get('not_flagged')]
            nf = collections.Counter(m['reason'] for m in t['missing'].values() if m.get('not_flagged'))
            print(f'- {t["name"]}: {len(t["got"])} of {len(t["should"])} got it' + (f'; {len(fl)} real problem(s)' if fl else '; no real problems')
                  + ''.join(f'; {n} {r}' for r, n in nf.items()))
print(f'\n**Waiting on {OWNER}**')
if not waiting:
    print('- None')
for w in waiting:
    print(f'- {w["id"]} {w["title"]}' + (f' — this week: ' + (w.get('summary') or '; '.join(f.get('reason') or f.get('company') or '' for f in w['found'][:3])) if w.get('found') else ''))
print(f'\nresults: {os.path.join(A.work, "results.json")}')
