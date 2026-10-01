'use strict';

/**
 * Writes the updated WLS spreadsheet: the original sheet with its 8 columns
 * left exactly as they were (values, links, formatting), audit columns added
 * to the right, and supporting sheets for HubSpot-only tasks, workflows,
 * suppression and review items.
 */

const ExcelJS = require('exceljs');

const AUDIT_COLUMNS = [
  ['Audit: Result', 18],
  ['Audit: HubSpot workflow(s)', 40],
  ['Audit: Workflow status', 12],
  ['Audit: HubSpot task title', 34],
  ['Audit: Tier / role / SOA coverage', 60],
  ['Audit: Assigned to (HubSpot)', 34],
  ['Audit: Trigger vs schedule', 40],
  ['Audit: Frequency', 34],
  ['Audit: Due date', 34],
  ['Audit: Task details', 30],
  ['Audit: Suppression / exclusions', 50],
  ['Audit: Notes / review', 70],
];

const FILL = {
  MATCH: 'FFD9EAD3',
  DIFFERENCE: 'FFFCE5CD',
  REVIEW: 'FFFFF2CC',
  NOT_IN_HUBSPOT: 'FFF4CCCC',
  NOT_IN_HUBSPOT_FOR_ROLE: 'FFF4CCCC',
};
const HEADER_FILL = 'FF434343';

function styleHeader(cell) {
  cell.font = { bold: true, color: { argb: 'FFFFFFFF' } };
  cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: HEADER_FILL } };
  cell.alignment = { wrapText: true, vertical: 'top' };
}

function addTableSheet(workbook, name, headers, rows) {
  const ws = workbook.addWorksheet(name);
  ws.columns = headers.map(([header, width]) => ({ header, width }));
  ws.getRow(1).eachCell(styleHeader);
  for (const r of rows) {
    const row = ws.addRow(r);
    row.alignment = { wrapText: true, vertical: 'top' };
  }
  ws.views = [{ state: 'frozen', ySplit: 1 }];
  ws.autoFilter = { from: { row: 1, column: 1 }, to: { row: 1, column: headers.length } };
  return ws;
}

async function writeAuditedSpreadsheet({ sourcePath, targetPath, audit }) {
  const workbook = new ExcelJS.Workbook();
  await workbook.xlsx.readFile(sourcePath);
  const ws = workbook.worksheets[0];
  const { headerRow } = audit.parsedDoc.source;
  const firstAuditCol = 9; // after the 8 original columns (A–H)

  AUDIT_COLUMNS.forEach(([title, width], i) => {
    const col = ws.getColumn(firstAuditCol + i);
    col.width = width;
    const cell = ws.getRow(headerRow).getCell(firstAuditCol + i);
    cell.value = title;
    styleHeader(cell);
  });

  const byRow = new Map(audit.comparison.rows.map((r) => [r.rowNumber, r]));
  for (const [rowNumber, r] of byRow) {
    const row = ws.getRow(rowNumber);
    const coverage = r.combos.map((c) => `${c.status === 'FOUND' ? '✔' : c.status === 'CONDITIONAL' ? '◐' : c.status === 'EXTRA' ? '+' : c.status === 'WORKFLOW_OFF' ? '○' : '✘'} ${c.text}`).join('\n');
    const fmt = (x) => (x ? `${x.status}: ${x.text}` : '');
    const values = [
      r.result,
      r.workflows.map((w) => `${w.name} (${w.id})`).join('\n') || (r.linkedWorkflowId ? `Linked ${r.linkedWorkflowId} (not readable)` : '—'),
      [...new Set(r.workflows.map((w) => w.status))].join(' / ') || '—',
      r.hubspotTitles.join('\n') || '—',
      coverage || '—',
      r.assignees.join('\n') || '—',
      fmt(r.trigger),
      fmt(r.frequency),
      fmt(r.due),
      fmt(r.details),
      r.suppression || '—',
      r.notes.join('\n') || '',
    ];
    values.forEach((v, i) => {
      const cell = row.getCell(firstAuditCol + i);
      cell.value = v;
      cell.alignment = { wrapText: true, vertical: 'top' };
    });
    const fill = FILL[r.result];
    if (fill) row.getCell(firstAuditCol).fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: fill } };
    row.getCell(firstAuditCol).font = { bold: true };
  }

  // Supporting sheets.
  addTableSheet(
    workbook,
    'Audit - HubSpot only tasks',
    [['Workflow', 40], ['Workflow ID', 14], ['Status', 8], ['Action', 8], ['Task title', 40], ['Assigned to', 34], ['Tier(s)', 30], ['SOA', 10], ['Branch path', 40], ['Reason', 40]],
    (audit.comparison.undocumented || []).map((u) => [u.workflowName, u.workflowId, u.status, u.actionId, u.title || '(no title)', u.assignee, u.tierConstrained ? u.tiers.join(', ') : 'Any tier', u.soa, u.path, u.reason])
  );
  addTableSheet(
    workbook,
    'Audit - Workflows',
    [['Workflow', 44], ['ID', 14], ['Status', 8], ['Schedule', 30], ['Enrolment', 60], ['Re-enrolment', 40], ['Unenrolment', 40], ['Suppression', 40], ['Branch steps', 10], ['No "otherwise"', 12], ['Tasks', 8], ['Last updated', 12], ['Issues', 60]],
    [
      ...audit.records.map((r) => [r.name, r.id, r.status, r.schedule.plainEnglish, r.enrollment.plainEnglish, r.reEnrollment.plainEnglish, r.unenrollment.plainEnglish, r.suppression.plainEnglish, r.actions.branches.length, r.actions.branches.filter((b) => !b.hasOtherwise).length, r.createdTasks.length, String(r.updatedAt || '').slice(0, 10), r.issues.map((i) => i.message).join('\n')]),
      ...audit.unavailable.map((u) => [u.name, u.id || '—', '—', '—', '—', '—', '—', '—', '—', '—', '—', '—', `NOT RETRIEVED — REVIEW: ${u.reason}`]),
    ]
  );
  addTableSheet(
    workbook,
    'Audit - Suppression',
    [['Workflow', 44], ['ID', 14], ['Suppression / exclusion (plain English)', 120]],
    audit.suppression.flatMap((s) => s.plainEnglish.map((p, i) => [i === 0 ? s.workflowName : '', i === 0 ? s.workflowId : '', p]))
  );
  addTableSheet(
    workbook,
    'Audit - Review items',
    [['Item', 50], ['What needs confirming', 110]],
    [
      ...audit.unavailable.map((u) => [`${u.name}${u.id ? ` (${u.id})` : ''}`, u.reason]),
      ...audit.records.flatMap((r) => r.issues.filter((i) => !['EMPTY_BRANCH'].includes(i.code)).map((i) => [`${r.name} (${r.id})`, i.message])),
      ...audit.comparison.rows.filter((r) => r.result === 'REVIEW').map((r) => [`Row ${r.rowNumber}: ${r.values.role} — ${r.values.taskTitle}`, r.notes.join('\n')]),
    ]
  );
  await workbook.xlsx.writeFile(targetPath);
  return { auditColumns: AUDIT_COLUMNS.map(([t]) => t) };
}

module.exports = { writeAuditedSpreadsheet, AUDIT_COLUMNS };
