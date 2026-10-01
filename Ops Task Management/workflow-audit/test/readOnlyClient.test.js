'use strict';

const test = require('node:test');
const assert = require('node:assert');
const {
  createReadOnlyClient,
  assertAllowed,
  ReadOnlyViolationError,
  HubSpotApiError,
} = require('../src/hubspot/readOnlyClient');
const { redact } = require('../src/redact');

// Dummy value assembled at runtime so secret scanners don't mistake it for a real token.
const TOKEN = ['pat', 'na1', '00000000', '1111', '2222', '3333', '444444444444'].join('-');

function fakeFetch(responses) {
  const calls = [];
  const fn = async (url, options) => {
    calls.push({ url: String(url), options });
    const next = responses.shift();
    return {
      ok: next.status >= 200 && next.status < 300,
      status: next.status,
      headers: { get: () => null },
      text: async () => JSON.stringify(next.body),
    };
  };
  fn.calls = calls;
  return fn;
}

test('blocks every non-GET method', () => {
  for (const method of ['POST', 'PUT', 'PATCH', 'DELETE']) {
    assert.throws(() => assertAllowed(method, '/automation/v4/flows/123'), ReadOnlyViolationError);
  }
});

test('blocks GET requests outside the read allowlist', () => {
  for (const path of [
    '/automation/v4/flows/123/enable',
    '/crm/v3/objects/contacts',
    '/automation/v4/flows/../../crm/v3/objects/contacts',
    '/automation/v4/flows/%2e%2e',
    '/automation/v4/flows?x=1',
  ]) {
    assert.throws(() => assertAllowed('GET', path), ReadOnlyViolationError, path);
  }
});

test('allows the read endpoints the audit needs', () => {
  for (const path of ['/automation/v4/flows', '/automation/v4/flows/123', '/crm/v3/lists/42', '/account-info/v3/details']) {
    assert.doesNotThrow(() => assertAllowed('GET', path));
  }
});

test('client exposes no write methods', () => {
  const client = createReadOnlyClient({ accessToken: TOKEN, fetchImpl: fakeFetch([]) });
  assert.deepStrictEqual(Object.keys(client).sort(), ['get', 'getAllPages', 'requestLog']);
});

test('blocked requests never reach the network', async () => {
  const fetchImpl = fakeFetch([]);
  const client = createReadOnlyClient({ accessToken: TOKEN, fetchImpl });
  await assert.rejects(client.get('/crm/v3/objects/contacts'), ReadOnlyViolationError);
  assert.strictEqual(fetchImpl.calls.length, 0);
});

test('sends only GET and follows paging', async () => {
  const fetchImpl = fakeFetch([
    { status: 200, body: { results: [{ id: '1' }], paging: { next: { after: 'abc' } } } },
    { status: 200, body: { results: [{ id: '2' }] } },
  ]);
  const client = createReadOnlyClient({ accessToken: TOKEN, fetchImpl });
  const results = await client.getAllPages('/automation/v4/flows', { query: { limit: 100 } });
  assert.deepStrictEqual(results.map((r) => r.id), ['1', '2']);
  assert.ok(fetchImpl.calls.every((c) => c.options.method === 'GET'));
  assert.match(fetchImpl.calls[1].url, /after=abc/);
});

test('403 errors explain the missing scope', async () => {
  const fetchImpl = fakeFetch([
    {
      status: 403,
      body: { category: 'MISSING_SCOPES', message: 'denied', errors: [{ context: { requiredGranularScopes: ['automation'] } }] },
    },
  ]);
  const client = createReadOnlyClient({ accessToken: TOKEN, fetchImpl, maxRetries: 0 });
  await assert.rejects(client.get('/automation/v4/flows', { label: 'list workflows' }), (error) => {
    assert.ok(error instanceof HubSpotApiError);
    assert.strictEqual(error.status, 403);
    assert.match(error.permissionHint, /automation/);
    assert.ok(!JSON.stringify(error.toJSON()).includes(TOKEN));
    return true;
  });
});

test('request log never contains the token', async () => {
  const fetchImpl = fakeFetch([{ status: 200, body: {} }]);
  const client = createReadOnlyClient({ accessToken: TOKEN, fetchImpl });
  await client.get('/account-info/v3/details');
  assert.ok(!JSON.stringify(client.requestLog).includes(TOKEN));
});

test('redact removes tokens and bearer headers', () => {
  const text = redact(`token ${TOKEN} and Authorization: Bearer abc.def`, []);
  assert.ok(!text.includes(TOKEN));
  assert.ok(!text.includes('abc.def'));
  assert.strictEqual(redact('secret-value here', ['secret-value']), '[REDACTED] here');
});
