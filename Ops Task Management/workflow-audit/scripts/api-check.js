#!/usr/bin/env node
'use strict';

/**
 * Phase 2 – read-only API validation.
 *
 * Confirms what the WLS HubSpot account actually returns for workflows before
 * the audit engine is built on assumptions. Makes GET requests only.
 *
 *   npm run api-check            # inventory + up to 5 sample definitions
 *   npm run api-check -- --all   # every workflow in the audit scope
 *   npm run api-check -- --all --doc "input/Phase 3 Task Management.xlsx"
 *                                # also fetch workflows linked from the WLS doc
 *
 * Raw responses and a summary are written to output/api-check-<timestamp>/
 * (git-ignored). The token is never written or printed.
 */

const fs = require('node:fs');
const path = require('node:path');
const { PROJECT_ROOT, getAccessToken, loadAuditScope } = require('../src/config');
const { createReadOnlyClient } = require('../src/hubspot/readOnlyClient');
const { normalizeTitle, parseTaskSpec } = require('../src/docs/parseTaskSpec');
const { redact } = require('../src/redact');

// Fields we expect the v4 flow definition may contain. Their presence or
// absence in the real responses is what this check is for.
const EXPECTED_FIELDS = [
  'id',
  'name',
  'description',
  'isEnabled',
  'flowType',
  'type',
  'objectTypeId',
  'createdAt',
  'updatedAt',
  'revisionId',
  'startActionId',
  'actions',
  'enrollmentCriteria',
  'enrollmentCriteria.type',
  'enrollmentCriteria.shouldReEnroll',
  'enrollmentCriteria.listFilterBranch',
  'enrollmentCriteria.eventFilterBranches',
  'enrollmentCriteria.reEnrollmentTriggersFilterBranches',
  'enrollmentCriteria.unEnrollObjectsNotMeetingCriteria',
  'suppressionListIds',
  'suppressionForCurrentlyEnrolled',
  'goalFilterBranch',
  'enrollmentSchedule',
  'timeWindows',
  'blockedDates',
  'dataSources',
];

function getPath(object, dotted) {
  return dotted.split('.').reduce((value, key) => (value == null ? undefined : value[key]), object);
}

function collectKeys(value, prefix = '', out = new Set(), depth = 0) {
  if (!value || typeof value !== 'object' || depth > 6) return out;
  for (const [key, child] of Object.entries(value)) {
    const keyPath = prefix ? `${prefix}.${key}` : key;
    out.add(keyPath.replace(/\.\d+(?=\.|$)/g, '[]'));
    collectKeys(child, Array.isArray(value) ? prefix : keyPath, out, depth + 1);
  }
  return out;
}

async function main() {
  const all = process.argv.includes('--all');
  const token = getAccessToken();
  if (process.env.HTTPS_PROXY && process.env.NODE_USE_ENV_PROXY !== '1') {
    console.warn('Note: HTTPS_PROXY is set; run via `npm run api-check` so Node uses the proxy.');
  }
  const client = createReadOnlyClient({ accessToken: token });
  const scope = loadAuditScope();
  const outDir = path.join(PROJECT_ROOT, 'output', `api-check-${new Date().toISOString().replace(/[:.]/g, '-')}`);
  fs.mkdirSync(outDir, { recursive: true });
  const save = (name, data) => fs.writeFileSync(path.join(outDir, name), redact(data, [token]));

  const summary = { startedAt: new Date().toISOString(), scope, checks: {}, errors: [] };
  const record = async (name, fn) => {
    try {
      const result = await fn();
      summary.checks[name] = { ok: true, ...result };
      console.log(`✔ ${name}`);
    } catch (error) {
      const detail = error.toJSON ? error.toJSON() : { message: redact(error.message, [token]) };
      summary.checks[name] = { ok: false, error: detail };
      summary.errors.push({ check: name, ...detail });
      console.log(`✘ ${name}: ${detail.message}${detail.permissionHint ? `\n    → ${detail.permissionHint}` : ''}`);
    }
  };

  await record('account', async () => {
    const account = await client.get('/account-info/v3/details', { label: 'account details' });
    save('account.json', account);
    return { portalId: account.portalId, accountType: account.accountType, timeZone: account.timeZone };
  });

  let flows = [];
  await record('workflowList (v4)', async () => {
    flows = await client.getAllPages('/automation/v4/flows', { query: { limit: 100 }, label: 'list workflows' });
    save('flows-list.json', flows);
    const listKeys = [...collectKeys(flows[0] || {})];
    return {
      totalWorkflowsInAccount: flows.length,
      keysOnListItems: listKeys,
      folderFieldOnList: listKeys.filter((k) => /folder/i.test(k)),
    };
  });

  // Resolve the audit scope: explicit IDs first, otherwise names from the folder.
  const byId = new Map(flows.map((f) => [String(f.id), f]));
  const byName = new Map(flows.map((f) => [normalizeTitle(f.name || ''), f]));
  const scopeIds = new Set(scope.workflowIds.map(String));
  const unmatchedNames = [];
  for (const name of scope.workflowNames) {
    const match = byName.get(normalizeTitle(name));
    if (match) scopeIds.add(String(match.id));
    else unmatchedNames.push(name);
  }
  summary.checks.scope = {
    ok: true,
    folderName: scope.folderName,
    expectedWorkflowCount: scope.expectedWorkflowCount,
    resolvedWorkflowIds: [...scopeIds],
    idsNotFoundInAccount: [...scopeIds].filter((id) => flows.length && !byId.has(id)),
    namesNotFoundInAccount: unmatchedNames,
    countMatchesExpected: scopeIds.size === scope.expectedWorkflowCount,
  };

  const docIndex = process.argv.indexOf('--doc');
  const documentedIds = docIndex > -1 ? (await parseTaskSpec(path.resolve(process.argv[docIndex + 1]))).summary.documentedWorkflowIds : [];
  summary.checks.scope.documentedWorkflowIds = documentedIds;
  summary.checks.scope.documentedIdsNotInScope = documentedIds.filter((id) => scopeIds.size && !scopeIds.has(id));

  let targets = [...scopeIds];
  if (!targets.length) {
    console.log('No workflow IDs/names in config/audit-scope.json yet; sampling the first 5 workflows.');
    targets = flows.slice(0, 5).map((f) => String(f.id));
  } else if (!all) {
    targets = targets.slice(0, 5);
  }
  for (const id of documentedIds) if (!targets.includes(id)) targets.push(id);

  const observedKeys = new Set();
  const fieldPresence = Object.fromEntries(EXPECTED_FIELDS.map((f) => [f, 0]));
  const actionTypes = {};
  const details = [];
  for (const id of targets) {
    await record(`workflow ${id}`, async () => {
      const flow = await client.get(`/automation/v4/flows/${id}`, { label: `workflow ${id}` });
      save(`flow-${id}.json`, flow);
      collectKeys(flow, '', observedKeys);
      for (const field of EXPECTED_FIELDS) if (getPath(flow, field) !== undefined) fieldPresence[field]++;
      for (const action of flow.actions || []) {
        const key = `${action.actionTypeId || '?'} (${action.type || '?'})`;
        actionTypes[key] = (actionTypes[key] || 0) + 1;
      }
      details.push(flow);
      return { name: flow.name, isEnabled: flow.isEnabled, objectTypeId: flow.objectTypeId, actions: (flow.actions || []).length };
    });
  }

  summary.fieldCoverage = {
    workflowsInspected: details.length,
    expectedFields: fieldPresence,
    expectedFieldsNeverReturned: EXPECTED_FIELDS.filter((f) => details.length && fieldPresence[f] === 0),
    folderFields: [...observedKeys].filter((k) => /folder/i.test(k)),
    goalFields: [...observedKeys].filter((k) => /goal/i.test(k)),
    suppressionFields: [...observedKeys].filter((k) => /suppress|unenroll|exclu/i.test(k)),
    allObservedKeys: [...observedKeys].sort(),
  };
  summary.actionTypesObserved = actionTypes;
  summary.requests = client.requestLog;
  summary.finishedAt = new Date().toISOString();
  save('summary.json', summary);

  console.log('\n— Summary —');
  console.log(`Portal: ${summary.checks.account && summary.checks.account.portalId}`);
  console.log(`Workflows in account: ${flows.length}`);
  console.log(`Audit scope resolved: ${scopeIds.size} of expected ${scope.expectedWorkflowCount}`);
  console.log(`Definitions inspected: ${details.length}`);
  console.log(`Folder fields found: ${summary.fieldCoverage.folderFields.join(', ') || 'none'}`);
  console.log(`Expected fields never returned: ${summary.fieldCoverage.expectedFieldsNeverReturned.join(', ') || 'none'}`);
  console.log(`Errors: ${summary.errors.length}`);
  console.log(`Raw output: ${path.relative(PROJECT_ROOT, outDir)}`);
  process.exitCode = summary.errors.length ? 1 : 0;
}

main().catch((error) => {
  console.error(redact(error.message, [process.env.HUBSPOT_ACCESS_TOKEN]));
  process.exitCode = 1;
});
