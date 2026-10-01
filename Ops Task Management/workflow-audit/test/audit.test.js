'use strict';

// Audit engine tests on a small synthetic workflow (no WLS data).

const test = require('node:test');
const assert = require('node:assert');
const F = require('../src/audit/filters');
const { normaliseFlow, htmlToText } = require('../src/audit/normalise');
const { analyseSuppression } = require('../src/audit/suppression');
const { compareDocument, titleMatch, parseTrigger } = require('../src/audit/compare');
const { runAudit } = require('../src/audit/runAudit');
const { buildReport } = require('../src/audit/report');

const or = (...groups) => ({ filterBranchType: 'OR', filters: [], filterBranches: groups.map((filters) => ({ filterBranchType: 'AND', filters, filterBranches: [] })) });
const prop = (property, operator, values) => ({ filterType: 'PROPERTY', property, operation: { operator, values, includeObjectsWithNoValueSet: false } });
const known = (property) => ({ filterType: 'PROPERTY', property, operation: { operator: 'IS_KNOWN' } });
const task = (actionId, subject, propertyName, delta = 2) => ({
  actionId,
  actionTypeId: '0-3',
  fields: {
    subject,
    body: '<p>1. Do the thing<br>2. Close the task</p>',
    owner_assignment: { type: 'CUSTOM', value: { type: 'OBJECT_PROPERTY', propertyName } },
    due_time: { delta, timeUnit: 'DAYS', timeOfDay: { hour: 8, minute: 0 } },
  },
});

const FLOW = {
  id: '1',
  name: 'Create Tasks | Example',
  objectTypeId: '0-2',
  isEnabled: true,
  startActionId: '1',
  enrollmentSchedule: { type: 'MONTHLY_SPECIFIC_DAYS', daysOfMonth: [6], timeOfDay: { hour: 10, minute: 0 } },
  enrollmentCriteria: { type: 'LIST_BASED', shouldReEnroll: true, unEnrollObjectsNotMeetingCriteria: false, listFilterBranch: or([prop('live', 'IS_ANY_OF', ['Yes'])]) },
  suppressionFilterBranch: or([{ filterType: 'IN_LIST', listId: '9', operator: 'IN_LIST' }]),
  actions: [
    {
      actionId: '1',
      type: 'LIST_BRANCH',
      listBranches: [
        { branchName: 'Tier 1', filterBranch: or([prop('customer_tier', 'IS_ANY_OF', ['TIER 1']), prop('name', 'DOES_NOT_CONTAIN_EXACTLY', ['SOA'])]), connection: { nextActionId: '2' } },
        { branchName: 'Tier 3', filterBranch: or([prop('customer_tier', 'IS_ANY_OF', ['TIER 3']), prop('name', 'DOES_NOT_CONTAIN_EXACTLY', ['SOA'])]), connection: { nextActionId: '5' } },
        { branchName: 'SOA', filterBranch: or([prop('name', 'STARTS_WITH', ['SOA - '])]) },
      ],
    },
    { actionId: '2', type: 'LIST_BRANCH', listBranches: [
      { branchName: 'T1 OM', filterBranch: or([known('operations_manager')]), connection: { nextActionId: '3' } },
      { branchName: 'T1 SM', filterBranch: or([known('site_manager')]), connection: { nextActionId: '4' } },
    ] },
    task('3', 'R+S - Monthly Report', 'operations_manager'),
    task('4', 'R+S - Monthly Report', 'site_manager'),
    task('5', 'R + S- Monthly Report', 'site_manager', 5),
  ],
};

const properties = {
  customer_tier: { name: 'customer_tier', label: 'Customer Tier', options: ['Enterprise', 'TIER 1', 'TIER 2', 'Tier 2 - L2', 'TIER 3', 'N/A'].map((v) => ({ value: v, label: v })) },
};
const allTiers = properties.customer_tier.options.map((o) => o.value);
const lists = { 9: { list: { listId: '9', name: 'Exclude', processingType: 'DYNAMIC', objectTypeId: '0-2', size: 3, filterBranch: or([prop('street_rate_management', 'IS_ANY_OF', ['Automated'])]) } } };
const ctx = { properties, lists, ownersById: new Map(), allTiers, folderName: 'Folder' };

test('filters: contradiction and first-match overlap', () => {
  assert.ok(F.treesExclusive(or([prop('customer_tier', 'IS_ANY_OF', ['TIER 1'])]), or([prop('customer_tier', 'IS_ANY_OF', ['TIER 3'])])));
  assert.ok(!F.treesExclusive(or([known('operations_manager')]), or([known('site_manager')])));
  assert.ok(F.treesExclusive(or([prop('name', 'DOES_NOT_CONTAIN_EXACTLY', ['SOA'])]), or([prop('name', 'STARTS_WITH', ['SOA - '])])));
  assert.deepStrictEqual(F.requiredValues(or([prop('customer_tier', 'IS_ANY_OF', ['TIER 1', 'TIER 3'])]), 'customer_tier'), ['TIER 1', 'TIER 3']);
});

test('normalise: walks branches and records every create-task path', () => {
  const r = normaliseFlow(FLOW, ctx);
  assert.strictEqual(r.createdTasks.length, 3);
  const sm = r.createdTasks.find((t) => t.actionId === '4');
  assert.deepStrictEqual(sm.tiers, ['TIER 1']);
  assert.strictEqual(sm.role, 'SM');
  assert.strictEqual(sm.soa, 'non-SOA');
  assert.deepStrictEqual(sm.path[1].notEarlier, ['T1 OM']);
  assert.ok(r.issues.some((i) => i.code === 'EMPTY_BRANCH' && /SOA/.test(i.message)));
  assert.strictEqual(r.actions.branches.every((b) => !b.hasOtherwise), true);
  assert.strictEqual(htmlToText(FLOW.actions[2].fields.body), '1. Do the thing\n2. Close the task');
});

test('suppression: list criteria, no-otherwise gaps, shadowed SM branch, SOA name gap', () => {
  const r = normaliseFlow(FLOW, ctx);
  const s = analyseSuppression(r, { lists, properties, allTiers, tierLabels: {} });
  assert.strictEqual(s.suppressionLists[0].name, 'Exclude');
  assert.match(s.suppressionLists[0].criteria, /street_rate_management is any of "Automated"/);
  assert.ok(s.shadowedBranches.some((b) => b.branch === 'T1 SM'));
  const top = s.noOtherwise.find((n) => n.actionId === '1');
  assert.ok(top.fallsThrough.some((f) => /"Enterprise"/.test(f) && /"N\/A"/.test(f)));
  assert.ok(top.fallsThrough.some((f) => /do not start with "SOA - "/.test(f)));
  assert.ok(s.plainEnglish.some((p) => /can never enter this workflow/.test(p)));
});

test('compare: titles, triggers and tier/role coverage', () => {
  assert.strictEqual(titleMatch('R+S - Monthly Report', 'R + S- Monthly Report'), 'EXACT');
  assert.strictEqual(titleMatch('Weekly Call: First 90 days live', 'Weekly KPI Review: First 90 days live'), null);
  assert.deepStrictEqual(parseTrigger('6th of the Month'), { type: 'MONTHLY', day: 6 });
  assert.deepStrictEqual(parseTrigger('Mondays'), { type: 'WEEKLY', day: 'MONDAY' });

  const record = normaliseFlow(FLOW, ctx);
  const row = (rowNumber, role, roles, tierCode, taskDue = '2 Days') => ({
    rowNumber,
    values: { role, tier: '', taskTitle: 'R+S - Monthly Report', taskDetails: '1. Do the thing 2. Close the task', trigger: '6th of the Month', taskDue, frequency: 'Monthly' },
    role: { tierCode, roles, qualifiers: [], recognised: true },
    workflowLink: { workflowId: '1' },
    interpreted: null,
  });
  const parsedDoc = { tasks: [row(2, 'T1-OM + SM', ['Operations Manager', 'Site Manager'], 'T1'), row(3, 'T3-OM', ['Operations Manager'], 'T3', '5 Days')] };
  const { rows, undocumented } = compareDocument({ parsedDoc, records: [record], tierLabels: {}, unavailable: [] });
  const [t1, t3] = rows;
  assert.deepStrictEqual(t1.combos.map((c) => c.status), ['FOUND', 'CONDITIONAL']);
  assert.strictEqual(t1.trigger.status, 'MATCH');
  assert.strictEqual(t1.due.status, 'MATCH');
  assert.strictEqual(t1.details.status, 'MATCH');
  assert.strictEqual(t3.combos[0].status, 'MISSING');
  assert.match(t3.combos[0].text, /Site Manager instead/);
  assert.strictEqual(t3.result, 'NOT_IN_HUBSPOT_FOR_ROLE');
  assert.deepStrictEqual(undocumented.map((u) => u.actionId), ['5']);
});

test('runAudit + report: unreadable workflows are flagged, all 9 sections present', () => {
  const bundle = {
    fetchedAt: '2026-01-01T00:00:00Z',
    scope: { folderName: 'Folder', expectedWorkflowCount: 2, workflowNames: ['Create Tasks | Example', 'Missing one'] },
    account: { portalId: 1 },
    flowsList: [{ id: '1', name: FLOW.name }],
    scopeResolution: { matched: [{ name: FLOW.name, ids: ['1'] }], unmatchedNames: ['Missing one'], extraIds: [] },
    flows: { 1: { apiVersion: 'v4', ...FLOW } },
    lists,
    owners: [],
    properties: { '0-2': Object.values(properties) },
    errors: [],
  };
  const audit = runAudit(bundle, null);
  assert.strictEqual(audit.unavailable.length, 1);
  assert.strictEqual(audit.unavailable[0].name, 'Missing one');
  const report = buildReport(audit);
  for (let i = 1; i <= 9; i++) assert.match(report, new RegExp(`^## ${i}\\. `, 'm'));
  assert.match(report, /Purpose could not be confidently determined from the available configuration\./);
  assert.ok(!/Bearer|pat-/.test(report));
});
