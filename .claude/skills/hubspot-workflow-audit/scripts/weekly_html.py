#!/usr/bin/env python3
"""Interactive weekly audit page: fills the skill's HTML template with weekly.py's results.json.

Usage:
  python3 weekly_html.py --work DIR [--out FILE] [--template FILE]
Default template: ../templates/weekly_check_template.html (same layout for every team).
Default output:   audits/<team>-workflow-audit/weekly/<team>-weekly-audit-<report day>.html

The template reads one data object, put in place of __DATA__. From the team's team-rules.md this script adds:
  queue_names   {queue ID: name}  (the API can't return queue names)
  page_colours  replaces the template's base colours when the team sets them
Company names and record IDs only - no customer contact details.
"""
import argparse, html, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rules

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument('--work', required=True)
ap.add_argument('--out')
ap.add_argument('--template', default=os.path.join(HERE, '..', 'templates', 'weekly_check_template.html'))
A = ap.parse_args()
R = json.load(open(os.path.join(A.work, 'results.json')))
_, TEAM = rules.load_team(R['team_slug'])
TEAM = TEAM or {}
out = A.out or os.path.join(rules.team_dir(R['team_slug']), 'weekly', f'{R["team_slug"]}-weekly-audit-{R["report_day"]}.html')
os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
page = open(A.template).read()
if page.count('__DATA__') != 1:
    sys.exit(f'STOP: {A.template} must contain __DATA__ exactly once.')

# The data object: what weekly.py built, plus the lookups the template needs. Nothing here is a contact detail.
data = {k: R[k] for k in ('team', 'decision_owner', 'portal', 'queue', 'queue_ids', 'window', 'report_day', 'time_zone', 'fetched_at', 'start_date',
                          'counts', 'top', 'types', 'new_facilities', 'links', 'subtasks', 'changes', 'waiting_on', 'known_issues', 'expected_off',
                          'problems', 'companies', 'tasks')}
data['schedules'] = R.get('schedules', [])
data['known_days'] = R.get('known_days', [])
data['switched_off'] = R.get('switched_off', [])
data['portal'] = str(TEAM.get('portal_id') or R.get('portal') or '')      # HubSpot links use the portal ID from team-rules.md
data['queue_names'] = {q: (v['name'] if isinstance(v, dict) else v) for q, v in (TEAM.get('queue_names') or {}).items()}
for n in data['new_facilities']:                       # field names the template's New facilities table reads
    n['id'] = n['company_id']
    n['live'] = n['went_live']
    n['got'] = [t['type'] for t in n.get('types', []) if t['status'].startswith('got')]
blob = json.dumps(data, default=str).replace('</', '<\\/')

page = page.replace('__DATA__', blob)
page = re.sub(r'<title>.*?</title>', f'<title>{html.escape(R["team"])} weekly check {R["report_day"]}</title>', page, count=1, flags=re.S)
col = TEAM.get('page_colours') or {}
for key, var in (('navy', 'navy'), ('grey', 'grey'), ('red', 'red'), ('white', 'white'), ('background', 'bg')):
    if col.get(key):
        page = re.sub(rf'(:root\{{[^}}]*?--{var}:)#[0-9A-Fa-f]{{3,8}}', rf'\g<1>{col[key]}', page, count=1)
open(out, 'w').write(page)
print(f'Wrote {out} ({os.path.getsize(out) // 1024} KB) from {os.path.relpath(A.template)}')
