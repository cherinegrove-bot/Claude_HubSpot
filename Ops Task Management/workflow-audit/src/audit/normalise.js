'use strict';

/**
 * Turns a raw v4 flow definition (from the fetch bundle) into a normalised
 * workflow record: enrollment, re-enrollment, unenrollment, schedule,
 * suppression, the branch tree walked from startActionId, and every
 * create-task action reached, with the path (branch decisions) that leads to it.
 *
 * HubSpot list branches are first-match: a record goes down the first branch
 * whose criteria it meets, in order, and records meeting none take the
 * "otherwise" (default) branch, or leave the workflow if there isn't one.
 */

const { createWorkflowRecord, RETRIEVAL } = require('../model/workflowRecord');
const F = require('./filters');

const ACTION_TYPES = { '0-1': 'DELAY', '0-3': 'CREATE_TASK' };
const ROLE_BY_PROPERTY = { operations_manager: 'OM', site_manager: 'SM' };
const TIER_PROPERTY = 'customer_tier';

function htmlToText(html) {
  return String(html || '')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/(p|div|li|h\d)>/gi, '\n')
    .replace(/<li[^>]*>/gi, '• ')
    .replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{2,}/g, '\n')
    .trim();
}

const pad = (n) => String(n).padStart(2, '0');
const DAY_SHORT = { MONDAY: 'Mon', TUESDAY: 'Tue', WEDNESDAY: 'Wed', THURSDAY: 'Thu', FRIDAY: 'Fri', SATURDAY: 'Sat', SUNDAY: 'Sun' };
const ordinal = (n) => `${n}${n % 10 === 1 && n !== 11 ? 'st' : n % 10 === 2 && n !== 12 ? 'nd' : n % 10 === 3 && n !== 13 ? 'rd' : 'th'}`;

function describeSchedule(schedule) {
  if (!schedule) return null;
  const time = schedule.timeOfDay ? `${pad(schedule.timeOfDay.hour)}:${pad(schedule.timeOfDay.minute)}` : '';
  if (schedule.type === 'MONTHLY_SPECIFIC_DAYS') return `Monthly on the ${(schedule.daysOfMonth || []).map(ordinal).join(' and ')} at ${time}`;
  if (schedule.type === 'WEEKLY') return `Weekly on ${(schedule.daysOfWeek || []).map((d) => DAY_SHORT[d] || d).join(', ')} at ${time}`;
  if (schedule.type === 'DAILY') return `Daily at ${time}`;
  return `${schedule.type} ${JSON.stringify(schedule)}`;
}

function describeDue(due) {
  if (!due) return 'No due date set';
  const unit = String(due.timeUnit || '').toLowerCase();
  const days = due.daysOfWeek && due.daysOfWeek.length ? ` on ${due.daysOfWeek.map((d) => DAY_SHORT[d] || d).join('/')}` : '';
  const at = due.timeOfDay ? ` at ${pad(due.timeOfDay.hour)}:${pad(due.timeOfDay.minute)}` : '';
  return `${due.delta} ${unit} after creation${at}${days}`;
}

function dueDays(due) {
  if (!due) return null;
  const perDay = { DAYS: 1, WEEKS: 7, HOURS: 1 / 24, MINUTES: 1 / 1440 };
  return due.delta * (perDay[due.timeUnit] || NaN);
}

function describeAssignee(assignment, ownersById) {
  const value = assignment && assignment.value;
  if (!value) return { role: null, text: 'Unassigned', ownerId: null };
  if (value.type === 'OBJECT_PROPERTY') {
    const role = ROLE_BY_PROPERTY[value.propertyName] || null;
    const label = role === 'OM' ? 'Operations Manager' : role === 'SM' ? 'Site Manager' : value.propertyName;
    return { role, text: `${label} (from company property ${value.propertyName})`, property: value.propertyName, ownerId: null };
  }
  if (value.type === 'STATIC_VALUE') {
    const owner = ownersById.get(String(value.staticValue));
    const name = owner ? [owner.firstName, owner.lastName].filter(Boolean).join(' ') || owner.email : null;
    return {
      role: 'NAMED',
      text: owner ? `Specific user: ${name}${owner.archived ? ' (archived owner)' : ''}` : `Specific user ID ${value.staticValue} (not found among active owners)`,
      ownerId: String(value.staticValue),
      ownerResolved: Boolean(owner),
    };
  }
  return { role: null, text: JSON.stringify(value), ownerId: null };
}

function soaFromTrees(trees) {
  let soa = 'any';
  for (const tree of trees) {
    for (const group of F.andGroups(tree)) {
      for (const f of group) {
        if (f.filterType !== 'PROPERTY' || f.property !== 'name') continue;
        const values = ((f.operation && f.operation.values) || []).map((v) => String(v).toUpperCase());
        if (!values.some((v) => v.includes('SOA'))) continue;
        const op = F.filterOperator(f);
        if (op === 'DOES_NOT_CONTAIN_EXACTLY') soa = soa === 'SOA only' ? 'contradictory' : 'non-SOA';
        else if (['STARTS_WITH', 'CONTAINS_EXACTLY', 'ENDS_WITH'].includes(op)) soa = soa === 'non-SOA' ? 'contradictory' : 'SOA only';
      }
    }
  }
  return soa;
}

function tiersFromTrees(trees, allTiers) {
  let tiers = allTiers.slice();
  let constrained = false;
  for (const tree of trees) {
    const required = F.requiredValues(tree, TIER_PROPERTY);
    if (required) {
      constrained = true;
      tiers = tiers.filter((t) => required.includes(t));
    }
  }
  return { tiers, constrained };
}

function normaliseFlow(flow, context) {
  const { properties, lists, ownersById, allTiers } = context;
  const record = createWorkflowRecord({ id: String(flow.id), name: flow.name, folder: context.folderName });
  const ctx = { properties, lists };

  record.objectType = flow.objectTypeId;
  record.workflowType = flow.type;
  record.status = flow.isEnabled ? 'ON' : 'OFF';
  record.createdAt = flow.createdAt;
  record.updatedAt = flow.updatedAt;
  record.revisionId = flow.revisionId;
  record.lastPublishedAt = { retrieval: RETRIEVAL.NOT_AVAILABLE, note: 'The v4 flows API does not return a publish date.' };
  record.purpose = { text: flow.description || null, basis: flow.description ? 'HubSpot description field' : null };
  record.raw = flow;

  const ec = flow.enrollmentCriteria || {};
  const enrollTree = ec.listFilterBranch || null;
  record.enrollment = {
    retrieval: RETRIEVAL.RETRIEVED,
    type: ec.type || null,
    scheduled: Boolean(flow.enrollmentSchedule),
    filters: enrollTree,
    plainEnglish: flow.enrollmentSchedule
      ? `${describeSchedule(flow.enrollmentSchedule)}, enrol companies where ${F.describeTree(enrollTree, ctx)}`
      : `Enrol companies when they start to meet: ${F.describeTree(enrollTree, ctx)}`,
  };
  const reTriggers = ec.reEnrollmentTriggersFilterBranches || [];
  record.reEnrollment = {
    retrieval: RETRIEVAL.RETRIEVED,
    enabled: Boolean(ec.shouldReEnroll),
    triggers: reTriggers,
    plainEnglish: ec.shouldReEnroll
      ? flow.enrollmentSchedule
        ? 'Re-enrolment ON: every scheduled run re-enrols companies that still meet the criteria.'
        : reTriggers.length
          ? `Re-enrolment ON, triggered by: ${reTriggers.map((t) => F.describeTree(t, ctx)).join('; ')}`
          : 'Re-enrolment ON: a company re-enrols when it stops meeting and then meets the criteria again.'
      : flow.enrollmentSchedule
        ? 'Re-enrolment OFF: each company is enrolled once only, so a recurring schedule creates the task only the first time.'
        : 'Re-enrolment OFF: each company is enrolled once only.',
  };
  record.unenrollment = {
    retrieval: RETRIEVAL.RETRIEVED,
    unenrollWhenCriteriaNoLongerMet: Boolean(ec.unEnrollObjectsNotMeetingCriteria),
    otherWorkflowTriggers: [],
    plainEnglish: ec.unEnrollObjectsNotMeetingCriteria
      ? 'Companies are removed from the workflow when they no longer meet the enrolment criteria.'
      : 'Companies stay enrolled even if they stop meeting the enrolment criteria (no automatic unenrolment). Unenrolment by other workflows is not visible from this folder.',
  };
  record.goals = { retrieval: RETRIEVAL.NOT_AVAILABLE, filters: null, plainEnglish: 'No goal criteria returned by the API.' };
  record.schedule = {
    retrieval: RETRIEVAL.RETRIEVED,
    enrollmentSchedule: flow.enrollmentSchedule || null,
    plainEnglish: describeSchedule(flow.enrollmentSchedule) || 'Not scheduled (event / criteria-based enrolment)',
    timeWindows: flow.timeWindows || [],
    blockedDates: flow.blockedDates || [],
  };

  // Suppression gets its own analysis (see suppression.js); capture the raw parts here.
  record.suppression = {
    retrieval: RETRIEVAL.RETRIEVED,
    tree: flow.suppressionFilterBranch || null,
    suppressionLists: F.listIdsIn(flow.suppressionFilterBranch).map((l) => l.listId),
    plainEnglish: flow.suppressionFilterBranch ? `Never enrol companies where ${F.describeTree(flow.suppressionFilterBranch, ctx)}` : 'No suppression',
    exclusionFilters: [],
    suppressingBranches: [],
  };

  // --- Walk the action graph ---
  const actions = new Map((flow.actions || []).map((a) => [String(a.actionId), a]));
  const reached = new Set();
  const steps = [];
  const branches = [];
  const tasks = [];
  const issues = [];
  const enrollTrees = enrollTree ? [enrollTree] : [];

  const describeAction = (action) => {
    const typeId = action.actionTypeId || action.type;
    return ACTION_TYPES[typeId] || typeId;
  };

  function walk(actionId, path, delayMinutes, seen) {
    if (actionId === undefined || actionId === null) return;
    const id = String(actionId);
    const action = actions.get(id);
    if (!action) {
      issues.push({ code: 'DANGLING_ACTION', severity: 'REVIEW', message: `A step points to action ${id}, which does not exist.` });
      return;
    }
    if (seen.has(id)) {
      issues.push({ code: 'ACTION_LOOP', severity: 'REVIEW', message: `Action ${id} is reached again on the same path (loop).` });
      return;
    }
    const nextSeen = new Set(seen).add(id);
    const firstVisit = !reached.has(id);
    reached.add(id);
    const kind = describeAction(action);

    if (action.type === 'LIST_BRANCH' || action.listBranches) {
      const list = action.listBranches || [];
      if (firstVisit) {
        const info = {
          actionId: id,
          branches: list.map((b, i) => {
            const overlapsEarlier = list
              .slice(0, i)
              .filter((prev) => !F.treesExclusive(prev.filterBranch, b.filterBranch))
              .map((prev) => prev.branchName);
            return {
              name: b.branchName,
              criteria: F.describeTree(b.filterBranch, ctx),
              nextActionId: b.connection ? String(b.connection.nextActionId) : null,
              exclusionFilters: F.negativeFilters(b.filterBranch).map((f) => F.describeFilter(f, ctx)),
              overlapsEarlier,
            };
          }),
          hasOtherwise: Boolean(action.defaultBranch && action.defaultBranch.nextActionId) || Boolean(action.defaultBranchName),
          otherwiseName: action.defaultBranchName || null,
          otherwiseNextActionId: action.defaultBranch ? String(action.defaultBranch.nextActionId) : null,
          pathLabel: path.map((p) => p.branchName).join(' › ') || '(start)',
          tierCoverage: null,
        };
        // Which tier values reach some branch here (given the path so far)?
        const pathTrees = enrollTrees.concat(path.map((p) => p.tree).filter(Boolean));
        const { tiers: tiersHere } = tiersFromTrees(pathTrees, allTiers);
        const anyBranchUnconstrained = list.some((b) => F.requiredValues(b.filterBranch, TIER_PROPERTY) === null);
        if (!anyBranchUnconstrained || list.some((b) => F.requiredValues(b.filterBranch, TIER_PROPERTY))) {
          const covered = new Set();
          for (const b of list) {
            const req = F.requiredValues(b.filterBranch, TIER_PROPERTY);
            for (const t of req || tiersHere) covered.add(t);
          }
          info.tierCoverage = {
            covered: tiersHere.filter((t) => covered.has(t)),
            uncovered: tiersHere.filter((t) => !covered.has(t)),
            anyBranchIgnoresTier: anyBranchUnconstrained,
          };
        }
        branches.push(info);
        steps.push({ actionId: id, kind: 'BRANCH', text: `Branch (${list.length} paths, ${info.hasOtherwise ? 'with' : 'no'} "otherwise" path)` });
      }
      list.forEach((b, i) => {
        const earlier = list.slice(0, i);
        const step = {
          actionId: id,
          branchName: b.branchName,
          tree: b.filterBranch,
          criteria: F.describeTree(b.filterBranch, ctx),
          notEarlier: earlier.filter((prev) => !F.treesExclusive(prev.filterBranch, b.filterBranch)).map((prev) => ({ name: prev.branchName, tree: prev.filterBranch })),
        };
        if (!b.connection || b.connection.nextActionId === undefined) {
          if (firstVisit) issues.push({ code: 'EMPTY_BRANCH', severity: 'REVIEW', message: `Branch "${b.branchName}" at action ${id} has no actions; matching companies get nothing.` });
          return;
        }
        walk(b.connection.nextActionId, path.concat(step), delayMinutes, nextSeen);
      });
      if (action.defaultBranch && action.defaultBranch.nextActionId !== undefined) {
        walk(action.defaultBranch.nextActionId, path.concat({ actionId: id, branchName: action.defaultBranchName || 'Otherwise', tree: null, otherwise: true, criteria: 'none of the branches above', notEarlier: list.map((b) => ({ name: b.branchName, tree: b.filterBranch })) }), delayMinutes, nextSeen);
      }
      return;
    }

    let nextDelay = delayMinutes;
    if (kind === 'DELAY') {
      const fields = action.fields || {};
      const minutes = Number(fields.delta) * ({ MINUTES: 1, HOURS: 60, DAYS: 1440 }[String(fields.time_unit).toUpperCase()] || 1);
      nextDelay += minutes;
      if (firstVisit) steps.push({ actionId: id, kind, text: `Delay ${minutes / 1440} days` });
    } else if (kind === 'CREATE_TASK') {
      const fields = action.fields || {};
      const assignee = describeAssignee(fields.owner_assignment, ownersById);
      const pathTrees = enrollTrees.concat(path.map((p) => p.tree).filter(Boolean));
      const { tiers, constrained } = tiersFromTrees(pathTrees, allTiers);
      const gating = [];
      for (const p of path) {
        for (const prev of p.notEarlier || []) gating.push(`not "${prev.name}"`);
      }
      tasks.push({
        actionId: id,
        title: fields.subject || '',
        details: htmlToText(fields.body),
        detailsHtml: fields.body || '',
        taskType: fields.task_type,
        priority: fields.priority,
        assignee,
        role: assignee.role,
        due: fields.due_time || null,
        dueText: describeDue(fields.due_time),
        dueDays: dueDays(fields.due_time),
        delayBeforeDays: delayMinutes / 1440,
        tiers,
        tierConstrained: constrained,
        soa: soaFromTrees(pathTrees),
        path: path.map((p) => ({ actionId: p.actionId, branchName: p.branchName, criteria: p.criteria, otherwise: Boolean(p.otherwise), notEarlier: (p.notEarlier || []).map((n) => n.name) })),
        pathLabel: path.map((p) => p.branchName).join(' › ') || '(no branches)',
        onlyIfNotEarlier: gating,
      });
      if (firstVisit) steps.push({ actionId: id, kind, text: `Create task "${fields.subject}" for ${assignee.text}` });
      if (firstVisit && !String(fields.subject || '').trim()) issues.push({ code: 'EMPTY_TASK_TITLE', severity: 'REVIEW', message: `Create-task action ${id} has no task title${fields.body ? '' : ' and no task details'}.` });
      if (firstVisit && assignee.role === 'NAMED' && !assignee.ownerResolved) issues.push({ code: 'UNKNOWN_ASSIGNEE', severity: 'REVIEW', message: `Create-task action ${id} is assigned to user ID ${assignee.ownerId}, who is not among the account's active owners (deactivated user?).` });
    } else if (firstVisit) {
      steps.push({ actionId: id, kind, text: `${kind} ${JSON.stringify(action.fields || {})}` });
    }
    if (action.connection && action.connection.nextActionId !== undefined) walk(action.connection.nextActionId, path, nextDelay, nextSeen);
  }

  walk(flow.startActionId, [], 0, new Set());

  const unreachable = [...actions.keys()].filter((id) => !reached.has(id));
  for (const id of unreachable) {
    const a = actions.get(id);
    issues.push({
      code: 'UNREACHABLE_ACTION',
      severity: 'REVIEW',
      message: `Action ${id} (${describeAction(a)}${a.fields && a.fields.subject ? ` "${a.fields.subject}"` : ''}) is not connected to the start, so it never runs.`,
    });
  }

  record.actions = { retrieval: RETRIEVAL.RETRIEVED, startActionId: flow.startActionId, steps, branches, unreachable };
  record.createdTasks = tasks;
  record.dependencies = {
    retrieval: RETRIEVAL.RETRIEVED,
    workflows: [],
    lists: [...new Set([...F.listIdsIn(flow.suppressionFilterBranch), ...F.listIdsIn(enrollTree)].map((l) => l.listId))],
    properties: [],
    emails: [],
    owners: [...new Set(tasks.map((t) => t.assignee.ownerId).filter(Boolean))],
    outsideFolder: [],
  };
  record.issues = issues;
  return record;
}

module.exports = { normaliseFlow, htmlToText, describeSchedule, describeDue, TIER_PROPERTY };
