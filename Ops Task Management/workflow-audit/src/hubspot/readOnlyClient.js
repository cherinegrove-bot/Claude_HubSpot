'use strict';

/**
 * Read-only HubSpot API client.
 *
 * The HubSpot `automation` scope also grants write access, so read-only is
 * enforced here instead of relying on the token: only GET requests to the
 * allowlisted read endpoints below can be sent. Anything else throws
 * ReadOnlyViolationError before a network request is made.
 */

const { redact } = require('../redact');

const BASE_URL = 'https://api.hubapi.com';

const ALLOWED_GET_PATHS = [
  /^\/account-info\/v3\/details$/,
  /^\/automation\/v4\/flows$/,
  /^\/automation\/v4\/flows\/\d+$/,
  /^\/automation\/v3\/workflows$/,
  /^\/automation\/v3\/workflows\/\d+$/,
  /^\/crm\/v3\/lists\/\d+$/,
  /^\/crm\/v3\/properties\/[A-Za-z0-9_-]+$/,
  /^\/crm\/v3\/pipelines\/[A-Za-z0-9_-]+$/,
  /^\/crm\/v3\/owners\/?$/,
  /^\/crm\/v3\/owners\/\d+$/,
  /^\/crm\/v3\/schemas$/,
  /^\/settings\/v3\/users\/?$/,
  /^\/settings\/v3\/users\/\d+$/,
  /^\/marketing\/v3\/emails\/\d+$/,
];

class ReadOnlyViolationError extends Error {
  constructor(method, path) {
    super(`Blocked ${method} ${path}: this audit tool only performs allowlisted read-only GET requests.`);
    this.name = 'ReadOnlyViolationError';
  }
}

class HubSpotApiError extends Error {
  constructor({ status, label, method, path, body }) {
    const detail = body && typeof body === 'object' ? body : {};
    super(`${label || path}: HubSpot returned ${status}${detail.message ? ` – ${detail.message}` : ''}`);
    this.name = 'HubSpotApiError';
    this.status = status;
    this.label = label;
    this.method = method;
    this.path = path;
    this.category = detail.category || null;
    this.correlationId = detail.correlationId || null;
    this.permissionHint = explainPermission(status, detail);
  }

  toJSON() {
    return {
      label: this.label,
      method: this.method,
      path: this.path,
      status: this.status,
      category: this.category,
      correlationId: this.correlationId,
      message: this.message,
      permissionHint: this.permissionHint,
    };
  }
}

function explainPermission(status, body) {
  if (status === 401) {
    return 'The token was rejected. It may be wrong, expired, rotated, or from a different HubSpot account.';
  }
  if (status !== 403) return null;
  const scopes = new Set();
  for (const err of body.errors || []) {
    const ctx = err.context || {};
    for (const key of ['requiredGranularScopes', 'requiredScopes', 'missingScopes']) {
      for (const scope of ctx[key] || []) scopes.add(scope);
    }
  }
  return scopes.size
    ? `The private app appears to be missing these scopes: ${[...scopes].join(', ')}.`
    : 'Access denied. The private app is probably missing a scope for this endpoint (see README → "Required scopes").';
}

function assertAllowed(method, path) {
  if (method !== 'GET') throw new ReadOnlyViolationError(method, path);
  if (path.includes('..') || /%2e|%2f/i.test(path)) throw new ReadOnlyViolationError(method, path);
  if (!ALLOWED_GET_PATHS.some((pattern) => pattern.test(path))) throw new ReadOnlyViolationError(method, path);
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function createReadOnlyClient({ accessToken, fetchImpl = globalThis.fetch, maxRetries = 3, retryBaseMs = 1000 } = {}) {
  if (!accessToken) throw new Error('createReadOnlyClient requires an access token.');
  const requestLog = [];

  async function get(path, { query, label } = {}) {
    assertAllowed('GET', path);
    const url = new URL(path, BASE_URL);
    for (const [key, value] of Object.entries(query || {})) {
      if (value !== undefined && value !== null) url.searchParams.set(key, String(value));
    }
    if (url.origin !== BASE_URL) throw new ReadOnlyViolationError('GET', path);

    for (let attempt = 0; ; attempt++) {
      const started = Date.now();
      let response;
      try {
        response = await fetchImpl(url, {
          method: 'GET',
          headers: { Authorization: `Bearer ${accessToken}`, Accept: 'application/json' },
        });
      } catch (networkError) {
        requestLog.push({ label, method: 'GET', path, status: 'NETWORK_ERROR', ms: Date.now() - started });
        if (attempt < maxRetries) {
          await sleep(retryBaseMs * 2 ** attempt);
          continue;
        }
        throw new Error(redact(`${label || path}: network error – ${networkError.message}`, [accessToken]));
      }

      requestLog.push({ label, method: 'GET', path, status: response.status, ms: Date.now() - started });
      const retryable = response.status === 429 || response.status >= 500;
      if (retryable && attempt < maxRetries) {
        const retryAfter = Number(response.headers.get('retry-after'));
        await sleep(retryAfter > 0 ? retryAfter * 1000 : retryBaseMs * 2 ** attempt);
        continue;
      }

      const text = await response.text();
      let body = null;
      try {
        body = text ? JSON.parse(text) : null;
      } catch {
        body = { message: redact(text.slice(0, 500), [accessToken]) };
      }
      if (!response.ok) throw new HubSpotApiError({ status: response.status, label, method: 'GET', path, body });
      return body;
    }
  }

  // Follows HubSpot's `paging.next.after` cursor until all pages are read.
  async function getAllPages(path, { query = {}, label, resultsKey = 'results' } = {}) {
    const results = [];
    let after;
    do {
      const page = await get(path, { query: { ...query, after }, label });
      results.push(...((page && page[resultsKey]) || []));
      after = page && page.paging && page.paging.next ? page.paging.next.after : undefined;
    } while (after);
    return results;
  }

  return { get, getAllPages, requestLog };
}

module.exports = {
  createReadOnlyClient,
  assertAllowed,
  ReadOnlyViolationError,
  HubSpotApiError,
  ALLOWED_GET_PATHS,
};
