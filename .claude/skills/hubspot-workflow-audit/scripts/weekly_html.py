#!/usr/bin/env python3
"""Interactive weekly audit page (one self-contained HTML file) from weekly.py's results.json.

Usage:
  python3 weekly_html.py --work DIR [--out FILE]
Default output: audits/<team>-workflow-audit/weekly/<team>-weekly-audit-<report day>.html

Colours come from the team's team-rules.md (page_colours). Same layout for every team: tabs Summary, Tasks created, Company links, Workflow changes, Waiting on <decision owner>;
a task-type dropdown; a facility search. Company names and record IDs only - no customer contact details.
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rules

ap = argparse.ArgumentParser()
ap.add_argument('--work', required=True)
ap.add_argument('--out')
A = ap.parse_args()
R = json.load(open(os.path.join(A.work, 'results.json')))
out = A.out or os.path.join(rules.team_dir(R['team_slug']), 'weekly', f'{R["team_slug"]}-weekly-audit-{R["report_day"]}.html')
os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)

# Only what the page shows. Nothing here is a contact detail.
data = {k: R[k] for k in ('team', 'decision_owner', 'portal', 'queue', 'queue_ids', 'window', 'report_day', 'time_zone', 'fetched_at', 'start_date',
                          'counts', 'top', 'types', 'new_facilities', 'links', 'subtasks', 'changes', 'waiting_on', 'known_issues', 'expected_off',
                          'problems', 'companies', 'tasks')}
blob = json.dumps(data, default=str).replace('</', '<\\/')
title = f'{R["team"]} weekly audit {R["report_day"]}'
# Page colours come from the team's settings (team-rules.md "page_colours"); neutral defaults otherwise.
COL = {'navy': '#1F2A3C', 'grey': '#666F7A', 'red': '#D62828', 'white': '#FFFFFF', 'background': '#F7F8FA'}
COL.update((rules.load_team(R['team_slug'])[1] or {}).get('page_colours') or {})

PAGE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--navy:__NAVY__;--grey:__GREY__;--red:__RED__;--white:__WHITE__;--bg:__BG__;--line:color-mix(in srgb,var(--grey) 22%,var(--white));--text:var(--navy)}
*{box-sizing:border-box}
body{margin:0;font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;color:var(--text);background:var(--bg)}
header{background:var(--navy);color:var(--white);padding:18px 24px 0}
header h1{margin:0;font-size:20px;font-weight:600}
header .sub{color:color-mix(in srgb,var(--white) 75%,var(--navy));font-size:13px;margin:4px 0 14px}
.bar{display:flex;flex-wrap:wrap;gap:12px;align-items:flex-end;justify-content:space-between}
nav{display:flex;flex-wrap:wrap;gap:2px}
nav button{background:transparent;color:color-mix(in srgb,var(--white) 75%,var(--navy));border:0;padding:10px 14px;font:inherit;cursor:pointer;border-radius:6px 6px 0 0}
nav button.on{background:var(--bg);color:var(--navy);font-weight:600}
nav button:hover:not(.on){color:var(--white);background:color-mix(in srgb,var(--white) 12%,var(--navy))}
.search{position:relative;margin-bottom:10px;flex:0 1 340px}
.search input{width:100%;padding:8px 10px;border-radius:6px;border:1px solid var(--grey);font:inherit;background:var(--white);color:var(--navy)}
main{padding:20px 24px 48px;max-width:1280px}
section{display:none}section.on{display:block}
h2{font-size:16px;color:var(--navy);margin:22px 0 8px}h2:first-child{margin-top:0}
h3{font-size:14px;color:var(--navy);margin:16px 0 6px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
.card{background:var(--white);border:1px solid var(--line);border-radius:8px;padding:12px 14px}
.card .n{font-size:24px;font-weight:600;color:var(--navy)}.card .l{color:var(--grey);font-size:12px}
.card.bad .n{color:var(--red)}
.q{background:var(--white);border:1px solid var(--line);border-left:4px solid var(--grey);border-radius:6px;padding:10px 14px;margin:8px 0}
.q.bad{border-left-color:var(--red)}
table{width:100%;border-collapse:collapse;background:var(--white);border:1px solid var(--line);border-radius:6px;overflow:hidden;margin:6px 0 14px}
th{background:var(--grey);color:var(--white);text-align:left;font-weight:600;padding:7px 9px;font-size:13px}
td{padding:7px 9px;border-top:1px solid var(--line);vertical-align:top;background:var(--white)}
.pill{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px;white-space:nowrap;border:1px solid var(--line);color:var(--grey);background:var(--white)}
.p-bad{border-color:var(--red);color:var(--red);font-weight:600}
.lbl{font-size:11px;color:var(--grey);white-space:nowrap}
.muted{color:var(--grey)}
select{padding:7px 9px;border-radius:6px;border:1px solid var(--line);font:inherit;min-width:320px;max-width:100%;background:var(--white);color:var(--navy)}
pre{white-space:pre-wrap;margin:0;font:12px/1.4 ui-monospace,Menlo,Consolas,monospace}
a{color:var(--navy)}
ol li,ul li{margin:4px 0}
.empty{background:var(--white);border:1px dashed var(--line);border-radius:6px;padding:12px;color:var(--grey)}
.tablewrap{overflow-x:auto}
@media (max-width:640px){header,main{padding-left:16px;padding-right:16px}select{min-width:0;width:100%}}
</style></head><body>
<header>
 <h1 id="h1"></h1><div class="sub" id="sub"></div>
 <div class="bar"><nav id="nav"></nav><div class="search"><input id="q" type="search" placeholder="Search a facility (name or ID)" aria-label="Search a facility"></div></div>
</header>
<main>
 <section id="s-search"></section>
 <section id="s-summary"></section>
 <section id="s-tasks"></section>
 <section id="s-links"></section>
 <section id="s-changes"></section>
 <section id="s-waiting"></section>
</main>
<script>
const D = __DATA__;
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const co = id => D.companies[id] || ('company ' + id);
const coLink = id => id ? `<a href="https://app.hubspot.com/contacts/${D.portal}/record/0-2/${esc(id)}" target="_blank" rel="noopener">${esc(co(id))}</a> <span class="lbl">${esc(id)}</span>` : '<span class="muted">none</span>';
const wfLink = (id, name) => id ? `<a href="https://app.hubspot.com/workflows/${D.portal}/platform/flow/${esc(id)}/edit" target="_blank" rel="noopener">${esc(name)}</a>` : esc(name);
const pill = (t, k) => `<span class="pill p-${k}">${esc(t)}</span>`;
const reasonPill = r => pill(r, /Waiting on|went live/.test(r) ? 'info' : 'bad');
const table = (head, rows) => rows.length ? `<div class="tablewrap"><table><thead><tr>${head.map(h => `<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${r.map(c => `<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table></div>` : '<div class="empty">Nothing to show.</div>';
const TABS = [['summary','Summary'],['tasks','Tasks created'],['links','Company links'],['changes','Workflow changes'],['waiting','Waiting on ' + D.decision_owner]];

$('#h1').textContent = `${D.team} weekly workflow audit`;
$('#sub').textContent = `Window ${D.window[0]} to ${D.window[1]} (${D.time_zone}) · report for ${D.report_day} · data read ${D.fetched_at} · queue ${D.queue} · read only`;
$('#nav').innerHTML = TABS.map(([k, l]) => `<button data-t="${k}">${esc(l)}</button>`).join('');
function show(k){ document.querySelectorAll('section').forEach(s => s.classList.toggle('on', s.id === 's-' + k)); document.querySelectorAll('nav button').forEach(b => b.classList.toggle('on', b.dataset.t === k)); try{localStorage.setItem('wa-tab', k)}catch(e){} }
$('#nav').addEventListener('click', e => { if (e.target.dataset.t) { $('#q').value = ''; show(e.target.dataset.t); } });

// ---------------------------------------------------------------- Summary
(function(){
 const c = D.counts, chAll = D.changes.filter(x => x.status !== 'same'), ch = chAll.length, chNew = chAll.filter(x => !x.pending).length;
 const q = (n, title, good, bad) => `<div class="q ${n ? 'bad' : 'good'}"><b>${esc(title)}</b><br>${n ? esc(bad) : esc(good)}</div>`;
 let h = `<div class="cards">
  <div class="card"><div class="n">${c.facilities_in_scope}</div><div class="l">facilities in scope</div></div>
  <div class="card"><div class="n">${c.main_tasks}</div><div class="l">main tasks created</div></div>
  <div class="card"><div class="n">${c.subtasks}</div><div class="l">subtasks created</div></div>
  <div class="card"><div class="n">${c.workflows}</div><div class="l">workflows compared</div></div></div>
 <h2>The three questions</h2>
 ${q(c.q1, '1. Were the tasks created?', 'All good.', c.q1 + ' problem(s). See Tasks created.')}
 ${q(c.q2, '2. Are they linked to the right company?', 'All good.', c.q2 + ' problem(s). See Company links.')}
 ${q(chNew, '3. Did anyone change the workflows?', ch ? ch + ' workflow(s) differ from the master rules file, all already listed as not yet confirmed. See Workflow changes.' : 'No changes.', ch + ' workflow(s) differ from the master rules file (' + chNew + ' new). See Workflow changes.')}
 <h2>Top problems</h2>` + (D.top.length ? `<ol>${D.top.map(t => `<li>${esc(t.text)} <span class="lbl">${esc(t.label)}</span></li>`).join('')}</ol>` : '<div class="empty">No problems found.</div>');
 h += `<h2>Waiting on ${esc(D.decision_owner)}</h2><ul>${D.waiting_on.map(w => `<li>${esc(w.title)}${w.found && w.found.length ? ' — ' + w.found.length + ' this week' : ''}</li>`).join('')}</ul>`;
 h += `<h2>Known issues</h2><ul>${D.known_issues.map(k => `<li><b>${esc(k.id)}</b>: ${esc(k.text)}${k.this_week ? ' <span class="muted">' + esc(k.this_week) + '</span>' : ''}</li>`).join('')}</ul>`;
 if (D.expected_off.length) h += `<h3>Workflows expected to be off</h3>` + table(['Workflow', 'Now'], D.expected_off.map(w => [wfLink(w.id, w.name), w.live === 'OFF' ? pill('off, as expected', 'ok') : pill('ON', 'bad')]));
 h += `<p class="muted">Labels: VERIFIED (config) = from the workflow settings; VERIFIED (records) = from HubSpot records; INFERENCE = worked out, not seen directly; NEEDS VERIFICATION = could not be checked. Who should get a task is worked out from the master rules file and each facility's property values at the time of the run.</p>`;
 $('#s-summary').innerHTML = h;
})();

// ---------------------------------------------------------------- Tasks created
(function(){
 const types = D.types;
 let h = `<h2>Tasks created, by task type</h2><select id="typeSel" aria-label="Task type">${types.map((t, i) => {
   const m = Object.keys(t.missing).length, s = Object.keys(t.shouldnt).length;
   return `<option value="${i}">${esc(t.name)} — ${t.runs.length ? (m || s ? (m + s) + ' problem(s)' : 'all good') : 'no run this week'}</option>`; }).join('')}</select><div id="typeView"></div>`;
 const other = D.problems.filter(p => p.q === 1 && !['missing', 'shouldnt'].includes(p.kind));
 h += `<h2>Other task problems</h2>` + table(['Problem', 'Facility', 'Label'], other.map(p => [esc(p.text), coLink(p.company_id), `<span class="lbl">${esc(p.label)}</span>`]));
 h += `<h2>New facilities this week</h2><p class="muted">Facilities whose Status changed to Live during the window (checked against the go-live date).</p>`;
 h += D.new_facilities.length ? D.new_facilities.map(n => `<h3>${coLink(n.company_id)}</h3><p>Live since ${esc(n.went_live)} · go-live date ${esc(n.go_live_date || 'empty')}${n.flag ? ' ' + pill(n.days_apart + ' days apart', 'bad') : ''}</p>` +
   table(['Task type', 'Status'], n.types.map(t => [esc(t.type), /^got/.test(t.status) ? pill(t.status, 'ok') : /^missing/.test(t.status) ? pill(t.status, 'bad') : /^not yet/.test(t.status) ? pill(t.status, 'info') : `<span class="muted">${esc(t.status)}</span>`]))).join('') : '<div class="empty">No facility became live this week.</div>';
 $('#s-tasks').innerHTML = h;
 function render(i){
  const t = types[i];
  let v = `<h3>Made by</h3><ul>${t.workflows.map(w => `<li>${wfLink(w.id, w.name)} ${w.on_live === false && w.on_master ? pill('switched off now', 'bad') : w.on_master === false ? pill('off (expected)', 'info') : ''}</li>`).join('')}</ul>`;
  v += `<h3>Runs in the window</h3>` + (t.runs.length ? `<ul>${t.runs.map(r => `<li>${esc(r.when)} — ${esc(r.name)}${r.off ? ' ' + pill('workflow now off', 'bad') : ''}</li>`).join('')}</ul>` : '<div class="empty">No scheduled run of this task type fell in the window, so nobody was due to get it.</div>');
  t.notes.forEach(n => v += `<p class="muted">${esc(n)}</p>`);
  v += `<div class="cards" style="margin:10px 0"><div class="card"><div class="n">${t.should.length}</div><div class="l">should have got it</div></div><div class="card"><div class="n">${t.got.length}</div><div class="l">did get it</div></div><div class="card${Object.keys(t.missing).length ? ' bad' : ''}"><div class="n">${Object.keys(t.missing).length}</div><div class="l">missing</div></div><div class="card${Object.keys(t.shouldnt).length ? ' bad' : ''}"><div class="n">${Object.keys(t.shouldnt).length}</div><div class="l">shouldn't have</div></div></div>`;
  v += `<h3>Missing</h3>` + table(['Facility', 'Reason', 'Workflow', 'Run', 'Label'], Object.entries(t.missing).map(([id, m]) => [coLink(id), reasonPill(m.reason), esc((t.workflows.find(w => w.id === m.workflow) || {}).name || m.workflow), esc(m.run), `<span class="lbl">${esc(m.label)}</span>`]));
  v += `<h3>Created for facilities that shouldn't have them</h3>` + table(['Facility', 'Why not', 'Created', 'Task ID', 'Label'], Object.entries(t.shouldnt).map(([id, m]) => [coLink(id), esc(m.reason), esc(m.created), esc(m.task), `<span class="lbl">${esc(m.label)}</span>`]));
  const ne = Object.entries(t.not_expected);
  if (ne.length) v += `<h3>In scope but not due this task (by the workflow settings)</h3>` + table(['Reason', 'Facilities'], ne.map(([r, n]) => [esc(r), n]));
  v += `<h3>Did get it (${t.got.length})</h3>` + (t.got.length ? `<p>${t.got.map(id => esc(co(id))).join(', ')}</p>` : '<div class="empty">None.</div>');
  $('#typeView').innerHTML = v;
  try{localStorage.setItem('wa-type', i)}catch(e){}
 }
 $('#typeSel').addEventListener('change', e => render(e.target.value));
 let saved = 0; try{ saved = +(localStorage.getItem('wa-type') || 0) }catch(e){}
 if (!types[saved]) saved = Math.max(0, types.findIndex(t => t.runs.length));
 $('#typeSel').value = saved; render(saved);
})();

// ---------------------------------------------------------------- Company links
(function(){
 const bad = D.links.filter(l => l.status !== 'ok');
 let h = `<h2>Main tasks and their company</h2><p>${D.links.length} main tasks created in the window; ${bad.length} with a problem.</p>`;
 h += table(['Task', 'Type', 'Workflow', 'Company', 'Problem', 'Label'], bad.map(l => [esc(l.title) + ` <span class="lbl">${esc(l.task)}</span>`, esc(l.type || ''), esc(l.workflow), l.companies.map(c => coLink(c.id)).join('<br>') || '<span class="muted">none</span>', pill(l.status, 'bad'), `<span class="lbl">${esc(l.label)}</span>`]));
 const sb = D.subtasks.filter(s => s.status !== 'ok');
 h += `<h2>Subtasks</h2><p>${D.subtasks.length} subtasks found through their main tasks; ${sb.length} linked to a ticket.</p>`;
 h += table(['Subtask', 'Main task', 'Ticket(s)'], sb.map(s => [esc(s.title) + ` <span class="lbl">${esc(s.task)}</span>`, esc(s.parent), esc(s.tickets.join(', '))]));
 $('#s-links').innerHTML = h;
})();

// ---------------------------------------------------------------- Workflow changes
(function(){
 const ch = D.changes.filter(c => c.status !== 'same'), same = D.changes.filter(c => c.status === 'same');
 let h = `<h2>Live workflows compared with the master rules file</h2><p>${ch.length} of ${D.changes.length} workflows differ. A change isn't automatically wrong: confirm whether it was planned, and only then update the master rules file.</p>`;
 h += ch.length ? ch.map(c => `<h3>${wfLink(c.workflow, c.name)} ${c.status === 'change, not yet confirmed' ? pill('change, not yet confirmed', 'warn') : pill(c.status, 'bad')}</h3>` +
   (c.pending ? `<p>${pill('first seen ' + c.pending.first_seen + ' · ' + c.pending.status, 'info')}</p>` : '') +
   (c.revision ? `<p class="muted">Revision ${esc(c.revision[0])} → ${esc(c.revision[1])} · last updated ${esc(c.updated)}${c.only_revision ? ' · no change found in the compared settings (trigger, schedule, re-enrollment, suppression, branches, task actions, queue)' : ''}</p>` : `<p class="muted">${esc(c.error || '')}</p>`) +
   (c.rule2 ? `<p>${pill(c.rule2, 'bad')}</p>` : '') +
   (c.only_revision ? '' : table(['Setting', 'Was (master rules file)', 'Now (live)'], c.diffs.filter(d => d.column !== 'Revision').map(d => [esc(d.column), `<pre>${esc(d.was)}</pre>`, `<pre>${esc(d.now)}</pre>`])))).join('') : '<div class="empty">No changes.</div>';
 h += `<h2>Unchanged (${same.length})</h2><p class="muted">${same.map(c => esc(c.name)).join(' · ')}</p>`;
 $('#s-changes').innerHTML = h;
})();

// ---------------------------------------------------------------- Waiting on
(function(){
 let h = `<h2>Waiting on ${esc(D.decision_owner)}</h2><p class="muted">Open decisions. They are reported here once per run, not as new problems every week.</p>`;
 h += D.waiting_on.map(w => `<h3>${esc(w.id)} · ${esc(w.title)}</h3><p>${esc(w.detail || '')}</p>` + (w.found && w.found.length ?
   table(['Facility', 'Task type', 'Detail'], w.found.map(f => [coLink(f.company_id), esc(f.type || ''), esc(f.reason || (f.day ? f.day + ': ' + (f.workflows || []).join(' + ') : ''))])) :
   '<p class="muted">Nothing affected this week.</p>')).join('');
 $('#s-waiting').innerHTML = h;
})();

// ---------------------------------------------------------------- Facility search
const byCo = {};
D.tasks.forEach(t => (t.companies.length ? t.companies : ['']).forEach(c => (byCo[c] = byCo[c] || []).push(t)));
$('#q').addEventListener('input', e => {
 const s = e.target.value.trim().toLowerCase();
 if (!s) { let k = 'summary'; try{ k = localStorage.getItem('wa-tab') || 'summary' }catch(e){} show(k); return; }
 document.querySelectorAll('section').forEach(x => x.classList.toggle('on', x.id === 's-search'));
 document.querySelectorAll('nav button').forEach(b => b.classList.remove('on'));
 const ids = Object.keys(D.companies).filter(id => id.includes(s) || co(id).toLowerCase().includes(s)).sort((a, b) => co(a).localeCompare(co(b))).slice(0, 25);
 let h = `<h2>Facilities matching “${esc(e.target.value)}”</h2>`;
 if (!ids.length) h += '<div class="empty">No facility with tasks or findings this week matches.</div>';
 ids.forEach(id => {
  const ts = byCo[id] || [];
  const miss = D.types.filter(t => t.missing[id]).map(t => [esc(t.name), reasonPill(t.missing[id].reason)]);
  const probs = D.problems.filter(p => p.company_id === id && p.kind !== 'missing');
  h += `<h3>${coLink(id)}</h3>` + table(['Task', 'Type', 'Created', 'Due', 'Company link', 'Problems'], ts.map(t => {
     const pr = D.problems.filter(p => p.task_id === t.id).map(p => esc(p.text));
     return [esc(t.title) + ` <span class="lbl">${esc(t.id)}</span>`, esc(t.type || ''), esc(t.created), esc(t.due), t.link === 'ok' ? pill('ok', 'ok') : pill(t.link || '', 'bad'), pr.join('<br>') || '<span class="muted">none</span>']; }));
  if (miss.length) h += `<p><b>Missing this week</b></p>` + table(['Task type', 'Reason'], miss);
  if (probs.length && !ts.length) h += `<p>${probs.map(p => esc(p.text)).join('<br>')}</p>`;
 });
 $('#s-search').innerHTML = h;
});
let start = 'summary'; try{ start = localStorage.getItem('wa-tab') || 'summary' }catch(e){}
show(TABS.some(t => t[0] === start) ? start : 'summary');
</script></body></html>'''
for k, v in (('__NAVY__', COL['navy']), ('__GREY__', COL['grey']), ('__RED__', COL['red']), ('__WHITE__', COL['white']), ('__BG__', COL['background'])):
    PAGE = PAGE.replace(k, v)
open(out, 'w').write(PAGE.replace('__TITLE__', title).replace('__DATA__', blob))
print(f'Wrote {out} ({os.path.getsize(out) // 1024} KB)')
