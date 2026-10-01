'use strict';

/**
 * Suppression / exclusion analysis, kept separate from the rest of the
 * workflow mapping so it can't get lost in it. For each workflow it lists
 * everything that stops a company from getting a task:
 *
 *   1. Suppression lists (and their own criteria, resolved from the list)
 *   2. Exclusion conditions in enrolment (negative filters such as "is none of")
 *   3. Exclusion conditions inside branches
 *   4. Branches with no "otherwise" path: companies matching none leave silently
 *   5. Empty branches (a path with no actions)
 *   6. Branches shadowed by an earlier, overlapping branch (first match wins)
 *   7. Tasks assigned from a property with no "is known" check (may be unassigned)
 */

const F = require('./filters');
const { TIER_PROPERTY } = require('./normalise');

function describeList(listId, lists, properties) {
  const entry = lists[listId];
  if (!entry || !entry.list) return { listId, name: null, retrieved: false, criteria: 'List could not be retrieved', size: null };
  const list = entry.list;
  return {
    listId,
    name: list.name,
    retrieved: true,
    processingType: list.processingType,
    objectTypeId: list.objectTypeId,
    size: list.size,
    updatedAt: list.updatedAt,
    criteria: list.filterBranch ? F.describeTree(list.filterBranch, { properties, lists }) : list.processingType === 'MANUAL' ? 'Manual list (members added by hand)' : 'No filter criteria returned',
    filterBranch: list.filterBranch || null,
  };
}

// Company-name gap between tier branches that say "does not contain SOA" and an
// SOA branch that needs the name to *start with* "SOA - ": names containing
// "SOA" elsewhere match neither.
function soaNameGap(branchAction, rawBranches) {
  const notContains = [];
  const startsWith = [];
  for (const b of rawBranches) {
    for (const f of F.andGroups(b.filterBranch).flat()) {
      if (f.filterType !== 'PROPERTY' || f.property !== 'name') continue;
      const op = F.filterOperator(f);
      const values = (f.operation && f.operation.values) || [];
      if (op === 'DOES_NOT_CONTAIN_EXACTLY') notContains.push(...values);
      if (op === 'STARTS_WITH') startsWith.push(...values);
    }
  }
  if (!notContains.length || !startsWith.length) return null;
  const strict = startsWith.filter((s) => !notContains.some((n) => s.toLowerCase() === n.toLowerCase()));
  if (!strict.length) return null;
  return `Company names that contain "${notContains[0]}" but do not start with ${strict.map((s) => `"${s}"`).join(' / ')} (for example "${notContains[0]}-Foo", "Foo ${notContains[0]}", or a name with "${notContains[0].toLowerCase()}" inside a word, if HubSpot matches case-insensitively) are excluded from every tier branch and also miss the SOA branch.`;
}

function analyseSuppression(record, { lists, properties, allTiers, tierLabels }) {
  const flow = record.raw;
  const ctx = { properties, lists };
  const out = {
    workflowId: record.id,
    workflowName: record.name,
    suppressionLists: record.suppression.suppressionLists.map((id) => describeList(id, lists, properties)),
    otherSuppression: [],
    enrollmentExclusions: [],
    branchExclusions: [],
    noOtherwise: [],
    emptyBranches: [],
    shadowedBranches: [],
    unguardedAssignments: [],
    plainEnglish: [],
  };

  // Anything in the suppression tree other than lists.
  for (const f of F.andGroups(flow.suppressionFilterBranch).flat()) {
    if (f.filterType !== 'IN_LIST') out.otherSuppression.push(F.describeFilter(f, ctx));
  }

  const enrollTree = flow.enrollmentCriteria && flow.enrollmentCriteria.listFilterBranch;
  out.enrollmentExclusions = F.negativeFilters(enrollTree).map((f) => F.describeFilter(f, ctx));
  const enrolTiers = F.requiredValues(enrollTree, TIER_PROPERTY);
  if (enrolTiers) {
    const left = allTiers.filter((t) => !enrolTiers.includes(t));
    out.enrollmentExclusions.push(`Only Customer Tier ${enrolTiers.map((t) => `"${tierLabels[t] || t}"`).join(', ')} can enrol (${left.map((t) => tierLabels[t] || t).join(', ')} and blank tier are left out).`);
  }

  const rawActions = new Map((flow.actions || []).map((a) => [String(a.actionId), a]));
  for (const br of record.actions.branches) {
    const raw = rawActions.get(br.actionId);
    const rawBranches = (raw && raw.listBranches) || [];
    for (const b of br.branches) {
      for (const e of b.exclusionFilters) out.branchExclusions.push({ actionId: br.actionId, at: br.pathLabel, branch: b.name, condition: e });
      if (!b.nextActionId) out.emptyBranches.push({ actionId: br.actionId, at: br.pathLabel, branch: b.name, criteria: b.criteria });
      if (b.overlapsEarlier.length) {
        out.shadowedBranches.push({
          actionId: br.actionId,
          at: br.pathLabel,
          branch: b.name,
          earlier: b.overlapsEarlier,
          effect: `Companies that also meet ${b.overlapsEarlier.map((n) => `"${n}"`).join(' / ')} go down that earlier branch instead, so "${b.name}" only gets companies that fail it.`,
        });
      }
    }
    if (!br.hasOtherwise) {
      const gaps = [];
      const namedTiers = new Set();
      let tierBranching = false;
      for (const rb of rawBranches) {
        const req = F.requiredValues(rb.filterBranch, TIER_PROPERTY);
        if (req) {
          tierBranching = true;
          req.forEach((t) => namedTiers.add(t));
        }
      }
      if (tierBranching) {
        const pathTrees = [enrollTree].filter(Boolean);
        const possible = F.requiredValues(pathTrees[0], TIER_PROPERTY) || allTiers;
        const missing = possible.filter((t) => !namedTiers.has(t));
        gaps.push(`Customer Tier ${missing.length ? `${missing.map((t) => `"${tierLabels[t] || t}"`).join(', ')} or ` : ''}blank (unless the company is caught by a branch that ignores tier, such as SOA)`);
        const soaGap = soaNameGap(br, rawBranches);
        if (soaGap) gaps.push(soaGap);
      }
      const props = rawBranches.flatMap((rb) => F.andGroups(rb.filterBranch).flat()).filter((f) => F.filterOperator(f) === 'IS_KNOWN').map((f) => f.property);
      if (props.length && props.length === rawBranches.length) {
        gaps.push(`${[...new Set(props)].map((p) => (properties[p] ? properties[p].label : p)).join(' and ')} all blank`);
      }
      out.noOtherwise.push({
        actionId: br.actionId,
        at: br.pathLabel,
        branches: br.branches.map((b) => b.name),
        fallsThrough: gaps.length ? gaps : ['Companies that match none of the branches'],
      });
    }
  }

  // Tasks assigned from OM/SM property on a path that never checked the property is known.
  for (const t of record.createdTasks) {
    if (!t.assignee.property) continue;
    const checked = t.path.some((p) => /\bis known\b/.test(p.criteria) && p.criteria.includes(`(${t.assignee.property})`));
    if (!checked) out.unguardedAssignments.push({ actionId: t.actionId, title: t.title, path: t.pathLabel, property: t.assignee.property });
  }

  // Plain-English summary for the Ops team.
  const p = out.plainEnglish;
  for (const l of out.suppressionLists) {
    p.push(
      l.retrieved
        ? `Companies in the list "${l.name}" (ID ${l.listId}, ${l.processingType === 'DYNAMIC' ? 'active' : l.processingType === 'MANUAL' ? 'static' : String(l.processingType).toLowerCase()} list, ${l.size} companies when fetched) can never enter this workflow. That list holds companies where ${l.criteria}.`
        : `Companies in list ${l.listId} can never enter this workflow (the list itself could not be read; REVIEW).`
    );
  }
  for (const s of out.otherSuppression) p.push(`Also suppressed: ${s}.`);
  for (const e of out.enrollmentExclusions) p.push(`Enrolment excludes: ${e}`);
  for (const b of out.branchExclusions) p.push(`Branch "${b.branch}" (at ${b.at}) excludes companies where ${b.condition.replace(/ does not contain /, ' contains ')}.`);
  for (const n of out.noOtherwise) p.push(`At the branch after ${n.at} there is no "otherwise" path, so these companies get no task and leave the workflow: ${n.fallsThrough.join('; ')}.`);
  for (const e of out.emptyBranches) p.push(`Branch "${e.branch}" (at ${e.at}) has no actions, so companies that match it (${e.criteria}) get no task.`);
  for (const s of out.shadowedBranches) p.push(`${s.effect}`);
  if (out.unguardedAssignments.length) {
    p.push(`${out.unguardedAssignments.length} task(s) are assigned from ${[...new Set(out.unguardedAssignments.map((u) => u.property))].join('/')} without first checking it is set; if it is blank the task is created unassigned (REVIEW).`);
  }
  if (record.unenrollment.unenrollWhenCriteriaNoLongerMet) p.push('Companies are removed when they stop meeting the enrolment criteria.');
  if (!record.reEnrollment.enabled) p.push('Re-enrolment is off: a company that has been through this workflow once is never enrolled again.');
  return out;
}

module.exports = { analyseSuppression, describeList };
