'use strict';

/**
 * Compares each spreadsheet row with the create-task actions found in
 * HubSpot, on title, role (OM/SM), tier and SOA, and then on trigger/schedule,
 * due date and task details. Neither source is assumed correct: results are
 * labelled MATCH, DIFFERENCE, NOT_IN_HUBSPOT or REVIEW.
 */

// Spreadsheet tier code → HubSpot Customer Tier values. HubSpot splits Tier 2
// into "TIER 2" (label "Tier 2 - L1", workflow names say "2.1") and
// "Tier 2 - L2" ("2.2"); the spreadsheet has a single Tier 2.
const TIER_MAP = { T1: ['TIER 1'], T2: ['TIER 2', 'Tier 2 - L2'], T3: ['TIER 3'] };
const ROLE_CODE = { 'Operations Manager': 'OM', 'Site Manager': 'SM' };
const ROLE_NAME = { OM: 'Operations Manager', SM: 'Site Manager' };

function titleKey(title) {
  return String(title || '')
    .toLowerCase()
    .replace(/r\s*\+\s*s\s*[-:]?\s*/g, 'r+s ')
    .replace(/\s\+\s/g, ' & ')
    .replace(/\band\b/g, '&')
    .replace(/[^a-z0-9+&/ ]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function levenshtein(a, b) {
  const row = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    let prev = row[0];
    row[0] = i;
    for (let j = 1; j <= b.length; j++) {
      const temp = row[j];
      row[j] = Math.min(row[j] + 1, row[j - 1] + 1, prev + (a[i - 1] === b[j - 1] ? 0 : 1));
      prev = temp;
    }
  }
  return row[b.length];
}

const words = (text) => new Set(String(text).toLowerCase().match(/[a-z0-9]+/g) || []);
function dice(a, b) {
  const wa = words(a);
  const wb = words(b);
  if (!wa.size && !wb.size) return 1;
  let shared = 0;
  for (const w of wa) if (wb.has(w)) shared++;
  return (2 * shared) / (wa.size + wb.size);
}

function titleMatch(docTitle, hsTitle) {
  const a = titleKey(docTitle);
  const b = titleKey(hsTitle);
  if (!a || !b) return null;
  if (a === b) return 'EXACT';
  const distance = levenshtein(a, b);
  if (distance <= 3) return 'CLOSE';
  if (dice(a.replace(/^r\+s /, ''), b.replace(/^r\+s /, '')) >= 0.85) return 'CLOSE';
  return null;
}

// "2 Days", "3 weeks", "1 week" → days
function parseDuration(text) {
  const m = String(text || '').match(/(\d+)\s*(day|week)/i);
  if (!m) return null;
  return Number(m[1]) * (/week/i.test(m[2]) ? 7 : 1);
}

const DAY_NAMES = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY'];
function parseTrigger(text) {
  const t = String(text || '');
  const dom = t.match(/(\d+)(st|nd|rd|th)\s+of\s+the\s+month/i);
  if (dom) return { type: 'MONTHLY', day: Number(dom[1]) };
  const day = DAY_NAMES.find((d) => new RegExp(`\\b${d.slice(0, 3)}`, 'i').test(t));
  if (day) return { type: 'WEEKLY', day };
  return null;
}

function compareTrigger(row, schedule) {
  const trig = parseTrigger(row.trigger);
  if (!schedule) {
    if (!trig) return { status: 'MATCH', text: 'Not scheduled in HubSpot; the document gives no schedule either.' };
    return { status: 'DIFFERENCE', text: `Document: ${row.trigger}. HubSpot: not on a schedule (criteria-based enrolment).` };
  }
  if (!trig) return { status: 'REVIEW', text: `Document trigger "${row.trigger || '(blank)'}" could not be compared with the HubSpot schedule.` };
  if (trig.type === 'MONTHLY') {
    if (schedule.type !== 'MONTHLY_SPECIFIC_DAYS') return { status: 'DIFFERENCE', text: `Document: ${row.trigger}. HubSpot runs weekly.` };
    if (!schedule.daysOfMonth.includes(trig.day)) return { status: 'DIFFERENCE', text: `Document: day ${trig.day} of the month. HubSpot: day(s) ${schedule.daysOfMonth.join(', ')}.` };
    if (schedule.daysOfMonth.length > 1) return { status: 'DIFFERENCE', text: `Document: day ${trig.day} only. HubSpot also runs on day(s) ${schedule.daysOfMonth.filter((d) => d !== trig.day).join(', ')}.` };
    return { status: 'MATCH', text: `Day ${trig.day} of the month in both.` };
  }
  if (schedule.type !== 'WEEKLY') return { status: 'DIFFERENCE', text: `Document: ${row.trigger} (weekly day). HubSpot: monthly on day(s) ${schedule.daysOfMonth.join(', ')}.` };
  if (!schedule.daysOfWeek.includes(trig.day)) return { status: 'DIFFERENCE', text: `Document: ${row.trigger}. HubSpot: ${schedule.daysOfWeek.join(', ')}.` };
  return { status: 'MATCH', text: `${trig.day.charAt(0)}${trig.day.slice(1).toLowerCase()} in both.` };
}

function compareFrequency(row, schedule, tasks) {
  const freq = String(row.frequency || '').toLowerCase();
  if (!freq) return { status: 'REVIEW', text: 'Frequency is blank in the document.' };
  if (!schedule) return { status: 'REVIEW', text: `Document: ${row.frequency}. HubSpot: created when the enrolment criteria are met (no fixed frequency).` };
  const perMonth = schedule.type === 'MONTHLY_SPECIFIC_DAYS' ? schedule.daysOfMonth.length : schedule.type === 'WEEKLY' ? 4.3 * schedule.daysOfWeek.length : null;
  const repeats = new Set(tasks.map((t) => t.delayBeforeDays)).size;
  const actual = schedule.type === 'WEEKLY' ? `weekly${repeats > 1 ? ` (plus a repeat ${[...new Set(tasks.map((t) => t.delayBeforeDays))].filter(Boolean).join('/')} days later)` : ''}` : `monthly on ${schedule.daysOfMonth.length} day(s)`;
  let expected = null;
  if (/^monthly$/.test(freq)) expected = 1;
  else if (/^weekly$/.test(freq)) expected = 4.3;
  else if (/bi\s*-?\s*weekly/.test(freq)) expected = 2.15;
  else if (/1\s*time\s*\/\s*3\s*weeks/.test(freq)) expected = 1.43;
  if (expected === null) return { status: 'REVIEW', text: `Document: ${row.frequency}. HubSpot: ${actual}.` };
  const close = perMonth && Math.abs(perMonth - expected) / expected <= 0.1;
  const approx = perMonth && Math.abs(perMonth - expected) / expected <= 0.25;
  if (close) return { status: 'MATCH', text: `Document: ${row.frequency}. HubSpot: ${actual}.` };
  if (approx) return { status: 'REVIEW', text: `Document: ${row.frequency}. HubSpot: ${actual} (close, not identical).` };
  return { status: 'DIFFERENCE', text: `Document: ${row.frequency}. HubSpot: ${actual}.` };
}

const normText = (t) =>
  String(t || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();

function compareDetails(docDetails, tasks) {
  const doc = normText(docDetails);
  const distinct = [...new Set(tasks.map((t) => t.details))];
  if (!doc) return { status: 'REVIEW', text: 'Task Details is blank in the document.', similarity: null };
  const best = Math.max(...distinct.map((d) => dice(doc, normText(d))));
  const exact = distinct.some((d) => normText(d) === doc);
  if (exact) return { status: 'MATCH', text: 'Same wording.', similarity: 1 };
  if (best >= 0.9) return { status: 'MATCH', text: `Same apart from minor wording (${Math.round(best * 100)}% word overlap).`, similarity: best };
  if (best >= 0.6) return { status: 'DIFFERENCE', text: `Similar but reworded (${Math.round(best * 100)}% word overlap).`, similarity: best };
  return { status: 'DIFFERENCE', text: `Different instructions (${Math.round(best * 100)}% word overlap).`, similarity: best };
}

function rowExpectations(task) {
  const tierCode = task.role.tierCode;
  const roles = task.role.roles.map((r) => ROLE_CODE[r]).filter(Boolean);
  const soa = task.role.qualifiers.some((q) => /soa/i.test(q)) ? 'SOA only' : 'non-SOA';
  return { tierCode, tierValues: TIER_MAP[tierCode] || [], roles, soa };
}

function soaCompatible(taskSoa, rowSoa) {
  return taskSoa === 'any' || taskSoa === rowSoa;
}

// Describe the earlier branches a task's path must fail ("only if OM is blank").
function gatingText(task, labels) {
  const parts = [];
  for (const p of task.path) {
    if (p.notEarlier && p.notEarlier.length) parts.push(`only reached when the company does not match ${p.notEarlier.map((n) => `"${n}"`).join(', ')}`);
  }
  return parts.join('; ');
}

// Tasks for this row's tier/role/SOA whose details closely match the row,
// whatever their title (finds the same task under a different name).
function detailsLookalikes(row, exp, allTasks, exclude = new Set()) {
  const doc = normText(row.values.taskDetails);
  if (doc.split(' ').length < 6) return [];
  return allTasks
    .filter((t) => !exclude.has(`${t.workflow.id}:${t.actionId}`))
    .filter((t) => exp.tierValues.some((x) => t.tiers.includes(x)) && exp.roles.includes(t.role) && soaCompatible(t.soa, exp.soa))
    .map((t) => ({ t, score: dice(doc, normText(t.details)) }))
    .filter((x) => x.score >= 0.8)
    .sort((a, b) => b.score - a.score);
}

function compareDocument({ parsedDoc, records, tierLabels, unavailable }) {
  const recordsById = new Map(records.map((r) => [r.id, r]));
  const allTasks = records.flatMap((r) => r.createdTasks.map((t) => ({ ...t, workflow: r })));
  const usedTaskKeys = new Set();
  const rows = [];

  for (const row of parsedDoc.tasks) {
    const v = row.values;
    const exp = rowExpectations(row);
    const linkedId = row.workflowLink && row.workflowLink.workflowId;
    const linked = linkedId ? recordsById.get(linkedId) : null;
    const result = {
      rowNumber: row.rowNumber,
      values: v,
      expectations: exp,
      linkedWorkflowId: linkedId || null,
      linkedWorkflowFound: Boolean(linked),
      workflows: [],
      titleMatch: null,
      hubspotTitles: [],
      combos: [],
      assignees: [],
      trigger: null,
      frequency: null,
      due: null,
      details: null,
      suppression: null,
      result: null,
      notes: [],
    };

    if (linkedId && !linked) {
      const u = unavailable.find((x) => x.id === linkedId);
      result.result = 'REVIEW';
      result.titleMatch = 'NOT_RETRIEVED';
      result.notes.push(
        u ? `Linked workflow ${linkedId} could not be read: ${u.reason}` : `Linked workflow ${linkedId} was not returned by HubSpot.`
      );
      rows.push(result);
      continue;
    }

    // Title candidates anywhere in the folder; per tier/role the linked workflow is preferred.
    const candidates = allTasks.map((t) => ({ t, m: titleMatch(v.taskTitle, t.title) })).filter((x) => x.m);
    const inLinked = (c) => linked && c.t.workflow.id === linked.id;
    if (linked && !candidates.some(inLinked) && candidates.length) {
      result.notes.push(`The linked workflow "${linked.name}" (${linked.id}) has no task with this title; a task with a matching title exists in ${[...new Set(candidates.map((x) => `"${x.t.workflow.name}" (${x.t.workflow.id})`))].join(', ')}.`);
    }

    if (!candidates.length) {
      result.titleMatch = 'NOT_FOUND';
      result.result = 'NOT_IN_HUBSPOT';
      result.notes.push(linked ? `No task titled like "${v.taskTitle}" in the linked workflow or anywhere in the folder.` : `No create-task action titled like "${v.taskTitle}" in the ${records.length} workflows that could be read.`);
      const alike = detailsLookalikes(row, exp, allTasks);
      if (alike.length) {
        const titles = [...new Set(alike.map((x) => `"${x.t.title.trim()}" in "${x.t.workflow.name}" (${x.t.workflow.id})`))];
        result.notes.push(`The task details closely match ${titles.join(', ')} (${Math.round(alike[0].score * 100)}% word overlap): probably the same task under a different title (REVIEW).`);
        result.result = 'REVIEW';
        result.hubspotTitles = [...new Set(alike.map((x) => x.t.title.trim()))];
      }
      if (linked) {
        const here = linked.createdTasks.filter((t) => exp.tierValues.some((x) => t.tiers.includes(x)) && soaCompatible(t.soa, exp.soa) && exp.roles.includes(t.role));
        if (here.length) {
          result.workflows = [{ id: linked.id, name: linked.name, status: linked.status, scheduleText: linked.schedule.plainEnglish }];
          result.hubspotTitles = [...new Set(here.map((t) => t.title.trim()))];
          result.notes.push(`For this tier/role the linked workflow creates ${result.hubspotTitles.map((t) => `"${t}"`).join(' / ')} instead (path ${[...new Set(here.map((t) => t.pathLabel))].join('; ')}); possibly the same task under another name (REVIEW).`);
          result.result = 'REVIEW';
        }
      }
      rows.push(result);
      continue;
    }

    result.titleMatch = candidates.some((c) => c.m === 'EXACT') ? 'EXACT' : 'CLOSE';
    const pool = candidates;

    // Tier × role coverage.
    const matchedTasks = [];
    // Prefer the linked workflow; if the title exists in several workflows, keep
    // the one whose task details are closest to this row's details.
    const pick = (hits) => {
      if (hits.some(inLinked)) return hits.filter(inLinked);
      const ids = [...new Set(hits.map((h) => h.t.workflow.id))];
      if (ids.length < 2) return hits;
      const score = (id) => Math.max(...hits.filter((h) => h.t.workflow.id === id).map((h) => dice(normText(v.taskDetails), normText(h.t.details))));
      const best = ids.reduce((a, b) => (score(b) > score(a) ? b : a));
      const note = `A task with this title is created by ${ids.length} workflows (${ids.join(', ')}); compared with ${best}, whose task details are closest to this row.`;
      if (!result.notes.includes(note)) result.notes.push(note);
      return hits.filter((h) => h.t.workflow.id === best);
    };
    for (const tierValue of exp.tierValues) {
      for (const role of exp.roles) {
        const hits = pick(pool.filter((c) => c.t.tiers.includes(tierValue) && c.t.role === role && soaCompatible(c.t.soa, exp.soa)));
        const label = `${tierLabels[tierValue] || tierValue} ${role}${exp.soa === 'SOA only' ? ' (SOA)' : ''}`;
        if (hits.length) {
          hits.forEach((h) => {
            matchedTasks.push(h.t);
            usedTaskKeys.add(`${h.t.workflow.id}:${h.t.actionId}`);
          });
          const gate = hits.map((h) => gatingText(h.t, tierLabels)).filter(Boolean);
          const off = hits.every((h) => h.t.workflow.status === 'OFF');
          const where = [...new Set(hits.map((h) => h.t.workflow.id))];
          const elsewhere = linked && !where.includes(linked.id) ? ` in "${hits[0].t.workflow.name}" (${where.join(', ')}), not the linked workflow` : where.length > 1 ? ` in ${where.length} workflows (${where.join(', ')})` : '';
          result.combos.push({
            label,
            status: gate.length ? 'CONDITIONAL' : off ? 'WORKFLOW_OFF' : 'FOUND',
            text: `${label}: task found${elsewhere} (${hits.map((h) => `action ${h.t.actionId}, ${h.t.pathLabel}`).join('; ')})${gate.length ? ` — ${gate[0]}` : ''}${off ? ' — workflow is OFF' : ''}`,
          });
        } else {
          const otherRole = pool.filter((c) => c.t.tiers.includes(tierValue) && soaCompatible(c.t.soa, exp.soa));
          const otherSoa = pool.filter((c) => c.t.tiers.includes(tierValue) && c.t.role === role);
          let why = 'no task for this tier/role';
          if (otherRole.length) why = `HubSpot assigns it to ${[...new Set(otherRole.map((c) => (c.t.assignee.role === 'NAMED' ? c.t.assignee.text : ROLE_NAME[c.t.role] || c.t.role)))].join(' / ')} instead`;
          else if (otherSoa.length) why = `HubSpot only creates it for ${otherSoa[0].t.soa} companies`;
          result.combos.push({ label, status: 'MISSING', text: `${label}: ${why}` });
        }
      }
    }
    // HubSpot tasks for the same title, tier and SOA but a role the document doesn't list.
    for (const tierValue of exp.tierValues) {
      const extra = pick(pool.filter((c) => c.t.tiers.includes(tierValue) && soaCompatible(c.t.soa, exp.soa) && !exp.roles.includes(c.t.role)));
      for (const c of extra) {
        result.combos.push({ label: `${tierLabels[tierValue] || tierValue} ${c.t.role}`, status: 'EXTRA', text: `${tierLabels[tierValue] || tierValue}: HubSpot also creates it for ${c.t.assignee.role === 'NAMED' ? c.t.assignee.text : ROLE_NAME[c.t.role] || c.t.role} (action ${c.t.actionId}; not in this row)` });
      }
    }

    const shown = matchedTasks.length ? matchedTasks : pool.filter((c) => !linked || inLinked(c)).map((c) => c.t);
    const showTasks = shown.length ? shown : pool.map((c) => c.t);
    const wfIds = [...new Set(showTasks.map((t) => t.workflow.id))];
    result.workflows = wfIds.map((id) => {
      const r = recordsById.get(id);
      return { id, name: r.name, status: r.status, schedule: r.schedule.enrollmentSchedule, scheduleText: r.schedule.plainEnglish };
    });
    result.hubspotTitles = [...new Set(showTasks.map((t) => t.title.trim()))];
    if (result.titleMatch === 'CLOSE' || result.hubspotTitles.some((t) => titleMatch(v.taskTitle, t) === 'CLOSE')) {
      result.notes.push(`Title differs: document "${v.taskTitle}", HubSpot ${result.hubspotTitles.map((t) => `"${t}"`).join(' / ')}.`);
    }

    const scopeTasks = showTasks;
    result.assignees = [...new Set(matchedTasks.map((t) => t.assignee.text))];
    const otherTiers = matchedTasks.length ? '' : ' (no task for this row\'s tier/role; compared with the same task for other tiers)';

    const eff = { ...v, ...(row.interpreted || {}) };
    const perWorkflow = wfIds.map((id) => {
      const wf = recordsById.get(id);
      const trig = compareTrigger(eff, wf.schedule.enrollmentSchedule);
      if (!wf.schedule.enrollmentSchedule) trig.text += ` HubSpot: ${wf.enrollment.plainEnglish}`;
      const freq = compareFrequency(eff, wf.schedule.enrollmentSchedule, scopeTasks.filter((t) => t.workflow.id === id));
      return { id, trig, freq };
    });
    const worst = (list) => (list.includes('DIFFERENCE') ? 'DIFFERENCE' : list.includes('REVIEW') ? 'REVIEW' : 'MATCH');
    const joinTexts = (key) => perWorkflow.map((p) => (perWorkflow.length > 1 ? `[${p.id}] ${p[key].text}` : p[key].text)).join(' ');
    result.trigger = { status: worst(perWorkflow.map((p) => p.trig.status)), text: joinTexts('trig') };
    result.frequency = { status: worst(perWorkflow.map((p) => p.freq.status)), text: joinTexts('freq') };
    const docDue = parseDuration(eff.taskDue);
    const hsDue = [...new Set(scopeTasks.map((t) => t.dueDays))];
    result.due =
      docDue === null
        ? { status: 'REVIEW', text: `Document due "${eff.taskDue || '(blank)'}" not recognised. HubSpot: ${hsDue.join('/')} days.` }
        : hsDue.length === 1 && hsDue[0] === docDue
          ? { status: 'MATCH', text: `${docDue} days in both (HubSpot: ${scopeTasks[0].dueText}).` }
          : { status: 'DIFFERENCE', text: `Document: ${eff.taskDue}. HubSpot: ${hsDue.join('/')} days (${scopeTasks[0].dueText}).` };
    result.details = compareDetails(v.taskDetails, scopeTasks);
    if (otherTiers) {
      result.due.text += otherTiers;
      result.details.text += otherTiers;
    }
    if (result.details.similarity !== null && result.details.similarity < 0.6) {
      const alike = detailsLookalikes(row, exp, allTasks, new Set(scopeTasks.map((t) => `${t.workflow.id}:${t.actionId}`)));
      if (alike.length) {
        result.notes.push(`These details closely match a different HubSpot task: ${[...new Set(alike.map((x) => `"${x.t.title.trim()}" in "${x.t.workflow.name}" (${x.t.workflow.id}), action ${x.t.actionId}`))].join('; ')} (${Math.round(alike[0].score * 100)}% word overlap). The row may combine one task's title with another's details (REVIEW).`);
        alike.forEach((x) => usedTaskKeys.add(`${x.t.workflow.id}:${x.t.actionId}`));
      }
    }
    result.suppression = [...new Set(wfIds.map((id) => recordsById.get(id).suppression.plainEnglish))].join(' ');

    const statuses = [
      result.titleMatch === 'CLOSE' ? 'DIFFERENCE' : 'MATCH',
      ...result.combos.map((c) => (c.status === 'FOUND' ? 'MATCH' : c.status === 'EXTRA' ? 'DIFFERENCE' : c.status === 'MISSING' ? 'DIFFERENCE' : 'REVIEW')),
      result.trigger.status,
      result.frequency.status,
      result.due.status,
      result.details.status,
    ];
    if (result.workflows.some((w) => w.status === 'OFF')) {
      result.notes.push(`Workflow ${result.workflows.filter((w) => w.status === 'OFF').map((w) => `"${w.name}"`).join(', ')} is OFF, so these tasks are not being created at present.`);
      statuses.push('REVIEW');
    }
    if (result.combos.every((c) => c.status === 'MISSING' || c.status === 'EXTRA')) result.result = 'NOT_IN_HUBSPOT_FOR_ROLE';
    else result.result = statuses.includes('DIFFERENCE') ? 'DIFFERENCE' : statuses.includes('REVIEW') ? 'REVIEW' : 'MATCH';
    rows.push(result);
  }

  // HubSpot tasks no row accounted for.
  const undocumented = allTasks
    .filter((t) => !usedTaskKeys.has(`${t.workflow.id}:${t.actionId}`))
    .map((t) => ({
      workflowId: t.workflow.id,
      workflowName: t.workflow.name,
      status: t.workflow.status,
      actionId: t.actionId,
      title: t.title.trim(),
      role: t.role,
      assignee: t.assignee.text,
      tiers: t.tiers.map((x) => tierLabels[x] || x),
      tierConstrained: t.tierConstrained,
      soa: t.soa,
      path: t.pathLabel,
      reason: !parsedDoc.tasks.some((r) => titleMatch(r.values.taskTitle, t.title))
        ? 'Title not in the document'
        : t.tierConstrained && t.tiers.every((x) => x === 'Enterprise')
          ? 'Enterprise tier is not in the document'
          : 'Title is documented, but not for this tier/role/SOA',
    }));

  return { rows, undocumented };
}

module.exports = { compareDocument, titleKey, titleMatch, parseDuration, parseTrigger, TIER_MAP };
