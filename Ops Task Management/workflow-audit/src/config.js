'use strict';

const fs = require('node:fs');
const path = require('node:path');

const PROJECT_ROOT = path.resolve(__dirname, '..');

// Minimal .env loader so local development works without extra dependencies.
// Values already present in the environment (Codespaces / cloud secrets) win.
function loadDotEnv(file = path.join(PROJECT_ROOT, '.env')) {
  if (!fs.existsSync(file)) return;
  for (const line of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    const match = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$/i);
    if (!match || line.trim().startsWith('#')) continue;
    const [, key, rawValue] = match;
    const value = rawValue.replace(/^(['"])(.*)\1$/, '$2');
    if (process.env[key] === undefined || process.env[key] === '') process.env[key] = value;
  }
}

function getAccessToken() {
  loadDotEnv();
  const token = (process.env.HUBSPOT_ACCESS_TOKEN || '').trim();
  if (!token) {
    throw new Error(
      'HUBSPOT_ACCESS_TOKEN is not set. Add it as an environment secret (see README → "HubSpot credential").'
    );
  }
  return token;
}

function loadAuditScope(file = path.join(PROJECT_ROOT, 'config', 'audit-scope.json')) {
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

module.exports = { PROJECT_ROOT, loadDotEnv, getAccessToken, loadAuditScope };
