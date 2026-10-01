#!/usr/bin/env node
'use strict';

/**
 * Parses the WLS task management spreadsheet and prints its rows and
 * documentation issues. Writes output/parsed-doc.json (git-ignored).
 *
 *   npm run parse-doc -- "input/Phase 3 Task Management.xlsx"
 */

const fs = require('node:fs');
const path = require('node:path');
const { PROJECT_ROOT } = require('../src/config');
const { parseTaskSpec } = require('../src/docs/parseTaskSpec');

async function main() {
  const file = process.argv[2];
  if (!file) {
    console.error('Usage: npm run parse-doc -- <path to .xlsx>');
    process.exitCode = 1;
    return;
  }
  const parsed = await parseTaskSpec(path.resolve(file));
  fs.mkdirSync(path.join(PROJECT_ROOT, 'output'), { recursive: true });
  fs.writeFileSync(path.join(PROJECT_ROOT, 'output', 'parsed-doc.json'), JSON.stringify(parsed, null, 2));

  const { summary } = parsed;
  console.log(`${parsed.source.fileName} – sheet "${parsed.source.sheetName}"`);
  console.log(`Task rows: ${summary.taskRows}, distinct titles: ${summary.distinctTaskTitles}`);
  console.log(`Roles: ${Object.entries(summary.roles).map(([r, n]) => `${r} (${n})`).join(', ')}`);
  console.log(`Rows linked to a workflow: ${summary.rowsLinkedToWorkflow}; portal(s): ${summary.portalIds.join(', ') || 'none'}`);
  console.log(`Documented workflow IDs (${summary.documentedWorkflowIds.length}): ${summary.documentedWorkflowIds.join(', ')}`);
  if (parsed.missingColumns.length) console.log(`Missing columns: ${parsed.missingColumns.join(', ')}`);
  for (const s of parsed.sections) console.log(`Section divider at row ${s.startsAtRow}: "${s.label}"`);

  console.log(`\nRow issues (${summary.rowsWithIssues} rows):`);
  for (const task of parsed.tasks.filter((t) => t.issues.some((i) => i.severity !== 'INFO'))) {
    console.log(`  Row ${task.rowNumber} ${task.values.role} – ${task.values.taskTitle}`);
    for (const i of task.issues.filter((x) => x.severity !== 'INFO')) console.log(`    [${i.severity}] ${i.code}: ${i.message}`);
  }
  console.log(`\nDocument-level issues (${parsed.documentIssues.length}):`);
  for (const i of parsed.documentIssues) {
    const extra = i.spellings || i.titles || (i.rows && i.rows.map((r) => `row ${r}`));
    console.log(`  [${i.severity}] ${i.code}: ${i.message}${extra ? ` → ${extra.join(' | ')}` : ''}`);
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
