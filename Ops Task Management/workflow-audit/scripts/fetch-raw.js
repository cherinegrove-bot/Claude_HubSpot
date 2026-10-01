#!/usr/bin/env node
'use strict';

/**
 * Fetches all HubSpot data needed for the audit (GET requests only) and
 * writes it to output/raw-<timestamp>/bundle.json (git-ignored). The audit can
 * then be run, re-run and debugged from the bundle without calling HubSpot.
 *
 *   npm run fetch-raw
 *   npm run fetch-raw -- --doc "input/Phase 3 Task Management.xlsx"   # also fetch doc-linked workflows
 */

const fs = require('node:fs');
const path = require('node:path');
const { PROJECT_ROOT, getAccessToken, loadAuditScope } = require('../src/config');
const { createReadOnlyClient } = require('../src/hubspot/readOnlyClient');
const { fetchAuditData } = require('../src/hubspot/fetchAudit');
const { parseTaskSpec } = require('../src/docs/parseTaskSpec');
const { redact } = require('../src/redact');

async function main() {
  const token = getAccessToken();
  const client = createReadOnlyClient({ accessToken: token });
  const scope = loadAuditScope();

  const docIndex = process.argv.indexOf('--doc');
  const extraWorkflowIds =
    docIndex > -1 ? (await parseTaskSpec(path.resolve(process.argv[docIndex + 1]))).summary.documentedWorkflowIds : [];

  const bundle = await fetchAuditData(client, scope, { extraWorkflowIds, onProgress: (m) => console.log(m) });

  const outDir = path.join(PROJECT_ROOT, 'output', `raw-${bundle.fetchedAt.replace(/[:.]/g, '-')}`);
  fs.mkdirSync(outDir, { recursive: true });
  const file = path.join(outDir, 'bundle.json');
  fs.writeFileSync(file, redact(bundle, [token]));

  console.log('\n— Fetch summary —');
  console.log(`Portal: ${bundle.account && bundle.account.portalId}`);
  console.log(`Workflows in account (v4 list): ${bundle.flowsList.length}`);
  console.log(`Folder names matched: ${bundle.scopeResolution.matched.length}/${(scope.workflowNames || []).length}`);
  if (bundle.scopeResolution.unmatchedNames.length) console.log(`Unmatched names: ${bundle.scopeResolution.unmatchedNames.join(' ; ')}`);
  if (bundle.legacyWorkflows) console.log(`Legacy v3 matches: ${JSON.stringify(bundle.legacyWorkflows.matches)}`);
  console.log(`Definitions fetched: ${Object.keys(bundle.flows).length}`);
  console.log(`Lists fetched: ${Object.keys(bundle.lists).join(', ') || 'none'}`);
  console.log(`Owners: ${bundle.owners.length}`);
  console.log(`Errors: ${bundle.errors.length}`);
  for (const e of bundle.errors) console.log(`  - ${e.context}: ${e.status || ''} ${e.message}${e.permissionHint ? ` → ${e.permissionHint}` : ''}`);
  console.log(`Bundle: ${path.relative(PROJECT_ROOT, file)}`);
}

main().catch((error) => {
  console.error(redact(error.message, [process.env.HUBSPOT_ACCESS_TOKEN]));
  process.exitCode = 1;
});
