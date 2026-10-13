"""Plain-English descriptions of HubSpot workflow settings.

Shared by master.py (master rules file + change check). Call init(work_dir) once with a
fetch.py work directory, so labels (properties, owners, lists, pipelines, association types)
can be looked up. Nothing here is team-specific.
"""
import html, json, os, re
import datetime as dt
import rules

PROPS, OWN, LIST_NAMES, ASSOC, STAGE, PIPE = {}, {}, {}, {}, {}, {}
TZNAME = 'UTC'
OBJ = {'0-1': 'Contact', '0-2': 'Company', '0-3': 'Deal', '0-5': 'Ticket', '0-27': 'Task', '0-53': 'Invoice'}


def init(work):
    global TZNAME
    W = lambda n, d: json.load(open(os.path.join(work, n))) if os.path.exists(os.path.join(work, n)) else d
    PROPS.clear(); PROPS.update(W('properties.json', {}))
    LIST_NAMES.clear(); LIST_NAMES.update(W('list_names.json', {}))
    OWN.clear()
    for o in W('owners.json', []):
        OWN[str(o['id'])] = (o.get('firstName', '') + ' ' + o.get('lastName', '')).strip() or o.get('email', str(o['id']))
    for obj, ps in W('pipelines.json', {}).items():
        for p in ps:
            PIPE[p['id']] = p['label']
            for s in p['stages']:
                STAGE[s['id']] = s['label'] if obj == 'tickets' else f'{s["label"]} ({p["label"]})'
    for pair, ls in W('assoc_labels.json', {}).items():
        a, b = [OBJ.get(x, x) for x in ({'tickets': '0-5', 'contacts': '0-1', 'companies': '0-2', 'deals': '0-3', 'tasks': '0-27'}[y] for y in pair.split('/'))]
        for l in ls:
            ASSOC.setdefault(l['typeId'], f'{a} -> {b}' + (f', label "{l["label"]}"' if l.get('label') else ' (all)'))
    TZNAME = W('account.json', {}).get('timeZone', 'UTC')


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
    for obj in ('tickets', 'deals', 'companies', 'contacts', 'tasks'):
        o = PROPS.get(obj, {}).get(name, {}).get('options', {})
        if str(v) in o:
            return o[str(v)]
    return {'true': 'Yes', 'false': 'No'}.get(str(v), v)


OPS = {'IS_KNOWN': 'is known', 'IS_UNKNOWN': 'is unknown', 'IS_ANY_OF': 'is any of', 'IS_NONE_OF': 'is none of', 'IS_EQUAL_TO': 'is equal to',
       'IS_NOT_EQUAL_TO': 'is not equal to', 'CONTAINS': 'contains', 'CONTAINS_EXACTLY': 'contains exactly', 'DOES_NOT_CONTAIN_EXACTLY': "doesn't contain exactly",
       'STARTS_WITH': 'starts with', 'ENDS_WITH': 'ends with', 'IS_AFTER': 'is after', 'IS_BEFORE': 'is before', 'IS_BETWEEN': 'is between',
       'IS_GREATER_THAN': 'is greater than', 'IS_LESS_THAN': 'is less than', 'IN_LIST': 'is in list', 'NOT_IN_LIST': 'is not in list'}


def _tp(tp):
    if not tp:
        return '?'
    if tp.get('timeType') == 'INDEXED':
        off = tp.get('offset', {})
        n = sum(v for v in off.values() if isinstance(v, int))
        ref = (tp.get('indexReference') or {}).get('referenceType', '').lower()
        return ref + (f' {n:+d} {next(iter(off))}' if n else '')
    return json.dumps(tp)[:60]


def filt(fb):
    if not fb:
        return ''
    parts = []
    for f in fb.get('filters', []):
        if f.get('filterType') == 'IN_LIST' or 'listId' in f:
            lid = str(f.get('listId'))
            nm = f' "{LIST_NAMES[lid]}"' if lid in LIST_NAMES else ''
            parts.append(f'record is {"not in" if f.get("operator") == "NOT_IN_LIST" else "in"} list {lid}{nm}')
            continue
        op = f.get('operation', {})
        prop = f.get('property', '?')
        if op.get('operator') == 'IS_BETWEEN' and op.get('lowerBoundTimePoint'):
            parts.append(f'{plabel(prop)} is between {_tp(op["lowerBoundTimePoint"])} and {_tp(op.get("upperBoundTimePoint"))}')
            continue
        vals = op.get('values') or ([op['value']] if 'value' in op else [])
        parts.append(f'{plabel(prop)} {OPS.get(op.get("operator"), str(op.get("operator", "")).lower())}' + (f' {", ".join(str(pval(prop, v)) for v in vals)}' if vals else ''))
    for sub in fb.get('filterBranches', []):
        inner = filt(sub)
        if sub.get('filterBranchType') == 'ASSOCIATION':
            inner = f'an associated {OBJ.get(sub.get("objectTypeId"), "record").lower()} where {inner}'
        if inner:
            parts.append(f'({inner})' if len(fb.get('filterBranches', [])) > 1 else inner)
    j = ' OR ' if fb.get('filterBranchType') == 'OR' else ' AND '
    return j.join(p for p in parts if p)


def event_filt(eb):
    out = []
    for b in eb:
        fs = {f['property']: f['operation'] for f in b.get('filters', [])}
        if 'hs_name' in fs:
            prop = fs['hs_name'].get('value')
            vop = fs.get('hs_value', {})
            vals = vop.get('values') or ([vop['value']] if 'value' in vop else [])
            out.append(f'{plabel(prop)} changes' + (f' to {", ".join(str(pval(prop, v)) for v in vals)}' if vals else ''))
        else:
            out.append(f'event {b.get("eventTypeId")} occurs' + (f' where {filt(b)}' if b.get('filters') else ''))
    return ' OR '.join(out)


def trigger_text(cfg):
    e = cfg.get('enrollmentCriteria', {})
    t = e.get('type')
    if t == 'LIST_BASED':
        return 'Filter-based: ' + filt(e.get('listFilterBranch'))
    if t == 'EVENT_BASED':
        s = event_filt(e.get('eventFilterBranches', []))
        if e.get('refinementCriteria'):
            s += ', AND ' + filt(e['refinementCriteria'])
        return 'Event: ' + s
    if t == 'MANUAL':
        return 'Manual enrollment only'
    return f'{t}: {json.dumps(e)[:300]}'


def reenroll_text(cfg):
    e = cfg.get('enrollmentCriteria', {})
    return (f'Re-enroll {"ON" if e.get("shouldReEnroll") else "OFF"}; '
            f'unenroll if no longer meets trigger {"ON" if e.get("unEnrollObjectsNotMeetingCriteria") else "OFF"}')


def suppression_text(cfg):
    sb = rules.suppression(cfg)
    return filt(sb) if sb else 'None'


def schedule_text(cfg):
    return (rules.schedule_text(cfg) or 'None').capitalize()


def strip(h):
    t = re.sub(r'<\s*(li|p|br)[^>]*>', '\n', h or '')
    t = html.unescape(re.sub(r'<[^>]+>', '', t))
    return re.sub(r'\n\s*\n+', ' | ', t).replace('\n', ' ').strip(' |')


def owner_text(f):
    v = f.get('owner_assignment', {}).get('value', {})
    if v.get('type') == 'OBJECT_PROPERTY':
        return f"record's {plabel(v.get('propertyName'))}"
    if v.get('type') == 'STATIC_VALUE':
        sid = str(v['staticValue'])
        return f'{OWN.get(sid, "user " + sid)} (fixed user)'
    return 'no owner'


def due_text(f):
    d = f.get('due_time')
    if not d:
        return 'no due date'
    bd = len(d.get('daysOfWeek', [])) == 5
    t = d.get('timeOfDay', {})
    return f'{d.get("delta")} {"business " if bd else ""}day(s) after creation at {t.get("hour", 0):02d}:{t.get("minute", 0):02d}'


def assoc_text(f):
    out = []
    for x in f.get('associations', []):
        tgt = ASSOC.get(x['target']['associationTypeId'], f'type {x["target"]["associationTypeId"]}').split(' -> ')[-1].split(',')[0].replace(' (all)', '')
        if x['value']['type'] == 'ENROLLED_OBJECT':
            out.append(f'{tgt} = enrolled record')
        else:
            out.append(f"{tgt} = from enrolled record's associations")
    return ', '.join(out) or 'none'


def akind(a):
    return a.get('actionTypeId') or a.get('type')


ATYPE = {'0-1': 'Delay', '0-35': 'Delay until a date', '0-3': 'Create task', '0-4': 'Send marketing email', '0-5': 'Edit record',
         '0-8': 'Internal email', '0-14': 'Create record', '0-15': 'Enroll in another workflow', '0-29': 'Wait for event',
         '0-63863438': 'Add to static list', '0-63189541': 'Create association', '0-73444249': 'Apply association label',
         'CUSTOM_CODE': 'Custom code', 'WEBHOOK': 'Webhook', 'LIST_BRANCH': 'If/then branch', 'STATIC_BRANCH': 'Value branch', 'AB_TEST_BRANCH': 'A/B branch'}


def paths(cfg):
    """[(action or marker, branch path)] in editor order. Markers: {'_end'}, {'_goto': id}."""
    acts = {a['actionId']: a for a in cfg.get('actions', [])}
    out, seen = [], set()

    def visit(aid, br):
        while aid:
            if aid in seen:
                out.append(({'_goto': aid}, br))
                return
            if aid not in acts:
                break
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
    return out


def _path(br):
    return br or '(start)'


def branch_lines(cfg):
    """One line per branch decision: where it sits and the conditions it checks, in order."""
    out = []
    for a, br in paths(cfg):
        k = akind(a)
        if k == 'LIST_BRANCH':
            bs = '; '.join(f'"{b.get("branchName")}" if {filt(b.get("filterBranch"))}' for b in a.get('listBranches', []))
            out.append(f'At {_path(br)}: {bs}; otherwise {"default branch" if a.get("defaultBranch") else "end"}')
        elif k == 'STATIC_BRANCH':
            iv = a.get('inputValue', {})
            out.append(f'At {_path(br)}: branch on {plabel(iv.get("propertyName") or "?")} = ' + ', '.join(str(b.get('branchValue')) for b in a.get('staticBranches', [])))
        elif a.get('_end') and br:
            pass
    ends = [br for a, br in paths(cfg) if a.get('_end') and br]
    tasks = {br for a, br in paths(cfg) if akind(a) == '0-3'}
    for br in ends:
        if not any(t == br or t.startswith(br + ' >') for t in tasks):
            out.append(f'{br}: ends with no task')
    return out


def task_lines(cfg, queue_name=None):
    out = []
    for a, br in paths(cfg):
        if akind(a) != '0-3':
            continue
        f = a.get('fields', {})
        q = f.get('queue_id')
        qtxt = (f'{queue_name} ({q})' if queue_name else str(q)) if q else 'no queue'
        b = f.get('body', '')
        blen = b.get('_len', 0) if isinstance(b, dict) else len(strip(b))
        out.append(f'{_path(br)}: "{(f.get("subject") or "").strip()}" | type {f.get("task_type")} | priority {f.get("priority")} | owner {owner_text(f)} | '
                   f'due {due_text(f)} | queue {qtxt} | links {assoc_text(f)} | description {blen} chars')
    return out


def other_lines(cfg):
    out = []
    for a, br in paths(cfg):
        k = akind(a)
        if a.get('_goto'):
            out.append(f'{_path(br)}: go to action {a["_goto"]}')
            continue
        if a.get('_end') or k in ('0-3', 'LIST_BRANCH', 'STATIC_BRANCH', 'AB_TEST_BRANCH'):
            continue
        f = a.get('fields', {})
        if k == '0-1':
            d = f'{f.get("delta")} {str(f.get("time_unit", "")).lower()}'
        elif k == '0-5':
            v = f.get('value', {})
            d = f'set {plabel(f.get("property_name"))} = ' + (str(pval(f.get('property_name'), v.get('staticValue'))) if v.get('type') == 'STATIC_VALUE' else v.get('type', '?'))
        else:
            d = json.dumps(f, sort_keys=True)[:200]
        out.append(f'{_path(br)}: {ATYPE.get(k, k)} - {d}')
    return out


def action_count(cfg):
    import collections
    c = collections.Counter(ATYPE.get(akind(a), akind(a)) for a in cfg.get('actions', []))
    return f'{len(cfg.get("actions", []))}' + (' (' + ', '.join(f'{n} {k}' for k, n in c.most_common()) + ')' if c else '')
