"""Shared helpers for fetch.py, weekly.py and build.py: team settings, a filter evaluator for
HubSpot enrollment criteria, and the team-rule checks. Read-only; nothing here calls HubSpot."""
import datetime as dt, json, os, re

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_team(name):
    teams = json.load(open(os.path.join(SKILL, 'teams.json')))
    for k, v in teams.items():
        if k.lower() == (name or '').lower():
            return k, v
    return name, None


# ------------------------------------------------------------------ filter evaluation
def _vals(op):
    v = op.get('values')
    if v is None and 'value' in op:
        v = [op['value']]
    return [str(x) for x in (v or [])]


def eval_filter(f, props, lists=None):
    """True / False / None (None = cannot be evaluated from the data we have)."""
    lists = lists or {}
    ft = f.get('filterType')
    if ft == 'IN_LIST' or 'listId' in f:
        lid = str(f.get('listId'))
        if lid not in lists:
            return None
        inside = props.get('hs_object_id') in lists[lid]
        return inside if f.get('operator', 'IN_LIST') == 'IN_LIST' else not inside
    if ft not in (None, 'PROPERTY'):
        return None
    op = f.get('operation', {})
    o = op.get('operator')
    raw = props.get(f.get('property'))
    have = raw not in (None, '')
    vals = _vals(op)
    cur = [x.strip() for x in str(raw).split(';')] if have else []
    if o == 'IS_KNOWN':
        return have
    if o == 'IS_UNKNOWN':
        return not have
    if o in ('IS_ANY_OF', 'IS_EQUAL_TO'):
        return have and any(c in vals for c in cur) if vals else None
    if o in ('IS_NONE_OF', 'IS_NOT_EQUAL_TO'):
        if not have:
            return bool(op.get('includeObjectsWithNoValueSet', True))
        return not any(c in vals for c in cur)
    txt = str(raw).lower() if have else ''
    if o in ('CONTAINS', 'CONTAINS_EXACTLY'):
        return have and any(v.lower() in txt for v in vals)
    if o in ('DOES_NOT_CONTAIN', 'DOES_NOT_CONTAIN_EXACTLY'):
        return (not have) or not any(v.lower() in txt for v in vals)
    if o == 'STARTS_WITH':
        return have and any(txt.startswith(v.lower()) for v in vals)
    if o == 'ENDS_WITH':
        return have and any(txt.endswith(v.lower()) for v in vals)
    if o in ('IS_BETWEEN', 'IS_NOT_BETWEEN', 'IS_AFTER', 'IS_BEFORE') and op.get('operationType') in ('TIME_RANGED', 'TIME_POINT'):
        if not have:
            return False
        val = _to_dt(raw)
        lo, hi = _time_point(op.get('lowerBoundTimePoint') or op.get('timePoint')), _time_point(op.get('upperBoundTimePoint'))
        if val is None or (o in ('IS_BETWEEN', 'IS_NOT_BETWEEN') and (lo is None or hi is None)):
            return None
        if o == 'IS_AFTER':
            return val > lo if lo else None
        if o == 'IS_BEFORE':
            return val < lo if lo else None
        inside = lo <= val <= hi
        return inside if o == 'IS_BETWEEN' else not inside
    if o in ('IS_GREATER_THAN', 'IS_GREATER_THAN_OR_EQUAL_TO', 'IS_LESS_THAN', 'IS_LESS_THAN_OR_EQUAL_TO'):
        try:
            a, b = float(raw), float(vals[0])
        except (TypeError, ValueError, IndexError):
            return None
        return {'IS_GREATER_THAN': a > b, 'IS_GREATER_THAN_OR_EQUAL_TO': a >= b, 'IS_LESS_THAN': a < b, 'IS_LESS_THAN_OR_EQUAL_TO': a <= b}[o]
    return None  # dates, rolling windows, associations, etc.


def _to_dt(v):
    try:
        if str(v).isdigit():
            return dt.datetime.fromtimestamp(int(v) / 1000, dt.timezone.utc)
        d = dt.datetime.fromisoformat(str(v).replace('Z', '+00:00'))
        return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def _time_point(tp):
    """Resolve a HubSpot time point (INDEXED: TODAY/NOW + offset; DATE/STATIC: fixed). None if unsupported."""
    if not tp:
        return None
    now = dt.datetime.now(dt.timezone.utc)
    if tp.get('timeType') == 'INDEXED':
        ref = tp.get('indexReference', {}).get('referenceType')
        base = now if ref == 'NOW' else (now.replace(hour=0, minute=0, second=0, microsecond=0) if ref == 'TODAY' else None)
        if base is None:
            return None
        off = tp.get('offset', {}) or {}
        return base + dt.timedelta(days=off.get('days', 0) + 7 * off.get('weeks', 0), hours=off.get('hours', 0), minutes=off.get('minutes', 0))
    if tp.get('timeType') in ('DATE', 'STATIC') and ('year' in tp or 'timestamp' in tp):
        if 'timestamp' in tp:
            return dt.datetime.fromtimestamp(int(tp['timestamp']) / 1000, dt.timezone.utc)
        return dt.datetime(tp['year'], tp['month'], tp['day'], tzinfo=dt.timezone.utc)
    return None


def eval_branch(fb, props, lists=None):
    """Evaluate a filterBranch tree (OR of ANDs). Tri-state."""
    if not fb:
        return True
    typ = fb.get('filterBranchType')
    if typ == 'ASSOCIATION':
        return None
    parts = [eval_filter(f, props, lists) for f in fb.get('filters', [])] + [eval_branch(b, props, lists) for b in fb.get('filterBranches', [])]
    if not parts:
        return True
    if typ == 'OR':
        if any(p is True for p in parts):
            return True
        return None if any(p is None for p in parts) else False
    if any(p is False for p in parts):
        return False
    return None if any(p is None for p in parts) else True


def scope_props(team_cfg):
    return [f['property'] for f in ((team_cfg or {}).get('company_scope') or {}).get('filters', [])]


def in_scope(company_props, team_cfg):
    sc = (team_cfg or {}).get('company_scope')
    if not sc:
        return True
    fb = {'filterBranchType': 'AND', 'filters': [{'filterType': 'PROPERTY', 'property': f['property'],
                                                    'operation': {'operator': f['operator'], 'values': f.get('values')}} for f in sc['filters']]}
    return eval_branch(fb, company_props)


def referenced_props(cfg):
    return sorted(set(re.findall(r'"property": "(\w+)"', json.dumps(cfg.get('enrollmentCriteria', {})))) - {'hs_name', 'hs_value'})


def referenced_lists(cfg):
    return sorted(set(re.findall(r'"listId": "?(\d+)', json.dumps(cfg))))


def referenced_props_all(cfg):
    return sorted(set(re.findall(r'"property": "(\w+)"', json.dumps({'e': cfg.get('enrollmentCriteria', {}), 's': suppression(cfg)}))) - {'hs_name', 'hs_value'})


def suppression(cfg):
    """HubSpot stores 'Unenroll / suppress if ...' at the TOP LEVEL of the flow as suppressionFilterBranch."""
    return cfg.get('suppressionFilterBranch') or cfg.get('enrollmentCriteria', {}).get('suppressionFilterBranch')


def suppressed(cfg, props, lists=None):
    sb = suppression(cfg)
    return eval_branch(sb, props, lists) if sb else False


def schedule_text(cfg):
    sc = cfg.get('enrollmentSchedule')
    if not sc:
        return None
    t = sc.get('timeOfDay', {})
    at = f"{t.get('hour', 0):02d}:{t.get('minute', 0):02d}"
    if sc.get('type') == 'WEEKLY':
        return f"re-checked every week on {', '.join(d.title() for d in sc.get('daysOfWeek', []))} at {at}"
    if sc.get('type') == 'MONTHLY_SPECIFIC_DAYS':
        return f"re-checked every month on day(s) {', '.join(str(d) for d in sc.get('daysOfMonth', []))} at {at}"
    if sc.get('type') == 'DAILY':
        return f"re-checked every day at {at}"
    return 'schedule ' + json.dumps(sc)


def list_filters(cfg):
    """[(listId, operator, where)] for every list filter in the suppression, trigger or branches."""
    out = []
    for m in re.finditer(r'\{[^{}]*"listId": "?(\d+)"?[^{}]*\}', json.dumps(suppression(cfg) or {})):
        out.append((m.group(1), 'SUPPRESS', 'suppression'))
    for m in re.finditer(r'\{[^{}]*"listId": "?(\d+)"?[^{}]*\}', json.dumps(cfg.get('enrollmentCriteria', {}))):
        op = re.search(r'"operator": "(\w+)"', m.group(0))
        out.append((m.group(1), op.group(1) if op else 'IN_LIST', 'trigger'))
    for a in cfg.get('actions', []):
        for m in re.finditer(r'\{[^{}]*"listId": "?(\d+)"?[^{}]*\}', json.dumps(a)):
            op = re.search(r'"operator": "(\w+)"', m.group(0))
            out.append((m.group(1), op.group(1) if op else 'IN_LIST', f'action {a["actionId"]}'))
    return out


def linear_task_actions(cfg):
    """Create task actions that run for every enrolled record (before the first branch)."""
    acts = {a['actionId']: a for a in cfg.get('actions', [])}
    aid, out, delay_first = cfg.get('startActionId'), [], False
    while aid and aid in acts:
        a = acts[aid]
        k = a.get('actionTypeId') or a.get('type')
        if k in ('LIST_BRANCH', 'STATIC_BRANCH', 'AB_TEST_BRANCH'):
            break
        if k in ('0-1', '0-35', '0-29') and not out:
            delay_first = True
        if k == '0-3':
            out.append(a)
        aid = a.get('connection', {}).get('nextActionId')
    return out, delay_first


def owner_spec(fields):
    v = fields.get('owner_assignment', {}).get('value', {})
    if v.get('type') == 'STATIC_VALUE':
        return ('static', str(v['staticValue']))
    if v.get('type') == 'OBJECT_PROPERTY':
        return ('property', v.get('propertyName'))
    return ('none', None)


def norm(s):
    return re.sub(r'\s+', ' ', (s or '').strip()).lower()


def parse_date(s):
    return dt.datetime.fromisoformat(s.replace('Z', '+00:00')) if s else None


def expected_task(cfg, props, lists=None):
    """Follow the workflow for one record using its current property values.
    Returns (expect, delayed): expect True = its path reaches a Create task, False = path ends with no task,
    None = a branch could not be evaluated. delayed = a delay/wait sits before that task."""
    acts = {a['actionId']: a for a in cfg.get('actions', [])}
    aid, delayed, seen = cfg.get('startActionId'), False, set()
    while aid and aid in acts and aid not in seen:
        seen.add(aid)
        a = acts[aid]
        k = a.get('actionTypeId') or a.get('type')
        if k == '0-3':
            return True, delayed
        if k in ('0-1', '0-35', '0-29'):
            delayed = True
        if k == 'LIST_BRANCH':
            nxt = None
            for b in a.get('listBranches', []):
                r = eval_branch(b.get('filterBranch'), props, lists)
                if r is None:
                    return None, delayed
                if r:
                    nxt = b.get('connection', {}).get('nextActionId')
                    break
            if nxt is None:
                nxt = (a.get('defaultBranch') or {}).get('nextActionId')
            aid = nxt
            continue
        if k == 'STATIC_BRANCH':
            iv = a.get('inputValue', {})
            prop = iv.get('propertyName')
            if not prop:
                return None, delayed
            cur = str(props.get(prop) or '')
            nxt = next((b.get('connection', {}).get('nextActionId') for b in a.get('staticBranches', []) if str(b.get('branchValue')) == cur), None)
            aid = nxt or (a.get('defaultBranch') or {}).get('nextActionId')
            continue
        aid = a.get('connection', {}).get('nextActionId')
    return False, delayed


def branch_props(cfg):
    """Properties read by branches (so fetch.py can download them)."""
    out = set()
    for a in cfg.get('actions', []):
        s = json.dumps(a)
        out |= set(re.findall(r'"property": "(\w+)"', s))
        if a.get('type') == 'STATIC_BRANCH' and a.get('inputValue', {}).get('propertyName'):
            out.add(a['inputValue']['propertyName'])
    return out
