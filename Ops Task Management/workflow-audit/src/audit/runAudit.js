'use strict';

/**
 * Runs the audit from a raw fetch bundle and a parsed spreadsheet. Pure: no
 * network access, no file writes. Everything HubSpot did not return is
 * recorded as unavailable and flagged for manual review rather than guessed.
 */

const { normaliseFlow } = require('./normalise');
const { analyseSuppression } = require('./suppression');
const { compareDocument } = require('./compare');
const { nameKey } = require('../hubspot/fetchAudit');

// Known gaps that are explained here so the report says why, not just "missing".
const KNOWN_UNAVAILABLE = {
  'Create Tasks | Respond to reviews at Storage Reach':
    'The folder lists it as a User-object workflow. It is absent from the v4 workflow list, and GET /automation/v4/flows/1682571075 (the ID the spreadsheet links to) returns 404, so its definition cannot be read through the API. Check it manually in HubSpot.',
  'R+S - Reminders: Respond within 1 day to external emails':
    'Not returned by the v4 workflow list or the legacy v3 list, so there is no ID and no definition to read. It may be a workflow type the public API does not expose. Check it manually in HubSpot.',
};

function runAudit(bundle, parsedDoc) {
  const properties = Object.fromEntries(Object.values(bundle.properties || {}).flat().map((p) => [p.name, p]));
  const tierProp = properties.customer_tier;
  const allTiers = tierProp ? tierProp.options.map((o) => o.value) : ['Enterprise', 'TIER 1', 'TIER 2', 'Tier 2 - L2', 'TIER 3'];
  const tierLabels = Object.fromEntries((tierProp ? tierProp.options : []).map((o) => [o.value, o.label]));
  const ownersById = new Map((bundle.owners || []).map((o) => [String(o.id), o]));
  const folderName = bundle.scope && bundle.scope.folderName;

  const records = Object.values(bundle.flows)
    .filter((f) => f.apiVersion === 'v4')
    .map((f) => normaliseFlow(f, { properties, lists: bundle.lists, ownersById, allTiers, folderName }));
  const suppression = records.map((r) => analyseSuppression(r, { lists: bundle.lists, properties, allTiers, tierLabels }));

  const listIds = new Map((bundle.flowsList || []).map((f) => [String(f.id), f]));
  const unavailable = [];
  for (const name of bundle.scopeResolution.unmatchedNames) {
    const linked = parsedDoc
      ? parsedDoc.tasks.find((t) => t.workflowLink && nameKey(t.values.taskTitle).includes(nameKey(name).replace(/^create tasks \| /, '').replace(/^r\+s - /, '')))
      : null;
    const id = linked ? linked.workflowLink.workflowId : null;
    const err = id ? (bundle.errors || []).find((e) => e.context === `workflow ${id}`) : null;
    unavailable.push({
      name,
      id,
      objectType: (bundle.scope.folderListedObjectTypes || {})[name] || null,
      httpStatus: err ? err.status : null,
      reason: KNOWN_UNAVAILABLE[name] || 'Not found in the v4 or v3 workflow lists.',
    });
  }
  for (const e of bundle.errors || []) {
    const m = e.context.match(/^workflow (\d+)$/);
    if (m && !unavailable.some((u) => u.id === m[1])) unavailable.push({ name: null, id: m[1], httpStatus: e.status, reason: `HubSpot returned ${e.status || 'an error'} for this workflow.` });
  }

  const comparison = parsedDoc ? compareDocument({ parsedDoc, records, tierLabels, unavailable }) : null;

  return {
    meta: {
      auditedAt: new Date().toISOString(),
      fetchedAt: bundle.fetchedAt,
      portalId: bundle.account && bundle.account.portalId,
      folderName,
      expectedCount: bundle.scope.expectedWorkflowCount,
      namesInScope: (bundle.scope.workflowNames || []).length,
      workflowsInAccount: (bundle.flowsList || []).length,
      analysed: records.length,
      apiErrors: bundle.errors || [],
      document: parsedDoc ? parsedDoc.source : null,
    },
    records,
    suppression,
    unavailable,
    comparison,
    parsedDoc,
    lists: bundle.lists,
    properties,
    tierLabels,
    allTiers,
    flowsListById: listIds,
  };
}

module.exports = { runAudit, KNOWN_UNAVAILABLE };
