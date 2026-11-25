#!/usr/bin/env python3
"""Error-log entries from a weekly audit, for the weekly page's "Error log" tab.

Usage:
  python3 error_log.py --work DIR [--why "<entry id>=<why text>" ...]
Reads DIR/results.json (weekly.py) and the team's "error_log_from" date in team-rules.md.
Writes DIR/error_log.json: one entry per error group that happened on or after that date,
  {"id": "<date>_<kind>_<task>", "data": {...}}
The session then writes each entry to the published page's database (collection "error_log"):
a NEW id with ArtifactData "set"; an id already in the log with "update" of the facts only
(count, facilities, why, label, last_seen), never "status" or "resolution", which people set on the page.
Company names and record IDs only - no customer contact details.
"""
import argparse, collections, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rules

ap = argparse.ArgumentParser()
ap.add_argument('--work', required=True)
ap.add_argument('--why', action='append', default=[], help='"<entry id>=<text>": the reason, once it is known')
A = ap.parse_args()
R = json.load(open(os.path.join(A.work, 'results.json')))
_, TEAM = rules.load_team(R['team_slug'])
FROM = (TEAM or {}).get('error_log_from')
if not FROM:
    sys.exit('STOP: no "error_log_from" date in team-rules.md, so this team keeps no error log.')
WHY = dict(w.split('=', 1) for w in A.why)

ERROR = {'missing': 'Task not created', 'shouldnt': 'Task created for a facility that should not get it',
         'link': 'Task linked to the wrong company', 'duplicate': 'Duplicate task', 'off_task': 'Task from a switched-off workflow',
         'unknown_source': 'Task from a workflow not in the master rules file', 'not_in_queue': 'Task not in the team queue',
         'golive_gap': 'Live date and go-live date far apart', 'not_live_90': 'Task for a facility outside the team scope',
         'change': 'Workflow changed, not yet confirmed'}
TASK_AT = {t['id']: t['created'] for t in R.get('tasks', [])}
RUN_AT = {(t['name'], cid): m.get('run', '') for t in R['types'] for cid, m in t['missing'].items()}
LIVE_AT = {n['company_id']: n['went_live'] for n in R.get('new_facilities', [])}
is_date = lambda s: bool(re.match(r'\d{4}-\d{2}-\d{2}', s or ''))
slug = lambda s: re.sub(r'[^A-Za-z0-9]+', '-', s or 'none').strip('-')[:60]


def when(p):
    if p['kind'] == 'missing':
        return RUN_AT.get((p.get('type'), p.get('company_id')), '')
    if p.get('task_id') and p['task_id'] in TASK_AT:
        return str(TASK_AT[p['task_id']])[:16].replace('T', ' ')
    if p['kind'] == 'golive_gap':
        return LIVE_AT.get(p.get('company_id'), '')
    return ''


groups = collections.OrderedDict()
for p in R['problems']:
    at = when(p)
    if not is_date(at) or at[:10] < FROM:
        continue
    kind = 'link' if p['kind'].startswith('link') or p['q'] == 2 else p['kind']
    task = p.get('type') or p.get('source') or ''
    gid = f'{at[:10]}_{kind}_{slug(task)}'
    g = groups.setdefault(gid, {'happened': at[:10], 'happened_at': at, 'error': ERROR.get(kind, kind.replace('_', ' ')),
                                'question': p['q'], 'task': task, 'workflow': p.get('source') or '', 'workflow_id': p.get('workflow') or '',
                                'reasons': collections.Counter(), 'labels': collections.Counter(), 'facilities': []})
    g['reasons'][p.get('reason') or p['text']] += 1
    g['labels'][p['label']] += 1
    if p.get('company_id'):
        g['facilities'].append({'id': str(p['company_id']), 'name': p.get('company') or '', 'task': p.get('task_id') or ''})
for c in R.get('changes', []):
    at = (c.get('updated') or '')[:16].replace('T', ' ')
    if c.get('status') == 'same' or not is_date(at) or at[:10] < FROM:
        continue
    gid = f'{at[:10]}_change_{c["workflow"]}'
    groups[gid] = {'happened': at[:10], 'happened_at': at, 'error': ERROR['change'], 'question': 3, 'task': '', 'workflow': c.get('name') or '',
                   'workflow_id': c['workflow'], 'reasons': collections.Counter({'; '.join(d.get('column', '') for d in c.get('diffs', [])) or 'changed': 1}),
                   'labels': collections.Counter({c.get('label') or 'VERIFIED (config)': 1}), 'facilities': []}

out = []
for gid, g in groups.items():
    reason = '; '.join(f'{r} ({n})' if len(g['reasons']) > 1 else r for r, n in g['reasons'].most_common())
    why = WHY.get(gid) or ('Not known yet: ' + reason if reason == 'unknown' else reason)
    out.append({'id': gid, 'data': {'happened': g['happened'], 'happened_at': g['happened_at'], 'error': g['error'], 'question': g['question'],
                                    'task': g['task'], 'workflow': g['workflow'], 'workflow_id': g['workflow_id'],
                                    'count': len(g['facilities']) or 1, 'facilities': g['facilities'], 'why': why,
                                    'label': g['labels'].most_common(1)[0][0], 'found_by_audit': R['window'][1], 'last_seen': R['window'][1],
                                    'status': 'Open', 'resolution': ''}})
json.dump(out, open(os.path.join(A.work, 'error_log.json'), 'w'), indent=1)
print(f'{len(out)} error-log entr{"y" if len(out) == 1 else "ies"} on or after {FROM} -> {os.path.join(A.work, "error_log.json")}')
for e in out:
    d = e['data']
    print(f'  {e["id"]}: {d["error"]} | {d["task"] or d["workflow"]} | {d["count"]} facilit{"y" if d["count"] == 1 else "ies"} | {d["why"][:90]}')
