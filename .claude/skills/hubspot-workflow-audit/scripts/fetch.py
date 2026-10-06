#!/usr/bin/env python3
"""Download everything needed to audit a set of HubSpot workflows.

Usage:
  python3 fetch.py --work DIR --list                       # list every workflow the API returns (id, object, on/off, name)
  python3 fetch.py --work DIR --ids 123 456 ...            # fetch these workflows + their records
  python3 fetch.py --work DIR --name-filter "Transitions"  # fetch workflows whose name matches the regex

Needs HUBSPOT_ACCESS_TOKEN (private app with `automation` + read scopes for the objects involved,
including the sensitive/highly-sensitive read scopes). Writes JSON files into DIR; nothing is changed in HubSpot.
"""
import argparse, json, os, re, sys, time, urllib.request, urllib.error

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
    a = ap.parse_args()
    os.makedirs(a.work, exist_ok=True)

    flows = list_flows()
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

    # 3. records: every task each workflow created (HubSpot stamps the workflow name on the task)
    tasks = []
    for i, c in cfg.items():
        got = search_all('tasks', [{'propertyName': 'hs_object_source_detail_1', 'operator': 'EQ', 'value': c['name']}], TASK_PROPS)
        for t in got:
            t['_flow'] = i
        tasks += got
        print('tasks', i, len(got))
    save(a.work, 'tasks.json', tasks)
    tids = [t['id'] for t in tasks]
    assoc = {}
    for obj in ('tickets', 'companies', 'contacts', 'deals'):
        for k, v in batch_assoc('tasks', obj, tids).items():
            assoc.setdefault(k, {})[obj] = v
    save(a.work, 'task_assoc.json', assoc)

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
    print(f'done: {len(cfg)} configs, {len(denied)} denied, {len(tasks)} tasks, {len(tickets)} tickets -> {a.work}')


if __name__ == '__main__':
    main()
