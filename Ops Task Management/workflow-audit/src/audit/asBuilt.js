'use strict';

/**
 * Writes an "as built" version of the WLS task spreadsheet: the same 8
 * columns and formatting as the team's document, but every row describes
 * what HubSpot actually does today. Two columns are added at the end
 * (HubSpot workflow, Notes). A second sheet lists every workflow in the
 * folder in plain words.
 *
 * Location Type is not stored in HubSpot; it is copied from the matching
 * spreadsheet row when there is one.
 */

const ExcelJS = require('exceljs');
const { titleMatch } = require('./compare');
const F = require('./filters');

const COLUMNS = ['Role', 'Tier', 'Location Type', 'Task Title', 'Task Details', 'Trigger', 'Task Due', 'Frequency'];
const EXTRA = [['HubSpot workflow', 40], ['Notes', 60]];
const TIER_ORDER = ['Enterprise', 'TIER 1', 'TIER 2', 'Tier 2 - L2', 'TIER 3', 'ALL'];
const TIER_CODE = { Enterprise: 'Ent', 'TIER 1': 'T1', 'TIER 2': 'T2.1', 'Tier 2 - L2': 'T2.2', 'TIER 3': 'T3' };
const TIER_NAME = { Enterprise: 'Enterprise', 'TIER 1': 'Tier 1', 'TIER 2': 'Tier 2.1', 'Tier 2 - L2': 'Tier 2.2', 'TIER 3': 'Tier 3' };
// Soft fills, one per task group, repeated in order.
const GROUP_FILLS = ['FFDDEBF7', 'FFE2EFDA', 'FFFFF2CC', 'FFFCE4D6', 'FFEDE2F6', 'FFD9F0EE', 'FFF8E1EC', 'FFEDEDED'];
const DAY = { MONDAY: 'Mondays', TUESDAY: 'Tuesdays', WEDNESDAY: 'Wednesdays', THURSDAY: 'Thursdays', FRIDAY: 'Fridays', SATURDAY: 'Saturdays', SUNDAY: 'Sundays' };
const ordinal = (n) => `${n}${n % 10 === 1 && n !== 11 ? 'st' : n % 10 === 2 && n !== 12 ? 'nd' : n % 10 === 3 && n !== 13 ? 'rd' : 'th'}`;
const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;

// "Customer Tier (customer_tier) is any of" → "Customer Tier is any of"
const plain = (text) => String(text || '').replace(/ \([a-z0-9_]+\)/g, '').replace(/\bstreet_rate_management\b/g, 'Street Rate Management').replace(/\bis any of\b/g, 'is').replace(/"/g, '');

function triggerText(record, delayDays, properties = {}) {
  const s = record.schedule.enrollmentSchedule;
  let base;
  if (!s) base = `When a facility meets: ${plain(F.describeTree(record.enrollment.filters, { properties, lists: {} }))}`;
  else if (s.type === 'MONTHLY_SPECIFIC_DAYS') base = `${s.daysOfMonth.map(ordinal).join(' and ')} of the Month`;
  else if (s.type === 'WEEKLY') base = s.daysOfWeek.map((d) => DAY[d] || d).join(', ');
  else base = record.schedule.plainEnglish;
  return delayDays ? `${base}, then again ${plural(delayDays, 'day')} later` : base;
}

function frequencyText(record) {
  const s = record.schedule.enrollmentSchedule;
  if (!record.reEnrollment.enabled) return 'Once only (per facility)';
  if (!s) return 'Each time it is triggered';
  if (s.type === 'WEEKLY') return s.daysOfWeek.length > 1 ? `${s.daysOfWeek.length} times a week` : 'Weekly';
  if (s.type === 'MONTHLY_SPECIFIC_DAYS') return s.daysOfMonth.length === 2 ? 'Twice a month' : s.daysOfMonth.length > 2 ? `${s.daysOfMonth.length} times a month` : 'Monthly';
  return record.schedule.plainEnglish;
}

function roleText(task, tierKey) {
  const prefix = tierKey === 'ALL' ? (task.soa === 'SOA only' ? 'SOA' : 'All') : TIER_CODE[tierKey] || tierKey;
  const who = task.role === 'NAMED' ? (task.assignee.ownerResolved ? task.assignee.text.replace(/^Specific user: /, '') : `inactive user (ID ${task.assignee.ownerId})`) : task.role || '?';
  const soaSuffix = task.soa === 'SOA only' && tierKey !== 'ALL' ? '-SOA' : '';
  return { prefix, who, soaSuffix };
}

// One row per (workflow, title, tier, SOA, delay); roles on that row are joined.
function buildRows(audit) {
  const docTasks = audit.parsedDoc ? audit.parsedDoc.tasks : [];
  const groups = new Map();
  for (const r of audit.records) {
    for (const t of r.createdTasks) {
      const tierKeys = t.tierConstrained && t.tiers.length < audit.allTiers.length ? t.tiers.filter((x) => TIER_ORDER.includes(x)) : ['ALL'];
      for (const tierKey of tierKeys) {
        const key = [r.id, t.title.trim().toLowerCase(), tierKey, t.soa, t.delayBeforeDays].join('|');
        if (!groups.has(key)) groups.set(key, { record: r, tierKey, tasks: [] });
        groups.get(key).tasks.push(t);
      }
    }
  }

  const rows = [];
  for (const g of groups.values()) {
    const first = g.tasks[0];
    const { prefix, soaSuffix } = roleText(first, g.tierKey);
    const roles = [];
    const notes = [];
    for (const t of g.tasks) {
      const { who } = roleText(t, g.tierKey);
      const onlyIfNoOm = t.role === 'SM' && t.path.some((p) => p.notEarlier.some((n) => /\bOM\b/i.test(n)));
      roles.push(onlyIfNoOm ? 'SM if no OM' : who);
      if (t.assignee.role === 'NAMED' && !t.assignee.ownerResolved) notes.push('Assigned to a user who is no longer active in HubSpot.');
      if (t.assignee.property && !t.path.some((p) => /\bis known\b/.test(p.criteria) && p.criteria.includes(`(${t.assignee.property})`))) {
        notes.push(`If the ${t.role} field is blank, the task has no owner.`);
      }
    }
    const order = { OM: 0, SM: 1, 'SM if no OM': 1 };
    const uniqueRoles = [...new Set(roles)].sort((a, b) => (order[a] ?? 2) - (order[b] ?? 2));
    const named = uniqueRoles.some((x) => !['OM', 'SM', 'SM if no OM'].includes(x));
    let roleWords = uniqueRoles.join(' + ');
    if (uniqueRoles.length === 2 && uniqueRoles[0] === 'OM' && uniqueRoles[1] === 'SM if no OM') roleWords = 'OM (SM if no OM)';
    else if (uniqueRoles.length === 1 && uniqueRoles[0] === 'SM if no OM') {
      roleWords = 'SM (only if no OM)';
      notes.push('Facilities that have an OM get no task here: the OM step in this workflow is empty.');
    }
    const role = named ? `${prefix}${soaSuffix} – ${roleWords}` : `${prefix}-${roleWords}${soaSuffix}`;
    const tier = g.tierKey === 'ALL' ? (first.soa === 'SOA only' ? 'All tiers (SOA facilities)' : 'All tiers') : TIER_NAME[g.tierKey] || g.tierKey;
    const docMatch = docTasks.find((d) => titleMatch(d.values.taskTitle, first.title));
    if (g.record.status === 'OFF') notes.unshift('Workflow is turned OFF, so this task is not being created.');
    if (!first.title.trim()) notes.unshift('Task has no title.');
    rows.push({
      record: g.record,
      tierKey: g.tierKey,
      title: first.title.trim(),
      docIndex: docMatch ? docTasks.indexOf(docMatch) : Infinity,
      values: [
        role,
        tier,
        docMatch ? docMatch.values.locationType : '',
        first.title.trim() || '(no title)',
        first.details || '(no details)',
        triggerText(g.record, first.delayBeforeDays, audit.properties),
        first.dueDays === null ? 'No due date' : plural(first.dueDays, 'Day'),
        frequencyText(g.record),
      ],
      notes: [...new Set(notes)],
    });
  }

  // Group rows by task: one group per workflow, and two workflows share a
  // group when they create the same task for different tiers (e.g. one for
  // Ent/T1/T2.1 and one for T2.2/T3). Groups follow the order of the team's
  // document; inside a group rows go by tier.
  const byWorkflow = new Map();
  for (const r of rows) {
    if (!byWorkflow.has(r.record.id)) byWorkflow.set(r.record.id, { ids: [r.record.id], rows: [], docIndex: Infinity, name: r.record.name });
    const g = byWorkflow.get(r.record.id);
    g.rows.push(r);
    g.docIndex = Math.min(g.docIndex, r.docIndex);
  }
  const taskGroups = [];
  for (const g of byWorkflow.values()) {
    const tiers = new Set(g.rows.map((r) => r.tierKey));
    const partner = taskGroups.find(
      (x) =>
        x.rows.some((a) => g.rows.some((b) => a.title && b.title && titleMatch(a.title, b.title))) &&
        !x.rows.some((a) => a.tierKey !== 'ALL' && tiers.has(a.tierKey))
    );
    if (partner) {
      partner.rows.push(...g.rows);
      partner.docIndex = Math.min(partner.docIndex, g.docIndex);
    } else taskGroups.push(g);
  }
  taskGroups.sort((a, b) => a.docIndex - b.docIndex || a.name.localeCompare(b.name)).forEach((g, i) => {
    g.order = i;
    for (const r of g.rows) r.group = g;
  });
  rows.sort(
    (a, b) =>
      a.group.order - b.group.order ||
      TIER_ORDER.indexOf(a.tierKey) - TIER_ORDER.indexOf(b.tierKey) ||
      a.record.name.localeCompare(b.record.name) ||
      a.values[5].length - b.values[5].length
  );
  // Say so when the same task is also created for this tier by another workflow.
  for (const r of rows) {
    const others = rows.filter((x) => x.record.id !== r.record.id && x.tierKey === r.tierKey && x.title && r.title && titleMatch(x.title, r.title));
    const names = [...new Set(others.map((x) => x.record.name))];
    if (names.length) r.notes.push(`This tier also gets a task with this name from: ${names.join('; ')}.`);
  }
  return rows;
}

function leftOut(record, suppression) {
  const out = [];
  for (const l of suppression.suppressionLists) out.push(`Facilities on the "${l.name || `list ${l.listId}`}" list${l.criteria ? ` (${plain(l.criteria)})` : ''}`);
  for (const e of suppression.enrollmentExclusions) out.push(plain(e).replace(/\.$/, ''));
  const topTier = suppression.noOtherwise.find((n) => n.at === '(start)');
  if (topTier && record.actions.branches.length) out.push('Facilities with Customer Tier N/A or blank');
  for (const e of suppression.emptyBranches) out.push(`${e.at === '(start)' ? '' : `${e.at} › `}${e.branch}: no task`);
  return out;
}

function copyStyle(from) {
  return JSON.parse(JSON.stringify(from || {}));
}

async function writeAsBuilt({ sourcePath, targetPath, audit }) {
  const src = new ExcelJS.Workbook();
  await src.xlsx.readFile(sourcePath);
  const ss = src.worksheets[0];
  const headerStyle = (c) => copyStyle(ss.getRow(1).getCell(c).style);
  const dataStyle = (c) => copyStyle(ss.getRow(2).getCell(c).style);
  const divider = ss.getRow((audit.parsedDoc.sections[0] || {}).startsAtRow || 2).getCell(1).style;

  const wb = new ExcelJS.Workbook();
  const ws = wb.addWorksheet('As built in HubSpot');
  const widths = [14, 14, 14, 30, 106, 26, 12, 17];
  COLUMNS.forEach((_, i) => (ws.getColumn(i + 1).width = ss.getColumn(i + 1).width || widths[i]));
  EXTRA.forEach(([, w], i) => (ws.getColumn(9 + i).width = w));

  const header = ws.getRow(1);
  [...COLUMNS, ...EXTRA.map(([t]) => t)].forEach((title, i) => {
    const cell = header.getCell(i + 1);
    cell.value = title;
    cell.style = headerStyle(Math.min(i + 1, 8));
  });
  ws.views = [{ state: 'frozen', ySplit: 1 }];

  const portalId = audit.meta.portalId;
  const link = (id) => `https://app.hubspot.com/workflows/${portalId}/platform/flow/${id}/edit`;
  const addDivider = (text) => {
    const row = ws.addRow([text]);
    ws.mergeCells(row.number, 1, row.number, COLUMNS.length + EXTRA.length);
    row.getCell(1).style = copyStyle(divider);
  };
  const addRow = (values, workflowCell, notes, url, fill) => {
    const row = ws.addRow([...values, workflowCell, notes]);
    for (let c = 1; c <= COLUMNS.length + EXTRA.length; c++) {
      const style = dataStyle(Math.min(c, 8));
      if (c !== 4 && style.font) delete style.font.underline;
      style.alignment = { ...(style.alignment || {}), wrapText: true, vertical: 'top' };
      if (fill) style.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: fill }, bgColor: { argb: fill } };
      row.getCell(c).style = style;
    }
    if (url) row.getCell(4).value = { text: values[3], hyperlink: url };
  };

  const rows = buildRows(audit);
  const documented = rows.filter((r) => r.group.docIndex !== Infinity);
  const extra = rows.filter((r) => r.group.docIndex === Infinity);
  const fillFor = (r) => GROUP_FILLS[r.group.order % GROUP_FILLS.length];
  for (const r of documented) addRow(r.values, `${r.record.name} (${r.record.status})`, r.notes.join('\n'), link(r.record.id), fillFor(r));
  if (extra.length) {
    addDivider('In HubSpot but not in the current spreadsheet');
    for (const r of extra) addRow(r.values, `${r.record.name} (${r.record.status})`, r.notes.join('\n'), link(r.record.id), fillFor(r));
  }
  if (audit.unavailable.length) {
    addDivider('Could not be read from HubSpot: check these manually');
    for (const u of audit.unavailable) {
      const docRows = audit.parsedDoc.tasks.filter((t) => t.workflowLink && t.workflowLink.workflowId === u.id);
      const note = `HubSpot did not return this workflow's settings, so these rows are copied from the current spreadsheet and not confirmed.`;
      if (docRows.length) for (const d of docRows) addRow(COLUMNS.map((_, i) => Object.values(d.values)[i]), `${u.name} (not readable)`, note, u.id ? link(u.id) : null);
      else addRow(['', '', '', u.name.replace(/^Create Tasks \| /, ''), '', '', '', ''], `${u.name} (not readable)`, 'Not listed by HubSpot at all; nothing to compare. Check it in HubSpot.', null);
    }
  }

  // Sheet 2: the workflows in the folder, in plain words.
  const wf = wb.addWorksheet('Workflows in the folder');
  const wfCols = [['Workflow', 44], ['On / Off', 9], ['Runs', 26], ['Facilities it includes', 50], ['Facilities it leaves out', 60], ['Tasks it creates', 44]];
  wfCols.forEach(([, w], i) => (wf.getColumn(i + 1).width = w));
  const wh = wf.getRow(1);
  wfCols.forEach(([t], i) => {
    wh.getCell(i + 1).value = t;
    wh.getCell(i + 1).style = headerStyle(1);
  });
  wf.views = [{ state: 'frozen', ySplit: 1 }];
  const supById = new Map(audit.suppression.map((s) => [s.workflowId, s]));
  for (const r of audit.records) {
    const includes = plain(F.describeTree(r.enrollment.filters, { properties: audit.properties, lists: audit.lists }));
    const row = wf.addRow([
      { text: r.name, hyperlink: link(r.id) },
      r.status,
      `${triggerText(r, 0, audit.properties)} (${frequencyText(r).toLowerCase()})`,
      includes,
      leftOut(r, supById.get(r.id)).join('\n'),
      [...new Set(r.createdTasks.map((t) => t.title.trim() || '(no title)'))].join('\n'),
    ]);
    for (let c = 1; c <= wfCols.length; c++) {
      const style = dataStyle(c === 1 ? 4 : 2);
      if (c !== 1 && style.font) delete style.font.underline;
      style.alignment = { wrapText: true, vertical: 'top' };
      row.getCell(c).style = style;
    }
  }
  for (const u of audit.unavailable) {
    const row = wf.addRow([u.name, '?', '?', '?', '?', 'Could not be read from HubSpot. Check manually.']);
    for (let c = 1; c <= wfCols.length; c++) {
      const style = dataStyle(2);
      style.alignment = { wrapText: true, vertical: 'top' };
      row.getCell(c).style = style;
    }
  }

  // Sheet 3: how to read it.
  const help = wb.addWorksheet('How to read this');
  help.getColumn(1).width = 110;
  const lines = [
    'What this is',
    `Every row on the first sheet is a task HubSpot actually creates today, taken from the ${audit.records.length} workflows in "${audit.meta.folderName}" (read on ${String(audit.meta.fetchedAt).slice(0, 10)}). Nothing in HubSpot was changed.`,
    'The first 8 columns match the current Phase 3 Task Management spreadsheet. Task Title links to the workflow in HubSpot.',
    '',
    'Role',
    'Tier code, then who gets the task: Ent = Enterprise, T1 = Tier 1, T2.1 = Tier 2.1 (HubSpot: "Tier 2 - L1"), T2.2 = Tier 2.2 (HubSpot: "Tier 2 - L2"), T3 = Tier 3, SOA = SOA facilities (any tier).',
    'Rows for the same task are grouped together and share a colour, so you can see which tiers get it.',
    'OM = Operations Manager, SM = Site Manager. "SM (only if no OM)" means HubSpot gives the task to the OM when there is one, and to the SM only when the OM field is blank.',
    '',
    'Location Type',
    'HubSpot does not store this. It is copied from the current spreadsheet where the same task exists, and left blank otherwise.',
    '',
    'Trigger, Task Due and Frequency',
    'Trigger is the day HubSpot creates the task. Task Due is the number of days until it is due; HubSpot sets the due time to 08:00 and only on a weekday.',
    '',
    'Who never gets tasks',
    'Every workflow leaves out facilities on the "Exclude from Ops tasks" list and facilities with Customer Tier N/A or blank. The "Workflows in the folder" sheet lists what each workflow includes and leaves out.',
  ];
  const HEADINGS = ['What this is', 'Role', 'Location Type', 'Trigger, Task Due and Frequency', 'Who never gets tasks'];
  for (const text of lines) {
    const row = help.addRow([text]);
    row.getCell(1).alignment = { wrapText: true, vertical: 'top' };
    if (HEADINGS.includes(text)) {
      row.getCell(1).style = headerStyle(1);
    }
  }

  await wb.xlsx.writeFile(targetPath);
  return { rows: rows.length, documented: documented.length, extra: extra.length };
}

module.exports = { writeAsBuilt, buildRows };
