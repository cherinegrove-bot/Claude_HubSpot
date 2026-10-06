"""Builds the WLS Transitions audit workbook from the HubSpot workflow configuration
(Automation v4 API, saved in cfg/<id>.json) cross-checked against the task/ticket records."""
import os, re, json, pickle, collections, datetime as dt, html
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.properties import CalcProperties

T, R, TK, OW, STG, WF = pickle.load(open('an.pkl', 'rb'))
M = pickle.load(open('model.pkl', 'rb'))
OB = json.load(open('onb_tickets.json'))
OA = json.load(open('onb_ticket_assoc.json'))
DEALS = {d['id']: d for d in json.load(open('onb_deals.json'))}
P = lambda s: dt.datetime.fromisoformat(s.replace('Z', '+00:00')) if s else None
AS_OF = '2026-10-02'
PORTAL = '45059701'
TURL = lambda i: f'https://app.hubspot.com/contacts/{PORTAL}/record/0-5/{i}'
WURL = lambda i: f'https://app.hubspot.com/workflows/{PORTAL}/platform/flow/{i}/edit'

SCOPE = [  # (workflow id, records-name used on tasks, stage it fires in)
    ('1670039203', None, None),
    ('1866384267', 'Transitions - Transition Kickoff Tasks (+SubTask)', '1094530721'),
    ('1866658899', 'Transitions - Pre Launch Setup Tasks (+SubTask)', '1094530722'),
    ('1866664080', 'Transitions - Launch Readiness Tasks (+SubTask)', '1094530723'),
    ('1866664222', 'Transitions - Go Live Execution Tasks (+SubTask)', '1094493506'),
    ('1866664327', 'Transitions - Final Sign Off Tasks (+SubTask)', '1094493507'),
    ('1866659765', 'Transitions - 30-Day Monitoring (+SubTask)', '1102485356'),
    ('1867929348', 'Transitions - TRANSITION COMPLETE (+SubTask)', '1094530724'),
    ('1699704693', None, None), ('1699666189', None, None), ('1699704743', None, None), ('1699730300', None, None), ('1699702705', None, None),
]
# stage-advance workflows: id -> (watched task title, from stage, to stage)
ADV = {}
CFG = {i: json.load(open(f'cfg/{i}.json')) for i, _, _ in SCOPE}
RNAME = {i: n for i, n, _ in SCOPE}
SHORT = {'1670039203': 'Closed Won', '1866384267': 'Kickoff', '1866658899': 'Pre-Launch', '1866664080': 'Launch Readiness',
         '1866664222': 'Go-Live', '1866664327': 'Final Sign-Off', '1866659765': '30-Day Monitoring', '1867929348': 'Transition Complete',
         '1699704693': 'Advance Kickoff->Pre-Launch', '1699666189': 'Advance Pre-Launch->Launch Readiness', '1699704743': 'Advance Launch Readiness->Go-Live',
         '1699730300': 'Advance Go-Live->Final Signoff', '1699702705': 'Advance Final Signoff->30-Day'}
for _w, _c in CFG.items():
    if _c['objectTypeId'] == '0-27':
        _rf = _c['enrollmentCriteria']['refinementCriteria']['filterBranches'][0]
        _title = _rf['filters'][0]['operation']['values'][0]
        _from = _rf['filterBranches'][0]['filters'][1]['operation']['values'][0]
        ADV[_w] = (_title, _from, _c['actions'][0]['fields']['value']['staticValue'])
ADV_FROM = {v[1]: w for w, v in ADV.items()}

# ------------------------------------------------------------------ lookups
OWN = {str(o['id']): (o.get('firstName', '') + ' ' + o.get('lastName', '')).strip() for o in json.load(open('owners.json'))}
DEAL_STAGE = {}
for p in json.load(open('deal_pipes.json'))['results']:
    for s in p['stages']:
        DEAL_STAGE[s['id']] = f'{s["label"]} ({p["label"]} pipeline)'
PIPE = {'751582029': 'Onboarding Pipeline'}
ASSOC = {  # association type id -> meaning (from /crm/v4/associations/*/labels)
    230: 'Task -> Ticket', 204: 'Task -> Contact', 192: 'Task -> Company', 16: 'Ticket -> Contact', 28: 'Ticket -> Deal',
    70: 'Ticket -> Company, label "Transitions"', 72: 'Ticket -> Contact, label "Transition"', 339: 'Ticket -> Company (all)',
    3: 'Deal -> Contact (all)', 341: 'Deal -> Company (all)', 26: 'Ticket -> Company, label "Primary"'}
PROP = {'createdate': 'Create date', 'hs_pipeline': 'Pipeline', 'hs_pipeline_stage': 'Ticket status', 'dealstage': 'Deal stage',
        'ppc_ads__yes_no_': 'PPC Ads (Yes/No)', 'marketing_portfolio_mgr': 'Marketing Portfolio Manager',
        'subject': 'Ticket name', 'hubspot_owner_id': 'Ticket owner', 'hs_task_subject': 'Task title', 'hs_task_status': 'Task status'}
OPS = {'IS_KNOWN': 'is known', 'IS_ANY_OF': 'is any of', 'IS_EQUAL_TO': 'is equal to', 'IS_NONE_OF': 'is none of'}


def val(prop, v):
    if prop == 'hs_pipeline_stage':
        return STG.get(v, v)
    if prop == 'hs_pipeline':
        return PIPE.get(v, v)
    if prop == 'dealstage':
        return DEAL_STAGE.get(v, v)
    if prop == 'hubspot_owner_id':
        return OWN.get(v, v)
    if isinstance(v, str) and '{{' in v:
        return re.sub(r'\{\{\s*enrolled_object\.(\w+)\s*\}\}', lambda m: f"the deal's {'name' if m.group(1) == 'dealname' else m.group(1)} (template {{{{ enrolled_object.{m.group(1)} }}}})", v)
    return {'true': 'Yes', 'false': 'No'}.get(v, v)


def filt(fb):
    """Plain-English rendering of a HubSpot filter branch."""
    parts = []
    for f in fb.get('filters', []):
        op = f['operation']
        vals = op.get('values') or ([op['value']] if 'value' in op else [])
        parts.append(f'{PROP.get(f["property"], f["property"])} {OPS.get(op["operator"], op["operator"]).lower()}' + (f' {", ".join(val(f["property"], v) for v in vals)}' if vals else ''))
    for sub in fb.get('filterBranches', []):
        inner = filt(sub)
        if sub.get('filterBranchType') == 'ASSOCIATION':
            _o = {'0-2': 'company', '0-5': 'ticket', '0-1': 'contact'}.get(sub.get('objectTypeId'), 'record')
            inner = f'an associated {_o} where {inner}'
        parts.append(inner)
    joiner = ' OR ' if fb.get('filterBranchType') == 'OR' else ' AND '
    return joiner.join(p for p in parts if p)


def strip(h):
    t = re.sub(r'<\s*(li|p|br)[^>]*>', '\n', h or '')
    t = html.unescape(re.sub(r'<[^>]+>', '', t))
    return re.sub(r'\n\s*\n+', ' | ', t).replace('\n', ' ').strip(' |')


def owner_rule(f):
    v = f.get('owner_assignment', {}).get('value', {})
    if v.get('type') == 'OBJECT_PROPERTY' and v.get('propertyName') == 'hubspot_owner_id':
        return 'Ticket owner (property hubspot_owner_id of the enrolled ticket)', None
    if v.get('type') == 'STATIC_VALUE':
        return f'{OWN.get(v["staticValue"], v["staticValue"])} (fixed user, owner ID {v["staticValue"]})', OWN.get(v['staticValue'])
    return 'Not set', None


def due_rule(f):
    d = f.get('due_time')
    if not d:
        return 'Not set', None
    bd = len(d.get('daysOfWeek', [])) == 5
    t = d.get('timeOfDay', {})
    return f'{d["delta"]} {"business " if bd else ""}day(s) after creation at {t.get("hour", 0):02d}:{t.get("minute", 0):02d} (account time zone UTC-04:00)', d['delta']


def assoc_rule(f):
    out = []
    for a in f.get('associations', []):
        tgt = ASSOC.get(a['target']['associationTypeId'], a['target']['associationTypeId'])
        if a['value']['type'] == 'ENROLLED_OBJECT':
            out.append(f'{tgt.split(" -> ")[-1]} = the enrolled record')
        else:
            src = ASSOC.get(a['value']['sourceSpec']['associationTypeId'], a['value']['sourceSpec']['associationTypeId'])
            out.append(f'{tgt.split(" -> ")[-1]} = copied from the enrolled record\'s associations: {src}')
    return '; '.join(out) or 'None'


# ------------------------------------------------------------------ walk each workflow in editor order
def walk(cfg):
    acts = {a['actionId']: a for a in cfg['actions']}
    order = []

    def visit(aid, branch, depth):
        while aid:
            a = acts[aid]
            order.append((a, branch))
            if a['type'] == 'LIST_BRANCH':
                for b in a['listBranches']:
                    visit(b['connection']['nextActionId'], f'{branch + " > " if branch else ""}"{b["branchName"]}" (IF {filt(b["filterBranch"])})', depth + 1)
                dflt = a.get('defaultBranch')
                order.append(({'_end': True, 'actionId': f'{aid}-else'}, f'{branch + " > " if branch else ""}None met ("{a.get("defaultBranchName", "Otherwise")}")') if not dflt else None)
                if dflt:
                    visit(dflt['nextActionId'], f'{branch + " > " if branch else ""}None met', depth + 1)
                return
            if a['type'] == 'STATIC_BRANCH':
                prop = re.sub(r'.*\.(\w+) }}$', r'\1', a['inputValue'].get('propertyToken', a['inputValue'].get('propertyName', '')))
                for b in a['staticBranches']:
                    visit(b['connection']['nextActionId'], f'{branch + " > " if branch else ""}{PROP.get(prop, prop)} = {b["branchValue"]}', depth + 1)
                if a.get('defaultBranch'):
                    visit(a['defaultBranch']['nextActionId'], f'{branch + " > " if branch else ""}{PROP.get(prop, prop)} = anything else (default branch)', depth + 1)
                return
            aid = a.get('connection', {}).get('nextActionId')
        order.append(({'_end': True, 'actionId': 'end'}, branch))

    visit(cfg['startActionId'], '', 0)
    return [o for o in order if o]


# execution index -> action id, per workflow (HubSpot counts every executed action incl. branches)
EXEC = {}
for wid, cfg in CFG.items():
    seq, aid, acts = [], cfg['startActionId'], {a['actionId']: a for a in cfg['actions']}
    while aid:
        seq.append(aid)
        a = acts[aid]
        if a['type'] in ('LIST_BRANCH', 'STATIC_BRANCH'):
            break
        aid = a.get('connection', {}).get('nextActionId')
    EXEC[wid] = {i: s for i, s in enumerate(seq)}
# Pre-Launch: index 5 = list branch, 6 = static branch, 7 = the proposal task on whichever branch ran
EXEC['1866658899'].update({5: '29', 6: '31', 7: '30|32|33|34'})

wfstats = {}
for wid, name, stage in SCOPE:
    if not name:
        continue
    enr = M[name]['enr']
    d = [i['delta'] for i in enr if i['delta'] is not None]
    wfstats[wid] = dict(n=len(enr), dmin=min(d), dmax=max(d), first=min(i['start'] for i in enr), last=max(i['start'] for i in enr),
                        tix=len({k for i in enr for k in i['tickets']}), multi=sum(1 for v in collections.Counter(k for i in enr for k in i['tickets']).values() if v > 1))


def groups_for(wid, aid):
    name = RNAME[wid]
    idxs = [i for i, a in EXEC[wid].items() if aid in a.split('|')]
    return [g for g in M[name]['groups'] if g['idx'] in idxs] if name else []


def rec_owner(g):
    n = g['n']
    return '; '.join(f'{k} {v}/{n}' for k, v in g['owners'].most_common())


def rec_due(g):
    n = g['n']
    bd, c = g['bd'].most_common(1)[0]
    tm, tc = g['time'].most_common(1)[0]
    return f'{bd} bd at {tm} on {c}/{n} (time {tc}/{n})'


# ------------------------------------------------------------------ workbook
wb = Workbook()
F = Font(name='Arial', size=10)
B = Font(name='Arial', size=10, bold=True)
HF = Font(name='Arial', size=10, bold=True, color='FFFFFF')
HFILL = PatternFill('solid', fgColor='1F3864')
LV = {'VERIFIED (config)': 'C6E0B4', 'VERIFIED (records)': 'E2EFDA', 'VERIFIED (screenshot)': 'C6E0B4', 'INFERENCE': 'FFF2CC', 'NEEDS VERIFICATION': 'FCE4D6'}
CL = {'Confirmed': 'E2EFDA', 'Potential Issue': 'FFF2CC', 'Needs Verification': 'FCE4D6', 'No Issue Found': 'DDEBF7'}
TH = Side(style='thin', color='BFBFBF')
BD = Border(left=TH, right=TH, top=TH, bottom=TH)


def sheet(name, headers, widths, rows, level=None, cls=None, links=()):
    ws = wb.create_sheet(name)
    ws.append(headers)
    for i, _ in enumerate(headers, 1):
        c = ws.cell(row=1, column=i)
        c.font, c.fill, c.border, c.alignment = HF, HFILL, BD, Alignment(wrap_text=True, vertical='center')
        ws.column_dimensions[get_column_letter(i)].width = widths[i - 1]
    for r in rows:
        ws.append(list(r))
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.font, c.border, c.alignment = F, BD, Alignment(wrap_text=True, vertical='top')
        if level is not None:
            v = str(row[level].value or '')
            for k, col in LV.items():
                if v.startswith(k):
                    row[level].fill = PatternFill('solid', fgColor=col)
        if cls is not None and row[cls].value in CL:
            row[cls].fill = PatternFill('solid', fgColor=CL[row[cls].value])
        for li in links:
            v = row[li].value
            if v and str(v).startswith('http'):
                row[li].hyperlink = v
                row[li].font = Font(name='Arial', size=10, color='0563C1', underline='single')
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = ws.dimensions
    return ws


# ------------------------------------------------------------------ stage-advance evidence from records
CUT = dt.datetime(2026, 8, 20, tzinfo=dt.timezone.utc)
ADV_EV, ADV_ROWS = {}, []
NEXT_WF = {stage: w for w, n, stage in SCOPE if stage}
for w, (title, frm, to) in ADV.items():
    ts = [t for t in T if (t['properties']['hs_task_subject'] or '').strip() == title]
    done = [t for t in ts if t['properties'].get('hs_task_completion_date')]
    moved, since, since_moved = 0, 0, 0
    for t in done:
        cd = P(t['properties']['hs_task_completion_date'])
        tk = TK.get(t['tickets'][0]) if t['tickets'] else None
        ne = P(tk['properties'].get('hs_v2_date_entered_' + to)) if tk else None
        ok = bool(ne and 0 <= (ne - cd).total_seconds() <= 120)
        moved += ok
        if cd >= CUT:
            since += 1
            since_moved += ok
            ADV_ROWS.append([CFG[w]['name'], w, title, t['id'], t['properties']['hs_object_source_detail_1'], t['tickets'][0] if t['tickets'] else '', tk['properties']['subject'] if tk else '',
                             TURL(t['tickets'][0]) if t['tickets'] else '', cd.strftime('%Y-%m-%d %H:%M:%S UTC'), ne.strftime('%Y-%m-%d %H:%M:%S UTC') if ne else '',
                             round((ne - cd).total_seconds(), 1) if ne else '', 'Yes' if ok else 'No / not within 2 min'])
    ADV_EV[w] = dict(n=len(ts), done=len(done), moved=moved, since=since, since_moved=since_moved,
                     summary=f'Records: {len(ts)} tasks titled "{title}" exist, all created by the legacy (non-subtask) workflow; {moved} of {len(done)} completions were followed within 2 minutes by the ticket entering {STG[to]}. Since 2026-08-20: {since} completions, {since_moved} followed by the stage move. None of the 13 workflows creates a task with this title.',
                     result=f'Ticket moves from {STG[frm]} to {STG[to]} (records: {moved} times in total, {since_moved} since 2026-08-20).')


def end_next(wid):
    stage = dict((w, st) for w, n, st in SCOPE).get(wid)
    if wid in ADV:
        to = ADV[wid][2]
        return f'Ticket now meets the trigger of {CFG[NEXT_WF[to]]["name"]}.' if to in NEXT_WF else 'End.'
    if wid == '1670039203':
        return 'Ticket waits in UNASSIGNED. None of the 13 workflows moves it to Transition Kickoff.'
    if wid == '1867929348':
        return 'End of the Transitions process.'
    if stage in ADV_FROM:
        a = ADV_FROM[stage]
        return f'Next: {CFG[a]["name"]} moves the ticket on when task "{ADV[a][0]}" is completed - but this workflow does not create a task with that title (F-01), so the ticket must be moved by hand.'
    return 'Next: no workflow in scope moves the ticket on; it must be moved by hand (F-02).'


# ------------------------------------------------------------------ Detailed Action Map
DAM, TASKROWS, PO = [], [], []
step_no = 0
for wid, name, stage in SCOPE:
    cfg = CFG[wid]
    e = cfg['enrollmentCriteria']
    if e['type'] == 'EVENT_BASED':
        trig = 'Task status changes to Completed, AND ' + filt(e['refinementCriteria'])
        trig_props = 'Task status; Task title; associated ticket Pipeline and Ticket status'
        trig_type = 'Event trigger: property value changed (Task status = Completed), with refinement filters'
    else:
        trig = filt(e['listFilterBranch'])
        trig_props = ', '.join(PROP.get(f['property'], f['property']) for b in e['listFilterBranch']['filterBranches'] for f in b['filters'])
        trig_type = 'Records meet custom conditions (filter-based, "LIST_BASED")'
    st = wfstats.get(wid)
    obj = {'0-3': 'Deal', '0-27': 'Task'}.get(cfg['objectTypeId'], 'Ticket')
    rec_trig = (f'Records: {st["n"]} enrollments on {st["tix"]} tickets, each starting {st["dmin"]:.0f}-{st["dmax"]:.0f} s after the ticket entered {STG[stage]}; no ticket enrolled twice.' if st else '')
    if wid in ADV:
        rec_trig = ADV_EV[wid]['summary']
    DAM.append([cfg['name'], wid, 'Trigger', '-', '0', 'Enrollment trigger', trig_type,
                f'Enrolls a {obj.lower()} when: {trig}.', obj, trig_props,
                'Any', trig, 'All conditions in the group must be true', 'None',
                f'Re-enroll: {"ON" if e["shouldReEnroll"] else "OFF"}. Unenroll when criteria no longer met: {"ON" if e.get("unEnrollObjectsNotMeetingCriteria") else "OFF"}. Unenroll/suppression criteria: none configured.',
                'Step 1', f'Workflow config (GET /automation/v4/flows/{wid}, revision {cfg["revisionId"]}, updated {cfg["updatedAt"][:10]}). {WURL(wid)}', rec_trig, 'VERIFIED (config)'])
    walked = walk(cfg)
    n = 0
    labels = {}
    for a, br in walked:
        if a.get('_end'):
            continue
        n += 1
        labels[a['actionId']] = n
    for k, (a, br) in enumerate(walked):
        nxt = None
        if a.get('_end'):
            DAM.append([cfg['name'], wid, 'End', br or 'Main path', '-', 'End', 'End of workflow', 'Workflow ends for this record.', '-', '-', '-', '-',
                        br or 'Reached after the last action', 'None', 'Record leaves the workflow',
                        (end_next(wid)),
                        'Workflow config', '', 'VERIFIED (config)'])
            continue
        f = a.get('fields', {})
        num = labels[a['actionId']]
        later = [x for x, _ in walked[k + 1:] if not x.get('_end')]
        if a['type'] in ('LIST_BRANCH', 'STATIC_BRANCH'):
            nxt_txt = 'Goes to the first action of the matching branch (see Branch column of following rows)'
        else:
            nx = a.get('connection', {}).get('nextActionId')
            nxt_txt = f'Step {labels[nx]}' if nx else 'End'
        if a.get('actionTypeId') == '0-3':
            own_txt, own_name = owner_rule(f)
            due_txt, delta = due_rule(f)
            gs = groups_for(wid, a['actionId'])
            par = [g for g in gs if g['kind'] == 'PARENT']
            subs = [g for g in gs if g['kind'] == 'SUB']
            if '|' in EXEC[wid].get(7, '') and a['actionId'] in EXEC[wid][7].split('|'):
                par = [g for g in par if own_name and g['owners'].get(own_name)]
                subs = []
            p = par[0] if par else None
            checks = []
            if p:
                checks.append(f'created {p["n"]}x')
                if own_name:
                    checks.append(f'owner {own_name} on {p["owners"].get(own_name, 0)}/{p["n"]}')
                else:
                    checks.append(f'owner = ticket\'s current owner on {p["tom"][0]}/{p["tom"][1]}')
                bdc = p['bd'].get(delta, 0)
                checks.append(f'due {delta} bd on {bdc}/{p["n"]}')
            rec = ('Records: ' + ', '.join(checks) + f'; {len(subs)} subtask(s) created under it.') if p else 'Records: never executed yet (branch not taken in any enrollment).'
            if p and wid == '1866658899' and a['actionId'] in ('30', '32'):
                rec = 'Records: 1 proposal task created for Brock Hegr (2026-09-25). Steps 8 (Brock branch) and 11 (default branch) both assign Brock, so the records cannot show which branch ran.'
            DAM.append([cfg['name'], wid, f'Step {num}', br or 'Main path (no branch)', num, 'Create task', 'Create task (actionTypeId 0-3)',
                        f'Creates task "{f["subject"].strip()}" assigned to {own_txt.split(" (")[0]}, due {due_txt.split(" (")[0]}' + (f', with {len(subs)} subtask(s) (subtasks are not returned by the API - from records)' if subs else '') + '.',
                        'Task', f'New task: "{f["subject"].strip()}"', '(new record)',
                        f'Title: {f["subject"].strip()} | Type: {f.get("task_type")} | Priority: {f.get("priority")} | Owner: {own_txt} | Due: {due_txt} | Associations: {assoc_rule(f)} | Queue: {f.get("queue_id", "none")} | Reminder: {"set" if f.get("reminder_time") else "none"}',
                        br or 'Always (no branch)', 'None (no delay actions in this workflow)', rec, nxt_txt,
                        f'Workflow config action {a["actionId"]} (revision {cfg["revisionId"]}).', 'Notes: ' + strip(f.get('body', ''))[:600], 'VERIFIED (config); subtasks from records'])
            # Task & Subtask sheet rows
            TASKROWS.append([cfg['name'], wid, num, f['subject'].strip(), '-', br or 'Always', own_txt, due_txt, f.get('priority'), f.get('task_type'), assoc_rule(f),
                             strip(f.get('body', '')), (rec_owner(p) if p else '-'), (rec_due(p) if p else '-'), (p['n'] if p else 0),
                             ('Not returned by the API' if True else ''), 'VERIFIED (config)'])
            for s in subs:
                var = '; '.join(f'"{v}" x{c} ({", ".join(d)})' for v, c, d in s['variants'])
                TASKROWS.append([cfg['name'], wid, num, f['subject'].strip(), s['title'], br or 'Always', '(subtask) ' + rec_owner(s), '(subtask) ' + rec_due(s), '-', '-',
                                 '; '.join(f'{k} {v}/{s["n"]}' for k, v in s['assoc'].most_common()), '-', rec_owner(s), rec_due(s), s['n'],
                                 ('Title also VERIFIED in Action 1 screenshot. ' if wid == '1866384267' and num == 1 else '') + (f'Title variants: {var}. ' if var else '') + (f'{s["open_under_done"]} open under a completed parent.' if s['open_under_done'] else ''),
                                 'VERIFIED (records)' + (' + screenshot' if wid == '1866384267' and num == 1 else '')])
        elif a.get('actionTypeId') == '0-14':
            props = '; '.join(f'{PROP.get(p["targetProperty"], p["targetProperty"])} = {val(p["targetProperty"], p["value"].get("staticValue"))}' for p in f['properties'])
            cw = [t for t in OB if t['properties'].get('hs_object_source_detail_1') == cfg['name']]
            DAM.append([cfg['name'], wid, f'Step {num}', br or 'Main path (no branch)', num, 'Create record', 'Create record - Ticket (actionTypeId 0-14, object 0-5)',
                        f'Creates a ticket: {props}. Associates it with: {assoc_rule(f)}.', 'Ticket', 'New ticket', '(new record)', props,
                        'Always (no branch)', 'None', f'Records: {len(cw)} tickets carry this workflow as their source ({min(t["properties"]["createdate"] for t in cw)[:10]} to {max(t["properties"]["createdate"] for t in cw)[:10]}).',
                        nxt_txt, f'Workflow config action {a["actionId"]}.', 'Pipeline is not set explicitly; HubSpot derives it from the stage (UNASSIGNED belongs to Onboarding Pipeline).', 'VERIFIED (config)'])
        elif a.get('actionTypeId') == '0-5':
            tgt = 'the ticket associated with the enrolled task' if f.get('association', {}).get('associationTypeId') == 230 else 'the enrolled record'
            newv = val(f['property_name'], f['value'].get('staticValue'))
            DAM.append([cfg['name'], wid, f'Step {num}', br or 'Main path (no branch)', num, 'Edit record', 'Edit record - set property value (actionTypeId 0-5)',
                        f'Sets {PROP.get(f["property_name"], f["property_name"])} = {newv} on {tgt}.', 'Ticket (associated with the task)', PROP.get(f['property_name'], f['property_name']),
                        STG.get(ADV[wid][1]) if wid in ADV else '-', newv, 'Always (no branch)', 'None', ADV_EV[wid]['result'] if wid in ADV else '', nxt_txt,
                        f'Workflow config action {a["actionId"]}.', f'Moving the ticket into {newv} makes it meet the trigger of the {newv} (+SubTask) workflow.' if wid in ADV else '', 'VERIFIED (config)'])
        elif a['type'] == 'LIST_BRANCH':
            bs = '; '.join(f'"{b["branchName"]}": {filt(b["filterBranch"])}' for b in a['listBranches'])
            DAM.append([cfg['name'], wid, f'Step {num}', br or 'Main path', num, 'If/then branch', 'If/then branch - filter based (LIST_BRANCH)',
                        f'Checks: {bs}. If none match: {"go to step " + str(labels[a["defaultBranch"]["nextActionId"]]) if a.get("defaultBranch") else "no default branch - workflow ends"}.',
                        'Company (associated to ticket)', 'PPC Ads (Yes/No)', '-', '-', bs, 'None', 'Routes the ticket', nxt_txt, f'Workflow config action {a["actionId"]}.', '', 'VERIFIED (config)'])
        elif a['type'] == 'STATIC_BRANCH':
            prop = re.sub(r'.*\.(\w+) }}$', r'\1', a['inputValue'].get('propertyToken', ''))
            bs = '; '.join(f'{b["branchValue"]} -> step {labels[b["connection"]["nextActionId"]]}' for b in a['staticBranches'])
            DAM.append([cfg['name'], wid, f'Step {num}', br, num, 'If/then branch', 'Branch on one property value (STATIC_BRANCH)',
                        f'Reads {PROP.get(prop, prop)} from the ticket\'s associated company (most recently modified one) and branches: {bs}; anything else -> step {labels[a["defaultBranch"]["nextActionId"]]}.',
                        'Company (fetched: most recently modified associated company)', PROP.get(prop, prop), '-', '-', bs, 'None', 'Routes to the proposal task for that manager', nxt_txt,
                        f'Workflow config action {a["actionId"]}; data source sorted by hs_lastmodifieddate DESC.', '', 'VERIFIED (config)'])

dam_h = ['Workflow', 'Workflow ID', 'Workflow Step', 'Branch', 'Action #', 'Action Name', 'Action Type', 'What The Action Does', 'Object', 'Property / Record Affected',
         'Current Value', 'New Value', 'Condition', 'Delay', 'Result', 'Next Action', 'Evidence', 'Notes', 'Evidence Level']

# ------------------------------------------------------------------ Process Overview
po = []
s = 1
cw_cfg = CFG['1670039203']
po.append([s, 'Deal moves to Closed won (White Label Storage SALES pipeline)', f'Deal stage is any of Closed won. Re-enroll OFF.', cw_cfg['name'], 'Enrollment trigger', 'Deal enrolls (once per deal)', s + 1]); s += 1
f0 = cw_cfg['actions'][0]['fields']
po.append([s, 'Ticket created', 'Always', cw_cfg['name'], 'Step 1 - Create record (Ticket)',
           'Ticket name = deal name; stage = UNASSIGNED (Onboarding Pipeline); owner = Elizabeth Airey; associated with the deal, all the deal\'s contacts and all the deal\'s companies (label "Transitions").', s + 1]); s += 1
po.append([s, 'Ticket sits in UNASSIGNED', 'None of the 7 Transitions workflows enrolls in UNASSIGNED', '-', '-',
           'None of the 13 workflows moves the ticket on. Someone (or something outside this scope) must change Ticket status to Transition Kickoff.', s + 1]); s += 1
for wid, name, stage in SCOPE[1:8]:
    cfg = CFG[wid]
    po.append([s, f'Ticket status becomes {STG[stage]}', filt(cfg['enrollmentCriteria']['listFilterBranch']) + '. Re-enroll OFF.', cfg['name'], 'Enrollment trigger',
               f'Ticket enrolls within seconds ({wfstats[wid]["n"]} enrollments so far)', s + 1]); s += 1
    for a, br in walk(cfg):
        if a.get('_end'):
            continue
        f = a.get('fields', {})
        if a.get('actionTypeId') == '0-3':
            own, _ = owner_rule(f)
            due, _ = due_rule(f)
            subs = [g for g in groups_for(wid, a['actionId']) if g['kind'] == 'SUB']
            po.append([s, f'Task created: {f["subject"].strip()}', br or 'Always', cfg['name'], 'Create task', f'Owner: {own.split(" (")[0]}; due {due.split(" (")[0]}; {len(subs)} subtask(s).', s + 1]); s += 1
        else:
            po.append([s, 'Branch', br or 'Always', cfg['name'], 'If/then branch', 'PPC Ads = Yes on an associated company -> branch on Marketing Portfolio Manager; otherwise workflow ends.' if a['type'] == 'LIST_BRANCH' else 'Brock Hegr / Sarah Schlosberg / Mohammad Abudahab -> proposal task for that person; anyone else -> Brock Hegr.', s + 1]); s += 1
    if stage in ADV_FROM:
        a = ADV_FROM[stage]
        po.append([s, f'Task "{ADV[a][0]}" is completed', f'Task title = "{ADV[a][0]}" AND associated ticket is in Onboarding Pipeline / {STG[stage]}', CFG[a]['name'], 'Enrollment trigger (task completed)',
                   f'NOT REACHED for (+SubTask) tickets: {CFG[wid]["name"]} creates no task with this title. Only legacy tasks still trigger it ({ADV_EV[a]["since"]} since 2026-08-20). Otherwise the ticket is moved by hand.', s + 1]); s += 1
        po.append([s, f'Ticket status set to {STG[ADV[a][2]]}', 'Only when the step above fires', CFG[a]['name'], 'Step 1 - Edit record (Ticket status)', ADV_EV[a]['result'], s + 1]); s += 1
    elif wid != '1867929348':
        po.append([s, f'{SHORT[wid]} work done; ticket must be moved to the next stage', 'No workflow in scope automates this move', '-', '-',
                   'Moved by hand (30-Day subtask 3 says so explicitly). Entering the next stage triggers the next workflow.', s + 1]); s += 1
po[-1][-1] = 'End'
po_h = ['Step #', 'Event', 'Condition', 'Workflow', 'Action', 'Result', 'Next Step']

# ------------------------------------------------------------------ Workflow Inventory
wi = []
for wid, name, stage in SCOPE:
    cfg = CFG[wid]
    e = cfg['enrollmentCriteria']
    acts = cfg['actions']
    kinds = collections.Counter({'0-3': 'Create task', '0-14': 'Create record', '0-5': 'Edit record'}.get(a.get('actionTypeId'), 'If/then branch') for a in acts)
    if wid in ADV:
        rel = f'Watches a task created by the legacy workflow; moves the ticket from {STG[ADV[wid][1]]} to {STG[ADV[wid][2]]}, which triggers {CFG[NEXT_WF[ADV[wid][2]]]["name"]}.'
    elif wid == '1670039203':
        rel = 'Creates the ticket the 7 Transitions workflows act on.'
    else:
        rel = f'Fires when Ticket status = {STG[stage]}.' + (f' Intended hand-off: {CFG[ADV_FROM[stage]]["name"]}.' if stage in ADV_FROM else ' No workflow in scope moves the ticket on.')
    wi.append([cfg['name'], wid, {'0-3': 'Deal', '0-27': 'Task'}.get(cfg['objectTypeId'], 'Ticket'), cfg.get('description') or '(no description)',
               (f'Records meet custom conditions: {filt(e["listFilterBranch"])}' if e['type'] != 'EVENT_BASED' else f'Event: Task status changes to Completed, AND {filt(e["refinementCriteria"])}'), 'ON' if e['shouldReEnroll'] else 'OFF',
               'None configured (no unenroll criteria; unenroll if criteria no longer met = OFF)', f'{len(acts)} ({", ".join(f"{v} {k}" for k, v in kinds.items())})',
               '; '.join(f'{a["fields"]["subject"].strip()}' for a in acts if a.get('actionTypeId') == '0-3') or ('Edit record: Ticket status = ' + STG[ADV[wid][2]] if wid in ADV else 'Create record: Ticket'),
               rel, f'{"ON" if cfg["isEnabled"] else "OFF"}; revision {cfg["revisionId"]}; created {cfg["createdAt"][:10]}; last updated {cfg["updatedAt"][:10]}. {WURL(wid)}'])
wi_h = ['Workflow Name', 'Workflow ID', 'Object', 'Purpose / Observed Function', 'Enrollment Trigger', 'Re-enrollment', 'Suppression', 'Number of Actions', 'Key Actions', 'Related Workflows', 'Notes']

# ------------------------------------------------------------------ Audit Findings
AF = []


def FN(cls, wf, act, finding, ev, why, verify):
    AF.append([f'F-{len(AF) + 1:02d}', cls, wf, act, finding, ev, why, verify, 'Open'])


def open_counts(name, stage):
    order = ["1175587148", "1100007030", "1298054295", "1094530721", "1094530722", "1094530723", "1094493506", "1094493507", "1102485356", "1094530724"]
    ts = M[name]['tasks']
    later = sum(1 for t in ts if t['properties']['hs_task_status'] not in ('COMPLETED', 'DEFERRED') and t['tickets'] and TK.get(t['tickets'][0]) and TK[t['tickets'][0]]['properties']['hs_pipeline_stage'] in order and order.index(TK[t['tickets'][0]]['properties']['hs_pipeline_stage']) > order.index(stage))
    over = sum(1 for t in ts if t['properties']['hs_task_status'] not in ('COMPLETED', 'DEFERRED') and t['due'] and t['due'] < dt.datetime(2026, 10, 2, tzinfo=dt.timezone.utc))
    oud = sum(g['open_under_done'] for g in M[name]['groups'])
    return later, over, oud


OC = {wid: open_counts(n, s) for wid, n, s in SCOPE[1:8]}
stage_writers = [(CFG[w]['name'], a['actionId']) for w in CFG for a in CFG[w]['actions'] if a.get('actionTypeId') == '0-5']
subs_noown = sum(g['n'] - g['owners'].get('(no owner)', 0) for w, n, s in SCOPE[1:7] for g in M[n]['groups'] if g['kind'] == 'SUB')
subs_all = sum(g['n'] for w, n, s in SCOPE[1:7] for g in M[n]['groups'] if g['kind'] == 'SUB')
contact_actions = [(SHORT[w], labels) for w in CFG for labels in [sum(1 for a in CFG[w]['actions'] if any(x['target']['associationTypeId'] == 204 for x in a.get('fields', {}).get('associations', [])))] if labels]
no_contact = [f'{SHORT[w]} "{a["fields"]["subject"].strip()}"' for w in CFG for a in CFG[w]['actions'] if a.get('actionTypeId') == '0-3' and not any(x['target']['associationTypeId'] == 204 for x in a['fields']['associations'])]
no_company = [f'{SHORT[w]} "{a["fields"]["subject"].strip()}"' for w in CFG for a in CFG[w]['actions'] if a.get('actionTypeId') == '0-3' and not any(x['target']['associationTypeId'] == 192 for x in a['fields']['associations'])]
tasks_with_contact = sum(1 for w, n, s in SCOPE[1:8] for t in M[n]['tasks'] if t['contacts'])
tasks_all = sum(len(M[n]['tasks']) for w, n, s in SCOPE[1:8])
static = collections.Counter()
for w in list(CFG)[1:]:
    for a in CFG[w]['actions']:
        if a.get('actionTypeId') == '0-3':
            o, nm = owner_rule(a['fields'])
            if nm:
                static[nm] += 1
cw = [t for t in OB if t['properties'].get('hs_object_source_detail_1') == CFG['1670039203']['name']]
cw_eliz = sum(1 for t in cw if t['properties']['hubspot_owner_id'] == '81929768')
cw2 = sum(1 for t in cw if len(OA.get(t['id'], {}).get('deals', [])) == 2)

tot_since = sum(v['since'] for v in ADV_EV.values())
FN('Confirmed', 'The 5 stage-advance workflows + the 7 Transitions (+SubTask) workflows', 'Advance workflows Trigger',
   'The automatic stage moves no longer work for the new process. Each stage-advance workflow moves the ticket on when a task with an exact title is completed: ' + '; '.join(f'"{ADV[w][0]}" ({STG[ADV[w][1]]} -> {STG[ADV[w][2]]})' for w in ADV) + '. Those titles were created only by the legacy (non-subtask) workflows. The (+SubTask) workflows create differently named tasks (e.g. "17. End of stage task sign off, Transition Kick Off"), so for tickets that started in the new process nothing moves the ticket automatically.',
   'Workflow config: refinement filter "Task title is equal to ..." on each advance workflow; no Create task action in the (+SubTask) workflows uses those titles; no task created by a (+SubTask) workflow has one. Records: historically ' + ', '.join(f'{ADV_EV[w]["moved"]}/{ADV_EV[w]["done"]}' for w in ADV) + f' completions moved the ticket within 2 minutes; since 2026-08-20 only {tot_since} completions of leftover legacy tasks (Evidence - Stage Advances).',
   'Every stage move in the new process is manual. A ticket stays in a stage until someone changes Ticket status, regardless of whether the sign-off subtask is done; meanwhile the advance workflows still fire on old tasks for tickets that began under the legacy process.',
   'Decide which (+SubTask) task should trigger each move (e.g. the parent "Ticket Owner/PM" task or the "End of stage" subtask) and update the advance workflows\' title filter, or retire them.')
FN('Confirmed', 'All 13', 'Stage moves',
   'Two stage moves have no automation at all in the 13 workflows: UNASSIGNED -> Transition Kickoff (after the Closed Won workflow creates the ticket) and Post 30-Day Monitoring -> Transition Completed (30-Day subtask 3 says to move it manually).',
   'Workflow config: no advance workflow has from-stage UNASSIGNED or Post 30-Day Monitoring.', 'Two process starts/ends rely entirely on a person.', 'Confirm ownership of these two moves.')
FN('No Issue Found', 'The 5 stage-advance workflows', 'Trigger',
   'The advance workflows only move a ticket if it is still in the expected stage (refinement filter on the associated ticket: Onboarding Pipeline AND Ticket status = the from-stage), so completing an old sign-off task on a ticket that has moved on does nothing. Re-enrollment is OFF, so each task triggers at most once.',
   'Workflow config: refinementCriteria association filter (typeId 230) on hs_pipeline and hs_pipeline_stage; shouldReEnroll = false.', 'Prevents tickets being pushed backwards or skipped.', 'n/a')
FN('Confirmed', 'All 7 Transitions workflows', 'Trigger',
   'Re-enrollment is OFF on all 13 workflows, and none has unenroll or suppression criteria. A ticket gets each stage\'s tasks only the first time it enters that stage.',
   'Workflow config: shouldReEnroll = false on all 13; unEnrollObjectsNotMeetingCriteria = false; no suppression lists.',
   'A ticket sent back to a stage (e.g. after On Hold, or moved back to fix something) gets no new tasks; its earlier tasks, possibly completed, are all it has. A deal that is re-closed won does not get a second ticket.',
   'Decide whether returning to a stage should re-create tasks.')
FN('Needs Verification', 'All 7 Transitions workflows', 'Every Create task action',
   'Subtask settings are not returned by the HubSpot API. The config for each Create task action has title, owner, due date, associations and notes, but no subtask list, so subtask titles, owners and due dates in this workbook come from the task records (and, for Kickoff Step 1, a screenshot).',
   'GET /automation/v4/flows/{id}: action fields contain no subtask key; the editor shows "with 14 subtasks" (Kickoff screenshot).',
   'Subtask owner and due-date rules cannot be confirmed from config.',
   'Screenshot one subtask\'s settings in any action to confirm owner/due options.')
FN('Confirmed', 'Kickoff, Pre-Launch, Launch Readiness, Go-Live, Final Sign-Off, 30-Day', 'All subtasks',
   f'Subtasks are created with no owner: {subs_noown} of {subs_all} subtasks from these 6 workflows have an owner. Only Transition Complete subtasks have one.',
   'Task records: hubspot_owner_id empty on every subtask from these workflows.',
   'Unowned subtasks do not appear in anyone\'s task list or overdue view; the parent owner has to open the parent to see them.',
   'Check the subtask owner option (see the subtask-settings finding).')
FN('Potential Issue', 'All 7 Transitions workflows', 'All Create task actions',
   f'Parent tasks get completed while their subtasks stay open: {sum(v[2] for v in OC.values())} open subtasks under completed parents (' + ', '.join(f'{SHORT[w]} {v[2]}' for w, v in OC.items()) + ').',
   'Task records: subtask status vs parent status.',
   'The parent looks done when work is not finished.', 'Confirm the intended behaviour for open subtasks.')
FN('Potential Issue', 'All 7 Transitions workflows', 'All',
   'Tasks from earlier stages stay open after the ticket moves on. Open tasks on tickets now in a later stage: ' + ', '.join(f'{SHORT[w]} {v[0]}' for w, v in list(OC.items())[:-1]) + f'. Open and past due on {AS_OF}: ' + ', '.join(f'{SHORT[w]} {v[1]}' for w, v in OC.items()) + '.',
   'Task records vs ticket stage.', 'No action in the 13 workflows closes, defers or checks earlier tasks, so stage moves are not gated on completion.', 'Decide whether tasks must be complete before a stage move.')
FN('Confirmed', 'All 7 Transitions workflows', 'Task notes',
   'Dependencies are written into task notes only. Example (Kickoff Step 1): "Waiting for Customer - Customer must pay the Setup Fee invoiced in item 5; Waiting for Other - All Kick-Off subtasks (PM, Momen, Bryn) must be complete"; Kickoff Steps 2-3: "Waiting for PM - needs client PoC details / contract details". All tasks are created at the same moment with no delays or conditions.',
   'Workflow config: task body text; no delay actions in any of the 13 workflows.',
   'Nothing enforces the order; people receive dependent tasks before their inputs exist.', 'None - awareness. Consider whether due dates reflect the dependencies.')
FN('Confirmed', 'All 13', 'Associations',
   f'The contact association setting almost never adds anyone. {sum(c for _, c in contact_actions)} Create task actions copy "Ticket -> Contact with label Transition" (associationTypeId 72), but ticket-contact associations on the enrolled tickets are unlabelled, so only {tasks_with_contact} of {tasks_all} tasks have a contact (from the few tickets where a contact does carry the label).',
   'Workflow config: association source 72 = ticket-contact label "Transition". Kickoff tickets: 21/21 have contacts, 0 labelled "Transition". Task records: contacts on tasks.',
   'Tasks never show on the customer contact\'s record.', 'Either label the main contact "Transition" on each ticket, or change the actions to copy all associated contacts (type 16).')
FN('Confirmed', 'Several', 'Associations',
   'Association settings differ between actions. No contact association: ' + '; '.join(dict.fromkeys(no_contact)) + '. No company association: ' + '; '.join(dict.fromkeys(no_company)) + '.',
   'Workflow config: associations per Create task action. Records match (e.g. Final Sign-Off Mike parent is ticket-only on 10/11).',
   'Tasks from those actions do not show on the company (or contact) record or in company-based views.', 'Confirm whether the differences are intentional.')
FN('Confirmed', 'All 7 Transitions workflows', 'Owner settings',
   'Owners: actions titled "Ticket Owner/PM", the main Kickoff task, the Pre-Launch "Subtask" task and both 30-Day tasks are assigned to the ticket owner. All other tasks are assigned to a fixed user: ' + ', '.join(f'{k} ({v})' for k, v in static.most_common()) + '.',
   'Workflow config owner_assignment (OBJECT_PROPERTY hubspot_owner_id vs STATIC_VALUE).',
   'Fixed users are hard-coded: if a person leaves or changes role, tasks keep going to them until each action is edited.', 'Review the fixed-user list.')
FN('Confirmed', 'Closed Won | Create Ticket in INITIAL SETUP - UNASSIGNED', 'Step 1',
   f'The ticket is created with a fixed owner, Elizabeth Airey (owner ID 81929768). Today only {cw_eliz} of {len(cw)} tickets created by this workflow are owned by her, so the owner is changed afterwards by something outside these 13 workflows. Every "Ticket owner" task in the Transitions workflows goes to whoever owns the ticket at the moment of enrollment.',
   'Workflow config: hubspot_owner_id = 81929768 (static). Ticket records: current owners.',
   'If the owner has not been changed by the time the ticket enters Kickoff, the PM tasks go to Elizabeth Airey.', 'Confirm how and when the ticket owner is changed to the PM.')
FN('Needs Verification', 'Closed Won | Create Ticket in INITIAL SETUP - UNASSIGNED', 'Step 1 associations',
   f'The action associates the ticket with the enrolled deal only, plus the deal\'s contacts and companies. Yet {cw2} of {len(cw)} tickets it created are associated with 2 deals.',
   'Workflow config: ticket->deal = enrolled object only. Ticket records: deal associations.', 'The second deal was added manually or by other automation; duplicate links can confuse reporting.', 'Spot-check a ticket with 2 deals.')
FN('Confirmed', 'Transitions - Pre Launch Setup Tasks (+SubTask)', 'Steps 6-8',
   'Marketing proposal logic (added 2026-09-24): if an associated company has PPC Ads = Yes, the workflow reads Marketing Portfolio Manager from the most recently modified associated company and creates "Marketing | Create Marketing Proposal" for Brock Hegr, Sarah Schlosberg or Mohammad Abudahab; any other value (including empty) goes to Brock Hegr. If PPC Ads is not Yes, the workflow ends with no proposal task.',
   'Workflow config actions 29 (list branch "PPC Yes"), 31 (branch on fetched company marketing_portfolio_mgr), 30/32/33/34 (create task). Records: ran once (2026-09-25, Brock).',
   'Tickets with several companies use whichever company was modified most recently, which can change over time. Unrecognised managers silently fall back to Brock.', 'Confirm the fallback owner and the multi-company behaviour.')
FN('Potential Issue', 'Transitions - Pre Launch Setup Tasks (+SubTask)', 'Steps 1-5',
   'One enrollment (Stow Pros (Frankford Deal), ticket 46316978849, 2026-08-31) has only the Step 4 task set. Steps 1-5 are unconditional in the config, so the other tasks were most likely created and later deleted (INFERENCE).',
   f'Workflow config: no branch before Step 6. Records: only actionExecutionIndex 3 tasks exist for that enrollment. {TURL("46316978849")}',
   'That ticket is missing most of its Pre-Launch work.', 'Check the ticket\'s activity/workflow history.')
FN('Potential Issue', 'Transitions - Transition Kickoff Tasks (+SubTask)', 'Trigger',
   'Spencerport Personal Storage (48042783912) entered Transition Kickoff on 2026-09-01 and was moved back to UNASSIGNED 9 seconds later. It got no Kickoff tasks. The config has no suppression and no branches, so the likely cause is timing: HubSpot evaluates the filter a few seconds after the change (4-13 s for other tickets), by which time the ticket no longer matched (INFERENCE).',
   f'Workflow config: filter-based trigger, no unenroll criteria. Ticket: entered Kickoff 12:27:50 UTC, entered UNASSIGNED 12:27:59 UTC. {TURL("48042783912")}',
   'Any ticket moved through a stage in under ~10 s skips that stage\'s tasks.', 'Check Kickoff Performance history for that ticket.')
FN('Potential Issue', 'Transitions - TRANSITION COMPLETE (+SubTask)', 'Step 1',
   'The final check is created after the ticket is closed: entering Transition Completed (a closed stage) creates "Transition | TRANSITION COMPLETE | Subtask - Ticket Owner/PM", due 0 business days (same day), with subtask "1.All open items completed and 30 days post transition". The 30-Day subtask 3 tells the PM to move the ticket to Transition Completed only after all items are done.',
   'Workflow config: due delta 0. Records: 17/18 due same day.', 'The completion check runs after the stage it should gate; open tasks on closed tickets are easy to miss.', 'Confirm the intended order.')
FN('Potential Issue', 'Transitions - 30-Day Monitoring (+SubTask)', 'Step 1',
   'Task "Transition | 30 - DAY MONITORING | Subtask - Automated" is assigned to the ticket owner and holds subtask "1. Send CSAT survey to client". The name suggests something automated, but it is a manual task for the PM (5 of 6 still not started).',
   'Workflow config: owner = ticket owner, due 30 business days.', 'The CSAT survey may be assumed to be automatic.', 'Confirm how the CSAT survey is meant to be sent.')
FN('Confirmed', 'All 7 Transitions workflows', 'Due dates',
   'All due dates are business-day offsets at 08:00 (UTC-04:00): Kickoff 7, Pre-Launch 6 (proposal 3), Launch Readiness 6, Go-Live 1, Final Sign-Off 4, 30-Day 30, Transition Complete 0. Records match on the parent tasks except where users later edited due dates (mostly Bryn\'s and Mo\'men\'s tasks).',
   'Workflow config due_time (delta, daysOfWeek Mon-Fri, 08:00). Records: parent due offsets (Detailed Action Map "Result").',
   'Go-Live gives 1 business day for 15 subtasks of work, which drives overdue counts.', 'Confirm the offsets are realistic.')
FN('Confirmed', 'Transitions - Pre Launch Setup Tasks (+SubTask); Launch Readiness; Kickoff', 'Subtasks',
   'Subtask content changed while live: Pre-Launch subtask 11 sent marketing requests to Rachel (enrollments 2026-08-20 to 08-25) then Brock (from 2026-09-01); Launch Readiness subtask 8 gained "at least 1 week before Target Go-Live..." from 2026-08-31; a live 2026-08-25 Pre-Launch enrollment created "TEST 1. Provide guidance..." with no associations.',
   'Task records by creation date.', 'Older tickets carry older instructions; one orphaned test subtask exists.', 'Clean up the TEST subtask.')
FN('Confirmed', 'Several', 'Task titles',
   'Facility-specific text appears in titles of workflow-created tasks (e.g. "Subtask - Bryn (Valparaiso)", "7. Complete Safelease set up (AC Storage -Pending Safelease Codes)"). Config titles do not contain these, so they are manual edits.',
   'Config titles vs task records.', 'Reports grouped by title will split.', 'None - awareness.')
FN('Needs Verification', 'Transitions - Transition Kickoff Tasks (+SubTask)', 'Step 1 subtasks',
   'In the 4 earliest Kickoff enrollments (2026-08-24 to 08-27) the parent got the company but 13-14 of its 14 subtasks did not; from 2026-08-28 subtasks get it too. Config was last updated 2026-08-31.',
   'Task records: company associations of subtasks vs parent.', 'About 70 older subtasks are not on the company record.', 'Optional clean-up.')
FN('Needs Verification', 'Transitions - TRANSITION COMPLETE (+SubTask)', 'Step 1',
   'One enrollment (2026-09-09) created tasks linked to company 38502110732 only, with no ticket, although the action associates the enrolled ticket.',
   'Task records: enrollment 2815002373637.', 'The ticket was probably deleted or merged after enrollment.', 'Check that company\'s ticket history.')
FN('Confirmed', 'Transitions - TRANSITION COMPLETE (+SubTask)', 'Step 1 subtask',
   'Transition Complete subtasks do have an owner (15/18; 14 match the parent owner), unlike every other workflow.', 'Task records.', 'Shows a subtask owner can be set.', 'Use this action as the reference when checking subtask owners.')
FN('No Issue Found', 'All 7 Transitions workflows', 'Enrollment',
   'Every ticket whose latest entry into a stage is after that workflow went live was enrolled exactly once, apart from Spencerport (see Kickoff Trigger finding). The configuration and the records agree on action order, owners and due dates.',
   'Enrollment evidence sheet; config vs records cross-check.', 'Task creation itself is reliable once a ticket reaches a stage.', 'n/a')
af_h = ['Finding #', 'Classification', 'Workflow', 'Action #', 'Finding', 'Evidence', 'Why It Matters', 'Recommended Verification', 'Status']

# ------------------------------------------------------------------ evidence sheets
ev = []
for wid, name, stage in SCOPE[1:8]:
    for i in M[name]['enr']:
        tk = TK.get(i['tickets'][0]) if i['tickets'] else None
        ev.append([CFG[wid]['name'], wid, i['enr'], i['tickets'][0] if i['tickets'] else '(no ticket)', tk['properties']['subject'] if tk else '', TURL(i['tickets'][0]) if i['tickets'] else '',
                   STG.get(tk['properties']['hs_pipeline_stage'], '') if tk else '', i['entered'].strftime('%Y-%m-%d %H:%M:%S UTC') if i['entered'] else '',
                   i['start'].strftime('%Y-%m-%d %H:%M:%S UTC'), round(i['delta'], 1) if i['delta'] is not None else '', len(i['tasks']),
                   sum(1 for t in i['tasks'] if t['properties']['hs_task_is_sub_task'] == 'true'), sum(1 for t in i['tasks'] if t['properties']['hs_task_status'] not in ('COMPLETED', 'DEFERRED'))])
ev_h = ['Workflow', 'Workflow ID', 'Enrollment ID', 'Ticket ID', 'Ticket Name', 'Ticket Link', 'Ticket Stage Now', 'Ticket Entered Stage (latest)', 'First Task Created', 'Seconds After Stage Entry', 'Tasks Created', 'Of Which Subtasks', 'Still Open']

tr_h = ['Workflow', 'Workflow ID', 'Action #', 'Parent Task (config title)', 'Subtask', 'Conditions / Branch', 'Owner (config)', 'Due (config)', 'Priority', 'Type', 'Associations (config)', 'Notes (config)',
        'Owner (records)', 'Due (records)', 'Times Created', 'Notes', 'Evidence Level']

# ------------------------------------------------------------------ Read Me
ws = wb.active
ws.title = 'Read Me'
lines = [('WLS Transitions Workflow Audit', Font(name='Arial', size=14, bold=True)),
         (f'Data as of {AS_OF}. HubSpot portal {PORTAL}.', F), ('', F),
         ('SOURCE OF TRUTH', B),
         ('The configuration of all 13 workflows was read from the HubSpot Automation API (GET /automation/v4/flows/{id}) on 2026-10-02. Every trigger, setting and action in this workbook comes from that configuration and is marked VERIFIED (config).', F),
         ('The API does not return subtasks. Subtask titles, owners and due dates come from the tasks the workflows actually created (VERIFIED (records)) and, for Kickoff Step 1, from a screenshot of the action supplied by WLS.', F),
         ('Task records are also used to check the configuration against what really happened (counts, owners, due dates, timing).', F), ('', F),
         ('EVIDENCE LABELS', B),
         ('VERIFIED (config) - read from the workflow configuration.', F), ('VERIFIED (records) - read from HubSpot task / ticket records.', F),
         ('INFERENCE - derived from config + records; not directly visible.', F), ('NEEDS VERIFICATION - cannot be determined from either source.', F), ('', F),
         ('ACTION NUMBERS', B),
         ('Step / Action # follows the workflow from its first action, through each branch in order, as the HubSpot editor shows it.', F), ('', F),
         ('SCOPE - these 13 workflows only', B)] + [(f'{k + 1}. {CFG[w]["name"]} ({w}) - {WURL(w)}', F) for k, (w, _, _) in enumerate(SCOPE)] + [
         ('', F), ('FINDINGS SUMMARY (live count from Audit Findings)', B)]
for t, fnt in lines:
    ws.append([t])
    c = ws.cell(row=ws.max_row, column=1)
    c.font, c.alignment = fnt, Alignment(wrap_text=True, vertical='top')
ws.column_dimensions['A'].width = 150
for cls in CL:
    ws.append([f'=CONCATENATE("{cls}: ",COUNTIF(\'Audit Findings\'!B:B,"{cls}"))'])
    ws.cell(row=ws.max_row, column=1).font = F

sheet('Process Overview', po_h, [7, 50, 55, 42, 26, 70, 9], po)
sheet('Detailed Action Map', dam_h, [36, 12, 10, 34, 8, 16, 26, 60, 18, 30, 10, 70, 34, 18, 50, 26, 40, 60, 20], DAM, level=18)
sheet('Workflow Inventory', wi_h, [40, 12, 8, 50, 60, 10, 30, 26, 60, 40, 50], wi, links=())
sheet('Task & Subtask Logic', tr_h, [34, 12, 8, 40, 50, 24, 34, 34, 8, 8, 40, 60, 34, 26, 8, 50, 22], TASKROWS, level=16)
sheet('Audit Findings', af_h, [9, 18, 36, 20, 70, 60, 50, 46, 9], AF, cls=1)
sheet('Evidence - Stage Advances', ['Advance Workflow', 'Workflow ID', 'Watched Task Title', 'Task ID', 'Task Created By', 'Ticket ID', 'Ticket Name', 'Ticket Link', 'Task Completed', 'Ticket Entered Next Stage (latest)', 'Seconds Between', 'Moved By This Workflow?'],
      [36, 12, 36, 14, 34, 14, 34, 22, 22, 24, 10, 16], sorted(ADV_ROWS, key=lambda r: r[8]), links=(7,))
sheet('Evidence - Enrollments', ev_h, [36, 12, 16, 14, 34, 22, 22, 22, 22, 10, 8, 8, 8], ev, links=(5,))

wb.calculation = CalcProperties(fullCalcOnLoad=True)
out = os.environ.get('AUDIT_OUT', '/home/user/Claude_HubSpot/audits/transitions-workflow-audit/WLS_Transitions_Workflow_Audit.xlsx')
wb.save(out)
print(out, 'DAM', len(DAM), 'tasks', len(TASKROWS), 'findings', len(AF), 'po', len(po))
