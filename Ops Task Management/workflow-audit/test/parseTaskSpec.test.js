'use strict';

const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const ExcelJS = require('exceljs');
const { parseTaskSpec, normalizeTitle, parseRole } = require('../src/docs/parseTaskSpec');

// Synthetic rows only: the real WLS document is never committed.
const HEADER = ['Role', 'Tier', 'Location Type', 'Task Title', 'Task Details', 'Trigger', 'Task Due', 'Frequency'];
const ROWS = [
  ['T1-OM', 'Tier 1', 'Remote', 'R+S - Status Call', '1. Prepare agenda', '10th of the Month', '5 Days', 'Monthly'],
  ['T2-OM + SM', 'Tier 2', 'Remote', 'R + S - Status Call', '1. Prepare agenda', '10th of the Month', '5 Days', 'Monthly'],
  ['T3-SM', 'Tier 3', 'Remote', 'R+S - Staus Call', '1. Prepare agenda', '10th of the Month', '5 Days', 'Monthly'],
  ['T1-OM', 'Tier 1', 'Remote', 'Shifted Task', 'Details', '', 'Score Under 6', '5 days'],
  ['T1-SM-SOA', 'Tier 1', 'Remote', 'Walk Through Monthly', '', '1st of the month', '1 days', 'Weekly'],
  ['Add in'],
  ['T1-OM', 'Tier 1', 'Remote', 'Weekly Call', 'Schedule the call', 'Monday', '2 days', 'Weekly'],
  ['T1-OM', 'Tier 1', 'Remote', 'Weekly Call', 'Share KPI updates', 'Monday', '2 days', 'Weekly'],
  ['T2-OM', 'Tier 3', '', 'Mismatch Task', 'Details', 'Monday', '2 days', 'Weekly'],
];

async function writeFixture() {
  const workbook = new ExcelJS.Workbook();
  const sheet = workbook.addWorksheet('Sheet1');
  sheet.addRow(HEADER);
  for (const row of ROWS) sheet.addRow(row);
  sheet.mergeCells('A7:H7');
  sheet.getCell('D2').value = {
    text: { richText: [{ text: 'R+S - ' }, { text: 'Status Call' }] },
    hyperlink: 'https://app.hubspot.com/workflows/111/platform/flow/222/edit/actions/1/list-branch',
  };
  const file = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'taskspec-')), 'fixture.xlsx');
  await workbook.xlsx.writeFile(file);
  return file;
}

const codes = (task) => task.issues.map((i) => i.code);

test('parses rows, roles and section dividers', async () => {
  const parsed = await parseTaskSpec(await writeFixture());
  assert.strictEqual(parsed.summary.taskRows, 8);
  assert.deepStrictEqual(parsed.missingColumns, []);
  assert.deepStrictEqual(parsed.sections.map((s) => s.label), ['Add in']);
  const afterDivider = parsed.tasks.filter((t) => t.section === 'Add in');
  assert.strictEqual(afterDivider.length, 3);
  assert.deepStrictEqual(parsed.tasks[1].role.roles, ['Operations Manager', 'Site Manager']);
});

test('flags shifted columns without rewriting the original values', async () => {
  const parsed = await parseTaskSpec(await writeFixture());
  const shifted = parsed.tasks.find((t) => t.values.taskTitle === 'Shifted Task');
  assert.ok(codes(shifted).includes('COLUMN_SHIFT'));
  assert.strictEqual(shifted.values.taskDue, 'Score Under 6');
  assert.deepStrictEqual(shifted.interpreted, { trigger: 'Score Under 6', taskDue: '5 days', frequency: '' });
  assert.ok(codes(shifted).includes('MISSING_FREQUENCY'));
});

test('flags missing fields, trigger/frequency and role/tier mismatches', async () => {
  const parsed = await parseTaskSpec(await writeFixture());
  const soa = parsed.tasks.find((t) => t.values.taskTitle === 'Walk Through Monthly');
  assert.ok(codes(soa).includes('MISSING_TASK_DETAILS'));
  assert.ok(codes(soa).includes('TRIGGER_FREQUENCY_MISMATCH'));
  const mismatch = parsed.tasks.find((t) => t.values.taskTitle === 'Mismatch Task');
  assert.ok(codes(mismatch).includes('ROLE_TIER_MISMATCH'));
  assert.ok(codes(mismatch).includes('MISSING_LOCATION_TYPE'));
});

test('flags spelling variants, likely typos and duplicates', async () => {
  const parsed = await parseTaskSpec(await writeFixture());
  const docCodes = parsed.documentIssues.map((i) => i.code);
  const variants = parsed.documentIssues.find((i) => i.code === 'TITLE_SPELLING_VARIANTS');
  assert.deepStrictEqual(variants.spellings.sort(), ['R + S - Status Call', 'R+S - Status Call']);
  assert.ok(docCodes.includes('POSSIBLE_TITLE_TYPO'));
  const duplicate = parsed.documentIssues.find((i) => i.code === 'DUPLICATE_ROLE_TITLE');
  assert.match(duplicate.message, /different details/);
});

test('normalizeTitle and parseRole', () => {
  assert.strictEqual(normalizeTitle('R + S- Bi-weekly  Call'), normalizeTitle('r+s - bi - weekly call'));
  assert.deepStrictEqual(parseRole('T1-SM-SOA'), {
    tierCode: 'T1',
    roles: ['Site Manager'],
    qualifiers: ['SOA'],
    recognised: true,
  });
  assert.strictEqual(parseRole('Add in').recognised, false);
});

test('reads hyperlinked titles and captures the linked workflow', async () => {
  const parsed = await parseTaskSpec(await writeFixture());
  const linked = parsed.tasks[0];
  assert.strictEqual(linked.values.taskTitle, 'R+S - Status Call');
  assert.deepStrictEqual(
    { portalId: linked.workflowLink.portalId, workflowId: linked.workflowLink.workflowId },
    { portalId: '111', workflowId: '222' }
  );
  assert.ok(codes(linked).includes('LINK_TO_ACTION'));
  assert.ok(codes(parsed.tasks[1]).includes('NO_WORKFLOW_LINK'));
  assert.deepStrictEqual(parsed.summary.documentedWorkflowIds, ['222']);
});
