'use strict';

/**
 * Builds the Markdown audit report (9 sections) from runAudit() output.
 *
 *   FACT        directly observed in HubSpot
 *   DOCUMENTED  stated in the existing WLS document
 *   DIFFERENCE  documentation and HubSpot do not match
 *   REVIEW      needs human confirmation
 */

const F = require('./filters');
const { describeDue } = require('./normalise');

const NO_PURPOSE = 'Purpose could not be confidently determined from the available configuration.';
const esc = (t) => String(t === null || t === undefined ? '' : t).replace(/\|/g, '\\|').replace(/\r?\n/g, ' ');
const table = (head, rows) => [`| ${head.join(' | ')} |`, `|${head.map(() => '---').join('|')}|`, ...rows.map((r) => `| ${r.map(esc).join(' | ')} |`)].join('\n');
const date = (iso) => (iso ? String(iso).slice(0, 10) : '—');
const tierText = (t, labels) => t.tiers.map((x) => labels[x] || x).join(', ');

const ordinal = (n) => `${n}${n % 10 === 1 && n !== 11 ? 'st' : n % 10 === 2 && n !== 12 ? 'nd' : n % 10 === 3 && n !== 13 ? 'rd' : 'th'}`;
const WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
// Day words in HubSpot's description that the configured schedule contradicts.
function descriptionConflicts(record) {
  const d = String(record.purpose.text || '').toLowerCase();
  const s = record.schedule.enrollmentSchedule;
  if (!d || !s) return [];
  const out = [];
  const days = WEEKDAYS.filter((w) => d.includes(w));
  if (days.length && (s.type !== 'WEEKLY' || !days.every((w) => s.daysOfWeek.includes(w.toUpperCase())))) out.push(`mentions ${days.map((w) => w[0].toUpperCase() + w.slice(1)).join('/')}`);
  const dom = [...d.matchAll(/\b(\d{1,2})(st|nd|rd|th)\b/g)].map((m) => Number(m[1]));
  if (dom.length && (s.type !== 'MONTHLY_SPECIFIC_DAYS' || !dom.some((n) => s.daysOfMonth.includes(n)))) out.push(`mentions the ${dom.map(ordinal).join('/')} of the month`);
  if (/\bweekly\b/.test(d) && s.type !== 'WEEKLY' && !/bi-?weekly/.test(d)) out.push('says weekly');
  if (/\bmonthly\b/.test(d) && s.type !== 'MONTHLY_SPECIFIC_DAYS' && !/bi-?monthly/.test(d)) out.push('says monthly');
  return out;
}

function renderSteps(record, ctx) {
  const flow = record.raw;
  const actions = new Map((flow.actions || []).map((a) => [String(a.actionId), a]));
  const lines = [];
  const seen = new Set();
  const walk = (id, depth) => {
    const indent = '   '.repeat(depth);
    while (id !== undefined && id !== null) {
      const a = actions.get(String(id));
      if (!a) {
        lines.push(`${indent}- ⚠ missing action ${id}`);
        return;
      }
      if (seen.has(`${depth}:${id}`)) return;
      seen.add(`${depth}:${id}`);
      if (a.listBranches) {
        lines.push(`${indent}- **Branch** (action ${a.actionId}) — first matching branch wins:`);
        a.listBranches.forEach((b, i) => {
          lines.push(`${indent}   ${i + 1}. **${b.branchName}** — if ${F.describeTree(b.filterBranch, ctx)}`);
          if (b.connection) walk(b.connection.nextActionId, depth + 2);
          else lines.push(`${indent}      - _(no actions: companies on this branch get nothing)_`);
        });
        if (a.defaultBranch) {
          lines.push(`${indent}   - **${a.defaultBranchName || 'Otherwise'}**`);
          walk(a.defaultBranch.nextActionId, depth + 2);
        } else lines.push(`${indent}   - _No "otherwise" path: companies matching none of the above leave the workflow with no task._`);
        return;
      }
      const f = a.fields || {};
      if (a.actionTypeId === '0-1') lines.push(`${indent}- Delay ${Number(f.delta) / 1440} days`);
      else if (a.actionTypeId === '0-3') {
        const t = record.createdTasks.find((x) => x.actionId === String(a.actionId));
        lines.push(`${indent}- Create task **"${esc(String(f.subject || '').trim()) || '(no title)'}"** → ${t ? t.assignee.text : '?'}; due ${describeDue(f.due_time)}${f.priority && f.priority !== 'NONE' ? `; priority ${f.priority}` : ''} (action ${a.actionId})`);
      } else lines.push(`${indent}- ${a.actionTypeId || a.type} (action ${a.actionId})`);
      id = a.connection ? a.connection.nextActionId : null;
    }
  };
  walk(flow.startActionId, 0);
  lines.push('- End');
  return lines.join('\n');
}

// Why a compared row needs review, in one line.
function reviewReasons(r) {
  const parts = [];
  for (const c of r.combos.filter((x) => x.status === 'CONDITIONAL' || x.status === 'WORKFLOW_OFF')) parts.push(c.text);
  for (const k of ['trigger', 'frequency', 'due', 'details']) if (r[k] && r[k].status === 'REVIEW') parts.push(`${k}: ${r[k].text}`);
  parts.push(...r.notes);
  return parts.join(' • ') || 'See section 6.';
}

function buildReport(audit) {
  const { meta, records, suppression, unavailable, comparison, tierLabels, parsedDoc, lists } = audit;
  const supById = new Map(suppression.map((s) => [s.workflowId, s]));
  const out = [];
  const h = (t) => out.push(`\n## ${t}\n`);
  const on = records.filter((r) => r.status === 'ON');
  const off = records.filter((r) => r.status === 'OFF');
  const totalBranchActions = records.reduce((n, r) => n + r.actions.branches.length, 0);
  const noOtherwise = suppression.reduce((n, s) => n + s.noOtherwise.length, 0);
  const shadowed = suppression.flatMap((s) => s.shadowedBranches.map((x) => ({ ...x, wf: s })));
  const emptyBranches = suppression.flatMap((s) => s.emptyBranches.map((x) => ({ ...x, wf: s })));
  const rows = comparison ? comparison.rows : [];
  const countBy = (k) => rows.reduce((acc, r) => ((acc[r[k]] = (acc[r[k]] || 0) + 1), acc), {});
  const results = countBy('result');
  const documentedIds = new Set(rows.flatMap((r) => r.workflows.map((w) => w.id)));
  const undocumentedWorkflows = records.filter((r) => !documentedIds.has(r.id));
  const reviewItems = [];

  out.push(`# C-Ops - Task Management — HubSpot Workflow Audit`);
  out.push('');
  out.push(`Portal ${meta.portalId} · data fetched ${meta.fetchedAt} · report generated ${meta.auditedAt}`);
  out.push(`Compared with: ${meta.document ? `${meta.document.fileName} (sheet "${meta.document.sheetName}")` : 'no document'}`);
  out.push('');
  out.push('Read-only audit: nothing in HubSpot was changed. Labels: **FACT** = observed in HubSpot · **DOCUMENTED** = stated in the WLS spreadsheet · **DIFFERENCE** = the two disagree · **REVIEW** = needs a person to confirm. Neither source is assumed to be correct.');
  out.push('');
  out.push('HubSpot rule used throughout: in a branch step a company goes down the **first** branch whose criteria it meets, in order. Companies meeting none take the "otherwise" path; if there isn\'t one, they leave the workflow.');

  // 1
  h('1. Executive Summary');
  out.push(table(['Metric', 'Value'], [
    ['Workflows in the folder (expected)', meta.expectedCount],
    ['Folder workflows found and analysed', `${records.length} of ${meta.namesInScope}`],
    ['Folder workflows that could not be read (REVIEW)', unavailable.length],
    ['Active (ON) / inactive (OFF)', `${on.length} / ${off.length}`],
    ['Workflows with a suppression list', suppression.filter((s) => s.suppressionLists.length).length],
    ['Workflows with branches', records.filter((r) => r.actions.branches.length).length],
    ['Branch steps / of which with no "otherwise" path', `${totalBranchActions} / ${noOtherwise}`],
    ['Create-task actions', records.reduce((n, r) => n + r.createdTasks.length, 0)],
    ['Spreadsheet task rows compared', rows.length],
    ...Object.entries(results).map(([k, v]) => [`  rows: ${k}`, v]),
    ['Folder workflows not referenced by any spreadsheet row', undocumentedWorkflows.length],
    ['HubSpot tasks (tier/role paths) with no spreadsheet row', comparison ? comparison.undocumented.length : '—'],
  ]));
  out.push('\n**Key findings**\n');
  const list4291 = suppression[0] && suppression[0].suppressionLists[0];
  const key = [];
  if (list4291) {
    const users = suppression.filter((s) => s.suppressionLists.some((l) => l.listId === list4291.listId)).length;
    key.push(`**FACT** — ${users} of ${records.length} workflows suppress the same list, "${list4291.name}" (${list4291.listId}). It is a ${String(list4291.processingType).toLowerCase()} list of ${list4291.size} companies defined only as: ${list4291.criteria}. Any company whose street rates are automated by WLS gets **no Ops tasks at all** from these workflows (playbook, BOG, NPS, calls, etc.), not just rate tasks. **REVIEW**: confirm this is intended.`);
  }
  const omFirst = shadowed.filter((s) => /OM/i.test(s.earlier.join(' ')) && /SM/i.test(s.branch));
  if (omFirst.length) key.push(`**FACT** — ${omFirst.length} branch steps check "Operations Manager is known" before "Site Manager is known". Because the first match wins, a facility that has both an OM and an SM only ever gets the OM task; the SM path runs only when the OM field is blank. Where the spreadsheet says "OM + SM", HubSpot gives one person the task, not both. **DIFFERENCE/REVIEW**.`);
  const emptyOm = emptyBranches.filter((e) => /\bOM\b/.test(e.branch)).map((e) => ({ ...e, off: (records.find((r) => r.id === e.wf.workflowId) || {}).status === 'OFF' }));
  if (emptyOm.length) key.push(`**FACT** — ${emptyOm.length} "OM" branches have no actions (${[...new Set(emptyOm.map((e) => `"${e.wf.workflowName}" › ${e.branch}${e.off ? ' (workflow OFF)' : ''}`))].join('; ')}). Facilities with an OM get no task there, and because the SM branch comes second, their SM gets nothing either.`);
  key.push(`**FACT** — None of the ${totalBranchActions} branch steps has an "otherwise" path. Companies with Customer Tier "N/A" or blank silently get no task in any tier-branched workflow, and where a branch step checks "OM is known" / "SM is known", facilities with neither set get no task.`);
  const soaStrict = suppression.filter((s) => s.noOtherwise.some((n) => n.fallsThrough.some((f) => /do not start with/.test(f))));
  if (soaStrict.length) key.push(`**REVIEW** — In ${soaStrict.length} workflows the tier branches exclude any name *containing* "SOA" while the SOA branch needs the name to *start with* a longer prefix such as "SOA - ". Companies named differently fall between the two and get no task.`);
  const soaEmpty = emptyBranches.filter((e) => /^SOA$/i.test(e.branch.trim()));
  if (soaEmpty.length) key.push(`**FACT** — ${soaEmpty.length} workflows have an empty "SOA" branch, so SOA facilities get none of those tasks.`);
  const ent = comparison ? comparison.undocumented.filter((u) => /Enterprise tier/.test(u.reason)).length : 0;
  if (ent) key.push(`**DIFFERENCE** — HubSpot creates ${ent} Enterprise-tier task paths; the spreadsheet has no Enterprise tier. HubSpot also splits Tier 2 into "Tier 2 - L1" and "Tier 2 - L2", which the spreadsheet treats as one Tier 2; L2 usually gets only an SM task.`);
  if (off.length) key.push(`**FACT** — ${off.length} folder workflows are OFF: ${off.map((r) => `"${r.name}"`).join(', ')}.`);
  key.push(`**REVIEW** — ${unavailable.length} folder workflows could not be read through the API: ${unavailable.map((u) => `"${u.name}"`).join(', ')}. See section 9.`);
  out.push(key.map((k) => `- ${k}`).join('\n'));

  // 2
  h('2. Workflow Inventory');
  out.push(table(
    ['#', 'Workflow', 'ID', 'Object', 'Status', 'Schedule', 'Re-enrol', 'Suppression', 'Branch steps', 'Tasks', 'Created', 'Last updated', 'Analysis'],
    [
      ...records.map((r, i) => [i + 1, r.name, r.id, r.objectType === '0-2' ? 'Company' : r.objectType, r.status, r.schedule.plainEnglish, r.reEnrollment.enabled ? 'Yes' : 'No', r.suppression.suppressionLists.join(', ') || 'none', r.actions.branches.length, r.createdTasks.length, date(r.createdAt), date(r.updatedAt), r.issues.length ? 'Complete (with REVIEW items)' : 'Complete']),
      ...unavailable.map((u, i) => [records.length + i + 1, u.name, u.id || '—', u.objectType || '—', '—', '—', '—', '—', '—', '—', '—', '—', 'NOT RETRIEVED (REVIEW)']),
    ]
  ));
  out.push('\n"Last published/activated" is not returned by the v4 API, so it is not shown. Goals are not returned for these workflows.');

  // 3
  h('3. Workflow Mapping');
  for (const r of records) {
    const s = supById.get(r.id);
    out.push(`\n### ${r.name}\n`);
    out.push(table(['Field', 'Value'], [
      ['Workflow ID', r.id],
      ['Folder', `${r.folder} (from the folder list supplied; the API does not return folder membership)`],
      ['Object', r.objectType === '0-2' ? 'Company' : r.objectType],
      ['Status', r.status],
      ['Purpose', NO_PURPOSE],
      ['HubSpot description (as stated in HubSpot)', r.purpose.text || '—'],
      ['Enrolment', r.enrollment.plainEnglish],
      ['Re-enrolment', r.reEnrollment.plainEnglish],
      ['Unenrolment', r.unenrollment.plainEnglish],
      ['Suppression / exclusion', s.plainEnglish.slice(0, 2).join(' ') + (s.plainEnglish.length > 2 ? ' (full list in section 4)' : '')],
      ['Delays', r.actions.steps.filter((x) => x.kind === 'DELAY').map((x) => x.text).join('; ') || 'None'],
      ['Goals', 'None returned'],
      ['Dependencies', `Lists: ${r.dependencies.lists.join(', ') || 'none'}; named task owners: ${r.dependencies.owners.length ? r.createdTasks.filter((t) => t.assignee.ownerId).map((t) => t.assignee.text.replace('Specific user: ', '')).filter((v, i, a) => a.indexOf(v) === i).join(', ') : 'none'}`],
      ['Created / last updated', `${date(r.createdAt)} / ${date(r.updatedAt)}`],
      ['Last published / activated', 'Not available from the API'],
      ['Potential issues', [...r.issues.map((i) => i.message), ...descriptionConflicts(r).map((c) => `HubSpot description ${c}, but the schedule is "${r.schedule.plainEnglish}".`)].join(' • ') || 'None found'],
    ]));
    out.push('\n**Sequence**\n');
    out.push(`1. Enrolment: ${r.enrollment.plainEnglish}`);
    out.push(`2. Suppression: ${r.suppression.plainEnglish}`);
    out.push(`3. Steps:\n`);
    out.push(renderSteps(r, { properties: audit.properties, lists }).split('\n').map((l) => `   ${l}`).join('\n'));
    out.push('\n**Tasks created (by path)**\n');
    out.push(table(['Action', 'Title', 'Assigned to', 'Tier(s)', 'SOA', 'Path', 'Due', 'Created after'], r.createdTasks.map((t) => [t.actionId, t.title.trim() || '(no title)', t.assignee.text, t.tierConstrained ? tierText(t, tierLabels) : 'Any tier', t.soa, t.pathLabel, t.dueText, t.delayBeforeDays ? `${t.delayBeforeDays} days` : 'at enrolment'])));
  }

  // 4
  h('4. Suppression / Exclusion Analysis');
  const allListIds = [...new Set(suppression.flatMap((s) => s.suppressionLists.map((l) => l.listId)))];
  for (const id of allListIds) {
    const l = suppression.flatMap((s) => s.suppressionLists).find((x) => x.listId === id);
    const users = suppression.filter((s) => s.suppressionLists.some((x) => x.listId === id));
    out.push(`### Suppression list ${id}: "${l.name}"\n`);
    out.push(table(['Field', 'Value'], [
      ['Type', l.processingType === 'DYNAMIC' ? 'Active (dynamic) list: membership updates automatically' : l.processingType],
      ['Object', l.objectTypeId === '0-2' ? 'Company' : l.objectTypeId],
      ['Criteria (FACT)', l.criteria],
      ['Members when fetched', l.size],
      ['List last updated', date(l.updatedAt)],
      ['Used as suppression by', `${users.length} workflows: ${users.map((u) => u.workflowName).join('; ')}`],
    ]));
    out.push(`\n**In plain English:** a company that is in "${l.name}" can never enter any of these ${users.length} workflows. The list is defined only by "${l.criteria}", so its name suggests a general opt-out but in practice it removes every Ops task for companies with automated street-rate management. **REVIEW**: is that intended, or should it only suppress the rate-review workflows?\n`);
  }
  out.push('### Exclusions that apply across the folder\n');
  out.push([
    '- **Companies with Customer Tier "N/A" or blank** get no task in any workflow: every first branch step lists the tiers explicitly, and none has an "otherwise" path. (FACT)',
    '- **Facilities with neither an Operations Manager nor a Site Manager** get no task where the branch checks "OM is known" / "SM is known". Where a task is assigned from the SM property without that check (Tier 2 - L2 and Tier 3 paths), a blank SM means the task is created unassigned. (FACT/REVIEW)',
    '- **Enrolment** in most workflows requires Status = Live and Full Management Type = "Full management (Excl Call center)" or "Full management (Incl Call center)". Other management types never enrol. (FACT)',
  ].join('\n'));
  out.push('\n### Per workflow\n');
  for (const s of suppression) {
    out.push(`#### ${s.workflowName} (${s.workflowId})\n`);
    out.push(s.plainEnglish.map((p) => `- ${p}`).join('\n'));
    out.push('');
  }

  // 5
  h('5. Workflow Relationships / Dependencies');
  const titleWorkflows = new Map();
  for (const r of records) for (const t of r.createdTasks) {
    const k = t.title.trim().toLowerCase().replace(/\s+/g, ' ');
    if (!titleWorkflows.has(k)) titleWorkflows.set(k, { title: t.title.trim(), ids: new Set() });
    titleWorkflows.get(k).ids.add(r.id);
  }
  const nameOf = (id) => (records.find((r) => r.id === id) || {}).name;
  out.push(`- **Shared suppression list** — ${allListIds.map((id) => `list ${id} is used by ${suppression.filter((s) => s.suppressionLists.some((l) => l.listId === id)).length} workflows`).join('; ')}. A change to that list changes all of them at once. (FACT)`);
  out.push('- **Tasks split across workflow pairs** (FACT):');
  for (const [, v] of titleWorkflows) if (v.ids.size > 1) out.push(`  - "${v.title}" is created by ${[...v.ids].map((id) => `"${nameOf(id)}" (${id})`).join(' and ')}`);
  const props = new Set();
  for (const r of records) {
    for (const g of F.andGroups(r.raw.enrollmentCriteria && r.raw.enrollmentCriteria.listFilterBranch).flat()) if (g.property) props.add(g.property);
    for (const a of r.raw.actions || []) for (const b of a.listBranches || []) for (const g of F.andGroups(b.filterBranch).flat()) if (g.property) props.add(g.property);
    for (const t of r.createdTasks) if (t.assignee.property) props.add(t.assignee.property);
  }
  out.push(`- **Company properties the folder depends on**: ${[...props].map((p) => (audit.properties[p] ? `${audit.properties[p].label} (\`${p}\`)` : `\`${p}\``)).join(', ')}. Workflows elsewhere in HubSpot that set these properties (or Street Rate Management, which drives list 4291) change who gets tasks. (FACT)`);
  const named = records.flatMap((r) => r.createdTasks.filter((t) => t.assignee.ownerId).map((t) => ({ r, t })));
  if (named.length) out.push(`- **Tasks assigned to named people instead of the OM/SM property**: ${[...new Set(named.map((x) => `${x.t.assignee.text.replace('Specific user: ', '')} in "${x.r.name}"`))].join('; ')}. (FACT)`);
  out.push('- **Not visible from this folder** (REVIEW): workflows outside the folder that enrol or unenrol companies here, or that change the properties above. No action in this folder enrols companies into, or removes them from, another workflow.');

  // 6
  h('6. Documentation vs Actual HubSpot');
  if (!comparison) out.push('No document supplied.');
  else {
    out.push('One row per spreadsheet task row. "Tier/role" checks each tier and role the row names (T2 = HubSpot Tier 2 - L1 and Tier 2 - L2). The updated spreadsheet has the same comparison in its audit columns.\n');
    out.push(table(['Row', 'Item (DOCUMENTED)', 'Existing documentation', 'Actual HubSpot (FACT)', 'Difference', 'Result'], rows.map((r) => {
      const v = r.values;
      const diffs = [
        ...r.combos.filter((c) => c.status !== 'FOUND').map((c) => c.text),
        ...['trigger', 'frequency', 'due', 'details'].filter((k) => r[k] && r[k].status !== 'MATCH').map((k) => `${k}: ${r[k].text}`),
        ...r.notes,
      ];
      return [
        r.rowNumber,
        `${v.role} — ${v.taskTitle}`,
        `Trigger: ${v.trigger || '—'}; due: ${v.taskDue || '—'}; frequency: ${v.frequency || '—'}`,
        r.workflows.length ? `${r.workflows.map((w) => `${w.name} (${w.id}, ${w.status})`).join('; ')} — ${r.workflows.map((w) => w.scheduleText).join('; ')}; title ${r.hubspotTitles.map((t) => `"${t}"`).join(' / ') || '—'}; assigned to ${r.assignees.join(' / ') || '—'}` : '—',
        diffs.join(' • ') || 'None',
        r.result,
      ];
    })));
    if (parsedDoc && parsedDoc.documentIssues.length) {
      out.push('\n**Issues within the spreadsheet itself** (DOCUMENTED)\n');
      out.push(parsedDoc.documentIssues.map((i) => `- ${i.severity}: ${i.message} ${i.spellings ? i.spellings.map((s) => `"${s}"`).join(' / ') : i.titles ? i.titles.map((s) => `"${s}"`).join(' / ') : i.rows ? `rows ${i.rows.join(', ')}` : ''}`).join('\n'));
      const rowIssues = parsedDoc.tasks.filter((t) => t.issues.some((i) => i.severity !== 'INFO'));
      out.push(rowIssues.map((t) => `- Row ${t.rowNumber} (${t.values.role} — ${t.values.taskTitle}): ${t.issues.filter((i) => i.severity !== 'INFO').map((i) => i.message).join(' ')}`).join('\n'));
    }
  }

  // 7
  h('7. Missing / Additional Workflows');
  out.push('**In the spreadsheet but not found in HubSpot**\n');
  const notFound = rows.filter((r) => r.result === 'NOT_IN_HUBSPOT' || r.titleMatch === 'NOT_RETRIEVED');
  out.push(notFound.length ? table(['Row', 'Role', 'Task title', 'Why'], notFound.map((r) => [r.rowNumber, r.values.role, r.values.taskTitle, r.notes.join(' ')])) : 'None.');
  out.push('\n**In the folder but not referenced by any spreadsheet row**\n');
  out.push(undocumentedWorkflows.length ? table(['Workflow', 'ID', 'Status', 'Tasks it creates'], undocumentedWorkflows.map((r) => [r.name, r.id, r.status, [...new Set(r.createdTasks.map((t) => t.title.trim() || '(no title)'))].join(' / ')])) : 'None.');
  out.push('\n**Folder workflows that could not be read** (REVIEW)\n');
  out.push(table(['Workflow', 'ID', 'Object', 'Reason'], unavailable.map((u) => [u.name, u.id || '—', u.objectType || '—', u.reason])));
  if (comparison) {
    out.push('\n**HubSpot task paths with no matching spreadsheet row** (grouped)\n');
    const groups = new Map();
    for (const u of comparison.undocumented) {
      const k = `${u.workflowId}|${u.title}|${u.reason}`;
      if (!groups.has(k)) groups.set(k, { ...u, combos: [] });
      groups.get(k).combos.push(`${u.tiers.length > 3 ? 'any tier' : u.tiers.join('/')} ${u.role === 'NAMED' ? u.assignee.replace('Specific user: ', '') : u.role}${u.soa === 'SOA only' ? ' (SOA)' : ''}`);
    }
    out.push(table(['Workflow', 'Status', 'Task title', 'Tier / role', 'Reason'], [...groups.values()].map((g) => [`${g.workflowName} (${g.workflowId})`, g.status, g.title || '(no title)', [...new Set(g.combos)].join(', '), g.reason])));
  }

  // 8
  h('8. Notable Configuration Differences');
  const notes = [];
  for (const r of records) {
    const c = descriptionConflicts(r);
    if (c.length) notes.push(`**${r.name}** — the HubSpot description ${c.join(' and ')}, but the workflow actually runs ${r.schedule.plainEnglish}. The description looks out of date. (DIFFERENCE within HubSpot)`);
  }
  const soaPrefixes = new Map();
  for (const r of records) for (const a of r.raw.actions || []) for (const b of a.listBranches || []) for (const f of F.andGroups(b.filterBranch).flat()) {
    if (f.property === 'name' && F.filterOperator(f) === 'STARTS_WITH') soaPrefixes.set(f.operation.values[0], (soaPrefixes.get(f.operation.values[0]) || []).concat(r.name));
  }
  if (soaPrefixes.size > 1) notes.push(`The SOA branch tests the company name differently across workflows: ${[...soaPrefixes.entries()].map(([p, n]) => `starts with "${p}" (${new Set(n).size} workflows)`).join('; ')}. (FACT)`);
  for (const s of suppression) for (const sh of s.shadowedBranches.filter((x) => /SOA/i.test(x.branch))) notes.push(`**${s.workflowName}** — the "${sh.branch}" branch overlaps the earlier ${sh.earlier.map((e) => `"${e}"`).join(', ')} branch(es), which don't exclude SOA names; SOA companies in those tiers go down the tier branch instead. (FACT)`);
  const variants = [...titleWorkflows.values()];
  const spellings = new Map();
  for (const r of records) for (const t of r.createdTasks) {
    const k = t.title.trim().toLowerCase().replace(/r\s*\+\s*s\s*[-:]?\s*/g, 'r+s ').replace(/\s+/g, ' ');
    if (!spellings.has(k)) spellings.set(k, new Set());
    spellings.get(k).add(t.title);
  }
  for (const [, set] of spellings) if (set.size > 1) notes.push(`One task title is spelled ${set.size} ways in HubSpot: ${[...set].map((t) => `"${t.replace(/\n/g, '⏎')}"`).join(', ')}. Reports that filter on the exact title will miss some. (FACT)`);
  const trailing = records.flatMap((r) => r.createdTasks.filter((t) => /\s$/.test(t.title)).map((t) => `"${r.name}" action ${t.actionId}`));
  if (trailing.length) notes.push(`Task titles ending in a line break or space: ${trailing.join('; ')}. (FACT)`);
  for (const r of records) {
    const ex = F.negativeFilters(r.raw.enrollmentCriteria && r.raw.enrollmentCriteria.listFilterBranch).filter((f) => f.property === 'name');
    for (const f of ex) notes.push(`**${r.name}** — enrolment hard-codes an exclusion for one company: ${F.describeFilter(f, { properties: audit.properties })}. (FACT)`);
  }
  const unguarded = suppression.filter((s) => s.unguardedAssignments.length);
  if (unguarded.length) notes.push(`${unguarded.length} workflows assign Tier 2 - L2 / Tier 3 tasks from the Site Manager property without checking it is set; when it is blank HubSpot creates the task unassigned. (FACT/REVIEW)`);
  const reEnrolOff = records.filter((r) => !r.reEnrollment.enabled);
  if (reEnrolOff.length) notes.push(`Re-enrolment is OFF in: ${reEnrolOff.map((r) => `"${r.name}"`).join(', ')}. (FACT)`);
  notes.push(`Every task is due a set number of days after creation at 08:00 and only on weekdays (HubSpot moves weekend due dates). The spreadsheet gives due periods in days or weeks without this detail. (FACT)`);
  out.push(notes.map((n) => `- ${n}`).join('\n'));

  // 9
  h('9. Items Requiring Human Review');
  for (const u of unavailable) reviewItems.push([`${u.name}${u.id ? ` (${u.id})` : ''}`, `${u.reason}${u.id ? ` Spreadsheet rows ${rows.filter((r) => r.linkedWorkflowId === u.id).map((r) => r.rowNumber).join(', ')} link to it and could not be checked.` : ''}`]);
  if (list4291) reviewItems.push([`Suppression list ${list4291.listId} "${list4291.name}"`, `Confirm it should suppress every Ops task workflow, given it is defined only by ${list4291.criteria}.`]);
  if (omFirst.length) reviewItems.push(['OM-before-SM branch order', `${omFirst.length} branch steps give the task to the OM only when both are set. Confirm whether "OM + SM" in the spreadsheet means both should get it.`]);
  for (const e of emptyOm) reviewItems.push([`${e.wf.workflowName} › ${e.branch}${e.off ? ' (workflow OFF)' : ''}`, 'Empty OM branch: facilities with an OM get no task, and their SM gets none either because the SM branch comes second.']);
  reviewItems.push(['Tier "N/A" / blank and no OM/SM', 'No workflow has an "otherwise" path, so these companies never get tasks. Confirm that is intended.']);
  if (soaStrict.length) reviewItems.push(['SOA name matching', `${soaStrict.length} workflows: names containing "SOA" that don't start with the SOA prefix get no task.`]);
  for (const r of records) for (const i of r.issues.filter((x) => ['EMPTY_TASK_TITLE', 'UNKNOWN_ASSIGNEE', 'UNREACHABLE_ACTION', 'DANGLING_ACTION', 'ACTION_LOOP'].includes(x.code))) reviewItems.push([`${r.name} (${r.id})`, i.message]);
  for (const r of rows.filter((x) => x.result === 'REVIEW' && x.titleMatch !== 'NOT_RETRIEVED')) reviewItems.push([`Spreadsheet row ${r.rowNumber} (${r.values.role} — ${r.values.taskTitle})`, reviewReasons(r)]);
  for (const r of rows) for (const n of r.notes.filter((x) => /different HubSpot task/.test(x))) reviewItems.push([`Spreadsheet row ${r.rowNumber} (${r.values.role} — ${r.values.taskTitle})`, n]);
  out.push(table(['Item', 'What needs confirming'], reviewItems));

  out.push('\n## Audit record\n');
  out.push(table(['Field', 'Value'], [
    ['Audit date/time', meta.auditedAt],
    ['HubSpot data fetched', meta.fetchedAt],
    ['Portal ID', meta.portalId],
    ['Folder audited', meta.folderName],
    ['Workflows discovered (names supplied)', meta.namesInScope],
    ['Workflows in account (v4 list)', meta.workflowsInAccount],
    ['Successfully analysed', records.length],
    ['Partially analysed', 0],
    ['Requiring manual review', unavailable.length],
    ['API errors', meta.apiErrors.map((e) => `${e.context}: ${e.status || ''} ${e.message}`).join('; ') || 'None'],
    ['Missing configuration fields', 'Folder membership, last published/activated date and goals are not returned by the v4 API.'],
  ]));
  return out.join('\n') + '\n';
}

module.exports = { buildReport, descriptionConflicts };
