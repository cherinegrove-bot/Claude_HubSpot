'use strict';

/**
 * Normalised workflow record (Phase 3 draft).
 *
 * Every section carries a `retrieval` status so the report can show exactly
 * what was observed, what HubSpot did not return, and what failed. Nothing is
 * defaulted to a "probably" value: unknown stays NOT_RETRIEVED until the
 * normaliser fills it from real API data.
 *
 *   RETRIEVED      – read directly from HubSpot (FACT)
 *   NOT_AVAILABLE  – the API does not expose this for this workflow (REVIEW)
 *   ERROR          – the request for it failed (see `errors`) (REVIEW)
 *   NOT_RETRIEVED  – not attempted yet
 */

const RETRIEVAL = Object.freeze({
  RETRIEVED: 'RETRIEVED',
  NOT_AVAILABLE: 'NOT_AVAILABLE',
  ERROR: 'ERROR',
  NOT_RETRIEVED: 'NOT_RETRIEVED',
});

const SECTIONS = [
  'enrollment',
  'reEnrollment',
  'suppression',
  'unenrollment',
  'goals',
  'schedule',
  'actions',
  'dependencies',
];

function section(extra = {}) {
  return { retrieval: RETRIEVAL.NOT_RETRIEVED, ...extra };
}

function createWorkflowRecord({ id, name = null, folder = null } = {}) {
  return {
    id,
    name,
    folder,
    objectType: null,
    workflowType: null,
    status: null, // 'ON' | 'OFF'
    createdAt: null,
    updatedAt: null,
    lastPublishedAt: section(), // likely NOT_AVAILABLE via API; confirmed in Phase 2
    revisionId: null,
    purpose: { text: null, basis: null }, // never inferred from the name alone

    enrollment: section({ type: null, filters: null, plainEnglish: null }),
    reEnrollment: section({ enabled: null, triggers: null, plainEnglish: null }),
    // Suppression is kept separate from enrollment so it can never be lost
    // inside a filter tree: lists, exclusion filters, and branches that act as
    // suppression (a branch path that ends the workflow) are all listed here.
    suppression: section({
      suppressionLists: [],
      exclusionFilters: [],
      suppressingBranches: [],
      suppressCurrentlyEnrolled: null,
      plainEnglish: null,
    }),
    unenrollment: section({ unenrollWhenCriteriaNoLongerMet: null, otherWorkflowTriggers: [], plainEnglish: null }),
    goals: section({ filters: null, plainEnglish: null }),
    schedule: section({ enrollmentSchedule: null, timeWindows: null, blockedDates: null }),
    actions: section({ startActionId: null, steps: [] }),
    dependencies: section({ workflows: [], lists: [], properties: [], emails: [], owners: [], outsideFolder: [] }),

    createdTasks: [], // "Create task" actions, used for the documentation comparison
    issues: [],
    errors: [],
    raw: null, // the untouched API response, kept for traceability
  };
}

function analysisStatus(record) {
  if (record.errors.length && SECTIONS.every((key) => record[key].retrieval !== RETRIEVAL.RETRIEVED)) return 'FAILED';
  const incomplete = SECTIONS.filter((key) => record[key].retrieval !== RETRIEVAL.RETRIEVED);
  return incomplete.length ? 'PARTIAL' : 'COMPLETE';
}

module.exports = { RETRIEVAL, SECTIONS, createWorkflowRecord, analysisStatus };
