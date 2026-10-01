'use strict';

const test = require('node:test');
const assert = require('node:assert');
const { fetchAuditData, nameKey } = require('../src/hubspot/fetchAudit');

function fakeClient(routes) {
  const calls = [];
  const get = async (path, { query } = {}) => {
    calls.push(path);
    if (!(path in routes)) {
      const error = new Error(`${path}: HubSpot returned 404`);
      error.toJSON = () => ({ path, status: 404, message: error.message });
      throw error;
    }
    return routes[path];
  };
  return {
    calls,
    get,
    getAllPages: async (path, opts) => (await get(path, opts)).results,
    requestLog: [],
  };
}

test('nameKey ignores spacing around pipes', () => {
  assert.strictEqual(nameKey('Create Tasks |  NPS  Detractor'), nameKey('Create Tasks | NPS Detractor'));
  assert.strictEqual(nameKey('Sentiment |Tier 2.2'), nameKey('Sentiment | Tier 2.2'));
});

test('resolves folder names, records unmatched names and failures, resolves lists', async () => {
  const client = fakeClient({
    '/account-info/v3/details': { portalId: 1 },
    '/automation/v4/flows': { results: [{ id: '10', name: 'Create Tasks |  Alpha' }] },
    '/automation/v4/flows/10': {
      id: '10',
      objectTypeId: '0-2',
      suppressionFilterBranch: { filters: [{ listId: '4291', filterType: 'IN_LIST' }] },
    },
    '/automation/v3/workflows': { workflows: [] },
    '/crm/v3/lists/4291': { list: { name: 'Do not task' } },
    '/crm/v3/owners': { results: [{ id: 'o1' }] },
    '/crm/v3/properties/companies': { results: [{ name: 'customer_tier' }] },
  });
  const bundle = await fetchAuditData(client, { workflowNames: ['Create Tasks | Alpha', 'Missing One'] }, { extraWorkflowIds: ['99'] });
  assert.deepStrictEqual(bundle.scopeResolution.unmatchedNames, ['Missing One']);
  assert.deepStrictEqual(Object.keys(bundle.flows), ['10']);
  assert.ok(bundle.lists['4291']);
  assert.strictEqual(bundle.owners.length, 1);
  assert.ok(bundle.properties['0-2']);
  assert.deepStrictEqual(bundle.errors.map((e) => e.context), ['workflow 99']);
});
