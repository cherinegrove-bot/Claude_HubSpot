'use strict';

// HubSpot private app tokens look like "pat-na1-xxxxxxxx-...". Anything that
// leaves this process (logs, raw dumps, reports) goes through redact().
const TOKEN_PATTERNS = [/pat-[a-z0-9]+-[0-9a-f-]{8,}/gi, /Bearer\s+[A-Za-z0-9._~+/=-]+/g];

function redact(value, secrets = []) {
  let text = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  for (const secret of secrets) {
    if (secret) text = text.split(secret).join('[REDACTED]');
  }
  for (const pattern of TOKEN_PATTERNS) text = text.replace(pattern, '[REDACTED]');
  return text;
}

module.exports = { redact };
