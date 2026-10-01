'use strict';

/**
 * Parses the WLS Ops task management spreadsheet (e.g. "Phase 3 Task
 * Management.xlsx") into structured task rows plus documentation issues.
 *
 * The parser never rewrites what the document says: `values` holds the cells
 * exactly as written, and any reinterpretation (e.g. columns that appear to be
 * shifted) is stored separately under `interpreted` and flagged for REVIEW.
 */

const path = require('node:path');
const ExcelJS = require('exceljs');

const COLUMNS = {
  role: 'Role',
  tier: 'Tier',
  locationType: 'Location Type',
  taskTitle: 'Task Title',
  taskDetails: 'Task Details',
  trigger: 'Trigger',
  taskDue: 'Task Due',
  frequency: 'Frequency',
};

const ROLE_NAMES = { OM: 'Operations Manager', SM: 'Site Manager' };

const WEEKDAY = /\b(mon|tues|wednes|thurs|fri|satur|sun)days?\b/i;
const TRIGGER_LIKE = new RegExp(`${WEEKDAY.source}|of the month|trigger|score|when|after|before`, 'i');
const DURATION_LIKE = /^\s*\d+\s*(day|days|week|weeks)\s*$/i;
const FREQUENCY_LIKE = /weekly|monthly|daily|bi\s*-?\s*weekly|time\s*\/|quarterly|annual/i;

function valueText(value) {
  if (value === null || value === undefined) return '';
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  if (typeof value === 'object') {
    if (value.richText) return value.richText.map((part) => part.text).join('');
    // Hyperlink cells: { text, hyperlink }, where text may itself be rich text.
    if (value.text !== undefined) return valueText(value.text);
    if (value.result !== undefined) return valueText(value.result);
  }
  return String(value);
}

const cellText = (cell) => valueText(cell && cell.value);
const cellLink = (cell) => (cell && cell.value && typeof cell.value === 'object' && cell.value.hyperlink) || null;

// https://app.hubspot.com/workflows/<portalId>/platform/flow/<flowId>/edit[/actions/<n>/...]
function parseWorkflowLink(url) {
  const match = url && url.match(/app\.hubspot\.com\/workflows\/(\d+)\/platform\/flow\/(\d+)(?:\/edit)?(\/actions\/.*)?/);
  if (!match) return null;
  return { portalId: match[1], workflowId: match[2], actionPath: match[3] || null, url };
}

const clean = (text) => text.replace(/\r\n/g, '\n').trim();

function normalizeTitle(title) {
  return title
    .toLowerCase()
    .replace(/\s*\+\s*/g, '+')
    .replace(/\s*-\s*/g, ' - ')
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

// "T2-OM + SM" → { tierCode: 'T2', roles: ['Operations Manager', 'Site Manager'], qualifiers: [] }
// "T1-SM-SOA"  → { tierCode: 'T1', roles: ['Site Manager'], qualifiers: ['SOA'] }
function parseRole(raw) {
  const match = raw.match(/^\s*(T\d+)\s*-\s*(.+)$/i);
  if (!match) return { tierCode: null, roles: [], qualifiers: [], recognised: false };
  const parts = match[2].split(/\s*[+-]\s*/).filter(Boolean);
  const roles = [];
  const qualifiers = [];
  for (const part of parts) {
    const key = part.toUpperCase();
    if (ROLE_NAMES[key]) roles.push(ROLE_NAMES[key]);
    else qualifiers.push(part);
  }
  return { tierCode: match[1].toUpperCase(), roles, qualifiers, recognised: roles.length > 0 };
}

function issue(code, severity, message, extra = {}) {
  return { code, severity, message, ...extra };
}

function findHeader(worksheet) {
  for (let r = 1; r <= Math.min(worksheet.rowCount, 10); r++) {
    const row = worksheet.getRow(r);
    const map = {};
    row.eachCell({ includeEmpty: false }, (cell, col) => {
      const text = clean(cellText(cell)).toLowerCase();
      for (const [key, label] of Object.entries(COLUMNS)) {
        if (text === label.toLowerCase()) map[key] = col;
      }
    });
    if (Object.keys(map).length >= 4) return { headerRow: r, columnMap: map };
  }
  throw new Error(`Could not find the header row (expected columns: ${Object.values(COLUMNS).join(', ')}).`);
}

function rowIssues(values, roleInfo) {
  const issues = [];
  let interpreted = null;

  if (!values.trigger && TRIGGER_LIKE.test(values.taskDue) && DURATION_LIKE.test(values.frequency)) {
    interpreted = { trigger: values.taskDue, taskDue: values.frequency, frequency: '' };
    issues.push(
      issue(
        'COLUMN_SHIFT',
        'REVIEW',
        `Trigger is blank, "${values.taskDue}" is under Task Due and "${values.frequency}" is under Frequency. ` +
          'The values look shifted one column to the right; frequency is then unspecified.'
      )
    );
  }

  const effective = { ...values, ...(interpreted || {}) };
  for (const [key, label] of [
    ['taskTitle', 'Task Title'],
    ['taskDetails', 'Task Details'],
    ['trigger', 'Trigger'],
    ['taskDue', 'Task Due'],
    ['frequency', 'Frequency'],
    ['locationType', 'Location Type'],
    ['tier', 'Tier'],
  ]) {
    if (!effective[key]) issues.push(issue(`MISSING_${key.replace(/[A-Z]/g, (c) => `_${c}`).toUpperCase()}`, 'REVIEW', `${label} is blank.`));
  }

  if (effective.trigger && effective.frequency) {
    const monthlyTrigger = /of the month/i.test(effective.trigger);
    const weekdayTrigger = WEEKDAY.test(effective.trigger);
    const weeklyFrequency = /^\s*weekly\s*$/i.test(effective.frequency);
    const monthlyFrequency = /^\s*monthly\s*$/i.test(effective.frequency);
    if ((monthlyTrigger && weeklyFrequency) || (weekdayTrigger && monthlyFrequency)) {
      issues.push(
        issue('TRIGGER_FREQUENCY_MISMATCH', 'REVIEW', `Trigger "${effective.trigger}" does not match frequency "${effective.frequency}".`)
      );
    }
  }
  if (effective.frequency && !FREQUENCY_LIKE.test(effective.frequency)) {
    issues.push(issue('UNRECOGNISED_FREQUENCY', 'REVIEW', `Frequency "${effective.frequency}" is not a recognised frequency.`));
  }

  if (!roleInfo.recognised) {
    issues.push(issue('UNRECOGNISED_ROLE', 'REVIEW', `Role "${values.role}" is not in the expected T<n>-OM/SM format.`));
  } else if (values.tier) {
    const tierNumber = (values.tier.match(/\d+/) || [])[0];
    if (tierNumber && `T${tierNumber}` !== roleInfo.tierCode) {
      issues.push(issue('ROLE_TIER_MISMATCH', 'REVIEW', `Role "${values.role}" does not match Tier "${values.tier}".`));
    }
  }
  return { issues, interpreted };
}

function documentIssues(tasks) {
  const issues = [];

  const byKey = new Map();
  for (const task of tasks) {
    if (!task.titleKey) continue;
    if (!byKey.has(task.titleKey)) byKey.set(task.titleKey, new Set());
    byKey.get(task.titleKey).add(task.values.taskTitle);
  }
  for (const [key, spellings] of byKey) {
    if (spellings.size > 1) {
      issues.push(
        issue('TITLE_SPELLING_VARIANTS', 'DIFFERENCE', `One task title is written ${spellings.size} ways.`, {
          titleKey: key,
          spellings: [...spellings],
        })
      );
    }
  }

  const keys = [...byKey.keys()];
  for (let i = 0; i < keys.length; i++) {
    for (let j = i + 1; j < keys.length; j++) {
      const distance = levenshtein(keys[i], keys[j]);
      if (distance > 0 && distance <= 2 && Math.min(keys[i].length, keys[j].length) >= 10) {
        issues.push(
          issue('POSSIBLE_TITLE_TYPO', 'REVIEW', 'Two task titles differ by only a few characters (possible typo).', {
            titles: [[...byKey.get(keys[i])][0], [...byKey.get(keys[j])][0]],
          })
        );
      }
    }
  }

  const byRoleTitle = new Map();
  for (const task of tasks) {
    const key = `${task.values.role}|${task.titleKey}`;
    if (!byRoleTitle.has(key)) byRoleTitle.set(key, []);
    byRoleTitle.get(key).push(task);
  }
  for (const group of byRoleTitle.values()) {
    if (group.length < 2) continue;
    const sameDetails = new Set(group.map((t) => t.values.taskDetails)).size === 1;
    issues.push(
      issue(
        'DUPLICATE_ROLE_TITLE',
        'REVIEW',
        `Role "${group[0].values.role}" has ${group.length} rows titled "${group[0].values.taskTitle}"` +
          (sameDetails ? ' with identical details (likely duplicate).' : ' with different details (two tasks, or a duplicate?).'),
        { rows: group.map((t) => t.rowNumber) }
      )
    );
  }
  return issues;
}

async function parseTaskSpec(filePath) {
  const workbook = new ExcelJS.Workbook();
  await workbook.xlsx.readFile(filePath);
  const worksheet = workbook.worksheets[0];
  if (!worksheet) throw new Error('The workbook has no worksheets.');

  const { headerRow, columnMap } = findHeader(worksheet);
  const missingColumns = Object.keys(COLUMNS).filter((key) => !columnMap[key]);
  const tasks = [];
  const sections = [];
  let currentSection = null;

  for (let r = headerRow + 1; r <= worksheet.rowCount; r++) {
    const row = worksheet.getRow(r);
    const values = {};
    for (const key of Object.keys(COLUMNS)) values[key] = columnMap[key] ? clean(cellText(row.getCell(columnMap[key]))) : '';
    const filled = Object.values(values).filter(Boolean);
    if (filled.length === 0) continue;

    // A row with a single value (one cell, or one cell merged across the
    // table, which repeats its value in every cell) is a section divider such
    // as "Add in", not a task.
    if (new Set(filled).size === 1 && (filled.length === 1 || row.getCell(1).isMerged)) {
      currentSection = { label: filled[0], startsAtRow: r };
      sections.push(currentSection);
      continue;
    }

    const links = {};
    for (const key of Object.keys(COLUMNS)) {
      const link = columnMap[key] ? cellLink(row.getCell(columnMap[key])) : null;
      if (link) links[key] = link;
    }
    const workflowLink = parseWorkflowLink(Object.values(links).find((url) => parseWorkflowLink(url)));

    const roleInfo = parseRole(values.role);
    const { issues, interpreted } = rowIssues(values, roleInfo);
    if (!workflowLink) {
      issues.push(issue('NO_WORKFLOW_LINK', 'INFO', 'The document does not link this task to a HubSpot workflow.'));
    } else if (workflowLink.actionPath) {
      issues.push(issue('LINK_TO_ACTION', 'INFO', `Links to a specific step in the workflow (${workflowLink.actionPath}).`));
    }
    tasks.push({
      rowNumber: r,
      section: currentSection ? currentSection.label : null,
      values,
      interpreted,
      role: roleInfo,
      links,
      workflowLink,
      titleKey: values.taskTitle ? normalizeTitle(values.taskTitle) : '',
      issues,
    });
  }

  const docIssues = documentIssues(tasks);
  const distinctTitles = [...new Set(tasks.map((t) => t.titleKey).filter(Boolean))];
  const documentedWorkflowIds = [...new Set(tasks.map((t) => t.workflowLink && t.workflowLink.workflowId).filter(Boolean))];
  const portalIds = [...new Set(tasks.map((t) => t.workflowLink && t.workflowLink.portalId).filter(Boolean))];

  return {
    source: { fileName: path.basename(filePath), sheetName: worksheet.name, headerRow, parsedAt: new Date().toISOString() },
    missingColumns,
    sections,
    tasks,
    documentIssues: docIssues,
    summary: {
      taskRows: tasks.length,
      distinctTaskTitles: distinctTitles.length,
      rowsWithIssues: tasks.filter((t) => t.issues.some((i) => i.severity !== 'INFO')).length,
      rowsLinkedToWorkflow: tasks.filter((t) => t.workflowLink).length,
      documentedWorkflowIds,
      portalIds,
      documentIssues: docIssues.length,
      roles: countBy(tasks, (t) => t.values.role),
    },
  };
}

function countBy(items, keyFn) {
  const counts = {};
  for (const item of items) {
    const key = keyFn(item) || '(blank)';
    counts[key] = (counts[key] || 0) + 1;
  }
  return counts;
}

module.exports = { parseTaskSpec, normalizeTitle, parseRole, COLUMNS };
