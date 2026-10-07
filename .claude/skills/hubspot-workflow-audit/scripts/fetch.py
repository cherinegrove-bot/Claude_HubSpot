#!/usr/bin/env python3
"""Download everything needed to audit a set of HubSpot workflows.

Usage:
  python3 fetch.py --work DIR --list                       # list every workflow the API returns (id, object, on/off, name)
  python3 fetch.py --work DIR --ids 123 456 ...            # fetch these workflows + their records
  python3 fetch.py --work DIR --name-filter "Transitions"  # fetch workflows whose name matches the regex
  python3 fetch.py --work DIR --weekly --team cs-ops        # weekly audit: the team's workflows (from its master rules file),
                                                           # tasks in the audit window, and the companies they concern
  options: --team cs-ops          load queue / start date / company scope from audits/<team>-workflow-audit/team-rules.md
           --queue 123            numeric queue ID(s), comma-separated (overrides team-rules.md)
           --since 2026-10-06     only tasks created on or after this date are in scope
           --from / --to          weekly mode: window dates (YYYY-MM-DD, portal time zone); default = the team's window

Needs HUBSPOT_ACCESS_TOKEN (private app with `automation` + read scopes for the objects involved,
including the sensitive/highly-sensitive read scopes). Writes JSON files into DIR; nothing is changed in HubSpot.
"""
import argparse, json, os, re, sys, time, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rules

API = 'https://api.hubapi.com'
TOKEN = os.environ.get('HUBSPOT_ACCESS_TOKEN')
if not TOKEN:
    sys.exit('HUBSPOT_ACCESS_TOKEN is not set')
H = {'Authorization': 'Bearer ' + TOKEN, 'Content-Type': 'application/json'}


def req(path, body=None):
    url = path if path.startswith('http') else API + path
    for attempt in range(6):
        try:
            r = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, headers=H,
                                       method='POST' if body is not None else 'GET')
            return json.load(urllib.request.urlopen(r, timeout=60))
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                time.sleep(2 * (attempt + 1))
                continue
            raise RuntimeError(f'{e.code} {url}: {e.read().decode()[:400]}')
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            time.sleep(3 * (attempt + 1))
            continue
    raise RuntimeError(f'gave up on {url}')


def save(work, name, obj):
    json.dump(obj, open(os.path.join(work, name), 'w'), indent=1)


def list_flows():
    out, after = [], None
    while True:
        d = req('/automation/v4/flows?limit=100' + (f'&after={after}' if after else ''))
        out += d['results']
        after = d.get('paging', {}).get('next', {}).get('after')
        if not after:
            return out


def search_all(obj, filters, props, cap=10000):
    out, after = [], None
    while True:
        body = {'filterGroups': [{'filters': filters}], 'properties': props, 'limit': 200,
                'sorts': [{'propertyName': 'hs_createdate' if obj == 'tasks' else 'createdate', 'direction': 'ASCENDING'}]}
        if after:
            body['after'] = after
        d = req(f'/crm/v3/objects/{obj}/search', body)
        out += d['results']
        after = d.get('paging', {}).get('next', {}).get('after')
        if not after or len(out) >= cap:
            return out
        time.sleep(0.12)


def batch_assoc(frm, to, ids):
    res = {}
    for i in range(0, len(ids), 1000):
        d = req(f'/crm/v4/associations/{frm}/{to}/batch/read', {'inputs': [{'id': x} for x in ids[i:i + 1000]]})
        for r in d.get('results', []):
            res[r['from']['id']] = [{'id': str(t['toObjectId']), 'labels': [l.get('label') for l in t['associationTypes']]} for t in r['to']]
    return res


def batch_read(obj, ids, props):
    out = []
    for i in range(0, len(ids), 100):
        out += req(f'/crm/v3/objects/{obj}/batch/read', {'inputs': [{'id': x} for x in ids[i:i + 100]], 'properties': props})['results']
    return out


TASK_PROPS = ['hs_task_subject', 'hs_task_body', 'hs_object_source', 'hs_object_source_id', 'hs_object_source_detail_1',
              'hs_task_is_sub_task', 'hs_task_parent_task_id', 'hs_task_sub_task_ids', 'hubspot_owner_id', 'hs_createdate',
              'hs_task_status', 'hs_task_priority', 'hs_timestamp', 'hs_task_type', 'hs_task_completion_date',
              'hs_queue_membership_ids', 'hs_lastmodifieddate']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', required=True)
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--ids', nargs='*')
    ap.add_argument('--name-filter')
    ap.add_argument('--team')
    ap.add_argument('--queue')
    ap.add_argument('--since')
    ap.add_argument('--weekly', action='store_true')
    ap.add_argument('--from', dest='start')
    ap.add_argument('--to', dest='end')
    a = ap.parse_args()
    os.makedirs(a.work, exist_ok=True)
    if os.path.exists(os.path.join(a.work, 'COMPLETE')):
        os.remove(os.path.join(a.work, 'COMPLETE'))

    flows = list_flows()
    if a.weekly:
        return fetch_weekly(a, flows)
    save(a.work, 'all_flows.json', flows)
    if a.list:
        for f in sorted(flows, key=lambda f: f['name']):
            print(f'{f["id"]}\t{f["objectTypeId"]}\t{"ON " if f["isEnabled"] else "off"}\t{f["name"]}')
        print(f'{len(flows)} workflows visible to the API', file=sys.stderr)
        return

    ids = list(a.ids or [])
    if a.name_filter:
        ids += [f['id'] for f in flows if re.search(a.name_filter, f['name'], re.I) and f['id'] not in ids]
    if not ids:
        sys.exit('no workflows selected')

    # 1. workflow configuration
    cfg, denied = {}, []
    for i in ids:
        try:
            cfg[i] = req(f'/automation/v4/flows/{i}')
            print('config', i, cfg[i]['name'])
        except RuntimeError as e:
            denied.append({'id': i, 'error': str(e)})
            print('DENIED', i, str(e)[:160], file=sys.stderr)
    save(a.work, 'configs.json', cfg)
    save(a.work, 'denied.json', denied)

    # 2. reference data
    save(a.work, 'owners.json', req('/crm/v3/owners?limit=500')['results'] + req('/crm/v3/owners?limit=500&archived=true')['results'])
    pipes = {}
    for obj in ('tickets', 'deals'):
        try:
            pipes[obj] = req(f'/crm/v3/pipelines/{obj}')['results']
        except RuntimeError:
            pipes[obj] = []
    save(a.work, 'pipelines.json', pipes)
    labels = {}
    for pair in ['tickets/contacts', 'tickets/companies', 'tickets/deals', 'tasks/tickets', 'tasks/contacts', 'tasks/companies', 'tasks/deals',
                 'deals/contacts', 'deals/companies', 'companies/contacts', 'contacts/companies', 'companies/tickets', 'contacts/tickets']:
        try:
            labels[pair] = req(f'/crm/v4/associations/{pair}/labels')['results']
        except RuntimeError:
            labels[pair] = []
    save(a.work, 'assoc_labels.json', labels)
    props = {}
    for obj in ('tickets', 'deals', 'companies', 'contacts', 'tasks'):
        try:
            props[obj] = {p['name']: {'label': p['label'], 'options': {o['value']: o['label'] for o in p.get('options', [])}} for p in req(f'/crm/v3/properties/{obj}')['results']}
        except RuntimeError:
            props[obj] = {}
    save(a.work, 'properties.json', props)

    # 3. records
    team_name, team = rules.load_team(a.team or a.queue) if (a.team or a.queue) else (None, None)
    since = a.since or (team or {}).get('start_date')
    queue_ids = []
    if a.queue:
        queue_ids = [q.strip() for q in a.queue.split(',') if q.strip().isdigit()]
        if not queue_ids and team:
            queue_ids = [str(x) for x in team.get('queue_ids', [])]
    elif team:
        queue_ids = [str(x) for x in team.get('queue_ids', [])]
    cfg_queues = sorted({str(x['fields']['queue_id']) for c in cfg.values() for x in c.get('actions', []) if x.get('fields', {}).get('queue_id')})
    if (a.queue or team) and not queue_ids:
        queue_ids = cfg_queues
        print(f'queue: no queue ID in team-rules.md for "{a.queue or team_name}"; using queue IDs set in the workflows\' Create task actions: {cfg_queues or "NONE"}', file=sys.stderr)
    save(a.work, 'scope.json', {'team': team_name, 'team_cfg': team, 'since': since, 'queue_ids': queue_ids, 'queue_ids_in_config': cfg_queues,
                                'queue_requested': a.queue or (team or {}).get('queue_name')})
    name2id = {c['name']: i for i, c in cfg.items()}
    # 3a. history: every task each workflow ever created (by the workflow name HubSpot stamps on the task)
    history = []
    for i, c in cfg.items():
        got = search_all('tasks', [{'propertyName': 'hs_object_source_detail_1', 'operator': 'EQ', 'value': c['name']}], TASK_PROPS)
        for t in got:
            t['_flow'] = i
        history += got
        print('history tasks', i, len(got))
    # renamed workflows: tasks made before a rename carry the OLD workflow name. Find candidate old names
    # through the task titles each workflow creates, keep names that are not a current workflow's name.
    current = {f['name'] for f in flows}
    aliases = {}
    for i, c in cfg.items():
        names = set()
        for t in {(x['fields'].get('subject') or '').strip() for x in c.get('actions', []) if x.get('actionTypeId') == '0-3'} - {''}:
            for r in search_all('tasks', [{'propertyName': 'hs_task_subject', 'operator': 'EQ', 'value': t},
                                          {'propertyName': 'hs_object_source', 'operator': 'EQ', 'value': 'AUTOMATION_PLATFORM'}], ['hs_object_source_detail_1'], cap=2000):
                n = r['properties'].get('hs_object_source_detail_1')
                if n and n not in current:
                    names.add(n)
        if names:
            aliases[i] = sorted(names)
    for i, names in aliases.items():
        for n in names:
            got = search_all('tasks', [{'propertyName': 'hs_object_source_detail_1', 'operator': 'EQ', 'value': n}], TASK_PROPS)
            for t in got:
                t['_flow'], t['_alias'] = i, n
            history += got
            print(f'history tasks {i} via old name "{n}": {len(got)}')
    save(a.work, 'aliases.json', aliases)
    save(a.work, 'history_tasks.json', history)
    # 3b. in-scope tasks: in the team queue (if one is known) and created on/after the start date
    sincef = [{'propertyName': 'hs_createdate', 'operator': 'GTE', 'value': since + 'T00:00:00Z'}] if since else []
    if queue_ids:
        tasks = []
        for q in queue_ids:
            tasks += search_all('tasks', [{'propertyName': 'hs_queue_membership_ids', 'operator': 'EQ', 'value': q}] + sincef, TASK_PROPS)
        pids = [t['id'] for t in tasks if t['properties'].get('hs_task_is_sub_task') != 'true']
        for k in range(0, len(pids), 100):
            tasks += search_all('tasks', [{'propertyName': 'hs_task_parent_task_id', 'operator': 'IN', 'values': pids[k:k + 100]}], TASK_PROPS)
        seen = set()
        tasks = [t for t in tasks if not (t['id'] in seen or seen.add(t['id']))]
        for t in tasks:
            t['_flow'] = name2id.get(t['properties'].get('hs_object_source_detail_1'))
        print(f'queue tasks (incl. subtasks of queued parents) since {since}: {len(tasks)}')
    else:
        tasks = [t for t in history if not since or t['properties']['hs_createdate'][:10] >= since]
        if a.queue or team:
            print('WARNING: no queue ID known - in-scope tasks are matched by workflow name only', file=sys.stderr)
    save(a.work, 'tasks.json', tasks)
    tids = sorted({t['id'] for t in tasks + history})
    assoc = {}
    for obj in ('tickets', 'companies', 'contacts', 'deals'):
        for k, v in batch_assoc('tasks', obj, tids).items():
            assoc.setdefault(k, {})[obj] = v
    save(a.work, 'task_assoc.json', assoc)

    # 3c. companies in scope (for "should have enrolled" checks) and list memberships used by triggers
    company_wfs = [c for c in cfg.values() if c.get('objectTypeId') == '0-2']
    if company_wfs or (team or {}).get('company_scope'):
        cprops = sorted({'name', 'hs_object_id', 'hubspot_owner_id'} | set(rules.scope_props(team)) |
                        {p for c in company_wfs for p in rules.referenced_props_all(c)} |
                        {p for c in company_wfs for p in rules.branch_props(c)} |
                        {rules.owner_spec(x['fields'])[1] for c in company_wfs for x in c.get('actions', []) if x.get('actionTypeId') == '0-3' and rules.owner_spec(x['fields'])[0] == 'property'} |
                        ({(team or {}).get('rules', {}).get('owner_property')} - {None}))
        opmap = {'IS_ANY_OF': 'IN', 'IS_NONE_OF': 'NOT_IN', 'IS_KNOWN': 'HAS_PROPERTY', 'IS_UNKNOWN': 'NOT_HAS_PROPERTY', 'IS_EQUAL_TO': 'EQ', 'IS_NOT_EQUAL_TO': 'NEQ'}
        cf = []
        for f in ((team or {}).get('company_scope') or {}).get('filters', []):
            x = {'propertyName': f['property'], 'operator': opmap[f['operator']]}
            if f.get('values'):
                x['values' if x['operator'] in ('IN', 'NOT_IN') else 'value'] = f['values'] if x['operator'] in ('IN', 'NOT_IN') else f['values'][0]
            cf.append(x)
        companies = search_all('companies', cf, cprops) if cf else search_all('companies', [{'propertyName': 'hs_object_id', 'operator': 'HAS_PROPERTY'}], cprops)
        save(a.work, 'companies.json', companies)
        print('companies in scope', len(companies))
        lists, names = {}, {}
        for lid in sorted({l for c in company_wfs for l in rules.referenced_lists(c)}):
            mem, after = [], None
            try:
                while True:
                    d = req(f'/crm/v3/lists/{lid}/memberships?limit=250' + (f'&after={after}' if after else ''))
                    mem += [str(r.get('recordId', r)) if isinstance(r, dict) else str(r) for r in d.get('results', [])]
                    after = d.get('paging', {}).get('next', {}).get('after')
                    if not after:
                        break
                lists[lid] = mem
                try:
                    meta = req(f'/crm/v3/lists/{lid}')
                    names[lid] = (meta.get('list') or meta).get('name')
                except RuntimeError:
                    pass
                print('list', lid, names.get(lid), len(mem))
            except RuntimeError as e:
                print('list', lid, 'not readable:', str(e)[:120], file=sys.stderr)
        save(a.work, 'lists.json', lists)
        save(a.work, 'list_names.json', names)

    # 4. tickets touched (by tasks or by triggers on ticket pipelines) with stage-entry dates
    stage_props = [f'hs_v2_date_entered_{s["id"]}' for p in pipes.get('tickets', []) for s in p['stages']]
    pipelines_used = set()
    for c in cfg.values():
        for m in re.findall(r'"hs_pipeline".{0,200}?"values?": \[?"(\d+)"', json.dumps(c)):
            pipelines_used.add(m)
    tix = {x['id'] for v in assoc.values() for x in v.get('tickets', [])}
    tickets = []
    tprops = ['subject', 'hs_pipeline', 'hs_pipeline_stage', 'createdate', 'hubspot_owner_id', 'hs_object_source', 'hs_object_source_detail_1'] + stage_props
    for p in pipelines_used:
        tickets += search_all('tickets', [{'propertyName': 'hs_pipeline', 'operator': 'EQ', 'value': p}], tprops)
    known = {t['id'] for t in tickets}
    tickets += batch_read('tickets', sorted(tix - known), tprops)
    save(a.work, 'tickets.json', tickets)
    tk_ids = [t['id'] for t in tickets]
    tassoc = {}
    for obj in ('contacts', 'companies', 'deals'):
        for k, v in batch_assoc('tickets', obj, tk_ids).items():
            tassoc.setdefault(k, {})[obj] = v
    save(a.work, 'ticket_assoc.json', tassoc)
    # 5. tasks whose exact title an in-scope workflow WATCHES (task-event triggers / branches on task title)
    watched = set()
    for c in cfg.values():
        s = json.dumps(c)
        for m in re.finditer(r'"property": "hs_task_subject", "operation": \{[^}]*?"values?": (\[[^\]]*\]|"[^"]*")', s):
            v = json.loads(m.group(1))
            watched.update(v if isinstance(v, list) else [v])
    wt = {}
    for title in sorted(watched):
        wt[title] = search_all('tasks', [{'propertyName': 'hs_task_subject', 'operator': 'EQ', 'value': title}], TASK_PROPS, cap=3000)
        print('watched title', repr(title), len(wt[title]))
    save(a.work, 'watched_tasks.json', wt)
    wids = [t['id'] for v in wt.values() for t in v]
    wassoc = batch_assoc('tasks', 'tickets', wids) if wids else {}
    save(a.work, 'watched_assoc.json', wassoc)
    extra = sorted({x['id'] for v in wassoc.values() for x in v} - {t['id'] for t in tickets})
    if extra:
        tickets += batch_read('tickets', extra, tprops)
        save(a.work, 'tickets.json', tickets)
    try:
        save(a.work, 'account.json', req('/account-info/v3/details'))
    except RuntimeError:
        save(a.work, 'account.json', {'timeZone': 'UTC'})
    open(os.path.join(a.work, 'COMPLETE'), 'w').write(time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    print(f'done: {len(cfg)} configs, {len(denied)} denied, {len(tasks)} tasks, {len(tickets)} tickets -> {a.work}')


def reference_data(work):
    save(work, 'owners.json', req('/crm/v3/owners?limit=500')['results'] + req('/crm/v3/owners?limit=500&archived=true')['results'])
    pipes = {}
    for obj in ('tickets', 'deals'):
        try:
            pipes[obj] = req(f'/crm/v3/pipelines/{obj}')['results']
        except RuntimeError:
            pipes[obj] = []
    save(work, 'pipelines.json', pipes)
    labels = {}
    for pair in ['tasks/tickets', 'tasks/companies', 'tasks/contacts', 'tasks/deals', 'companies/tickets']:
        try:
            labels[pair] = req(f'/crm/v4/associations/{pair}/labels')['results']
        except RuntimeError:
            labels[pair] = []
    save(work, 'assoc_labels.json', labels)
    props = {}
    for obj in ('tickets', 'companies', 'tasks'):
        try:
            props[obj] = {p['name']: {'label': p['label'], 'options': {o['value']: o['label'] for o in p.get('options', [])}} for p in req(f'/crm/v3/properties/{obj}')['results']}
        except RuntimeError:
            props[obj] = {}
    save(work, 'properties.json', props)
    try:
        acct = req('/account-info/v3/details')
    except RuntimeError:
        acct = {'timeZone': 'UTC'}
    save(work, 'account.json', acct)
    return acct


def batch_read_history(obj, ids, props, hist):
    out = []
    for i in range(0, len(ids), 50):
        out += req(f'/crm/v3/objects/{obj}/batch/read', {'inputs': [{'id': x} for x in ids[i:i + 50]], 'properties': props,
                                                         'propertiesWithHistory': hist})['results']
        time.sleep(0.12)
    return out


def fetch_weekly(a, flows):
    """Weekly audit data: live settings of the workflows in the team's master rules file, the tasks created in the
    window (queue tasks + their subtasks + any task those workflows made outside the queue), their associations,
    and the companies involved with the property history needed to know who qualified when."""
    import datetime as dt
    from zoneinfo import ZoneInfo
    import master
    team_name, team = rules.load_team(a.team)
    if not team:
        sys.exit(f'STOP: no team-rules.md for team "{a.team}". Set the team up first (SKILL.md, "Set up a new team").')
    M, _ = master.read_master(os.path.join(team['_dir'], team['master_rules_file']))
    acct = reference_data(a.work)
    tz = ZoneInfo(acct.get('timeZone') or 'UTC')
    today = dt.datetime.now(tz).date()
    first, last = rules.week_window(team, today, dt.date.fromisoformat(a.start) if a.start else None,
                                    dt.date.fromisoformat(a.end) if a.end else None)
    if last < first:
        sys.exit(f'STOP: the window {first}..{last} ends before the team start date {team.get("start_date")}. Nothing to audit.')
    t0 = dt.datetime(first.year, first.month, first.day, tzinfo=tz).astimezone(dt.timezone.utc)
    t1 = (dt.datetime(last.year, last.month, last.day, tzinfo=tz) + dt.timedelta(days=1)).astimezone(dt.timezone.utc)
    iso = lambda x: x.strftime('%Y-%m-%dT%H:%M:%SZ')
    print(f'window {first}..{last} ({acct.get("timeZone")}) = {iso(t0)}..{iso(t1)}')

    # 1. live settings of every workflow in the master file
    cfg, denied = {}, []
    for i in M:
        try:
            cfg[i] = req(f'/automation/v4/flows/{i}')
        except RuntimeError as e:
            denied.append({'id': i, 'error': str(e)})
            print('NOT RETURNED', i, str(e)[:160], file=sys.stderr)
    save(a.work, 'configs.json', cfg)
    save(a.work, 'denied.json', denied)
    names = {}
    for i, e in M.items():
        names.setdefault(e['row'].get('Workflow Name'), i)
        if i in cfg:
            names.setdefault(cfg[i]['name'], i)
    for n in team.get('not_readable', []):
        names.setdefault(n['name'], 'not_readable:' + n.get('known_issue', ''))

    # 2. tasks created in the window: queue tasks, their subtasks, and tasks the workflows made outside the queue
    queue_ids = [q.strip() for q in (a.queue or '').split(',') if q.strip()] or [str(q) for q in team.get('queue_ids', [])]
    win = [{'propertyName': 'hs_createdate', 'operator': 'GTE', 'value': iso(t0)}, {'propertyName': 'hs_createdate', 'operator': 'LT', 'value': iso(t1)}]
    tasks = []
    for q in queue_ids:
        tasks += search_all('tasks', [{'propertyName': 'hs_queue_membership_ids', 'operator': 'EQ', 'value': q}] + win, TASK_PROPS)
    for n in names:
        tasks += search_all('tasks', [{'propertyName': 'hs_object_source_detail_1', 'operator': 'EQ', 'value': n}] + win, TASK_PROPS)
    pids = sorted({t['id'] for t in tasks if t['properties'].get('hs_task_is_sub_task') != 'true'})
    for k in range(0, len(pids), 100):
        tasks += search_all('tasks', [{'propertyName': 'hs_task_parent_task_id', 'operator': 'IN', 'values': pids[k:k + 100]}], TASK_PROPS)
    seen = set()
    tasks = [t for t in tasks if not (t['id'] in seen or seen.add(t['id']))]
    for t in tasks:
        t['_flow'] = names.get(t['properties'].get('hs_object_source_detail_1'))
    save(a.work, 'tasks.json', tasks)
    print('tasks in window (incl. subtasks):', len(tasks))
    assoc = {}
    tids = [t['id'] for t in tasks]
    for obj in ('companies', 'tickets'):
        for k, v in batch_assoc('tasks', obj, tids).items():
            assoc.setdefault(k, {})[obj] = v
    save(a.work, 'task_assoc.json', assoc)

    # 3. companies: every live company, every company changed during the window, and every company a task is linked to
    mcfgs = [e['cfg'] for e in M.values() if e.get('cfg')] + list(cfg.values())
    hist = sorted(set(rules.scope_props(team)) | {p for c in mcfgs for p in rules.referenced_props_all(c)} |
                  {p for c in mcfgs for p in rules.branch_props(c)} | {(team.get('went_live') or {}).get(k) for k in ('status_property', 'go_live_date_property')} - {None, 'hs_name', 'hs_value'})
    cprops = sorted(set(hist) | {'name', 'hs_object_id'})
    sp = (team.get('went_live') or {}).get('status_property', 'live')
    lv = (team.get('went_live') or {}).get('live_value', 'Yes')
    cids = {c['id'] for c in search_all('companies', [{'propertyName': sp, 'operator': 'EQ', 'value': lv}], ['name'])}
    cids |= {c['id'] for c in search_all('companies', [{'propertyName': 'hs_lastmodifieddate', 'operator': 'GTE', 'value': iso(t0)},
                                                       {'propertyName': sp, 'operator': 'HAS_PROPERTY'}], ['name'])}
    cids |= {x['id'] for v in assoc.values() for x in v.get('companies', [])}
    companies = batch_read_history('companies', sorted(cids), cprops, hist)
    save(a.work, 'companies.json', companies)
    print('companies fetched (with property history):', len(companies))
    lists, lnames = {}, {}
    for lid in sorted({l for c in mcfgs for l in rules.referenced_lists(c)}):
        mem, after = [], None
        try:
            while True:
                d = req(f'/crm/v3/lists/{lid}/memberships?limit=250' + (f'&after={after}' if after else ''))
                mem += [str(r.get('recordId', r)) if isinstance(r, dict) else str(r) for r in d.get('results', [])]
                after = d.get('paging', {}).get('next', {}).get('after')
                if not after:
                    break
            lists[lid] = mem
            try:
                meta = req(f'/crm/v3/lists/{lid}')
                lnames[lid] = (meta.get('list') or meta).get('name')
            except RuntimeError:
                pass
        except RuntimeError as e:
            print('list', lid, 'not readable:', str(e)[:120], file=sys.stderr)
    save(a.work, 'lists.json', lists)
    save(a.work, 'list_names.json', lnames)
    tix = sorted({x['id'] for v in assoc.values() for x in v.get('tickets', [])})
    save(a.work, 'tickets.json', batch_read('tickets', tix, ['subject', 'hs_pipeline', 'hs_pipeline_stage']) if tix else [])
    save(a.work, 'scope.json', {'mode': 'weekly', 'team': team_name, 'team_slug': rules.team_slug(a.team), 'queue_ids': queue_ids,
                                'window': [first.isoformat(), last.isoformat()], 'window_utc': [iso(t0), iso(t1)],
                                'fetched_at': iso(dt.datetime.now(dt.timezone.utc)), 'history_props': hist})
    open(os.path.join(a.work, 'COMPLETE'), 'w').write(time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    print(f'done: {len(cfg)} workflows ({len(denied)} not returned), {len(tasks)} tasks, {len(companies)} companies -> {a.work}')


if __name__ == '__main__':
    main()
