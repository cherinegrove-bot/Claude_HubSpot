import os
import pickle, json, collections, re, difflib, datetime as dt
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

T, R, TK, OW, STG, WF = pickle.load(open('an.pkl', 'rb'))
M = pickle.load(open('model.pkl', 'rb'))
OB = json.load(open('onb_tickets.json'))
OA = json.load(open('onb_ticket_assoc.json'))
DEALS = {d['id']: d for d in json.load(open('onb_deals.json'))}
P = lambda s: dt.datetime.fromisoformat(s.replace('Z', '+00:00')) if s else None
AS_OF = '2026-10-02'
PORTAL = '45059701'
CW_NAME = 'Closed Won | Create Ticket in INITIAL SETUP - UNASSIGNED'
CW_ID = '1670039203'
TURL = lambda i: f'https://app.hubspot.com/contacts/{PORTAL}/record/0-5/{i}'
NOID = 'Not exposed by HubSpot API - Needs Verification'
WID = lambda w: CFG[w]['id'] if w in CFG and CFG[w].get('id') else NOID

SHORT = {
    'Transitions - Transition Kickoff Tasks (+SubTask)': 'Kickoff',
    'Transitions - Pre Launch Setup Tasks (+SubTask)': 'Pre-Launch',
    'Transitions - Launch Readiness Tasks (+SubTask)': 'Launch Readiness',
    'Transitions - Go Live Execution Tasks (+SubTask)': 'Go-Live',
    'Transitions - Final Sign Off Tasks (+SubTask)': 'Final Sign-Off',
    'Transitions - 30-Day Monitoring (+SubTask)': '30-Day Monitoring',
    'Transitions - TRANSITION COMPLETE (+SubTask)': 'Transition Complete',
}
NEWS = [w[0] for w in WF]
# Configuration supplied by WLS as screenshots (VERIFIED (screenshot)). Key = workflow name.
CFG = {
    'Transitions - Transition Kickoff Tasks (+SubTask)': dict(
        trigger_type='Records meet custom conditions (filter-based enrollment, not an event trigger)',
        trigger='Group 1 (all must be true): Create date is known AND Pipeline is any of Onboarding Pipeline AND Ticket status is any of Transition Kickoff (Onboarding Pipeline). No other groups (no OR).',
        source='Screenshot of the enrollment trigger panel supplied by WLS on 2026-10-02',
        id='1866384267', status='ON',
        reenroll='OFF - "Allow tickets to re-enroll after completing the workflow" is switched off',
        suppression='None - "Unenroll if tickets meet the following conditions" has no criteria',
        n_actions='3 actions, then End. No branches, no delays, no other action types',
        canvas_source='Screenshots of the workflow canvas and the trigger Settings tab supplied by WLS on 2026-10-02',
        actions={0: dict(label='Create task', text='Create task Transition | TRANSITION KICK-OFF with 14 subtasks and assign to Ticket owner', subs=14, owner='Ticket owner'),
                 1: dict(label='Create task', text="Create task Transition | TRANSITION KICK-OFF | Subtask - Mo'men with 2 subtasks and assign to Mo'men Khattab", subs=2, owner="Mo'men Khattab"),
                 2: dict(label='Create task', text='Create task Transition | TRANSITION KICK-OFF | Subtask - Bryn with 1 subtask and assign to Bryn Morgan', subs=1, owner='Bryn Morgan')},
        last_action=2),
}



def frac(c, n):
    return f'{c}/{n}'


def top(counter, n, fmt=lambda k: str(k)):
    items = counter.most_common()
    return '; '.join(f'{fmt(k)} ({frac(v, n)})' for k, v in items)


def due_text(g):
    n = g['n']
    bd, bdc = g['bd'].most_common(1)[0]
    cal = collections.Counter(c for c in g['cal'].elements())
    tm, tmc = g['time'].most_common(1)[0]
    s = f'Most common: {bd} business day(s) after creation date, at {tm} US/Eastern ({frac(bdc, n)} for days, {frac(tmc, n)} for time).'
    others = [(k, v) for k, v in g['bd'].items() if k != bd]
    if others:
        s += ' Other observed offsets: ' + ', '.join(f'{k} bd x{v}' for k, v in sorted(others, key=lambda x: (x[0] is None, x[0]))) + ' (could be manual due-date edits after creation - Needs Verification).'
    return s


def owner_text(g):
    n = g['n']
    if g['kind'] == 'SUB':
        no = g['owners'].get('(no owner)', 0)
        if no == n:
            return f'No owner on any of the {n} subtasks.'
        return 'Observed owners: ' + top(g['owners'], n)
    if len(g['owners']) == 1:
        o = list(g['owners'])[0]
        return f'{o} on all {n} ({"looks like a fixed/static owner" if g["tom"] and g["tom"][0] < n else "also equals ticket owner"}).'
    m, tot = g['tom']
    return f'Varies by ticket: {top(g["owners"], n)}. Matches the ticket\'s current owner on {m}/{tot} - consistent with "assign to ticket owner" (INFERENCE).'


def legacy_similar(old, title):
    if not old:
        return None
    base = re.sub(r'^\s*(test\s*)?\d+\.\s*', '', title.lower())
    base = re.sub(r'\(.*?\)', '', base).strip()
    best = (0, None)
    seen = {}
    for t in T:
        if t['properties']['hs_object_source_detail_1'] == old:
            s = (t['properties']['hs_task_subject'] or '').strip()
            seen.setdefault(s, t['c'])
            seen[s] = max(seen[s], t['c'])
    for s, last in seen.items():
        b = re.sub(r'^[A-Z\- ]+:\s*', '', s).lower()
        b = re.sub(r'\(.*?\)', '', b).strip()
        r = difflib.SequenceMatcher(None, base, b).ratio()
        if r > best[0]:
            best = (r, (s, last))
    if best[0] >= 0.55:
        return best[1]
    return None


# ---------------------------------------------------------------- workbook setup
wb = Workbook()
FONT = Font(name='Arial', size=10)
BOLD = Font(name='Arial', size=10, bold=True)
HFONT = Font(name='Arial', size=10, bold=True, color='FFFFFF')
HFILL = PatternFill('solid', fgColor='1F3864')
TITLE = Font(name='Arial', size=14, bold=True)
LEVEL_FILL = {
    'VERIFIED': PatternFill('solid', fgColor='E2EFDA'),
    'INFERENCE': PatternFill('solid', fgColor='FFF2CC'),
    'NEEDS VERIFICATION': PatternFill('solid', fgColor='FCE4D6'),
}
CLASS_FILL = {
    'Confirmed': PatternFill('solid', fgColor='E2EFDA'),
    'Potential Issue': PatternFill('solid', fgColor='FFF2CC'),
    'Needs Verification': PatternFill('solid', fgColor='FCE4D6'),
    'No Issue Found': PatternFill('solid', fgColor='DDEBF7'),
}
THIN = Side(style='thin', color='BFBFBF')
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical='top')


def sheet(name, headers, widths, rows, level_col=None, class_col=None, link_col=None):
    ws = wb.create_sheet(name)
    ws.append(headers)
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=i)
        c.font, c.fill, c.alignment, c.border = HFONT, HFILL, Alignment(wrap_text=True, vertical='center'), BORDER
        ws.column_dimensions[get_column_letter(i)].width = widths[i - 1]
    for r in rows:
        ws.append(list(r))
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.font, c.alignment, c.border = FONT, WRAP, BORDER
        if level_col is not None:
            v = str(row[level_col].value or '')
            for k, f in LEVEL_FILL.items():
                if v.startswith(k):
                    row[level_col].fill = f
        if class_col is not None:
            f = CLASS_FILL.get(row[class_col].value)
            if f:
                row[class_col].fill = f
        if link_col is not None and row[link_col].value and str(row[link_col].value).startswith('http'):
            row[link_col].hyperlink = row[link_col].value
            row[link_col].font = Font(name='Arial', size=10, color='0563C1', underline='single')
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = ws.dimensions
    return ws


# ---------------------------------------------------------------- shared facts
cw = [t for t in OB if t['properties'].get('hs_object_source_detail_1') == CW_NAME]
cw_unassigned_at_create = sum(1 for t in cw if t['properties'].get('hs_v2_date_entered_1100007030') and abs((P(t['properties']['hs_v2_date_entered_1100007030']) - P(t['properties']['createdate'])).total_seconds()) <= 60)
cw_deal_counts = collections.Counter(len(OA.get(t['id'], {}).get('deals', [])) for t in cw)
cw_owner = sum(1 for t in cw if t['properties']['hubspot_owner_id'])
cw_name_match = 0
for t in cw:
    names = [DEALS.get(str(d), {}).get('properties', {}).get('dealname') for d in OA.get(t['id'], {}).get('deals', [])]
    if any(n and n.strip().lower() == (t['properties']['subject'] or '').strip().lower() for n in names):
        cw_name_match += 1
cw_first = min(t['properties']['createdate'] for t in cw)[:10]
cw_last = max(t['properties']['createdate'] for t in cw)[:10]
comp_multi = collections.defaultdict(list)
for t in OB:
    for c in OA.get(t['id'], {}).get('companies', []):
        comp_multi[c].append(t['id'])
comp_multi_n = sum(1 for v in comp_multi.values() if len(v) > 1)

wfstats = {}
for new, stage, old in WF:
    enr = M[new]['enr']
    d = [i['delta'] for i in enr if i['delta'] is not None]
    match = sum(1 for x in d if -60 <= x <= 600)
    spread = max((max(t['c'] for t in i['tasks']) - min(t['c'] for t in i['tasks'])).total_seconds() for i in enr)
    tix = collections.Counter(k for i in enr for k in i['tickets'])
    wfstats[new] = dict(n_enr=len(enr), n_tasks=len(M[new]['tasks']), n_tix=len(tix), multi=sum(1 for v in tix.values() if v > 1),
                        match=match, n_d=len(d), dmin=min(d), dmax=max(d), spread=spread,
                        first=min(i['start'] for i in enr), last=max(i['start'] for i in enr),
                        parents=sum(1 for g in M[new]['groups'] if g['kind'] == 'PARENT'),
                        subs=sum(1 for g in M[new]['groups'] if g['kind'] == 'SUB'),
                        idxs=sorted({g['idx'] for g in M[new]['groups']}),
                        no_ticket=sum(1 for i in enr if not i['tickets']))


def ex_ticket(new):
    i = M[new]['enr'][-1]
    return i['tickets'][0] if i['tickets'] else None


def trig_evidence(new):
    s = wfstats[new]
    return (f'{s["match"]}/{s["n_d"]} enrollments started {s["dmin"]:.0f}-{s["dmax"]:.0f} seconds after the ticket\'s "Date entered {STG[M[new]["stage"]]}" '
            f'(hs_v2_date_entered_{M[new]["stage"]}). Enrollments observed {s["first"]:%Y-%m-%d} to {s["last"]:%Y-%m-%d}.')


# ---------------------------------------------------------------- Read Me
ws = wb.active
ws.title = 'Read Me'
lines = [
    ('WLS Transitions Workflow Audit - observed-behaviour build (Option 2)', TITLE),
    (f'Data as of {AS_OF}. HubSpot portal {PORTAL}. Built from HubSpot CRM records read through the API.', FONT),
    ('', FONT),
    ('WHY THIS IS NOT YET A CONFIGURATION AUDIT', BOLD),
    (f'The HubSpot Automation API refuses to return these workflows: GET /automation/v4/flows/{CW_ID} returns 403 FLOW_ACCESS_DENIED ("Flow must be accessible via external APIs..."), even after every sensitive / highly-sensitive read scope and the write scopes were added. The 7 Transitions (+SubTask) workflows do not appear at all in the 129 workflows the API lists.', FONT),
    ('So the enrollment triggers, re-enrollment, suppression, branches, delays, non-task actions and the exact HubSpot action labels CANNOT be read. Every one of those items is marked NEEDS VERIFICATION.', FONT),
    ('What CAN be read: every task the workflows created. HubSpot stamps each workflow-created task with the workflow name (Record source detail 1), the enrollment ID and the action execution index (Record creation source ID). That shows what each workflow did, in what order, for which ticket and when.', FONT),
    ('', FONT),
    ('EVIDENCE LABELS USED IN EVERY SHEET', BOLD),
    ('VERIFIED (screenshot) - workflow configuration seen in a screenshot of the HubSpot workflow editor supplied by WLS. This is real configuration.', FONT),
    ('VERIFIED (records) - directly visible in HubSpot task / ticket / deal records. Not the workflow configuration itself.', FONT),
    ('INFERENCE - logically derived from the records (for example: tasks appear within seconds of a ticket entering a stage, so the trigger is probably "ticket enters stage"). Not proven.', FONT),
    ('NEEDS VERIFICATION - cannot be determined without opening the workflow in HubSpot.', FONT),
    ('', FONT),
    ('HOW TO READ "ACTION #"', BOLD),
    ('Action # = HubSpot\'s actionExecutionIndex + 1, taken from each task\'s Record creation source ID. It is the order in which the enrollment executed actions. It is NOT necessarily the step number shown in the workflow editor: branches, delays and property edits that create no task leave no record. A gap in the sequence (e.g. Pre-Launch #6-#7) means something ran there that created no task.', FONT),
    ('', FONT),
    ('DUE DATES, OWNERS, TITLES', BOLD),
    ('Values are the CURRENT values on each task. Users may have edited due dates, owners or titles after creation, so the most common value (shown with its count, e.g. 18/21) is the best evidence of what the workflow sets. Times are US/Eastern (portal time zone). "bd" = business days (Mon-Fri) between creation date and due date.', FONT),
    ('', FONT),
    ('SCOPE - these 8 workflows only', BOLD),
    (f'1. {CW_NAME} (ID {CW_ID}) - creates the ticket.', FONT),
] + [(f'{i + 2}. {w}', FONT) for i, w in enumerate(NEWS)] + [
    ('Other workflows (legacy non-subtask versions, Set task queue, Set OM and SM overdue tasks to Deferred, Marketing Proposal Task) are mentioned only in Audit Findings, where they create duplicates of or act on tasks from these 7. They are not mapped.', FONT),
    ('', FONT),
    ('FINDINGS SUMMARY (live count from the Audit Findings sheet)', BOLD),
]
for text, f in lines:
    ws.append([text])
    ws.cell(row=ws.max_row, column=1).font = f
    ws.cell(row=ws.max_row, column=1).alignment = Alignment(wrap_text=True, vertical='top')
ws.column_dimensions['A'].width = 150
summary_start = ws.max_row + 1

# ---------------------------------------------------------------- Detailed Action Map
dam = []
# Closed Won workflow
dam.append([CW_NAME, CW_ID, 'Trigger', 'n/a', '-', 'Enrollment trigger', 'NEEDS VERIFICATION',
            'NEEDS VERIFICATION. The workflow name says it fires on a Closed Won deal. API returned 403, so the actual criteria, re-enrollment and suppression are unknown.',
            'Deal (INFERENCE from name)', 'Deal stage (INFERENCE)', 'Needs Verification', 'Closed Won (INFERENCE from name)', 'Needs Verification', 'Needs Verification',
            'Deal enrolls', 'Action #1 (create ticket)', f'GET /automation/v4/flows/{CW_ID} -> 403 FLOW_ACCESS_DENIED on {AS_OF}', 'Workflow name only.', 'NEEDS VERIFICATION'])
dam.append([CW_NAME, CW_ID, '1 (observed)', 'Unknown', '1', 'Create record - Ticket (exact HubSpot label Needs Verification)', 'Record creation (observed output)',
            f'Creates a ticket in Onboarding Pipeline (751582029), stage UNASSIGNED (1100007030). {len(cw)} tickets carry Record source = AUTOMATION_PLATFORM / "{CW_NAME}" ({cw_first} to {cw_last}). {cw_unassigned_at_create}/{len(cw)} still show "Date entered UNASSIGNED" within 60 s of creation; the other {len(cw) - cw_unassigned_at_create} re-entered UNASSIGNED later, which overwrites that date.',
            'Ticket', 'Pipeline; Pipeline stage; Ticket name; Owner; associations', '(new record)',
            f'Pipeline = Onboarding Pipeline; Stage = UNASSIGNED. Ticket name = an associated deal\'s name on {cw_name_match}/{len(cw)}. Owner present on {cw_owner}/{len(cw)} (whether the workflow sets it: Needs Verification).',
            'Needs Verification', 'Needs Verification',
            f'Ticket exists in UNASSIGNED. Associated deals: 1 deal on {cw_deal_counts.get(1, 0)}, 2 deals on {cw_deal_counts.get(2, 0)}.',
            'No Transitions (+SubTask) workflow fires in UNASSIGNED. Next observed automated event: ticket enters Transition Kickoff -> Kickoff workflow (how the stage changes: Needs Verification).',
            f'Ticket property hs_object_source_detail_1 = "{CW_NAME}" on {len(cw)} tickets. Example: {TURL(cw[-1]["id"])}',
            'Other actions in this workflow (property edits, notifications, associations) leave no record: Needs Verification.', 'VERIFIED (records) for output; label NEEDS VERIFICATION'])

for new, stage, old in WF:
    st = wfstats[new]
    groups = M[new]['groups']
    cfg = CFG.get(new)
    if cfg:
        dam.append([new, WID(new), 'Trigger', 'Group 1', '-', 'Enrollment trigger', cfg['trigger_type'],
                    f'Enrolls a ticket when it meets: {cfg["trigger"]}',
                    'Ticket', 'Create date; Pipeline; Ticket status (pipeline stage)', 'Any', f'Pipeline = Onboarding Pipeline AND Ticket status = {STG[stage]}',
                    'The three conditions above, all required. Re-enroll OFF; no unenroll criteria (VERIFIED)', 'n/a',
                    f'{st["n_enr"]} enrollments on {st["n_tix"]} tickets; no ticket enrolled twice.', 'Action #1',
                    f'{cfg["source"]}. Matches the records: {trig_evidence(new)}',
                    f'Re-enrollment: {cfg["reenroll"]}. Unenrollment/suppression: {cfg["suppression"]} (VERIFIED screenshot).', 'VERIFIED (screenshot)'])
    else:
      dam.append([new, WID(new), 'Trigger', 'n/a', '-', 'Enrollment trigger', 'NEEDS VERIFICATION',
                f'NEEDS VERIFICATION. Observed: enrollment starts when the ticket enters "{STG[stage]}".',
                'Ticket', 'Pipeline stage (hs_pipeline_stage)', 'Any earlier stage', f'{STG[stage]} ({stage})', 'Needs Verification (re-enrollment and suppression unreadable)', 'n/a',
                f'{st["n_enr"]} enrollments on {st["n_tix"]} tickets; no ticket enrolled twice.', f'Action #1', trig_evidence(new),
                'Ticket source does not matter: tickets created by the Closed Won workflow, by cloning and manually all enroll.', 'INFERENCE'])
    idxs = st['idxs']
    for pos, idx in enumerate(idxs):
        # gap rows
        if pos > 0 and idx - idxs[pos - 1] > 1:
            for gidx in range(idxs[pos - 1] + 1, idx):
                dam.append([new, WID(new), f'{gidx + 1} (observed)', 'Unknown', gidx + 1, 'Unknown action (no task created)', 'NEEDS VERIFICATION',
                            'An action executed at this position but created no task record. Could be a branch, delay, property edit or notification.',
                            'Unknown', 'Unknown', '', '', 'Needs Verification', 'Needs Verification', 'Unknown', f'Action #{gidx + 2}',
                            f'Gap in actionExecutionIndex between {idxs[pos - 1]} and {idx} in task records.', 'Only seen in the enrollment(s) that reached the next action.', 'NEEDS VERIFICATION'])
        par = [g for g in groups if g['idx'] == idx and g['kind'] == 'PARENT'][0]
        subs = [g for g in groups if g['idx'] == idx and g['kind'] == 'SUB']
        cond = 'None observed - ran in every enrollment' if par['n'] == st['n_enr'] else f'Ran in {par["n"]}/{st["n_enr"]} enrollments (first {par["first"]:%Y-%m-%d}). A branch condition or a later edit to the workflow - Needs Verification.'
        sub_list = '; '.join(f'{s["title"]}' for s in subs) or '(none)'
        nxt = idxs[pos + 1] if pos + 1 < len(idxs) else None
        nxt_txt = (f'Action #{nxt + 1}' if nxt is not None and nxt == idx + 1 else (f'Unknown action(s) at #{idx + 2}-#{nxt}, then Action #{nxt + 1}' if nxt is not None else 'No further task-creating action observed. Anything after this (e.g. a property edit) is Needs Verification. Next process event: ticket moved to the next stage.'))
        exid = M[new]['enr'][-1]
        ex_task = [t for t in exid['tasks'] if t['idx'] == idx and t['properties']['hs_task_is_sub_task'] != 'true']
        ex_task = ex_task[0]['id'] if ex_task else 'n/a'
        va = CFG.get(new, {}).get('actions', {}).get(idx)
        if va:
            cond = 'None - no branches in this workflow (VERIFIED screenshot)'
            if idx == CFG[new].get('last_action'):
                nxt_txt = 'End (VERIFIED screenshot). Next process event: ticket moved to Pre-Launch Setup (manual - INFERENCE).'
        dam.append([new, WID(new), f'{idx + 1}' + ('' if va else ' (observed)'), ('None (VERIFIED)' if va else ('Unknown (no branch evidence)' if par['n'] == st['n_enr'] else 'Possibly conditional - Needs Verification')), idx + 1,
                    (va['label'] if va else 'Create task, with subtasks (exact HubSpot label Needs Verification)'), ('Create task (VERIFIED screenshot)' if va else 'Task creation (observed output)'),
                    (f'Canvas reads: "{va["text"]}" (VERIFIED). Records: parent "{par["title"]}" with {len(subs)} subtask(s): {sub_list}.' if va else f'Creates parent task "{par["title"]}" with {len(subs)} subtask(s): {sub_list}.'),
                    'Task (parent + subtasks), associated with the Ticket', f'Parent: {par["title"]}', '(new record)',
                    (f'Owner: {va["owner"]} (VERIFIED screenshot; records: {owner_text(par)}) ' if va else f'Owner: {owner_text(par)} ') + f'Due: {due_text(par)} Priority: {top(par["pri"], par["n"])}. Type: {top(par["typ"], par["n"])}. Associations: {top(par["assoc"], par["n"])}.',
                    cond, ('None - no delay actions in this workflow (VERIFIED screenshot)' if va else f'None observed: all tasks of one enrollment were created within {st["spread"]:.0f} s.'),
                    f'{par["n"]} parent tasks and {sum(s["n"] for s in subs)} subtasks created across all enrollments. Current parent status: {top(par["st"], par["n"])}.',
                    nxt_txt,
                    f'Task records with Record source detail 1 = "{new}", Record creation source ID actionExecutionIndex = {idx}. Example parent task ID {ex_task} on ticket {TURL(exid["tickets"][0]) if exid["tickets"] else "n/a"}',
                    ' '.join(x for x in [('Title variants: ' + '; '.join(f'"{v}" x{c} ({", ".join(d)})' for v, c, d in par['variants'])) if par['variants'] else '',
                        ('WORKFLOW HANDOFF: "Set task queue" (1677143128) then puts subtask "' + next(s['title'] for s in subs if 'BOG' in s['title']) + '" into queue "BOG - Run and Sustain" (VERIFIED config + records, see F-24).') if any('BOG' in s['title'] for s in subs) else '',
                        ('WORKFLOW HANDOFF: "Set OM and SM overdue tasks to Deferred" (1795953061) can set this parent to DEFERRED once overdue (4 observed, see F-25).') if 'Hunter' in par['title'] else ''] if x),
                    ('VERIFIED (screenshot + records); subtask owner/due/associations from records only' if va else 'VERIFIED (records) for output; action label NEEDS VERIFICATION')])

dam_headers = ['Workflow', 'Workflow ID', 'Workflow Step', 'Branch', 'Action #', 'Action Name', 'Action Type', 'What The Action Does', 'Object',
               'Property / Record Affected', 'Current Value', 'New Value', 'Condition', 'Delay', 'Result', 'Next Action', 'Evidence', 'Notes', 'Evidence Level']

# ---------------------------------------------------------------- Process Overview
po = []
step = 1
po.append([step, 'Deal reaches Closed Won (INFERENCE from workflow name)', 'Enrollment criteria: Needs Verification', CW_NAME, 'Enrollment trigger', 'Deal enrolls', step + 1]); step += 1
po.append([step, 'Ticket created in Onboarding Pipeline / UNASSIGNED', 'Needs Verification', CW_NAME, 'Action #1 - Create record (Ticket) [label Needs Verification]',
           f'{len(cw)} tickets created {cw_first} to {cw_last}; ticket name = deal name on {cw_name_match}/{len(cw)} (VERIFIED records)', step + 1]); step += 1
po.append([step, 'Ticket waits in UNASSIGNED (or On Hold / Website Only)', 'None - no (+SubTask) workflow fires in these stages', '(none in scope)', '(none)',
           'No Transitions (+SubTask) tasks created. How a ticket gets to Transition Kickoff (manual move or another workflow) is Needs Verification. Tickets created by cloning or manually (not by this workflow) also enter Kickoff and get the same tasks.', step + 1]); step += 1
for k, (new, stage, old) in enumerate(WF):
    st = wfstats[new]
    po.append([step, f'Ticket enters stage "{STG[stage]}"', (f'VERIFIED (screenshot): {CFG[new]["trigger"]}' if new in CFG else 'Enrollment trigger Needs Verification; observed match ' + f'{st["match"]}/{st["n_d"]}'), new, ('Enrollment: ' + CFG[new]['trigger_type']) if new in CFG else 'Enrollment (INFERENCE: "ticket enters stage")',
               f'Workflow enrolls {st["dmin"]:.0f}-{st["dmax"]:.0f} s after stage entry ({st["n_enr"]} enrollments, {st["first"]:%Y-%m-%d} to {st["last"]:%Y-%m-%d})', step + 1]); step += 1
    for g in [g for g in M[new]['groups'] if g['kind'] == 'PARENT']:
        subs = [s for s in M[new]['groups'] if s['idx'] == g['idx'] and s['kind'] == 'SUB']
        cond = 'Always (ran in every enrollment)' if g['n'] == st['n_enr'] else f'Only {g["n"]}/{st["n_enr"]} enrollments - Needs Verification'
        po.append([step, f'Task created: {g["title"]}', cond, new, f'Action #{g["idx"] + 1} - Create task with {len(subs)} subtask(s)',
                   f'Parent owner: {owner_text(g)} Parent due: {g["bd"].most_common(1)[0][0]} bd. Subtasks: {", ".join(str(s["key"][2]) for s in subs)} (no owner).' if subs and all(s['owners'].get('(no owner)', 0) == s['n'] for s in subs)
                   else f'Parent owner: {owner_text(g)} Subtasks: {", ".join(str(s["key"][2]) for s in subs) or "none"}.', step + 1]); step += 1
    if k < len(WF) - 1:
        po.append([step, f'Team works the {SHORT[new]} tasks; ticket is moved to "{STG[WF[k + 1][1]]}"', 'Needs Verification - no evidence that completing tasks moves the stage automatically',
                   '(manual or unknown)', '(none observed)',
                   'Stage-entry times vary from minutes to weeks after the "End of stage" subtask is completed, and the 30-Day subtask text says "move manually". INFERENCE: stage moves are manual.', step + 1]); step += 1
po.append([step, 'Process end: ticket in Transition Completed (closed stage)', 'n/a', 'Transitions - TRANSITION COMPLETE (+SubTask)', 'Last observed action',
           'Leaves one PM task that is due the same day. No further automation observed.', 'End'])
po_headers = ['Step #', 'Event', 'Condition', 'Workflow', 'Action', 'Result', 'Next Step']

# ---------------------------------------------------------------- Workflow Inventory
wi = []
wi.append([CW_NAME, CW_ID, 'Deal (INFERENCE from name); creates Ticket', 'Creates the Onboarding Pipeline ticket in UNASSIGNED (VERIFIED from ticket records).',
           'Needs Verification (403)', 'Needs Verification', 'Needs Verification', 'Needs Verification (at least 1: create ticket)',
           'Create record (Ticket) - label Needs Verification', 'Creates the ticket that the 7 Transitions workflows act on (Kickoff first)',
           f'{len(cw)} tickets {cw_first} to {cw_last}. {cw_deal_counts.get(2, 0)} of these tickets are associated with 2 deals.'])
for new, stage, old in WF:
    st = wfstats[new]
    keys = '; '.join(f'#{g["idx"] + 1}: {g["title"]}' for g in M[new]['groups'] if g['kind'] == 'PARENT')
    prev = NEWS[NEWS.index(new) - 1] if NEWS.index(new) > 0 else CW_NAME + ' (creates the ticket; ticket is then moved into Transition Kickoff)'
    nxtw = NEWS[NEWS.index(new) + 1] if NEWS.index(new) + 1 < len(NEWS) else '(end)'
    c = CFG.get(new, {})
    wi.append([new, WID(new) + (f' ({c["status"]}, VERIFIED screenshot)' if c.get('status') else ''), 'Ticket' + (' (VERIFIED: "Trigger enrollment for tickets")' if c else ' (INFERENCE: tasks are associated to the enrolled ticket)'),
               f'Creates the {STG[stage]} task set: {st["parents"]} parent tasks with {st["subs"]} subtasks in total.',
               (f'VERIFIED (screenshot): {CFG[new]["trigger_type"]}. {CFG[new]["trigger"]}' if new in CFG else f'NEEDS VERIFICATION. Observed: ticket enters "{STG[stage]}" (stage ID {stage}). {trig_evidence(new)}'),
               (f'VERIFIED (screenshot): {c["reenroll"]}' if c.get('reenroll') else f'Needs Verification. Observed: {st["multi"]} tickets enrolled more than once (so far no ticket has re-entered this stage after {st["first"]:%Y-%m-%d}).'),
               (f'VERIFIED (screenshot): {c["suppression"]}' if c.get('suppression') else 'Needs Verification. No missed enrollment observed for tickets entering this stage since go-live.'),
               (f'VERIFIED (screenshot): {c["n_actions"]}' if c.get('n_actions') else '') or f'Needs Verification. At least {len(st["idxs"])} task-creating action(s) observed' + (f' and {max(st["idxs"]) + 1 - len(st["idxs"])} unknown action(s) in index gaps' if max(st['idxs']) + 1 > len(st['idxs']) else '') + '.',
               keys, f'Upstream: {prev}. Downstream (via manual stage move, INFERENCE): {nxtw}. Replaced legacy: {old or "n/a"}.',
               f'{st["n_tasks"]} tasks; first enrollment {st["first"]:%Y-%m-%d}, latest {st["last"]:%Y-%m-%d}.'])
wi_headers = ['Workflow Name', 'Workflow ID', 'Object', 'Purpose / Observed Function', 'Enrollment Trigger', 'Re-enrollment', 'Suppression', 'Number of Actions', 'Key Actions', 'Related Workflows', 'Notes']

# ---------------------------------------------------------------- Task & Subtask Logic
ts = []
for new, stage, old in WF:
    st = wfstats[new]
    for g in M[new]['groups']:
        if g['kind'] == 'PARENT':
            parent, sub = g['title'], '-'
            tconf = f'Owner: {owner_text(g)} Due: {due_text(g)} Priority: {top(g["pri"], g["n"])}. Type: {top(g["typ"], g["n"])}. Associations: {top(g["assoc"], g["n"])}.'
            sconf = f'{sum(1 for s in M[new]["groups"] if s["idx"] == g["idx"] and s["kind"] == "SUB")} subtask(s) created under this parent (rows below)'
        else:
            parent, sub = g['parent'], g['title']
            tconf = '(see parent row)'
            sconf = f'Owner: {owner_text(g)} Due: {due_text(g)} Priority: {top(g["pri"], g["n"])}. Type: {top(g["typ"], g["n"])}. Associations: {top(g["assoc"], g["n"])}.'
        cond = 'None observed - created in every enrollment' if g['n'] == st['n_enr'] else f'Created in {g["n"]}/{st["n_enr"]} enrollments - Needs Verification'
        sim = legacy_similar(old, g['title']) if g['kind'] == 'SUB' or not g['title'].startswith('Transition |') else None
        if new.startswith('Transitions - Pre Launch') and g['title'].startswith('Marketing |'):
            dup = 'HIGH: "Marketing Proposal Task" (1890156974, Company-based) creates a task with the identical title when PPC Ads = true. Same company could get two.'
        elif sim:
            dup = f'Legacy "{old}" created a similar task "{sim[0]}" (last {sim[1]:%Y-%m-%d}). Legacy stopped before this workflow started, so no overlap for the same stage entry; 3 tickets got both across separate Kickoff entries (see F-05).' if 'Kickoff' in new else f'Legacy "{old}" created a similar task "{sim[0]}" (last {sim[1]:%Y-%m-%d}). No ticket received both (legacy stopped before this workflow started).'
        else:
            dup = 'None found in the task data'
        deps = ''
        if g['kind'] == 'SUB':
            deps = 'Belongs to the parent task; completing the parent does not close it (open subtasks under completed parents observed)' if g['open_under_done'] else 'Belongs to the parent task'
            if re.search(r'Task \d out of 3|task 2 and 3|STAGE \d', g['title'], re.I):
                deps += '. Title says it is part of a 3-part sequence spread across stages (Pre-Launch -> Go-Live -> Final Sign-Off); the dependency is in the title only, not enforced by any observed automation.'
            if 'End of stage' in g['title']:
                deps += '. "End of stage" sign-off: no evidence its completion moves the ticket stage (INFERENCE).'
        notes = []
        if g['variants']:
            notes.append('Title variants: ' + '; '.join(f'"{v}" x{c} ({", ".join(d)})' for v, c, d in g['variants']))
        if g['open_under_done']:
            notes.append(f'{g["open_under_done"]} still open while their parent is Completed')
        notes.append(f'Current status: {top(g["st"], g["n"])}')
        if new in CFG and CFG[new].get('actions'):
            cond = 'None - workflow has no branches (VERIFIED screenshot)'
        ts.append([new, g['idx'] + 1, parent, sub, (f'VERIFIED (screenshot): {CFG[new]["trigger"]}' if new in CFG else f'Ticket enters {STG[stage]} (INFERENCE)'), cond, tconf, sconf, deps or '-', dup, ' | '.join(notes),
                   g['n'], f'{g["first"]:%Y-%m-%d} to {g["last"]:%Y-%m-%d}', ('VERIFIED (screenshot: structure, parent owner) + records' if new in CFG and CFG[new].get('actions') else 'VERIFIED (records)')])
ts_headers = ['Workflow', 'Action #', 'Parent Task', 'Subtask', 'Trigger', 'Conditions', 'Task Configuration', 'Subtask Configuration', 'Dependencies',
              'Potential Duplicate Risk', 'Notes', 'Times Created', 'Created Between', 'Evidence Level']

# ---------------------------------------------------------------- Audit Findings
def open_counts(new):
    tasks = M[new]['tasks']
    order = ["1175587148", "1100007030", "1298054295", "1094530721", "1094530722", "1094530723", "1094493506", "1094493507", "1102485356", "1094530724"]
    stage = M[new]['stage']
    later = sum(1 for t in tasks if t['properties']['hs_task_status'] not in ('COMPLETED', 'DEFERRED') and t['tickets'] and TK.get(t['tickets'][0])
                and TK[t['tickets'][0]]['properties']['hs_pipeline_stage'] in order and order.index(TK[t['tickets'][0]]['properties']['hs_pipeline_stage']) > order.index(stage))
    overdue = sum(1 for t in tasks if t['properties']['hs_task_status'] not in ('COMPLETED', 'DEFERRED') and t['due'] and t['due'] < dt.datetime(2026, 10, 2, tzinfo=dt.timezone.utc))
    oud = sum(g['open_under_done'] for g in M[new]['groups'])
    return later, overdue, oud

oc = {n: open_counts(n) for n in NEWS}
subs_all = sum(g['n'] for n in NEWS[:-1] for g in M[n]['groups'] if g['kind'] == 'SUB')
tc_sub = [g for g in M[NEWS[-1]]['groups'] if g['kind'] == 'SUB'][0]
pl = M['Transitions - Pre Launch Setup Tasks (+SubTask)']
pl_partial = [i for i in pl['enr'] if len(i['tasks']) < 5]
lr11 = [g for g in pl['groups'] if g['kind'] == 'SUB' and g['key'][2] == 11][0]
named = collections.Counter()
for n in NEWS:
    for g in M[n]['groups']:
        if g['kind'] == 'PARENT' and len(g['owners']) == 1:
            named[list(g['owners'])[0]] += 1

AF = []
def F(cls, wf, act, finding, ev, why, verify, status='Open'):
    AF.append([f'F-{len(AF) + 1:02d}', cls, wf, act, finding, ev, why, verify, status])

F('Needs Verification', 'All 8 workflows', 'All',
  'HubSpot does not return the configuration of any of the 8 in-scope workflows through its API (Kickoff 1866384267 also returns 403). Kickoff is now verified from WLS screenshots (trigger, re-enrollment, unenrollment, canvas). For the other 7, triggers, re-enrollment, suppression, branches, delays, non-task actions and action labels remain unverified.',
  f'GET /automation/v4/flows/{CW_ID} -> 403 FLOW_ACCESS_DENIED ({AS_OF}); the 7 (+SubTask) workflows are absent from the 129-workflow list. None of the readable "Create task" actions in this portal contain a subtask field, which suggests (INFERENCE) that workflows using subtasks are not supported by the public API.',
  'Everything in this workbook about logic (as opposed to output) is inference until the workflows are opened.',
  'Open each workflow in HubSpot and capture: enrollment trigger, re-enrollment tab, suppression, every action panel. Compare against Detailed Action Map.')
F('Confirmed', '6 of 7 (+SubTask) workflows', 'Every subtask',
  f'Subtasks are created with NO owner. 0 of {subs_all} subtasks created by Kickoff, Pre-Launch, Launch Readiness, Go-Live, Final Sign-Off and 30-Day have an owner. Only TRANSITION COMPLETE subtasks have one ({tc_sub["n"] - tc_sub["owners"].get("(no owner)", 0)}/{tc_sub["n"]}).',
  'Task property hubspot_owner_id is empty on every subtask (Is Subtask = true) from those 6 workflows.',
  'Unowned subtasks do not appear in anyone\'s own task list or overdue counts; responsibility depends entirely on the parent owner opening the parent task.',
  'Check the subtask owner setting inside each Create task action. Confirm whether "no owner" is intended.')
F('Potential Issue', 'All 7 (+SubTask)', 'All task actions',
  f'Parent tasks are being completed while subtasks stay open: {sum(oc[n][2] for n in NEWS)} open subtasks sit under Completed parents (Kickoff {oc[NEWS[0]][2]}, Pre-Launch {oc[NEWS[1]][2]}, Launch Readiness {oc[NEWS[2]][2]}, Go-Live {oc[NEWS[3]][2]}, Final Sign-Off {oc[NEWS[4]][2]}, 30-Day {oc[NEWS[5]][2]}, Complete {oc[NEWS[6]][2]}).',
  'Task status of subtasks vs. their parent (hs_task_parent_task_id). Only 4 tasks in the whole set are DEFERRED.',
  'Work marked done at parent level may not actually be done; there is no evidence that open subtasks are deferred when the parent closes.',
  'Confirm HubSpot\'s behaviour for open subtasks when a parent is completed, and whether the team expects them to auto-close/defer.')
F('Potential Issue', 'All 7 (+SubTask)', 'All',
  'Tasks from earlier stages stay open after the ticket moves on. Open tasks on tickets that are now in a later stage: ' + ', '.join(f'{SHORT[n]} {oc[n][0]}' for n in NEWS[:-1]) + '. Open and past due as of ' + AS_OF + ': ' + ', '.join(f'{SHORT[n]} {oc[n][1]}' for n in NEWS) + '.',
  'Task status + due date vs. the associated ticket\'s current pipeline stage.',
  'No observed automation closes or reassigns prior-stage tasks, so overdue counts accumulate and stage gates are not enforced.',
  'Confirm whether any workflow (or the team) is supposed to close/defer leftover tasks on a stage change.')
F('Confirmed', 'Transitions - Transition Kickoff Tasks (+SubTask) and legacy "Transitions - Transition Kickoff Tasks"', 'All',
  '3 tickets received two full Kickoff task sets, one from the legacy workflow and one from the (+SubTask) workflow, because they entered Transition Kickoff again months later. One of them (Dalston Mini Storage) also got the legacy set twice (2026-05-14 and 2026-07-13), so the legacy workflow re-enrolled on re-entry.',
  'Tickets 45732124308, 45687131913, 46699346342: legacy Kickoff tasks dated 2026-05/06/07 and (+SubTask) tasks dated 2026-08/09.',
  'The legacy workflow re-created the whole task set on re-entry. The (+SubTask) Kickoff workflow has Re-enroll OFF (VERIFIED screenshot), so it will NOT create duplicates - but a ticket that returns to Transition Kickoff (e.g. after On Hold) will get NO new Kickoff tasks. Its original tasks (possibly completed or old) are all it has.',
  'Decide whether a ticket returning to Kickoff should get fresh tasks. Check the re-enrollment setting on the other 6 (+SubTask) workflows.')
F('No Issue Found', 'All 7 (+SubTask) vs legacy versions', 'All',
  'Clean cut-over: each legacy workflow created its last task (2026-08-11 to 2026-08-18) before its (+SubTask) replacement created its first (2026-08-20 to 2026-08-31). No ticket got both versions for the same stage entry.',
  'Max created date of legacy-sourced tasks vs. min created date of (+SubTask)-sourced tasks, per stage.',
  'Legacy workflows still exist. If any is switched back on, duplicate task sets would be created.',
  'Confirm all legacy Transitions task workflows are OFF.')
F('Potential Issue', 'Transitions - Transition Kickoff Tasks (+SubTask)', 'Trigger / suppression',
  'Ticket "Spencerport Personal Storage" (48042783912) entered Transition Kickoff on 2026-09-01 at 12:27:50 UTC (08:27 ET) and was back in UNASSIGNED 9 seconds later. The Kickoff workflow created no tasks; "Website Only Onboarding" created 13 tasks instead and the ticket is now in Website Only. It is the only ticket that entered Kickoff since go-live without getting tasks.',
  f'hs_v2_date_entered_1094530721 = 2026-09-01T12:27:50Z, hs_v2_date_entered_1100007030 = 2026-09-01T12:27:59Z; no tasks with source "{NEWS[0]}" on this ticket. {TURL("48042783912")}',
  'Suppression and unenrollment are ruled out: Kickoff has no unenroll criteria and no branches (VERIFIED screenshot). The trigger is filter-based (Ticket status is any of Transition Kickoff). INFERENCE: the ticket left Kickoff 9 seconds after entering, before HubSpot evaluated it (other tickets enroll 4-13 s after entry), so it never met the conditions at evaluation time.',
  'Check the ticket\'s workflow history (Kickoff > Performance history) to confirm it was never enrolled. Any ticket moved through Kickoff in under ~10 seconds will skip the Kickoff tasks.')
F('Potential Issue', 'Transitions - Pre Launch Setup Tasks (+SubTask)', 'Action #1 and #4',
  f'One enrollment produced only part of the task set: "{TK[pl_partial[0]["tickets"][0]]["properties"]["subject"]}" (ticket {pl_partial[0]["tickets"][0]}, 2026-08-31) received only the Bryn parent (Action #4) and its subtask. Actions #1-#3 and #5 left no tasks.' if pl_partial else 'n/a',
  f'Enrollment {pl_partial[0]["enr"]}: tasks only at actionExecutionIndex 3. {TURL(pl_partial[0]["tickets"][0])}' if pl_partial else '',
  'Either the workflow branches (so most tasks are conditional) or tasks were deleted after creation. Either way, that ticket is missing most Pre-Launch work.',
  'Check this ticket\'s workflow history; check for branches before Actions #1-#3 and #5.')
F('Confirmed', 'Transitions - Pre Launch Setup Tasks (+SubTask)', 'Unknown #6-#7, Action #8',
  'From 2026-09-25 the workflow runs extra steps: two actions that create no task (#6-#7), then a new parent task "Marketing | Create Marketing Proposal" owned by Brock Hegr (#8). Seen in 1 of 11 enrollments (the latest).',
  'actionExecutionIndex 7 on task "Marketing | Create Marketing Proposal" (enrollment 2026-09-25); no tasks at indexes 5-6.',
  'Indicates a recent edit (probably a branch on marketing manager). The readable workflow "Marketing Proposal Task" (1890156974) creates a task with the identical title for the company, so the same customer can get two.',
  'Open Pre-Launch and confirm what #6-#7 are; decide whether Pre-Launch or 1890156974 owns the proposal task.')
F('Confirmed', 'Transitions - Pre Launch Setup Tasks (+SubTask)', 'Action #1, subtask 11',
  'Subtask 11 changed who marketing requests go to. Enrollments 2026-08-20 to 2026-08-25 (5) say "...pass on any marketing requirements to Rachel (via HubSpot)"; enrollments 2026-09-01 to 2026-09-25 (5) say "...pass on any marketing requests to Brock (via HubSpot)".',
  'Subtask titles on task records, grouped by creation date.',
  'Tickets created before the change still tell the PM to send marketing requests to the old person.',
  'Confirm current owner of marketing requests; fix any open subtasks with the old name.')
F('Confirmed', 'Transitions - Pre Launch Setup Tasks (+SubTask)', 'Action #1, subtask 1',
  'A live enrollment on 2026-08-25 created a subtask titled "TEST 1. Provide guidance to onsite point of contact to complete video verificaiton" with no associations at all (not linked to the ticket or company).',
  'Task with hs_task_subject starting "TEST 1." and zero associations.',
  'Test configuration ran on a real customer; an unassociated subtask is invisible from the ticket.',
  'Confirm the test text has been removed from the workflow (later enrollments show "1. ..."), and clean up the orphan task.')
F('Confirmed', 'Transitions - Launch Readiness Tasks (+SubTask); Transitions - Transition Kickoff Tasks (+SubTask)', 'LR Action #3 subtask 8; Kickoff Action #3 subtask 11',
  'Subtask wording was changed while live. Launch Readiness subtask 8 became "Internal meeting with OM/SM - at least 1 week before Target Go-Live. Include Gabe/Ilse for all Enterprise and Tier 1" from 2026-08-31 (earlier: "8. Internal meeting with OM/SM"). Kickoff subtask "Submit CSF/Toast form to Storable" was unnumbered in the first enrollment (2026-08-24) and "11." afterwards.',
  'Subtask titles on task records by creation date.',
  'Earlier tickets carry older instructions. Normal for an evolving process, but means task sets are not identical across tickets.',
  'None required beyond awareness; confirm the current wording is final.')
F('Confirmed', 'Several (+SubTask) workflows', 'Various',
  'Facility-specific text appears in titles of workflow-created tasks, e.g. "Subtask - Bryn (Valparaiso)", "7. Complete Safelease set up (AC Storage -Pending Safelease Codes)", "4. Review current unit mix ... (Meridian Self Storage)".',
  'Title variants on task records (see Task & Subtask Logic "Notes").',
  'Most likely manual renames after creation (INFERENCE) - they are used as notes. Reporting by exact title will split these tasks.',
  'Confirm titles were edited manually and not via per-facility workflow copies.')
F('Confirmed', 'All 7 (+SubTask)', 'Owner of parent tasks',
  'Two owner patterns: (a) parents named "Ticket Owner/PM", the main Kickoff parent, the Pre-Launch "Subtask" parent and both 30-Day parents go to the ticket owner (they match the ticket\'s current owner in almost every case; the exceptions match later reassignments) (INFERENCE: "assign to ticket owner"); (b) all other parents always go to the same named person: ' + ', '.join(f'{k} ({v} action{"s" if v > 1 else ""})' for k, v in named.most_common()) + '.',
  'Task owner vs. ticket owner; owner counts per parent title (Task & Subtask Logic).',
  'Named owners are probably hard-coded (INFERENCE). Kickoff confirms it: Action 1 "assign to Ticket owner", Action 2 "assign to Mo\'men Khattab", Action 3 "assign to Bryn Morgan" (VERIFIED screenshot). If someone leaves or changes role, new tasks still go to them.',
  'Confirm the owner setting of every Create task action (static user vs. ticket owner).')
F('Potential Issue', 'Transitions - 30-Day Monitoring (+SubTask)', 'Action #1',
  'The parent "Transition | 30 - DAY MONITORING | Subtask - Automated" is owned by the ticket owner (not automated) and holds the subtask "1. Send CSAT survey to client".',
  'Owner = ticket owner on 6/6; subtask has no owner.',
  'The name suggests the CSAT survey is sent automatically; the data shows it is a manual task for the PM (5 of 6 still not started).',
  'Confirm whether a CSAT survey is sent automatically anywhere, or whether this task is the only mechanism.')
F('Potential Issue', 'Transitions - TRANSITION COMPLETE (+SubTask); Transitions - 30-Day Monitoring (+SubTask)', 'TC Action #1; 30-Day Action #2 subtask 3',
  'The final check runs after the ticket is already closed. 30-Day subtask 3 tells the PM to close the ticket and move it to Transition Completed manually once all items are done. Entering Transition Completed (a closed stage) then creates "1.All open items completed and 30 days post transition", due the same day (0 business days on 17/18).',
  'TRANSITION COMPLETE enrolls seconds after "Date entered Transition Completed"; subtask due offset 0 bd.',
  'The "all items completed" check is created after the stage that should depend on it. Open tasks on closed tickets are easy to miss.',
  'Confirm the intended order: check before moving to Transition Completed, or after?')
F('Confirmed', 'Transitions - TRANSITION COMPLETE (+SubTask)', 'Action #1',
  'Unlike every other workflow, TRANSITION COMPLETE subtasks DO have an owner: 15 of 18 have one, and 14 of those 15 match the parent task owner.',
  'hubspot_owner_id on subtasks of this workflow.',
  'Shows the subtask owner can be set; the other 6 workflows leave it empty (F-02).',
  'Use this action\'s settings as the reference when checking F-02.')
F('Needs Verification', 'Transitions - TRANSITION COMPLETE (+SubTask)', 'Action #1',
  'One enrollment (2026-09-09) created its tasks associated with company 38502110732 only - no ticket.',
  'Enrollment 2815002373637: tasks have a company association and no ticket association.',
  'Either the ticket was deleted/merged after enrollment, or the association step failed. The task cannot be found from any ticket.',
  'Look up the workflow history for that enrollment.')
F('Potential Issue', 'Several (+SubTask) workflows', 'Associations',
  'Association settings differ between actions: e.g. Final Sign-Off "Subtask - Mike" parent is linked to the ticket only (10/11) while the other parents are linked to ticket + company; subtasks in early enrollments (mostly August) are ticket-only while later ones are ticket + company (Kickoff 70 ticket-only subtasks, all 2026-08-24 to 09-01; Launch Readiness 40, all 08-20 to 08-28). In Pre-Launch, 67 of 140 subtasks are ticket-only throughout (to 2026-09-25).',
  'Association counts per parent/subtask title (Task & Subtask Logic "Task/Subtask Configuration").',
  'Tasks without a company link do not appear on the company record or in company-based views/reports.',
  'Check the association settings on each Create task action.')
F('Needs Verification', 'All 7 (+SubTask)', 'Stage transitions',
  'No evidence that completing tasks moves the ticket to the next stage. Time between finishing the "End of stage task sign off" subtask and the ticket entering the next stage ranges from about -5 days (ticket moved before sign-off) to +14 days; a few are within minutes (same person doing both).',
  'hs_task_completion_date of "End of stage ..." subtasks vs. next stage hs_v2_date_entered_*.',
  'The stages, and therefore all task creation, depend on someone moving the ticket by hand (INFERENCE). Tickets that are never moved never get the next task set.',
  'Confirm no workflow advances the ticket stage.')
F('Confirmed', 'All 7 (+SubTask)', 'Due dates',
  'Almost all due dates are set at 08:00 US/Eastern and mostly a fixed number of business days after the task is created; Go-Live tasks are all due the next business day; 30-Day parents are due in 30 business days. Some tasks show different values (e.g. Bryn\'s parents 11-20 bd; times like 16:45) - these look like manual edits.',
  'hs_timestamp vs hs_createdate, per title (Task & Subtask Logic).',
  'Go-Live due dates of 1 business day for 15 tasks explain part of the overdue volume in F-04.',
  'Confirm the configured due-date rule (delta and business-day setting) on each action.')
F('Needs Verification', CW_NAME, 'Action #1 associations',
  f'{cw_deal_counts.get(2, 0)} of {len(cw)} tickets created by this workflow are associated with 2 deals; {comp_multi_n} companies have more than one Onboarding Pipeline ticket.',
  'Ticket -> deal and ticket -> company associations (v4 associations API).',
  'Could be intended (renewals, multi-facility owners) or duplicate association copying. Duplicated tickets would create duplicate task sets.',
  'Open the Create ticket action\'s association settings; spot-check a ticket with 2 deals.')
F('Needs Verification', CW_NAME, 'Handoff to Kickoff',
  f'The Closed Won workflow puts tickets in UNASSIGNED, and none of the 7 Transitions workflows fires there. Nothing observed moves the ticket to Transition Kickoff. 3 of the {len(cw)} tickets are still in UNASSIGNED and 10 are On Hold.',
  'Current pipeline stage of tickets created by this workflow; no task or stage automation observed between UNASSIGNED and Transition Kickoff.',
  'The whole Transitions task flow starts only when someone moves the ticket by hand (INFERENCE).',
  'Confirm who moves tickets from UNASSIGNED to Transition Kickoff and whether any workflow does it.')
F('No Issue Found', 'All 7 (+SubTask)', 'Enrollment',
  'Every ticket whose latest entry into a stage is after the matching (+SubTask) workflow went live got exactly one enrollment, with the single exception in F-07 (based on the latest "Date entered" value per stage; earlier entries are overwritten). No delays between task actions (all tasks of an enrollment created within ~1-85 seconds).',
  'Enrollment evidence sheet; stage-entry dates of all 262 Onboarding Pipeline tickets.',
  'Task creation itself is reliable once a ticket reaches a stage.',
  'n/a')

F('Confirmed', 'Set task queue (1677143128) + Kickoff (+SubTask) + Launch Readiness (+SubTask)', 'Kickoff #1 subtask 9; Launch Readiness #2 subtask 2',
  'A different workflow moves two Transitions subtasks into the "BOG - Run and Sustain" task queue. "Set task queue" (readable, ON) enrolls every newly created task and, if the title contains "BOG", sets Queue = 9999918 (its "BOG - Run and Sustain" branch). "9. Submit BOG request in HubSpot to Hunter" (21/21) and "2. Finalize BOG candidates, paperwork, details in Hubspot" (20/20) are in that queue; no other Transitions task is in any queue.',
  'Config of workflow 1677143128 (VERIFIED: list branch "BOG - Run and Sustain" -> action 3 sets hs_queue_membership_ids = 9999918). Task records: hs_queue_membership_ids = 9999918 on exactly those 41 subtasks.',
  'Onboarding subtasks with no owner show up in a Run & Sustain queue. That may be how Hunter\'s team finds them, or it may be unintended.',
  'Confirm with the BOG team whether onboarding subtasks should be in the Run & Sustain queue.')
F('Potential Issue', 'Set OM and SM overdue tasks to Deferred (1795953061) + all 7 (+SubTask)', 'Parent tasks owned by OM/SM team members',
  'A different workflow can defer Transitions tasks automatically. "Set OM and SM overdue tasks to Deferred" (readable, ON) sets Status = DEFERRED on overdue, not-completed tasks whose owner team is 58458611 or 58458777. The 4 DEFERRED Transitions tasks are all "Transition | LAUNCH READINESS | Subtask - Hunter" parents (owner Hunter Stoner) (INFERENCE: deferred by this workflow; the team names/members could not be read - scope settings.users.teams.read missing). Subtasks have no owner, so this workflow can never act on them.',
  'Config of workflow 1795953061 (VERIFIED: enrollment = hs_task_is_overdue true AND hubspot_team_id in [58458611, 58458777] AND status not Completed; action 1 sets hs_task_status = DEFERRED). Task records: 4 DEFERRED parents, all owner 80038421.',
  'A deferred Launch Readiness parent drops out of overdue views while its subtask (2. Finalize BOG candidates) can still be open.',
  'Confirm which users are in teams 58458611 / 58458777 and whether Transitions tasks should be excluded from auto-deferral.')
af_headers = ['Finding #', 'Classification', 'Workflow', 'Action #', 'Finding', 'Evidence', 'Why It Matters', 'Recommended Verification', 'Status']

# ---------------------------------------------------------------- evidence sheets
ev = []
for new, stage, old in WF:
    for i in M[new]['enr']:
        tk = TK.get(i['tickets'][0]) if i['tickets'] else None
        sig_par = sorted({t['idx'] + 1 for t in i['tasks']})
        ev.append([new, i['enr'], i['tickets'][0] if i['tickets'] else '(no ticket)', tk['properties']['subject'] if tk else '', TURL(i['tickets'][0]) if i['tickets'] else '',
                   (tk['properties'].get('hs_object_source_detail_1') or tk['properties'].get('hs_object_source')) if tk else '',
                   STG.get(tk['properties']['hs_pipeline_stage'], tk['properties']['hs_pipeline_stage']) if tk else '',
                   i['entered'].strftime('%Y-%m-%d %H:%M:%S UTC') if i['entered'] else '', i['start'].strftime('%Y-%m-%d %H:%M:%S UTC'),
                   round(i['delta'], 1) if i['delta'] is not None else '', len(i['tasks']), sum(1 for t in i['tasks'] if t['properties']['hs_task_is_sub_task'] == 'true'),
                   ', '.join(f'#{x}' for x in sig_par), sum(1 for t in i['tasks'] if t['properties']['hs_task_status'] not in ('COMPLETED', 'DEFERRED'))])
ev_headers = ['Workflow', 'Enrollment ID', 'Ticket ID', 'Ticket Name', 'Ticket Link', 'Ticket Created By', 'Ticket Stage Now', 'Ticket Entered This Stage (latest)', 'First Task Created',
              'Seconds After Stage Entry', 'Tasks Created', 'Of Which Subtasks', 'Actions Observed', 'Still Open']

cov = []
legacy_by_ticket = collections.defaultdict(set)
for t in T:
    for k in t['tickets']:
        legacy_by_ticket[k].add(t['properties']['hs_object_source_detail_1'])
for t in OB:
    p = t['properties']
    entered = {s: P(p.get('hs_v2_date_entered_' + s)) for s in [w[1] for w in WF]}
    if not any(v and v >= dt.datetime(2026, 8, 20, tzinfo=dt.timezone.utc) for v in entered.values()):
        continue
    row = [t['id'], p['subject'], TURL(t['id']), p.get('hs_object_source_detail_1') or p.get('hs_object_source'), STG.get(p['hs_pipeline_stage'], p['hs_pipeline_stage'])]
    flags = []
    for new, stage, old in WF:
        e = entered[stage]
        got = new in legacy_by_ticket[t['id']]
        oldg = old in legacy_by_ticket[t['id']] if old else False
        cell = ('Yes' if got else ('No' if e and e >= wfstats[new]['first'] else '-')) + (' + legacy' if oldg else '')
        if e and e >= wfstats[new]['first'] and not got:
            flags.append(f'Entered {STG[stage]} {e:%Y-%m-%d} with no tasks')
        if got and oldg:
            flags.append(f'{SHORT[new]}: legacy and new sets')
        row.append(cell)
    row.append('; '.join(flags))
    cov.append(row)
cov_headers = ['Ticket ID', 'Ticket Name', 'Ticket Link', 'Created By', 'Stage Now'] + [f'{SHORT[n]} tasks?' for n in NEWS] + ['Flags']

# ---------------------------------------------------------------- write
sheet('Process Overview', po_headers, [7, 45, 38, 42, 40, 70, 9], po)
sheet('Detailed Action Map', dam_headers, [34, 18, 12, 18, 8, 30, 20, 60, 22, 30, 14, 60, 34, 26, 40, 34, 60, 40, 22], dam, level_col=18)
sheet('Workflow Inventory', wi_headers, [40, 20, 22, 44, 60, 34, 34, 30, 60, 40, 44], wi)
sheet('Task & Subtask Logic', ts_headers, [34, 8, 40, 44, 26, 30, 60, 60, 44, 44, 50, 9, 22, 16], ts, level_col=13)
sheet('Audit Findings', af_headers, [9, 18, 36, 20, 70, 60, 50, 50, 10], AF, class_col=1)
sheet('Evidence - Enrollments', ev_headers, [34, 16, 14, 34, 22, 30, 22, 22, 22, 10, 8, 8, 16, 8], ev, link_col=4)
sheet('Evidence - Ticket Coverage', cov_headers, [14, 36, 22, 30, 22] + [14] * 7 + [50], cov, link_col=2)

ws = wb['Read Me']
for cls in ['Confirmed', 'Potential Issue', 'Needs Verification', 'No Issue Found']:
    r = ws.max_row + 1
    ws.cell(row=r, column=1, value=f'=CONCATENATE("{cls}: ",COUNTIF(\'Audit Findings\'!B:B,"{cls}"))').font = FONT
ws.cell(row=ws.max_row + 2, column=1, value='Sheets: Process Overview | Detailed Action Map | Workflow Inventory | Task & Subtask Logic | Audit Findings | Evidence - Enrollments (one row per workflow run) | Evidence - Ticket Coverage (one row per ticket that entered a Transitions stage since 2026-08-20)').font = FONT

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'WLS_Transitions_Workflow_Audit.xlsx')
os.makedirs(os.path.dirname(out), exist_ok=True)
from openpyxl.workbook.properties import CalcProperties
wb.calculation = CalcProperties(fullCalcOnLoad=True)
wb.save(out)
print(out, len(dam), len(ts), len(AF), len(ev), len(cov))
