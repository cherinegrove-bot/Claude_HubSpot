'use strict';

/**
 * Collects everything the audit needs from HubSpot into one raw "bundle".
 * GET-only (via the read-only client). Every failure is recorded against the
 * request that caused it and the run continues with the remaining items.
 */

const OBJECT_TYPE_PATHS = { '0-1': 'contacts', '0-2': 'companies', '0-3': 'deals', '0-5': 'tickets' };

// Folder names as typed in HubSpot can differ from the API only in spacing
// around "|" and repeated spaces, so match on a whitespace-insensitive key.
function nameKey(name) {
  return String(name || '')
    .toLowerCase()
    .replace(/\s*\|\s*/g, ' | ')
    .replace(/\s+/g, ' ')
    .trim();
}

function collectListIds(value, out = new Set()) {
  if (!value || typeof value !== 'object') return out;
  if (Array.isArray(value)) {
    for (const item of value) collectListIds(item, out);
    return out;
  }
  if (value.listId !== undefined && value.listId !== null) out.add(String(value.listId));
  for (const child of Object.values(value)) collectListIds(child, out);
  return out;
}

function errorDetail(error, context) {
  const base = error && error.toJSON ? error.toJSON() : { message: String(error && error.message) };
  return { context, ...base };
}

async function fetchAuditData(client, scope, { extraWorkflowIds = [], onProgress = () => {} } = {}) {
  const bundle = {
    fetchedAt: new Date().toISOString(),
    scope,
    account: null,
    flowsList: [],
    scopeResolution: { matched: [], unmatchedNames: [], extraIds: [] },
    flows: {},
    lists: {},
    owners: [],
    properties: {},
    legacyWorkflows: null,
    errors: [],
  };
  const attempt = async (context, fn) => {
    try {
      return await fn();
    } catch (error) {
      bundle.errors.push(errorDetail(error, context));
      onProgress(`✘ ${context}: ${error.message}`);
      return undefined;
    }
  };

  onProgress('Reading account details');
  bundle.account = (await attempt('account details', () => client.get('/account-info/v3/details', { label: 'account details' }))) || null;

  onProgress('Listing workflows');
  bundle.flowsList =
    (await attempt('list workflows', () =>
      client.getAllPages('/automation/v4/flows', { query: { limit: 100 }, label: 'list workflows' })
    )) || [];

  const byName = new Map();
  for (const flow of bundle.flowsList) {
    const key = nameKey(flow.name);
    if (!byName.has(key)) byName.set(key, []);
    byName.get(key).push(flow);
  }
  const targetIds = new Set((scope.workflowIds || []).map(String));
  for (const name of scope.workflowNames || []) {
    const matches = byName.get(nameKey(name)) || [];
    if (matches.length) {
      for (const match of matches) targetIds.add(String(match.id));
      bundle.scopeResolution.matched.push({ name, ids: matches.map((m) => String(m.id)) });
    } else {
      bundle.scopeResolution.unmatchedNames.push(name);
    }
  }
  for (const id of extraWorkflowIds.map(String)) {
    if (!targetIds.has(id)) bundle.scopeResolution.extraIds.push(id);
    targetIds.add(id);
  }

  // The v4 list may omit some workflow types; the legacy v3 list is checked
  // so unmatched folder names can be explained rather than silently dropped.
  if (bundle.scopeResolution.unmatchedNames.length) {
    onProgress('Checking legacy (v3) workflow list for unmatched names');
    const legacy = await attempt('list legacy v3 workflows', () => client.get('/automation/v3/workflows', { label: 'list legacy v3 workflows' }));
    if (legacy) {
      const all = legacy.workflows || [];
      bundle.legacyWorkflows = {
        total: all.length,
        matches: all
          .filter((wf) => bundle.scopeResolution.unmatchedNames.some((name) => nameKey(name) === nameKey(wf.name)))
          .map((wf) => ({ id: String(wf.id), name: wf.name, type: wf.type, enabled: wf.enabled })),
      };
      for (const match of bundle.legacyWorkflows.matches) {
        const detail = await attempt(`legacy workflow ${match.id}`, () =>
          client.get(`/automation/v3/workflows/${match.id}`, { label: `legacy workflow ${match.id}` })
        );
        if (detail) bundle.flows[`v3:${match.id}`] = { apiVersion: 'v3', ...detail };
      }
    }
  }

  let index = 0;
  for (const id of targetIds) {
    index++;
    onProgress(`Reading workflow ${index}/${targetIds.size} (${id})`);
    const flow = await attempt(`workflow ${id}`, () => client.get(`/automation/v4/flows/${id}`, { label: `workflow ${id}` }));
    if (flow) bundle.flows[id] = { apiVersion: 'v4', ...flow };
  }

  const listIds = collectListIds(Object.values(bundle.flows));
  for (const listId of listIds) {
    onProgress(`Reading list ${listId}`);
    const list = await attempt(`list ${listId}`, () =>
      client.get(`/crm/v3/lists/${listId}`, { query: { includeFilters: true }, label: `list ${listId}` })
    );
    if (list) bundle.lists[listId] = list;
  }

  onProgress('Reading owners');
  bundle.owners =
    (await attempt('owners', () => client.getAllPages('/crm/v3/owners', { query: { limit: 500 }, label: 'owners' }))) || [];

  const objectTypes = new Set(Object.values(bundle.flows).map((f) => f.objectTypeId).filter(Boolean));
  for (const objectTypeId of objectTypes) {
    const objectPath = OBJECT_TYPE_PATHS[objectTypeId];
    if (!objectPath) continue;
    onProgress(`Reading ${objectPath} properties`);
    const props = await attempt(`${objectPath} properties`, () =>
      client.get(`/crm/v3/properties/${objectPath}`, { label: `${objectPath} properties` })
    );
    if (props) bundle.properties[objectTypeId] = props.results || [];
  }

  bundle.requests = client.requestLog;
  bundle.finishedAt = new Date().toISOString();
  return bundle;
}

module.exports = { fetchAuditData, nameKey, collectListIds, OBJECT_TYPE_PATHS };
