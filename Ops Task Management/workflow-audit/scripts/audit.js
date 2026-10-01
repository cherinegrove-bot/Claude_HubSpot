#!/usr/bin/env node
'use strict';

/**
 * Runs the audit offline from the latest raw bundle (npm run fetch-raw) and
 * the WLS spreadsheet. No HubSpot calls. Writes to output/audit-<timestamp>/:
 *   report.md                 the 9-section audit report
 *   <spreadsheet> - Audited.xlsx  the original 8 columns plus audit columns
 *   audit.json                normalised records and comparison (for debugging)
 *
 *   npm run audit -- --doc "input/Phase 3 Task Management.xlsx" [--bundle output/raw-.../bundle.json]
 */

const fs = require('node:fs');
const path = require('node:path');
const { PROJECT_ROOT } = require('../src/config');
const { parseTaskSpec } = require('../src/docs/parseTaskSpec');
const { runAudit } = require('../src/audit/runAudit');
const { buildReport } = require('../src/audit/report');
const { writeAuditedSpreadsheet } = require('../src/audit/spreadsheet');
const { writeAsBuilt } = require('../src/audit/asBuilt');

const arg = (name) => {
  const i = process.argv.indexOf(name);
  return i > -1 ? process.argv[i + 1] : null;
};

function latestBundle() {
  const dir = path.join(PROJECT_ROOT, 'output');
  const raws = fs.existsSync(dir) ? fs.readdirSync(dir).filter((d) => d.startsWith('raw-')).sort() : [];
  if (!raws.length) throw new Error('No raw bundle found. Run: npm run fetch-raw -- --doc "<spreadsheet>"');
  return path.join(dir, raws[raws.length - 1], 'bundle.json');
}

async function main() {
  const bundlePath = path.resolve(arg('--bundle') || latestBundle());
  const docPath = arg('--doc') ? path.resolve(arg('--doc')) : null;
  const bundle = JSON.parse(fs.readFileSync(bundlePath, 'utf8'));
  const parsedDoc = docPath ? await parseTaskSpec(docPath) : null;

  const audit = runAudit(bundle, parsedDoc);
  const outDir = path.join(PROJECT_ROOT, 'output', `audit-${audit.meta.auditedAt.replace(/[:.]/g, '-')}`);
  fs.mkdirSync(outDir, { recursive: true });

  fs.writeFileSync(path.join(outDir, 'report.md'), buildReport(audit));
  fs.writeFileSync(
    path.join(outDir, 'audit.json'),
    JSON.stringify({ meta: audit.meta, records: audit.records.map(({ raw: _raw, ...r }) => r), suppression: audit.suppression, unavailable: audit.unavailable, comparison: audit.comparison }, null, 2)
  );
  let sheet = null;
  let asBuilt = null;
  if (docPath) {
    sheet = path.join(outDir, `${path.basename(docPath, path.extname(docPath))} - Audited.xlsx`);
    await writeAuditedSpreadsheet({ sourcePath: docPath, targetPath: sheet, audit });
    asBuilt = path.join(outDir, `${path.basename(docPath, path.extname(docPath))} - As built in HubSpot.xlsx`);
    await writeAsBuilt({ sourcePath: docPath, targetPath: asBuilt, audit });
  }

  const results = {};
  for (const r of (audit.comparison && audit.comparison.rows) || []) results[r.result] = (results[r.result] || 0) + 1;
  console.log(`Bundle: ${path.relative(PROJECT_ROOT, bundlePath)} (fetched ${audit.meta.fetchedAt})`);
  console.log(`Workflows analysed: ${audit.records.length}; not readable: ${audit.unavailable.map((u) => u.name).join(' ; ') || 'none'}`);
  console.log(`Spreadsheet rows: ${JSON.stringify(results)}`);
  console.log(`Report: ${path.relative(PROJECT_ROOT, path.join(outDir, 'report.md'))}`);
  if (sheet) console.log(`Spreadsheet: ${path.relative(PROJECT_ROOT, sheet)}`);
  if (asBuilt) console.log(`As built: ${path.relative(PROJECT_ROOT, asBuilt)}`);
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exitCode = 1;
});
