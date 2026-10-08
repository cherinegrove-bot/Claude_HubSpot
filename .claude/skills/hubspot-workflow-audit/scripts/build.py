#!/usr/bin/env python3
"""Build the workflow-audit workbook from the data fetch.py saved.

Usage:
  python3 build.py --work DIR --team "Transitions" --out audits/transitions-workflow-audit/WLS_Transitions_Workflow_Audit.xlsx \
                   [--findings findings.json]

findings.json (optional, written by Claude after reviewing the auto output):
  {"suppress": ["A13"],                      # auto-finding keys to drop (key shown in the Notes column)
   "findings": [{"classification": "Potential Issue", "workflow": "...", "action": "Step 3",
                 "finding": "...", "evidence": "...", "why": "...", "verify": "..."}],
   "process_notes": ["optional extra lines for the Read Me sheet"]}
Every statement in the workbook carries an evidence label: VERIFIED (config), VERIFIED (records), INFERENCE, NEEDS VERIFICATION.
"""
import argparse, collections, datetime as dt, html, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rules
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.properties import CalcProperties

ap = argparse.ArgumentParser()
ap.add_argument('--work', required=True)
ap.add_argument('--team', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--findings')
ap.add_argument('--portal', default='45059701')
ap.add_argument('--template', action='store_true', help='only the 5 core sheets (Process Overview, Detailed Action Map, Task & Subtask Logic, Workflow Inventory, Audit Findings), no Source column')
ap.add_argument('--include-team-practice', action='store_true', help='also report overdue tasks and titles changed since creation')
A = ap.parse_args()
W = lambda n, d=None: json.load(open(os.path.join(A.work, n))) if os.path.exists(os.path.join(A.work, n)) else d

if not os.path.exists(os.path.join(A.work, 'COMPLETE')):
    sys.exit(f'STOP: {A.work} is incomplete (fetch.py did not finish). Re-run fetch.py - no workbook was produced.')
CFG = W('configs.json', {})
DENIED = W('denied.json', [])
ALL_TASKS = W('tasks.json', [])
TASKS = [t for t in ALL_TASKS if t.get('_flow') in CFG]
OTHER_TASKS = [t for t in ALL_TASKS if t.get('_flow') not in CFG]
SCOPE = W('scope.json', {})
COMPANIES = {c['id']: c for c in W('companies.json', [])}
_excl = {str(x['id']) for x in ((rules.load_team(A.team)[1] or {}).get('excluded_companies') or [])}
COMPANIES = {k: v for k, v in COMPANIES.items() if k not in _excl}      # companies the team excludes from every audit (team-rules.md)
LISTS = W('lists.json', {})
LIST_NAMES = W('list_names.json', {})
HIST = W('history_tasks.json', [])
TEAM_NAME, TEAM = rules.load_team(A.team)
TRULES = (TEAM or {}).get('rules', {}) or {}
SINCE = SCOPE.get('since')
QIDS = set(SCOPE.get('queue_ids') or [])
TASSOC = W('task_assoc.json', {})
TICKETS = {t['id']: t for t in W('tickets.json', [])}
TKASSOC = W('ticket_assoc.json', {})
PIPES = W('pipelines.json', {})
LABELS = W('assoc_labels.json', {})
PROPS = W('properties.json', {})
WATCHED = W('watched_tasks.json', {})
WASSOC = W('watched_assoc.json', {})
ACCT = W('account.json', {})
OWNERS = W('owners.json', [])
NOW = dt.datetime.now(dt.timezone.utc)
AS_OF = NOW.strftime('%Y-%m-%d')
PORTAL = A.portal
TURL = lambda i: f'https://app.hubspot.com/contacts/{PORTAL}/record/0-5/{i}'
WURL = lambda i: f'https://app.hubspot.com/workflows/{PORTAL}/platform/flow/{i}/edit'
P = lambda s: dt.datetime.fromisoformat(s.replace('Z', '+00:00')) if s else None
try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo(ACCT.get('timeZone', 'UTC'))
except Exception:
    TZ = dt.timezone(dt.timedelta(milliseconds=ACCT.get('utcOffsetMilliseconds', 0)))
TZNAME = ACCT.get('timeZone', 'UTC')

# ------------------------------------------------------------------ lookups
OWN = {str(o['id']): ((o.get('firstName', '') + ' ' + o.get('lastName', '')).strip() or o.get('email', str(o['id']))) for o in OWNERS}
ARCHIVED = {str(o['id']) for o in OWNERS if o.get('archived')}
STAGE, STAGE_ORDER, PIPE = {}, {}, {}
for obj, ps in PIPES.items():
    for p in ps:
        PIPE[p['id']] = p['label']
        for s in p['stages']:
            STAGE[s['id']] = s['label'] if obj == 'tickets' else f'{s["label"]} ({p["label"]})'
            STAGE_ORDER[s['id']] = (p['id'], s['displayOrder'])
OBJ = {'0-1': 'Contact', '0-2': 'Company', '0-3': 'Deal', '0-5': 'Ticket', '0-27': 'Task', '0-53': 'Invoice'}
ASSOC = {}
for pair, ls in LABELS.items():
    a, b = [OBJ.get(x, x) for x in ({'tickets': '0-5', 'contacts': '0-1', 'companies': '0-2', 'deals': '0-3', 'tasks': '0-27'}[y] for y in pair.split('/'))]
    for l in ls:
        ASSOC.setdefault(l['typeId'], f'{a} -> {b}' + (f', label "{l["label"]}"' if l.get('label') else ' (all)'))


def plabel(name):
    for obj in ('tickets', 'deals', 'companies', 'contacts', 'tasks'):
        if name in PROPS.get(obj, {}):
            return PROPS[obj][name]['label']
    return name


def pval(name, v):
    if v is None:
        return ''
    if name in ('hs_pipeline_stage', 'dealstage'):
        return STAGE.get(v, v)
    if name in ('hs_pipeline', 'pipeline'):
        return PIPE.get(v, v)
    if name == 'hubspot_owner_id':
        return OWN.get(str(v), v)
    if isinstance(v, str) and '{{' in v:
        return f'(template) {v}'
    for obj in ('tickets', 'deals', 'companies', 'contacts', 'tasks'):
        o = PROPS.get(obj, {}).get(name, {}).get('options', {})
        if str(v) in o:
            return o[str(v)]
    return {'true': 'Yes', 'false': 'No'}.get(str(v), v)


OPS = {'IS_KNOWN': 'is known', 'IS_UNKNOWN': 'is unknown', 'IS_ANY_OF': 'is any of', 'IS_NONE_OF': 'is none of', 'IS_EQUAL_TO': 'is equal to',
       'IS_NOT_EQUAL_TO': 'is not equal to', 'CONTAINS': 'contains', 'CONTAINS_EXACTLY': 'contains exactly', 'IS_AFTER': 'is after', 'IS_BEFORE': 'is before',
       'IS_GREATER_THAN': 'is greater than', 'IS_LESS_THAN': 'is less than', 'IN_LIST': 'is in list', 'NOT_IN_LIST': 'is not in list'}


def filt(fb):
    if not fb:
        return ''
    parts = []
    for f in fb.get('filters', []):
        if f.get('filterType') == 'IN_LIST' or 'listId' in f:
            parts.append(f'record is {"in" if f.get("operator") != "NOT_IN_LIST" else "not in"} list {f.get("listId")}')
            continue
        op = f.get('operation', {})
        vals = op.get('values') or ([op['value']] if 'value' in op else [])
        prop = f.get('property', '?')
        parts.append(f'{plabel(prop)} {OPS.get(op.get("operator"), str(op.get("operator", "")).lower())}' + (f' {", ".join(str(pval(prop, v)) for v in vals)}' if vals else ''))
    for sub in fb.get('filterBranches', []):
        inner = filt(sub)
        if sub.get('filterBranchType') == 'ASSOCIATION':
            inner = f'an associated {OBJ.get(sub.get("objectTypeId"), "record").lower()} where {inner}'
        if inner:
            parts.append(f'({inner})' if len(fb.get('filterBranches', [])) > 1 else inner)
    j = ' OR ' if fb.get('filterBranchType') == 'OR' else ' AND '
    return j.join(p for p in parts if p)


def supp_text(cfg):
    sb = rules.suppression(cfg)
    if not sb:
        return None
    t = filt(sb)
    for lid, nm in LIST_NAMES.items():
        t = t.replace(f'list {lid}', f'list {lid} "{nm}"')
    return t


def event_filt(eb):
    out = []
    for b in eb:
        fs = {f['property']: f['operation'] for f in b.get('filters', [])}
        if 'hs_name' in fs:
            prop = fs['hs_name'].get('value')
            vop = fs.get('hs_value', {})
            vals = vop.get('values') or ([vop['value']] if 'value' in vop else [])
            out.append(f'{plabel(prop)} changes' + (f' to {", ".join(str(pval(prop, v)) for v in vals)}' if vals else (' (any new value)' if vop.get('operator') == 'IS_KNOWN' else '')))
        else:
            out.append(f'event {b.get("eventTypeId")} occurs' + (f' where {filt(b)}' if b.get('filters') else ''))
    return ' OR '.join(out)


def trigger_text(e):
    t = e.get('type')
    if t == 'LIST_BASED':
        return 'Records meet custom conditions (filter-based)', filt(e.get('listFilterBranch'))
    if t == 'EVENT_BASED':
        s = event_filt(e.get('eventFilterBranches', []))
        if e.get('refinementCriteria'):
            s += ', AND ' + filt(e['refinementCriteria'])
        return 'Event trigger', s
    if t == 'MANUAL':
        return 'Manual enrollment only', 'Records are enrolled by hand (no automatic trigger)'
    return t or 'Unknown', json.dumps(e)[:300]


def strip(h):
    t = re.sub(r'<\s*(li|p|br)[^>]*>', '\n', h or '')
    t = html.unescape(re.sub(r'<[^>]+>', '', t))
    return re.sub(r'\n\s*\n+', ' | ', t).replace('\n', ' ').strip(' |')


def owner_rule(f):
    v = f.get('owner_assignment', {}).get('value', {})
    if v.get('type') == 'OBJECT_PROPERTY':
        return f'Record\'s {plabel(v.get("propertyName"))} (copied from the enrolled record)', None, None
    if v.get('type') == 'STATIC_VALUE':
        sid = str(v['staticValue'])
        return f'{OWN.get(sid, "Owner ID " + sid)} (fixed user)', OWN.get(sid, sid), sid
    return 'No owner set', None, None


def due_rule(f):
    d = f.get('due_time')
    if not d:
        return 'No due date set', None
    bd = len(d.get('daysOfWeek', [])) == 5
    t = d.get('timeOfDay', {})
    return f'{d.get("delta")} {"business " if bd else ""}day(s) after creation at {t.get("hour", 0):02d}:{t.get("minute", 0):02d} ({TZNAME})', d.get('delta')


def assoc_rule(f):
    out = []
    for x in f.get('associations', []):
        tgt = ASSOC.get(x['target']['associationTypeId'], f'type {x["target"]["associationTypeId"]}').split(' -> ')[-1].split(',')[0].replace(' (all)', '')
        if x['value']['type'] == 'ENROLLED_OBJECT':
            out.append(f'{tgt}: the enrolled record')
        else:
            src = ASSOC.get(x['value'].get('sourceSpec', {}).get('associationTypeId'), str(x['value'].get('sourceSpec')))
            out.append(f'{tgt}: copied from enrolled record\'s associations ({src})')
    return '; '.join(out) or 'None'


ATYPE = {'0-1': 'Delay', '0-35': 'Delay until a date', '0-3': 'Create task', '0-4': 'Send marketing email', '0-5': 'Edit record (set property value)',
         '0-8': 'Send internal email notification', '0-14': 'Create record', '0-15': 'Enroll in another workflow', '0-29': 'Wait for event / condition',
         '0-31': 'Set marketing contact status', '0-63863438': 'Add to static list', '0-63189541': 'Create association', '0-73444249': 'Apply association label',
         '1-179507819': 'Send Slack notification (app action)', '1-2796901': 'Google Sheets row (app action)', 'CUSTOM_CODE': 'Custom code',
         'WEBHOOK': 'Send webhook', 'LIST_BRANCH': 'If/then branch', 'STATIC_BRANCH': 'Branch on one property value', 'AB_TEST_BRANCH': 'A/B test branch'}


def akind(a):
    return a.get('actionTypeId') or a.get('type')


def describe(a):
    """(what it does, object, property/record, new value)"""
    f = a.get('fields', {})
    k = akind(a)
    if k == '0-3':
        o, _, _ = owner_rule(f)
        d, _ = due_rule(f)
        return (f'Creates task "{(f.get("subject") or "").strip()}" for {o.split(" (")[0]}, due {d.split(" (")[0]}.', 'Task', f'New task "{(f.get("subject") or "").strip()}"',
                f'Title: {(f.get("subject") or "").strip()} | Type: {f.get("task_type")} | Priority: {f.get("priority")} | Owner: {o} | Due: {d} | Associations: {assoc_rule(f)} | Queue: {f.get("queue_id", "none")}')
    if k == '0-5':
        tgt = 'the associated record (' + ASSOC.get(f['association']['associationTypeId'], '?') + ')' if f.get('association') else 'the enrolled record'
        v = f.get('value', {})
        nv = pval(f.get('property_name'), v.get('staticValue')) if v.get('type') == 'STATIC_VALUE' else ('time the action runs' if v.get('type') == 'TIMESTAMP' else json.dumps(v)[:120])
        return f'Sets {plabel(f.get("property_name"))} = {nv} on {tgt}.', tgt, plabel(f.get('property_name')), nv
    if k == '0-14':
        props = '; '.join(f'{plabel(p["targetProperty"])} = {pval(p["targetProperty"], p["value"].get("staticValue") or p["value"].get("propertyName"))}' for p in f.get('properties', []))
        return f'Creates a {OBJ.get(f.get("object_type_id"), f.get("object_type_id"))}: {props}. Associations: {assoc_rule(f)}.', OBJ.get(f.get('object_type_id'), '?'), 'New record', props
    if k in ('0-1',):
        mins = int(f.get('delta', 0)) if f.get('time_unit') == 'MINUTES' else None
        return (f'Waits {f.get("delta")} {f.get("time_unit", "").lower()}' + (f' (= {mins / 1440:g} days)' if mins else '') + '.'), '-', '-', '-'
    if k == '0-35':
        d = f.get('date', {})
        when = dt.datetime.fromtimestamp(int(d['staticValue']) / 1000, dt.timezone.utc).strftime('%Y-%m-%d') if d.get('type') == 'STATIC_VALUE' else d.get('propertyName', json.dumps(d)[:80])
        return f'Waits until {when} (+{f.get("delta")} {f.get("time_unit", "").lower()}) at {f.get("time_of_day", {}).get("hour", 0):02d}:{f.get("time_of_day", {}).get("minute", 0):02d}.', '-', '-', '-'
    if k == '0-8':
        return f'Emails users {", ".join(OWN.get(u, u) for u in f.get("user_ids", []))}: "{f.get("subject")}".', 'Internal email', '-', strip(f.get('body', ''))[:300]
    if k == '0-15':
        return f'Enrolls the record in workflow {f.get("flow_id")}.', 'Workflow', f.get('flow_id'), '-'
    if k == '0-4':
        return f'Sends marketing email (content ID {f.get("content_id")}).', 'Email', f.get('content_id'), '-'
    if k == '0-29':
        return f'Waits for: {event_filt(f.get("event_filter_branches", []))}' + (f' (max {f.get("expiration_minutes")} min)' if f.get('expiration_minutes') else '') + '.', '-', '-', '-'
    if k == '1-179507819':
        return f'Slack message to {", ".join(f.get("slackUserIds", []) or f.get("channelIds", []) or ["?"])}: "{(f.get("message") or "")[:200]}".', 'Slack', '-', '-'
    if k == 'LIST_BRANCH':
        bs = '; '.join(f'"{b.get("branchName")}": {filt(b.get("filterBranch"))}' for b in a.get('listBranches', []))
        return f'Checks, in order: {bs}. Otherwise: {"default branch" if a.get("defaultBranch") else "no default branch (workflow ends)"}.', '-', '-', '-'
    if k == 'STATIC_BRANCH':
        iv = a.get('inputValue', {})
        src = iv.get('propertyName') or re.sub(r'.*\.(\w+) }}$', r'\1', iv.get('propertyToken', '')) or f'output of step with action ID {iv.get("actionId")}'
        bs = '; '.join(str(b.get('branchValue')) for b in a.get('staticBranches', []))
        return f'Branches on {plabel(src)}: {bs}; anything else -> {"default branch" if a.get("defaultBranch") else "ends"}.', '-', plabel(src), '-'
    return f'{ATYPE.get(k, "Action type " + str(k))}. Fields: {json.dumps(f)[:300]}', '-', '-', '-'


def walk(cfg):
    """Editor-order list of (action | marker, branch path). Markers: {'_end'}, {'_goto': id}."""
    acts = {a['actionId']: a for a in cfg.get('actions', [])}
    out, seen = [], set()

    def visit(aid, br):
        while aid:
            if aid in seen:
                out.append(({'_goto': aid}, br))
                return
            seen.add(aid)
            a = acts[aid]
            out.append((a, br))
            k = akind(a)
            if k == 'LIST_BRANCH':
                for b in a.get('listBranches', []):
                    visit(b.get('connection', {}).get('nextActionId'), (br + ' > ' if br else '') + f'"{b.get("branchName")}"')
                if a.get('defaultBranch'):
                    visit(a['defaultBranch'].get('nextActionId'), (br + ' > ' if br else '') + f'"{a.get("defaultBranchName", "None met")}"')
                else:
                    out.append(({'_end': True}, (br + ' > ' if br else '') + 'None met'))
                return
            if k in ('STATIC_BRANCH', 'AB_TEST_BRANCH'):
                for b in a.get('staticBranches', []):
                    visit(b.get('connection', {}).get('nextActionId'), (br + ' > ' if br else '') + f'= {b.get("branchValue")}')
                if a.get('defaultBranch'):
                    visit(a['defaultBranch'].get('nextActionId'), (br + ' > ' if br else '') + 'any other value')
                return
            aid = a.get('connection', {}).get('nextActionId')
        out.append(({'_end': True}, br))

    if cfg.get('startActionId'):
        visit(cfg['startActionId'], '')
    else:
        out.append(({'_end': True}, ''))
    return out


# ------------------------------------------------------------------ records
def bdays(a, b):
    n, d, step = 0, a, (1 if b >= a else -1)
    while d != b:
        d += dt.timedelta(days=step)
        if d.weekday() < 5:
            n += step
    return n


for t in TASKS:
    p = t['properties']
    m = re.match(r'enrollmentId:(\d+);actionExecutionIndex:(\d+)', p.get('hs_object_source_id') or '')
    t['enr'], t['idx'] = (m.group(1), int(m.group(2))) if m else (None, None)
    t['c'], t['due'] = P(p['hs_createdate']), P(p.get('hs_timestamp'))
    a = TASSOC.get(t['id'], {})
    t['tickets'] = [x['id'] for x in a.get('tickets', [])]
    t['companies'] = [x['id'] for x in a.get('companies', [])]
    t['contacts'] = [x['id'] for x in a.get('contacts', [])]
    t['deals'] = [x['id'] for x in a.get('deals', [])]
    t['sub'] = p.get('hs_task_is_sub_task') == 'true'
    t['open'] = p.get('hs_task_status') not in ('COMPLETED', 'DEFERRED')
    if t['due']:
        cd, dd = t['c'].astimezone(TZ).date(), t['due'].astimezone(TZ)
        t['bd'], t['time'] = bdays(cd, dd.date()), dd.strftime('%H:%M')
    else:
        t['bd'] = t['time'] = None
BYFLOW = collections.defaultdict(list)
for t in TASKS:
    BYFLOW[t['_flow']].append(t)
BYID = {t['id']: t for t in TASKS}
norm = lambda s: re.sub(r'\s+', ' ', (s or '').strip()).lower()


def cnt(c, n):
    return '; '.join(f'{k} {v}/{n}' for k, v in c.most_common())


def assoc_pat(t):
    return ' + '.join(x for x, y in (('Ticket', t['tickets']), ('Company', t['companies']), ('Contact', t['contacts']), ('Deal', t['deals'])) if y) or '(none)'


def enrollments(wid):
    e = collections.defaultdict(list)
    for t in BYFLOW[wid]:
        e[t['enr']].append(t)
    return e


def stage_trigger(cfg):
    """Ticket stage a LIST_BASED ticket workflow fires in (single stage), else None."""
    if cfg.get('objectTypeId') != '0-5' or cfg['enrollmentCriteria'].get('type') != 'LIST_BASED':
        return None
    st = re.findall(r'"hs_pipeline_stage", "operation": \{[^}]*?"values": \["(\d+)"\]', json.dumps(cfg['enrollmentCriteria']))
    return st[0] if len(st) == 1 else None


def match_parents(wid, cfg):
    """Create-task action id -> list of parent task records it produced (title match; owner breaks ties; else exec index)."""
    acts = [a for a in cfg.get('actions', []) if akind(a) == '0-3']
    parents = [t for t in BYFLOW[wid] if not t['sub']]
    res = {a['actionId']: [] for a in acts}
    linear = []
    aid, amap = cfg.get('startActionId'), {a['actionId']: a for a in cfg.get('actions', [])}
    while aid and akind(amap[aid]) not in ('LIST_BRANCH', 'STATIC_BRANCH', 'AB_TEST_BRANCH'):
        linear.append(aid)
        aid = amap[aid].get('connection', {}).get('nextActionId')
    unmatched = []
    for t in parents:
        title = norm(t['properties']['hs_task_subject'])
        cands = [a for a in acts if norm(a['fields'].get('subject')) == title]
        if len(cands) > 1:
            cands = [a for a in cands if owner_rule(a['fields'])[2] in (None, t['properties'].get('hubspot_owner_id'))] or cands
        if not cands and t['idx'] is not None and t['idx'] < len(linear) and akind(amap[linear[t['idx']]]) == '0-3':
            cands = [amap[linear[t['idx']]]]
        if cands:
            for a in cands:
                res[a['actionId']].append(t)
            t['_shared'] = len(cands) > 1
        else:
            unmatched.append(t)
    return res, unmatched, linear


# ------------------------------------------------------------------ connections between workflows
writes, reads = [], []
for wid, c in CFG.items():
    for a in c.get('actions', []):
        f = a.get('fields', {})
        if akind(a) == '0-5':
            writes.append((wid, a['actionId'], f.get('property_name'), f.get('value', {}).get('staticValue')))
        if akind(a) == '0-14':
            for p in f.get('properties', []):
                writes.append((wid, a['actionId'], p['targetProperty'], p['value'].get('staticValue')))
        if akind(a) == '0-3':
            writes.append((wid, a['actionId'], 'hs_task_subject', (f.get('subject') or '').strip()))
    ec = c.get('enrollmentCriteria', {})
    parts = [('trigger', json.dumps({k: v for k, v in ec.items() if k != 'refinementCriteria'})), ('condition', json.dumps(ec.get('refinementCriteria', {})))]
    for kind, s in parts:
        for m in re.finditer(r'"property": "(\w+)", "operation": \{([^}]*)\}', s):
            prop, body = m.group(1), m.group(2)
            if prop in ('hs_name', 'hs_value'):
                continue
            vals = re.findall(r'"values": \[([^\]]*)\]', body) + re.findall(r'"value": "([^"]*)"', body)
            vs = [json.loads('[' + v + ']') if v.startswith('"') else [v] for v in vals]
            reads.append((wid, prop, sorted({str(x) for v in vs for x in v}), kind))
        for m in re.finditer(r'"hs_name", "operation": \{[^}]*"value": "(\w+)"', s):
            reads.append((wid, m.group(1), [], kind))
ALL_LINKS = []
for (w1, aid, prop, v) in writes:
    for (w2, rprop, rvals, kind) in reads:
        if w1 == w2 or prop != rprop:
            continue
        if not rvals or (v is not None and str(v).strip() in [x.strip() for x in rvals]):
            ALL_LINKS.append((w1, aid, w2, prop, v, kind))
ALL_LINKS = sorted(set(ALL_LINKS))
LINKS = [l[:5] for l in ALL_LINKS if l[5] == 'trigger']

# ------------------------------------------------------------------ order workflows for the process view
def sort_key(wid):
    c = CFG[wid]
    st = stage_trigger(c)
    if st:
        return (1, STAGE_ORDER.get(st, ('', 99)), c['name'])
    rf = re.findall(r'"hs_pipeline_stage", "operation": \{[^}]*?"values": \["(\d+)"\]', json.dumps(c['enrollmentCriteria'].get('refinementCriteria', {})))
    if rf:
        return (1, (STAGE_ORDER.get(rf[0], ('', 99))[0], STAGE_ORDER.get(rf[0], ('', 99))[1] + 0.5), c['name'])
    creates = any(akind(a) == '0-14' for a in c.get('actions', []))
    return (0 if creates or any(l[0] == wid for l in LINKS) else 2, ('', 0), c['name'])


ORDER = sorted(CFG, key=sort_key)
_created = {norm(v) for (w, aid, p, v) in writes if p == 'hs_task_subject'}
BROKEN = set()
for _w in CFG:
    for _v in re.findall(r'"hs_task_subject", "operation": \{[^}]*?"values": \[([^\]]*)\]', json.dumps(CFG[_w]['enrollmentCriteria'].get('refinementCriteria', {}))):
        if any(norm(t) not in _created for t in json.loads('[' + _v + ']')):
            BROKEN.add(_w)
SHORT = {w: CFG[w]['name'] for w in CFG}

# ------------------------------------------------------------------ build per-workflow rows
DAM, TS, PO, EV, MISSED, ADVEV = [], [], [], [], [], []
AUTO = {}  # key -> finding row (without number)
stats = {}
step = 0
for wid in ORDER:
    c = CFG[wid]
    e = c['enrollmentCriteria']
    ttype, ttext = trigger_text(e)
    obj = OBJ.get(c['objectTypeId'], c['objectTypeId'])
    enr = enrollments(wid)
    st = stage_trigger(c)
    deltas = []
    for k, ts in enr.items():
        start = min(t['c'] for t in ts)
        tk = TICKETS.get(ts[0]['tickets'][0]) if ts[0]['tickets'] else None
        de = P(tk['properties'].get(f'hs_v2_date_entered_{st}')) if (tk and st) else None
        d = (start - de).total_seconds() if de else None
        if d is not None:
            deltas.append(d)
        EV.append([c['name'], wid, k, ts[0]['tickets'][0] if ts[0]['tickets'] else '', tk['properties'].get('subject') if tk else '',
                   TURL(ts[0]['tickets'][0]) if ts[0]['tickets'] else '', STAGE.get(tk['properties'].get('hs_pipeline_stage'), '') if tk else '',
                   de.strftime('%Y-%m-%d %H:%M:%S UTC') if de else '', start.strftime('%Y-%m-%d %H:%M:%S UTC'), round(d, 1) if d is not None else '',
                   len(ts), sum(t['sub'] for t in ts), sum(t['open'] for t in ts)])
    stats[wid] = dict(enr=len(enr), tasks=len(BYFLOW[wid]), deltas=deltas, first=min((t['c'] for t in BYFLOW[wid]), default=None))
    trec = ''
    if enr:
        trec = f'Records: {len(enr)} enrollments that created tasks ({stats[wid]["first"]:%Y-%m-%d} to {max(t["c"] for t in BYFLOW[wid]):%Y-%m-%d}).'
        if deltas:
            ok = sum(1 for d in deltas if -60 <= d <= 900)
            trec += f' {ok}/{len(deltas)} started {min(deltas):.0f}-{max(deltas):.0f} s after the ticket entered {STAGE.get(st)}.'
    DAM.append([c['name'], wid, 'Trigger', '-', 0, 'Enrollment trigger', ttype, f'Enrolls a {obj.lower()} when: {ttext}.' + (f' EXCEPT records where {supp_text(c)} (suppression).' if supp_text(c) else '') + (f' Enrollment is {rules.schedule_text(c)}.' if rules.schedule_text(c) else ''), obj, '-', '-', ttext,
                'All listed conditions', 'None',
                f'Re-enroll: {"ON" if e.get("shouldReEnroll") else "OFF"}. Unenroll if no longer meets criteria: {"ON" if e.get("unEnrollObjectsNotMeetingCriteria") else "OFF"}. '
                f'Suppression (never enroll / unenroll): {("records where " + supp_text(c)) if supp_text(c) else "none"}.' + (f' Schedule: {rules.schedule_text(c)}.' if rules.schedule_text(c) else ''),
                'Step 1', f'Config GET /automation/v4/flows/{wid} (revision {c.get("revisionId")}, updated {c.get("updatedAt", "")[:10]}). {WURL(wid)}', trec, 'VERIFIED (config)'])
    walked = walk(c)
    num = {}
    for a, br in walked:
        if '_end' not in a and '_goto' not in a:
            num[a['actionId']] = len(num) + 1
    pm, unmatched, linear = match_parents(wid, c)
    PO.append([None, f'{obj} meets trigger', ttext + (f'. Not if: {supp_text(c)}' if supp_text(c) else '') + f'. Re-enroll {"ON" if e.get("shouldReEnroll") else "OFF"}.' + (f' {rules.schedule_text(c).capitalize()}.' if rules.schedule_text(c) else ''), c['name'], 'Enrollment trigger', trec or 'Enrolls', None])
    for a, br in walked:
        if '_end' in a:
            nxt = [l for l in LINKS if l[0] == wid]
            DAM.append([c['name'], wid, 'End', br or 'Main path', '-', 'End', 'End of workflow', 'Workflow ends for this record.', '-', '-', '-', '-', br or 'After the last action', 'None',
                        'Record leaves the workflow', '; '.join(f'Step {num.get(l[1])} sets {plabel(l[3])} = {pval(l[3], l[4])}, which {CFG[l[2]]["name"]} reacts to' for l in nxt) or 'No in-scope workflow is triggered by this workflow.',
                        'Workflow config', '', 'VERIFIED (config)'])
            continue
        if '_goto' in a:
            DAM.append([c['name'], wid, 'Go to', br, '-', 'Go to action', 'Branch rejoins', f'Continues at step {num.get(a["_goto"])}.', '-', '-', '-', '-', br, 'None', '-', f'Step {num.get(a["_goto"])}', 'Workflow config', '', 'VERIFIED (config)'])
            continue
        k = akind(a)
        f = a.get('fields', {})
        what, o2, propc, newv = describe(a)
        nx = a.get('connection', {}).get('nextActionId')
        nxt_txt = 'First action of each branch (see following rows)' if k in ('LIST_BRANCH', 'STATIC_BRANCH', 'AB_TEST_BRANCH') else (f'Step {num[nx]}' if nx in num else 'End')
        delay = 'This is a delay' if k in ('0-1', '0-35', '0-29') else 'None'
        result, notes, level = '', '', 'VERIFIED (config)'
        if k == '0-3':
            par = pm.get(a['actionId'], [])
            subs = [BYID.get(s) for p in par for s in []]
            kids = [t for t in BYFLOW[wid] if t['sub'] and t['properties'].get('hs_task_parent_task_id') in {p['id'] for p in par}]
            o_txt, o_name, o_id = owner_rule(f)
            _, delta = due_rule(f)
            if par:
                n = len(par)
                own_ok = (sum(1 for p in par if p['properties'].get('hubspot_owner_id') == o_id) if o_id else
                          sum(1 for p in par if p['tickets'] and TICKETS.get(p['tickets'][0]) and TICKETS[p['tickets'][0]]['properties'].get('hubspot_owner_id') == p['properties'].get('hubspot_owner_id')))
                due_ok = sum(1 for p in par if p['bd'] == delta)
                result = (f'Records: created {n}x; owner {"= " + o_name if o_name else "= the record owner"} on {own_ok}/{n}; due {delta} bd on {due_ok}/{n}; '
                          f'{len(kids)} subtasks under them; {sum(p["open"] for p in par)} parents still open.' + (' Shares its title with another action - counts may be split.' if any(p.get('_shared') for p in par) else ''))
                level = 'VERIFIED (config); results VERIFIED (records)'
            else:
                result = 'Records: no task from this action found (never executed, or title edited after creation).' if enr else 'Records: none.'
            notes = 'Notes: ' + strip(f.get('body', ''))[:500]
            if kids:
                what += f' Records show {len({norm(k2["properties"]["hs_task_subject"]) for k2 in kids})} distinct subtasks (subtasks are not returned by the API).'
            # task sheet
            TS.append([c['name'], wid, num[a['actionId']], (f.get('subject') or '').strip(), '-', br or 'Always', o_txt, due_rule(f)[0], f.get('priority'), f.get('task_type'),
                       assoc_rule(f), strip(f.get('body', '')), cnt(collections.Counter(OWN.get(p['properties'].get('hubspot_owner_id'), '(no owner)') for p in par), len(par)) if par else '-',
                       cnt(collections.Counter(f'{p["bd"]} bd {p["time"]}' for p in par), len(par)) if par else '-', len(par),
                       '; '.join(f'"{t}" x{v}' for t, v in collections.Counter(p['properties']['hs_task_subject'].strip() for p in par).items() if norm(t) != norm(f.get('subject'))), 'VERIFIED (config)'])
            groups = collections.defaultdict(list)
            for kd in kids:
                s = kd['properties']['hs_task_subject'] or ''
                m = re.match(r'\s*(?:test\s*)?(\d+)\s*\.', s, re.I)
                groups[m.group(1) if m else norm(re.sub(r'\(.*?\)', '', s))].append(kd)
            for gk in sorted(groups, key=lambda x: (not x.isdigit(), int(x) if x.isdigit() else 0, x)):
                g = groups[gk]
                titles = collections.Counter(x['properties']['hs_task_subject'].strip() for x in g)
                main = titles.most_common(1)[0][0]
                n = len(g)
                open_under_done = sum(1 for x in g if x['open'] and BYID.get(x['properties'].get('hs_task_parent_task_id'), {}).get('properties', {}).get('hs_task_status') == 'COMPLETED')
                TS.append([c['name'], wid, num[a['actionId']], (f.get('subject') or '').strip(), main, br or 'Always',
                           '(subtask) ' + cnt(collections.Counter(OWN.get(x['properties'].get('hubspot_owner_id'), '(no owner)') for x in g), n),
                           '(subtask) ' + cnt(collections.Counter(f'{x["bd"]} bd {x["time"]}' for x in g), n), cnt(collections.Counter(x['properties'].get('hs_task_priority') for x in g), n),
                           cnt(collections.Counter(x['properties'].get('hs_task_type') for x in g), n), cnt(collections.Counter(assoc_pat(x) for x in g), n), '-',
                           cnt(collections.Counter(OWN.get(x['properties'].get('hubspot_owner_id'), '(no owner)') for x in g), n), cnt(collections.Counter(f'{x["bd"]} bd' for x in g), n), n,
                           ('Title variants: ' + '; '.join(f'"{t}" x{v} ({min(x["c"] for x in g if x["properties"]["hs_task_subject"].strip() == t):%Y-%m-%d})' for t, v in titles.items() if t != main) + '. ' if len(titles) > 1 else '')
                           + (f'{open_under_done} open under a completed parent. ' if open_under_done else '') + f'Status: {cnt(collections.Counter(x["properties"]["hs_task_status"] for x in g), n)}',
                           'VERIFIED (records)'])
        elif k == '0-5' and f.get('property_name') == 'hs_pipeline_stage':
            # stage-move action: measure it from watched-title tasks if this workflow is task-event triggered
            rf = c['enrollmentCriteria'].get('refinementCriteria', {})
            titles = re.findall(r'"hs_task_subject", "operation": \{[^}]*?"values": \[([^\]]*)\]', json.dumps(rf))
            titles = [x for v in titles for x in json.loads('[' + v + ']')]
            to = f.get('value', {}).get('staticValue')
            moved = tot = since = since_moved = 0
            first_new = min((stats[w]['first'] for w in stats if stats[w]['first']), default=None)
            for tt in titles:
                for wt in WATCHED.get(tt, []):
                    cd = P(wt['properties'].get('hs_task_completion_date'))
                    if not cd:
                        continue
                    tot += 1
                    tk = TICKETS.get((WASSOC.get(wt['id']) or [{}])[0].get('id'))
                    ne = P(tk['properties'].get(f'hs_v2_date_entered_{to}')) if tk else None
                    ok = bool(ne and 0 <= (ne - cd).total_seconds() <= 120)
                    moved += ok
                    ADVEV.append([c['name'], wid, tt, wt['id'], wt['properties'].get('hs_object_source_detail_1') or wt['properties'].get('hs_object_source'), tk['id'] if tk else '',
                                  tk['properties'].get('subject') if tk else '', TURL(tk['id']) if tk else '', cd.strftime('%Y-%m-%d %H:%M:%S UTC'),
                                  ne.strftime('%Y-%m-%d %H:%M:%S UTC') if ne else '', round((ne - cd).total_seconds(), 1) if ne else '', 'Yes' if ok else 'No / not within 2 min'])
            if titles:
                result = f'Records: {moved} of {tot} completions of the watched task title(s) were followed within 2 min by the ticket entering {STAGE.get(to, to)}.'
                level = 'VERIFIED (config); results VERIFIED (records)'
        DAM.append([c['name'], wid, f'Step {num[a["actionId"]]}', br or 'Main path (no branch)', num[a['actionId']], ATYPE.get(k, f'Action type {k} (label Needs Verification)'),
                    f'{ATYPE.get(k, "Unknown")} (actionTypeId {k})', what, o2, propc, '(new record)' if k in ('0-3', '0-14') else '-', newv, br or 'Always (no branch)', delay,
                    result, nxt_txt, f'Config action {a["actionId"]} (revision {c.get("revisionId")}).', notes, level])
        if k not in ('LIST_BRANCH', 'STATIC_BRANCH'):
            PO.append([None, f'{ATYPE.get(k, k)}: {what[:140]}', br or 'Always', c['name'], f'Step {num[a["actionId"]]} - {ATYPE.get(k, k)}', result[:200] or '-', None])
        else:
            PO.append([None, 'Branch', br or 'Always', c['name'], f'Step {num[a["actionId"]]} - {ATYPE.get(k)}', what[:250], None])
    # hand-off row
    outs = [l for l in LINKS if l[0] == wid]
    ins_next = None
    if st:
        later = sorted((w for w in CFG if stage_trigger(CFG[w]) and STAGE_ORDER.get(stage_trigger(CFG[w]), ('', 0))[0] == STAGE_ORDER.get(st, ('', 0))[0]
                        and STAGE_ORDER.get(stage_trigger(CFG[w]))[1] > STAGE_ORDER.get(st)[1]), key=lambda w: STAGE_ORDER[stage_trigger(CFG[w])][1])
        ins_next = later[0] if later else None
    if outs:
        PO.append([None, 'Hand-off', '-', c['name'], '-', '; '.join(f'Sets {plabel(l[3])} = {pval(l[3], l[4])} -> triggers {CFG[l[2]]["name"]}' for l in outs), None])
    elif ins_next:
        movers = [l for l in LINKS if l[2] == ins_next and l[3] == 'hs_pipeline_stage']
        PO.append([None, f'Ticket must reach {STAGE.get(stage_trigger(CFG[ins_next]))}', 'Hand-off', '-', '-',
                   ('Moved by: ' + '; '.join(f'{CFG[l[0]]["name"]} (action ID {l[1]})' + (' - BUT that workflow is triggered by a task title no in-scope workflow creates, so in practice the move is manual (see Audit Findings)' if l[0] in BROKEN else '') for l in movers)) if movers else 'No in-scope workflow moves the ticket to the next stage - moved by a person or by automation outside scope.', None])
    # missed enrollments (ticket stage workflows that create tasks)
    if st and stats[wid]['first']:
        got = {x for ts in enr.values() for t in ts for x in t['tickets']}
        for tk in TICKETS.values():
            de = P(tk['properties'].get(f'hs_v2_date_entered_{st}'))
            if de and de >= stats[wid]['first'] and tk['id'] not in got and tk['properties'].get('hs_pipeline') == STAGE_ORDER.get(st, ('',))[0]:
                MISSED.append([c['name'], wid, tk['id'], tk['properties'].get('subject'), TURL(tk['id']), de.strftime('%Y-%m-%d %H:%M:%S UTC'), STAGE.get(tk['properties'].get('hs_pipeline_stage'))])
    stats[wid].update(pm=pm, unmatched=unmatched, linear=linear, enr_map=enr)

for i, r in enumerate(PO, 1):
    r[0], r[6] = i, (i + 1 if i < len(PO) else 'End')

# ------------------------------------------------------------------ automatic findings
def F(key, cls, wf, act, finding, ev, why, verify):
    AUTO[key] = [cls, wf, act, finding, ev, why, verify, f'auto:{key}']


names = lambda ws: ', '.join(CFG[w]['name'] for w in ws) if len(ws) < 4 else f'{len(ws)} workflows'
if DENIED:
    F('A01', 'Needs Verification', ', '.join(d['id'] for d in DENIED), 'All', f'{len(DENIED)} workflow(s) could not be read from the API and are NOT in this workbook.',
      '; '.join(d['error'][:160] for d in DENIED), 'Their logic is unaudited.', 'Re-check token scopes, or supply screenshots.')
off = [w for w in CFG if not CFG[w].get('isEnabled')]
if off:
    F('A02', 'Confirmed', names(off), 'All', f'{len(off)} in-scope workflow(s) are switched OFF: ' + ', '.join(CFG[w]['name'] for w in off) + '.', 'Config isEnabled = false.', 'They do nothing until turned on.', 'Confirm they should be off.')
re_on = [w for w in CFG if CFG[w]['enrollmentCriteria'].get('shouldReEnroll')]
F('A03', 'Confirmed', 'All in scope', 'Trigger', f'Re-enrollment is ON for {len(re_on)} and OFF for {len(CFG) - len(re_on)} workflows.' + (f' ON: {", ".join(CFG[w]["name"] for w in re_on)}.' if re_on else '') +
  f' Suppression is configured on {sum(1 for w in CFG if rules.suppression(CFG[w]))}.',
  'Config shouldReEnroll / suppression fields.', 'With re-enroll OFF a record that meets the trigger again (e.g. returns to a stage) gets nothing new; with it ON it can get duplicates.', 'Confirm each setting is intended.')
subtask_flows = [w for w in CFG if any(t['sub'] for t in BYFLOW[w])]
if subtask_flows:
    F('A04', 'Needs Verification', names(subtask_flows), 'Create task actions', 'Subtasks are not returned by the HubSpot API, so subtask titles, owners and due dates in this workbook come from the task records only.',
      'Config of Create task actions has no subtask field; records show subtasks (Is Subtask = true).', 'Subtask settings cannot be confirmed from config.', 'Screenshot one subtask\'s settings per workflow.')
    subs = [t for w in subtask_flows for t in BYFLOW[w] if t['sub']]
    unowned = sum(1 for t in subs if not t['properties'].get('hubspot_owner_id'))
    if unowned:
        F('A05', 'Confirmed', names(subtask_flows), 'Subtasks', f'{unowned} of {len(subs)} subtasks have no owner.', 'Task records: hubspot_owner_id empty on subtasks.',
          'Unowned subtasks do not appear in anyone\'s task list or overdue view.', 'Confirm the subtask owner setting.')
    oud = [t for t in subs if t['open'] and BYID.get(t['properties'].get('hs_task_parent_task_id'), {}).get('properties', {}).get('hs_task_status') == 'COMPLETED']
    if oud:
        F('A06', 'Potential Issue', names(subtask_flows), 'Subtasks', f'{len(oud)} subtasks are still open under a parent that is already Completed (' + ', '.join(f'{CFG[w]["name"]}: {v}' for w, v in collections.Counter(t["_flow"] for t in oud).items()) + ').',
          'Task records: subtask status vs parent status.', 'The parent looks done while work is unfinished.', 'Confirm the intended behaviour.')
od = collections.Counter(t['_flow'] for t in TASKS if t['open'] and t['due'] and t['due'] < NOW)
if od and A.include_team_practice:
    F('A07', 'Potential Issue', names(list(od)), 'Create task actions', f'Open and past-due tasks on {AS_OF}: ' + ', '.join(f'{CFG[w]["name"]} {v}' for w, v in od.most_common()) + '.',
      'Task records: status not Completed/Deferred and due date in the past.', 'Due dates may be unrealistic or tasks are not being closed.', 'Confirm with the task owners.')
static = collections.Counter()
arch = set()
for w in CFG:
    for a in CFG[w].get('actions', []):
        if akind(a) == '0-3':
            _, nm, sid = owner_rule(a['fields'])
            if nm:
                static[nm] += 1
                if sid in ARCHIVED:
                    arch.add(nm)
if static:
    F('A08', 'Confirmed', 'All in scope', 'Owner settings', 'Tasks assigned to a fixed user: ' + ', '.join(f'{k} ({v} action{"s" if v > 1 else ""})' for k, v in static.most_common()) + '.',
      'Config owner_assignment = STATIC_VALUE.', 'If a person leaves or changes role, tasks keep going to them until each action is edited.', 'Review the list.')
if arch:
    F('A09', 'Confirmed', 'All in scope', 'Owner settings', 'Tasks are assigned to deactivated (archived) users: ' + ', '.join(sorted(arch)) + '.', 'Config static owner IDs vs archived owners.', 'Those tasks go to nobody active.', 'Confirm who should receive these tasks.')
low = []
for w in CFG:
    pm = stats[w]['pm']
    for a in CFG[w].get('actions', []):
        if akind(a) != '0-3':
            continue
        par = pm.get(a['actionId'], [])
        for x in a['fields'].get('associations', []):
            ss = x['value'].get('sourceSpec', {})
            if ss.get('associationCategory') == 'USER_DEFINED' and par:
                tgt = ASSOC.get(x['target']['associationTypeId'], '').split(' -> ')[-1].split(',')[0].strip().lower()
                have = sum(1 for p in par if p.get({'contact': 'contacts', 'company': 'companies', 'ticket': 'tickets', 'deal': 'deals'}.get(tgt, 'x')))
                if have / len(par) < 0.2:
                    low.append(f'{CFG[w]["name"]} step "{a["fields"].get("subject", "").strip()}" ({ASSOC.get(ss.get("associationTypeId"))}: {have}/{len(par)})')
if low:
    F('A10', 'Confirmed', 'Several', 'Associations', f'Association copies that rely on an association LABEL almost never add anything ({len(low)} actions): ' + '; '.join(low[:8]) + ('...' if len(low) > 8 else '') + '.',
      'Config: COPY_ASSOCIATION with a USER_DEFINED source label; records: tasks created by these actions that have that association.', 'The enrolled records rarely carry that label, so tasks do not show on the related record.', 'Confirm whether the label is meant to be set on these records.')
for w in CFG:
    acts = [a for a in CFG[w].get('actions', []) if akind(a) == '0-3']
    if len(acts) < 2:
        continue
    sets = {a['actionId']: frozenset(ASSOC.get(x['target']['associationTypeId'], '').split(' -> ')[-1].split(',')[0].replace(' (all)', '') for x in a['fields'].get('associations', [])) for a in acts}
    allt = set().union(*sets.values())
    diff = [f'"{a["fields"]["subject"].strip()}" lacks {", ".join(sorted(allt - sets[a["actionId"]]))}' for a in acts if allt - sets[a['actionId']]]
    if diff:
        F(f'A11-{w}', 'Confirmed', CFG[w]['name'], 'Associations', 'Create task actions in this workflow associate different record types: ' + '; '.join(diff) + '.',
          'Config associations per Create task action.', 'Those tasks do not show on the missing record type.', 'Confirm whether intentional.')
created_titles = {norm(v) for (w, aid, p, v) in writes if p == 'hs_task_subject'}
for w in CFG:
    rf = json.dumps(CFG[w]['enrollmentCriteria'].get('refinementCriteria', {}))
    for v in re.findall(r'"hs_task_subject", "operation": \{[^}]*?"values": \[([^\]]*)\]', rf):
        for tt in json.loads('[' + v + ']'):
            if norm(tt) not in created_titles:
                wt = WATCHED.get(tt, [])
                srcs = collections.Counter(x['properties'].get('hs_object_source_detail_1') or x['properties'].get('hs_object_source') for x in wt)
                last = max((P(x['properties']['hs_createdate']) for x in wt), default=None)
                F(f'A12-{w}', 'Confirmed', CFG[w]['name'], 'Trigger', f'This workflow is triggered by completing a task titled "{tt}", but no in-scope workflow creates a task with that title. '
                  f'{len(wt)} such tasks exist, created by: ' + (', '.join(f'{k} ({v})' for k, v in srcs.most_common(3)) or 'none') + (f'; newest created {last:%Y-%m-%d}.' if last else '.'),
                  'Config refinement filter on Task title vs titles of every in-scope Create task action; records: tasks with that exact title.',
                  'Once the old tasks are used up, this workflow never fires; whatever it does (e.g. move a stage) has to be done by hand.', 'Confirm which task is meant to trigger this workflow.')
stage_wfs = [w for w in CFG if stage_trigger(CFG[w])]
if stage_wfs:
    nomover = [w for w in stage_wfs if not any(l[2] == w and l[3] == 'hs_pipeline_stage' for l in LINKS)]
    if nomover:
        F('A13', 'Confirmed', names(nomover), 'Trigger', 'Nothing in scope moves the ticket into the stage these workflows fire in: ' + ', '.join(f'{STAGE.get(stage_trigger(CFG[w]))} ({CFG[w]["name"]})' for w in nomover) + '.',
          'Config: no in-scope Edit/Create record action writes that pipeline stage.', 'Those workflows only run when a person (or automation outside scope) moves the ticket.', 'Confirm who moves tickets into these stages.')
never = [(w, a) for w in CFG for a in CFG[w].get('actions', []) if akind(a) == '0-3' and stats[w]['enr'] and not stats[w]['pm'].get(a['actionId'])]
if never:
    F('A14', 'Needs Verification', names(list({w for w, _ in never})), 'Create task actions', 'Create task actions with no matching task in the records: ' + '; '.join(f'{CFG[w]["name"]}: "{a["fields"].get("subject", "").strip()}"' for w, a in never[:10]) + '.',
      'Records matched by title (and owner), then by execution index.', 'Either the branch was never taken, the action was added recently, or titles were edited after creation.', 'Check the branch conditions / history.')
um = [(w, t) for w in CFG for t in stats[w]['unmatched']]
if um and A.include_team_practice:
    ex = collections.Counter(f'{CFG[w]["name"]}: "{t["properties"]["hs_task_subject"].strip()}"' for w, t in um)
    F('A15', 'Confirmed', names(list({w for w, _ in um})), 'Task titles', f'{len(um)} parent tasks have titles that differ from the current config (manual renames, or the config changed). Most common: ' + '; '.join(f'{k} x{v}' for k, v in ex.most_common(6)) + '.',
      'Task records vs config titles.', 'Reports by title split; older tickets carry older wording.', 'Awareness only.')
if MISSED:
    F('A16', 'Potential Issue', names(list({m[1] for m in MISSED})), 'Trigger', f'{len(MISSED)} ticket(s) entered a trigger stage after the workflow went live but got no tasks from it (see Evidence - Missed Enrollments).',
      'Ticket "Date entered <stage>" vs tasks created by the workflow.', 'Possible causes: moved through the stage within seconds (filter-based triggers evaluate a few seconds later), branches, or suppression.', 'Check each ticket\'s workflow history.')
deps = [(w, a) for w in CFG for a in CFG[w].get('actions', []) if akind(a) == '0-3' and re.search(r'waiting for|depends on|after .* (is|are) complete', strip(a['fields'].get('body', '')), re.I)]
if deps and not any(akind(a) in ('0-1', '0-35', '0-29') for w, _ in deps for a in CFG[w]['actions']):
    F('A17', 'Confirmed', names(list({w for w, _ in deps})), 'Task notes', f'{len(deps)} tasks describe dependencies in their notes ("Waiting for ...") but every task is created immediately; nothing in the workflow enforces the order.',
      'Config task body text; no delay / wait actions in these workflows.', 'People get tasks before their inputs exist.', 'Confirm whether the order matters.')
partial = []
for w in CFG:
    lin_tasks = [x for x in stats[w]['linear'] if akind({a['actionId']: a for a in CFG[w]['actions']}[x]) == '0-3']
    if len(lin_tasks) < 2:
        continue
    for k2, ts in stats[w]['enr_map'].items():
        got = {t['idx'] for t in ts if not t['sub']}
        if len(got & set(range(len(stats[w]['linear'])))) < len(lin_tasks) and len(got) > 0:
            partial.append(f'{CFG[w]["name"]}: ticket {(ts[0]["tickets"] or ["?"])[0]} ({min(t["c"] for t in ts):%Y-%m-%d}) has {len(got)} of {len(lin_tasks)} unconditional parent tasks')
if partial:
    F('A18', 'Potential Issue', 'Several', 'Create task actions', f'{len(partial)} enrollment(s) have fewer parent tasks than the unconditional actions should create: ' + '; '.join(partial[:6]) + '.',
      'Config: actions before the first branch always run; records per enrollment.', 'Tasks were probably deleted after creation, or the config changed.', 'Check those tickets.')
noassoc = collections.Counter(t['_flow'] for t in TASKS if not (t['tickets'] or t['companies'] or t['contacts'] or t['deals']))
if noassoc:
    F('A19', 'Confirmed', names(list(noassoc)), 'Associations', f'{sum(noassoc.values())} workflow-created tasks are not associated with any record.', 'Task records with no associations.', 'They cannot be found from any record.', 'Confirm whether these tasks should be linked to a record.')
mism = []
for w in CFG:
    for a in CFG[w].get('actions', []):
        if akind(a) == '0-3':
            par = stats[w]['pm'].get(a['actionId'], [])
            _, delta = due_rule(a['fields'])
            if len(par) >= 3 and delta is not None:
                ok = sum(1 for p in par if p['bd'] == delta)
                if ok / len(par) < 0.7:
                    mism.append(f'{CFG[w]["name"]} "{a["fields"].get("subject", "").strip()}" ({ok}/{len(par)} at {delta} bd)')
if mism:
    F('A20', 'Confirmed', 'Several', 'Due dates', 'Due dates on these tasks often differ from the configured rule (edited after creation, or the rule changed): ' + '; '.join(mism[:8]) + '.', 'Config due_time vs records.', 'Due-date reporting does not reflect the configured SLA.', 'Confirm the rules.')

# ------------------------------------------------------------------ team rules (team-rules.md) and company enrollment
in_window = lambda t: not SINCE or t['properties']['hs_createdate'][:10] >= SINCE
if TRULES.get('subtasks_not_on_ticket'):
    bad = [t for t in TASKS if t['sub'] and in_window(t) and t['tickets']]
    if bad:
        F('T01', 'Confirmed', names(list({t['_flow'] for t in bad})), 'Subtasks', f'{len(bad)} subtasks created on or after {SINCE or "(no start date)"} are associated with a ticket; the team rule says only main tasks should be (' +
          ', '.join(f'{CFG[w]["name"]} {v}' for w, v in collections.Counter(t['_flow'] for t in bad).most_common()) + ').', 'Task records: subtask -> ticket associations.', 'Breaks the team rule for subtasks.', 'Confirm the subtask association setting.')
if TRULES.get('owner_property'):
    off = []
    for w in CFG:
        for a in CFG[w].get('actions', []):
            if akind(a) == '0-3':
                kind, val = rules.owner_spec(a['fields'])
                if val != TRULES['owner_property']:
                    off.append(f'{CFG[w]["name"]} "{a["fields"].get("subject", "").strip()}" ({"fixed user " + OWN.get(val, val) if kind == "static" else (val or "no owner")})')
    if off:
        F('T02', 'Confirmed', 'Several', 'Owner settings', f'{len(off)} Create task actions are not assigned from {TRULES["owner_property"]} as the team rule requires: ' + '; '.join(off[:10]) + ('...' if len(off) > 10 else '') + '.',
          'Config owner_assignment per action vs the team owner_property (team-rules.md).', TRULES.get('owner_property_note', 'Breaks the team owner rule.'), 'Confirm the owner setting on each listed action.')
if TRULES.get('exclusion_only_in_workflows') is not None:
    rows_x = []
    for w in CFG:
        ex = [l for l in rules.list_filters(CFG[w]) if l[1] in ('NOT_IN_LIST', 'SUPPRESS')]
        allowed = w in TRULES['exclusion_only_in_workflows']
        if ex and not allowed:
            rows_x.append(f'{CFG[w]["name"]} ({"ON" if CFG[w].get("isEnabled") else "switched OFF"}) excludes list {", ".join(x[0] + (" " + chr(34) + LIST_NAMES.get(x[0], "") + chr(34) if LIST_NAMES.get(x[0]) else "") for x in ex)}')
        if allowed and not ex:
            rows_x.append(f'{CFG[w]["name"]} has no list exclusion')
    on_viol = [r for r in rows_x if '(ON)' in r or 'has no list exclusion' in r]
    have = [CFG[w]['name'] for w in CFG if CFG[w].get('isEnabled') and any(l[1] in ('NOT_IN_LIST', 'SUPPRESS') for l in rules.list_filters(CFG[w]))]
    if on_viol:
        F('T03', 'Confirmed', 'Several', 'Suppression', f'Exclusion rule ("only {names(TRULES["exclusion_only_in_workflows"]) if all(x in CFG for x in TRULES["exclusion_only_in_workflows"]) else "the listed"} workflows exclude the segment") is broken: ' + '; '.join(on_viol) + '.', 'Config suppressionFilterBranch and NOT_IN_LIST filters.', 'Companies may be excluded (or included) against the team rule.', 'Confirm which workflows should exclude the list.')
    else:
        F('T03', 'No Issue Found', 'All in scope', 'Suppression', f'Exclusion rule holds for switched-on workflows: only {", ".join(have) or "none"} exclude the segment.' + (' Switched-off workflows that also carry it: ' + '; '.join(r for r in rows_x if 'switched OFF' in r) + '.' if any('switched OFF' in r for r in rows_x) else ''),
          'Config suppressionFilterBranch (top-level) and NOT_IN_LIST filters of every in-scope workflow.', 'Confirms the rule.', 'n/a')
if TRULES.get('flag_tasks_from_off_or_removed_actions'):
    stray = [t for t in OTHER_TASKS if t['properties'].get('hs_task_is_sub_task') != 'true'] + [t for t in TASKS if not t['sub'] and in_window(t) and not CFG[t['_flow']].get('isEnabled')]
    if stray and QIDS:
        F('T04', 'Confirmed', 'Team queue', 'Tasks', f'{len(stray)} tasks in the team queue come from workflows that are switched off or not in this audit: ' +
          '; '.join(f'{k} x{v}' for k, v in collections.Counter(t['properties'].get('hs_object_source_detail_1') or t['properties'].get('hs_object_source') for t in stray).most_common(6)) + '.',
          'Task records in the queue vs in-scope, switched-on workflows.', 'Turned-off or duplicate tasks are still reaching the queue.', 'Confirm where these tasks come from.')
if TRULES.get('every_task_action_in_queue', True) and QIDS:
    noq = []
    for w in CFG:
        for a in CFG[w].get('actions', []):
            if akind(a) == '0-3' and str(a['fields'].get('queue_id', '')) not in QIDS:
                noq.append((w, a))
    if noq:
        on = [(w, a) for w, a in noq if CFG[w].get('isEnabled')]
        F('T06', 'Confirmed' if on else 'No Issue Found', names(list({w for w, _ in noq})), 'Create task actions',
          (f'{len(on)} Create task action(s) in switched-on workflows do not use the team queue ({", ".join(QIDS)}): ' + '; '.join(f'{CFG[w]["name"]} "{a["fields"].get("subject", "").strip()}" (queue {a["fields"].get("queue_id", "none")})' for w, a in on[:10]) + '. ' if on else 'Every Create task action in the switched-on workflows uses the team queue. ')
          + (f'Switched-off workflows without the queue: {", ".join(sorted({CFG[w]["name"] for w, _ in noq if not CFG[w].get("isEnabled")}))}.' if any(not CFG[w].get('isEnabled') for w, _ in noq) else ''),
          'Config queue_id on every Create task action vs the team queue ID.', 'Tasks outside the queue are not seen by the team.', 'Confirm the queue on each listed action.')
    else:
        F('T06', 'No Issue Found', 'All in scope', 'Create task actions', f'Every Create task action in every in-scope workflow uses the team queue ({", ".join(QIDS)}).', 'Config queue_id on every Create task action.', 'Confirms the rule.', 'n/a')
    unq = [t for t in TASKS if not t['sub'] and in_window(t) and CFG[t['_flow']].get('isEnabled') and not (set((t['properties'].get('hs_queue_membership_ids') or '').split(';')) & QIDS)]
    if unq:
        F('T07', 'Confirmed', names(list({t['_flow'] for t in unq})), 'Tasks', f'{len(unq)} tasks created on or after {SINCE} by switched-on workflows are not in the team queue.', 'Task records: Queue property.', 'Not visible to the team in the queue.', 'Confirm the queue setting.')
if TRULES.get('flag_tasks_from_off_or_removed_actions'):
    off_new = [t for t in HIST if t['properties'].get('hs_task_is_sub_task') != 'true' and (not SINCE or t['properties']['hs_createdate'][:10] >= SINCE) and not CFG.get(t['_flow'], {}).get('isEnabled', True) and not t.get('_alias')]
    key = collections.defaultdict(list)
    for t in HIST:
        if t['properties'].get('hs_task_is_sub_task') == 'true' or (SINCE and t['properties']['hs_createdate'][:10] < SINCE):
            continue
        for x in TASSOC.get(t['id'], {}).get('companies', []):
            key[(x['id'], rules.norm(re.sub(r'\s*[:|-]\s*', ' ', t['properties']['hs_task_subject'] or '')), t['properties']['hs_createdate'][:10])].append(t)
    dups = {k: v for k, v in key.items() if len({x['_flow'] for x in v}) > 1 or len({x['id'] for x in v}) > 1}
    if off_new:
        F('T08', 'Confirmed', names(list({t['_flow'] for t in off_new})), 'Tasks', f'{len(off_new)} tasks were created on or after {SINCE} by workflows that are now switched off (turned-off tasks still being created): ' +
          '; '.join(f'{CFG[w]["name"]} x{v}' for w, v in collections.Counter(t['_flow'] for t in off_new).most_common()) + '.', 'Task records (workflow name) vs config isEnabled.', 'Duplicates the team turned off are still reaching people.', 'Confirm when each workflow was switched off.')
    else:
        F('T08', 'No Issue Found', 'All in scope', 'Tasks', f'No task has been created on or after {SINCE} by any in-scope workflow that is now switched off.', 'Task records by workflow name, start date onward.', 'Confirms the rule.', 'n/a')
    if dups:
        ex = list(dups.items())[:6]
        F('T09', 'Potential Issue', 'Several', 'Tasks', f'{len(dups)} cases where the same company got the same task more than once on the same day (since {SINCE}). Examples: ' +
          '; '.join(f'company {k[0]} "{v[0]["properties"]["hs_task_subject"].strip()}" {k[2]} from {", ".join(sorted({CFG.get(x["_flow"], {}).get("name", "?") for x in v}))}' for k, v in ex) + '.',
          'Task records: company + task title + creation date.', 'Duplicate work for the owner.', 'Confirm whether these are intended (e.g. separate SM/OM tasks).')
    elif SINCE:
        F('T09', 'No Issue Found', 'All in scope', 'Tasks', f'No company received the same task twice on the same day since {SINCE}.', 'Task records: company + task title + creation date.', 'Confirms the rule.', 'n/a')
hist_flow = collections.defaultdict(set)
for t in HIST:
    for x in TASSOC.get(t['id'], {}).get('companies', []):
        hist_flow[t['_flow']].add(x['id'])
CMISSED = []
for w in CFG:
    c = CFG[w]
    if c.get('objectTypeId') != '0-2' or not c.get('isEnabled') or c['enrollmentCriteria'].get('type') != 'LIST_BASED' or not COMPANIES:
        continue
    for cid, comp in COMPANIES.items():
        if rules.in_scope(comp['properties'], TEAM) is False:
            continue
        if rules.eval_branch(c['enrollmentCriteria'].get('listFilterBranch'), comp['properties'], LISTS) and rules.suppressed(c, comp['properties'], LISTS) is False and cid not in hist_flow[w] and rules.expected_task(c, comp['properties'], LISTS)[0]:
            CMISSED.append([c['name'], w, cid, comp['properties'].get('name'), f'https://app.hubspot.com/contacts/{PORTAL}/record/0-2/{cid}', 'Meets team scope + enrollment filter; no task from this workflow at any date', '-'])
if CMISSED:
    F('T05', 'Potential Issue', names(list({m[1] for m in CMISSED})), 'Trigger', f'{len(CMISSED)} company/workflow pairs: the company meets the team scope and the workflow\'s enrollment filter but has no task from it (see Evidence - Missed Enrollments).',
      'Company properties and list memberships evaluated against the configured filter; records: tasks from the workflow at any date.', 'The company may not be getting the work the workflow should create.', 'Check the listed companies\' workflow history.')
MISSED += CMISSED

# ------------------------------------------------------------------ merge manual findings
EXTRA = json.load(open(A.findings)) if A.findings else {}
rows = [r for k, r in AUTO.items() if not any(k == s or k.startswith(s + '-') for s in EXTRA.get('suppress', []))]
for m in EXTRA.get('findings', []):
    rows.append([m['classification'], m['workflow'], m.get('action', '-'), m['finding'], m.get('evidence', ''), m.get('why', ''), m.get('verify', ''), 'reviewed'])
order = {'Confirmed': 0, 'Potential Issue': 1, 'Needs Verification': 2, 'No Issue Found': 3}
rows.sort(key=lambda r: order.get(r[0], 9))
AF = [[f'F-{i:02d}'] + r[:7] + ['Open', r[7]] for i, r in enumerate(rows, 1)]

# ------------------------------------------------------------------ workbook
wb = Workbook()
FN = Font(name='Arial', size=10)
BD = Font(name='Arial', size=10, bold=True)
HF = Font(name='Arial', size=10, bold=True, color='FFFFFF')
TH = Side(style='thin', color='BFBFBF')
BR = Border(left=TH, right=TH, top=TH, bottom=TH)
LV = {'VERIFIED (config)': 'C6E0B4', 'VERIFIED (records)': 'E2EFDA', 'INFERENCE': 'FFF2CC', 'NEEDS VERIFICATION': 'FCE4D6'}
CL = {'Confirmed': 'E2EFDA', 'Potential Issue': 'FFF2CC', 'Needs Verification': 'FCE4D6', 'No Issue Found': 'DDEBF7'}


def sheet(name, headers, widths, data, level=None, cls=None, links=()):
    ws = wb.create_sheet(name)
    ws.append(headers)
    for i in range(1, len(headers) + 1):
        c = ws.cell(row=1, column=i)
        c.font, c.fill, c.border, c.alignment = HF, PatternFill('solid', fgColor='1F3864'), BR, Alignment(wrap_text=True, vertical='center')
        ws.column_dimensions[get_column_letter(i)].width = widths[i - 1]
    for r in data:
        ws.append([x if not isinstance(x, (list, dict)) else json.dumps(x) for x in r])
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.font, c.border, c.alignment = FN, BR, Alignment(wrap_text=True, vertical='top')
        if level is not None:
            for k, col in LV.items():
                if str(row[level].value or '').startswith(k):
                    row[level].fill = PatternFill('solid', fgColor=col)
        if cls is not None and row[cls].value in CL:
            row[cls].fill = PatternFill('solid', fgColor=CL[row[cls].value])
        for li in links:
            if str(row[li].value or '').startswith('http'):
                row[li].hyperlink = row[li].value
                row[li].font = Font(name='Arial', size=10, color='0563C1', underline='single')
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = ws.dimensions


ws = wb.active
ws.title = 'Read Me'
if A.template:
    wb.remove(ws)
    ws = Workbook().active
lines = [(f'WLS {A.team} Workflow Audit', Font(name='Arial', size=14, bold=True)), (f'Data as of {AS_OF}. HubSpot portal {PORTAL}. Time zone {TZNAME}.', FN), ('', FN),
         ('SOURCES', BD), ('Workflow configuration: HubSpot Automation v4 API (GET /automation/v4/flows/{id}) - the source of truth for triggers, settings and actions. Labelled VERIFIED (config).', FN),
         ('Records: tasks each workflow created (HubSpot stamps the workflow name on each task), their associations, and ticket stage-entry dates. Used to check the configuration against what happened. Labelled VERIFIED (records).', FN),
         ('The API does not return subtasks: subtask details come from records only.', FN), ('', FN),
         ('EVIDENCE LABELS', BD), ('VERIFIED (config) | VERIFIED (records) | INFERENCE (derived, not directly visible) | NEEDS VERIFICATION (cannot be determined).', FN), ('', FN),
         ('ACTION NUMBERS', BD), ('Step numbers follow the workflow from its first action through each branch in order, as the HubSpot editor lists them.', FN), ('', FN),
         ('TEAM SETTINGS', BD), (f'Team: {TEAM_NAME}. Queue: {", ".join(QIDS) or "not known (tasks matched by workflow name)"}. Start date: {SINCE or "none"} (tasks created before it are not reported). Company scope: {((TEAM or {}).get("company_scope") or {}).get("description", "all")}.', FN), ('', FN),
         (f'SCOPE - {len(CFG)} workflows', BD)] + [(f'{i}. {CFG[w]["name"]} ({w}) - {WURL(w)}', FN) for i, w in enumerate(ORDER, 1)]
lines += [(f'NOT READABLE: {d["id"]} - {d["error"][:120]}', FN) for d in DENIED]
lines += [('', FN)] + [(n, FN) for n in EXTRA.get('process_notes', [])] + [('', FN), ('FINDINGS SUMMARY (live count from Audit Findings)', BD)]
for t, fnt in lines:
    ws.append([t])
    ws.cell(row=ws.max_row, column=1).font = fnt
    ws.cell(row=ws.max_row, column=1).alignment = Alignment(wrap_text=True, vertical='top')
ws.column_dimensions['A'].width = 150
for k in CL:
    ws.append([f'=CONCATENATE("{k}: ",COUNTIF(\'Audit Findings\'!B:B,"{k}"))'])
    ws.cell(row=ws.max_row, column=1).font = FN

if A.template:
    _sheet = sheet
    KEEP = ['Process Overview', 'Detailed Action Map', 'Task & Subtask Logic', 'Workflow Inventory', 'Audit Findings']

    def sheet(name, headers, widths, data, **kw):
        if name not in KEEP:
            return
        if name == 'Audit Findings':
            headers, widths, data = headers[:9], widths[:9], [r[:9] for r in data]
        _sheet(name, headers, widths, data, **kw)
sheet('Process Overview', ['Step #', 'Event', 'Condition', 'Workflow', 'Action', 'Result', 'Next Step'], [7, 60, 50, 40, 30, 70, 9], PO)
sheet('Detailed Action Map', ['Workflow', 'Workflow ID', 'Workflow Step', 'Branch', 'Action #', 'Action Name', 'Action Type', 'What The Action Does', 'Object', 'Property / Record Affected',
                              'Current Value', 'New Value', 'Condition', 'Delay', 'Result', 'Next Action', 'Evidence', 'Notes', 'Evidence Level'],
      [36, 12, 10, 30, 8, 22, 26, 60, 18, 28, 10, 70, 30, 16, 50, 30, 40, 60, 22], DAM, level=18)
sheet('Workflow Inventory', ['Workflow Name', 'Workflow ID', 'Object', 'Purpose / Observed Function', 'Enrollment Trigger', 'Re-enrollment', 'Suppression', 'Number of Actions', 'Key Actions', 'Related Workflows', 'Notes'],
      [40, 12, 9, 50, 60, 10, 26, 26, 60, 50, 50],
      [[CFG[w]['name'], w, OBJ.get(CFG[w]['objectTypeId'], CFG[w]['objectTypeId']), CFG[w].get('description') or '(no description)', ' - '.join(trigger_text(CFG[w]['enrollmentCriteria'])),
        'ON' if CFG[w]['enrollmentCriteria'].get('shouldReEnroll') else 'OFF',
        (f'Records where {supp_text(CFG[w])}' if supp_text(CFG[w]) else 'None configured') + (f'. Schedule: {rules.schedule_text(CFG[w])}' if rules.schedule_text(CFG[w]) else ''),
        f'{len(CFG[w].get("actions", []))} (' + ', '.join(f'{v} {k}' for k, v in collections.Counter(ATYPE.get(akind(a), akind(a)) for a in CFG[w].get('actions', [])).items()) + ')',
        '; '.join(describe(a)[0][:120] for a in CFG[w].get('actions', []))[:1500],
        '; '.join([f'Triggers {CFG[l[2]]["name"]} (sets {plabel(l[3])})' for l in LINKS if l[0] == w] + [f'Triggered by {CFG[l[0]]["name"]}' for l in LINKS if l[2] == w]) or 'None in scope',
        f'{"ON" if CFG[w].get("isEnabled") else "OFF"}; revision {CFG[w].get("revisionId")}; created {CFG[w].get("createdAt", "")[:10]}; updated {CFG[w].get("updatedAt", "")[:10]}; {stats[w]["tasks"]} tasks in records. {WURL(w)}']
       for w in ORDER])
sheet('Task & Subtask Logic', ['Workflow', 'Workflow ID', 'Action #', 'Parent Task (config title)', 'Subtask', 'Conditions / Branch', 'Owner (config)', 'Due (config)', 'Priority', 'Type',
                               'Associations (config)', 'Notes (config)', 'Owner (records)', 'Due (records)', 'Times Created', 'Notes', 'Evidence Level'],
      [34, 12, 8, 40, 50, 24, 34, 34, 8, 8, 40, 60, 34, 26, 8, 50, 20], TS, level=16)
sheet('Workflow Connections', ['From Workflow', 'Action ID', 'Writes', 'Value', 'To Workflow', 'Kind', 'Evidence Level'], [40, 10, 26, 40, 40, 50, 18],
      [[CFG[l[0]]['name'], l[1], plabel(l[3]), pval(l[3], l[4]), CFG[l[2]]['name'],
        'Enrolls the target (matches its trigger)' if l[5] == 'trigger' else 'Satisfies an extra condition of the target (does not enroll it by itself)', 'VERIFIED (config)'] for l in ALL_LINKS])
sheet('Audit Findings', ['Finding #', 'Classification', 'Workflow', 'Action #', 'Finding', 'Evidence', 'Why It Matters', 'Recommended Verification', 'Status', 'Source'],
      [9, 18, 36, 18, 70, 60, 50, 46, 9, 14], AF, cls=1)
sheet('Evidence - Enrollments', ['Workflow', 'Workflow ID', 'Enrollment ID', 'Ticket ID', 'Ticket Name', 'Ticket Link', 'Ticket Stage Now', 'Ticket Entered Trigger Stage (latest)', 'First Task Created',
                                 'Seconds After Stage Entry', 'Tasks Created', 'Of Which Subtasks', 'Still Open'], [36, 12, 16, 14, 34, 22, 22, 24, 22, 10, 8, 8, 8], EV, links=(5,))
if MISSED:
    sheet('Evidence - Missed Enrollments', ['Workflow', 'Workflow ID', 'Record ID', 'Record Name', 'Link', 'Entered Trigger Stage / Evidence', 'Stage Now'], [36, 12, 14, 34, 22, 22, 22], MISSED, links=(4,))
if ADVEV:
    sheet('Evidence - Stage Moves', ['Workflow', 'Workflow ID', 'Watched Task Title', 'Task ID', 'Task Created By', 'Ticket ID', 'Ticket Name', 'Ticket Link', 'Task Completed',
                                     'Ticket Entered Target Stage (latest)', 'Seconds Between', 'Moved?'], [36, 12, 36, 14, 34, 14, 34, 22, 22, 24, 10, 14], ADVEV, links=(7,))
if A.template:
    wb._sheets.sort(key=lambda w: KEEP.index(w.title) if w.title in KEEP else 99)
wb.calculation = CalcProperties(fullCalcOnLoad=True)
os.makedirs(os.path.dirname(os.path.abspath(A.out)), exist_ok=True)
wb.save(A.out)
print(f'{A.out}: {len(CFG)} workflows, {len(DAM)} action rows, {len(TS)} task rows, {len(AF)} findings ({len(AUTO)} auto), {len(LINKS)} connections, {len(MISSED)} missed enrollments')
print('auto finding keys:', ', '.join(AUTO))
