'use strict';

/**
 * Helpers for HubSpot v4 filter trees (enrollment, suppression, list and
 * branch criteria): plain-English descriptions, exclusion detection, and a
 * conservative check of whether two branches can both match one record.
 *
 * A filter tree is an OR of AND groups:
 *   { filterBranchType: 'OR', filterBranches: [{ filterBranchType: 'AND', filters: [...] }], filters: [] }
 */

const OPERATOR_TEXT = {
  IS_ANY_OF: 'is any of',
  IS_NONE_OF: 'is none of',
  IS_EQUAL_TO: 'is',
  IS_NOT_EQUAL_TO: 'is not',
  IS_KNOWN: 'is known',
  IS_UNKNOWN: 'is unknown',
  CONTAINS_EXACTLY: 'contains',
  DOES_NOT_CONTAIN_EXACTLY: 'does not contain',
  STARTS_WITH: 'starts with',
  ENDS_WITH: 'ends with',
  IS_LESS_THAN: 'is less than',
  IS_LESS_THAN_OR_EQUAL_TO: 'is at most',
  IS_GREATER_THAN: 'is greater than',
  IS_GREATER_THAN_OR_EQUAL_TO: 'is at least',
  IS_BETWEEN: 'is between',
  IN_LIST: 'is in list',
  NOT_IN_LIST: 'is not in list',
  HAS_EVER_BEEN_ANY_OF: 'has ever been any of',
  HAS_NEVER_BEEN_ANY_OF: 'has never been any of',
};

// Operators that leave records out rather than pull them in.
const NEGATIVE_OPERATORS = new Set([
  'IS_NONE_OF',
  'IS_NOT_EQUAL_TO',
  'IS_UNKNOWN',
  'DOES_NOT_CONTAIN_EXACTLY',
  'DOES_NOT_CONTAIN',
  'NOT_IN_LIST',
  'HAS_NEVER_BEEN_ANY_OF',
  'IS_NOT_ANY_OF',
  'NOT_HAS_PROPERTY',
]);

function propertyLabel(name, properties) {
  const prop = properties && properties[name];
  return prop && prop.label ? `${prop.label} (${name})` : name;
}

function optionLabel(name, value, properties) {
  const prop = properties && properties[name];
  const option = prop && (prop.options || []).find((o) => o.value === value);
  return option && option.label !== value ? `${option.label}` : value;
}

function describeTimePoint(point) {
  if (!point) return '?';
  if (point.timeType === 'INDEXED') {
    const ref = point.indexReference && point.indexReference.referenceType;
    const days = point.offset && point.offset.days;
    const base = ref === 'NOW' ? 'now' : ref === 'TODAY' ? 'today' : String(ref).toLowerCase();
    return days ? `${base} ${days > 0 ? '+' : '−'} ${Math.abs(days)} days` : base;
  }
  return point.timestamp ? new Date(point.timestamp).toISOString().slice(0, 10) : JSON.stringify(point);
}

function filterOperator(filter) {
  if (filter.filterType === 'IN_LIST') return filter.operator || 'IN_LIST';
  return (filter.operation && filter.operation.operator) || filter.operator || 'UNKNOWN';
}

function describeFilter(filter, { properties = {}, lists = {} } = {}) {
  const operator = filterOperator(filter);
  const opText = OPERATOR_TEXT[operator] || operator.toLowerCase().replace(/_/g, ' ');
  if (filter.filterType === 'IN_LIST') {
    const list = lists[String(filter.listId)];
    const name = list && list.list ? `"${list.list.name}" (${filter.listId})` : `list ${filter.listId}`;
    return `${operator === 'NOT_IN_LIST' ? 'Not in' : 'In'} ${name}`;
  }
  if (filter.filterType !== 'PROPERTY') return `${filter.filterType} filter: ${JSON.stringify(filter)}`;
  const op = filter.operation || {};
  const label = propertyLabel(filter.property, properties);
  let value = '';
  if (Array.isArray(op.values)) value = op.values.map((v) => `"${optionLabel(filter.property, v, properties)}"`).join(', ');
  else if (op.value !== undefined) value = `${op.value}`;
  else if (op.operationType === 'TIME_RANGED') value = `${describeTimePoint(op.lowerBoundTimePoint)} and ${describeTimePoint(op.upperBoundTimePoint)}`;
  const blanks = op.includeObjectsWithNoValueSet ? ' (or has no value)' : '';
  return `${label} ${opText}${value ? ` ${value}` : ''}${blanks}`;
}

// Normalise any tree to an array of AND groups (each an array of filters).
function andGroups(tree) {
  if (!tree) return [];
  const groups = [];
  const top = tree.filters || [];
  const branches = tree.filterBranches || [];
  if (tree.filterBranchType === 'AND') {
    // An AND node: its own filters AND every child (children are OR trees).
    let combos = [top.slice()];
    for (const child of branches) {
      const childGroups = andGroups(child);
      if (!childGroups.length) continue;
      const next = [];
      for (const combo of combos) for (const group of childGroups) next.push(combo.concat(group));
      combos = next;
    }
    return combos;
  }
  // An OR node: each own filter is its own group, each child contributes its groups.
  for (const filter of top) groups.push([filter]);
  for (const child of branches) groups.push(...andGroups(child));
  return groups;
}

function describeTree(tree, context) {
  const groups = andGroups(tree).filter((g) => g.length);
  if (!groups.length) return '(no criteria)';
  const parts = groups.map((group) => group.map((f) => describeFilter(f, context)).join(' AND '));
  return parts.length === 1 ? parts[0] : parts.map((p) => `(${p})`).join(' OR ');
}

const isNegative = (filter) => NEGATIVE_OPERATORS.has(filterOperator(filter));

function negativeFilters(tree) {
  return andGroups(tree).flat().filter(isNegative);
}

function listIdsIn(tree) {
  return andGroups(tree)
    .flat()
    .filter((f) => f.filterType === 'IN_LIST')
    .map((f) => ({ listId: String(f.listId), operator: filterOperator(f) }));
}

// Two single filters on the same property that can never both be true.
function filtersContradict(a, b) {
  if (a.filterType !== 'PROPERTY' || b.filterType !== 'PROPERTY' || a.property !== b.property) return false;
  const oa = filterOperator(a);
  const ob = filterOperator(b);
  const va = (a.operation && a.operation.values) || [];
  const vb = (b.operation && b.operation.values) || [];
  const lower = (list) => list.map((v) => String(v).toLowerCase());
  if (oa === 'IS_ANY_OF' && ob === 'IS_ANY_OF') return !va.some((v) => vb.includes(v));
  if (oa === 'IS_ANY_OF' && ob === 'IS_NONE_OF') return va.every((v) => vb.includes(v));
  if (ob === 'IS_ANY_OF' && oa === 'IS_NONE_OF') return vb.every((v) => va.includes(v));
  const pair = new Set([oa, ob]);
  if (pair.has('IS_KNOWN') && pair.has('IS_UNKNOWN')) return true;
  if (pair.has('IS_UNKNOWN') && (pair.has('IS_ANY_OF') || pair.has('STARTS_WITH') || pair.has('CONTAINS_EXACTLY'))) return true;
  // "starts with / contains X" against "does not contain X'" where X' is part of X.
  const positive = ['STARTS_WITH', 'CONTAINS_EXACTLY', 'ENDS_WITH'];
  const [pos, neg] = positive.includes(oa) && ob === 'DOES_NOT_CONTAIN_EXACTLY' ? [va, vb] : positive.includes(ob) && oa === 'DOES_NOT_CONTAIN_EXACTLY' ? [vb, va] : [null, null];
  if (pos && neg) return lower(pos).every((p) => lower(neg).some((n) => p.includes(n)));
  return false;
}

// Groups are mutually exclusive when some filter in one contradicts some filter in the other.
function groupsExclusive(groupA, groupB) {
  return groupA.some((a) => groupB.some((b) => filtersContradict(a, b)));
}

// True only when we can show no record can satisfy both trees.
function treesExclusive(treeA, treeB) {
  const ga = andGroups(treeA);
  const gb = andGroups(treeB);
  if (!ga.length || !gb.length) return false;
  return ga.every((a) => gb.every((b) => groupsExclusive(a, b)));
}

// Values a tree requires for one property (IS_ANY_OF), or null if it doesn't constrain it.
function requiredValues(tree, property) {
  const groups = andGroups(tree);
  if (!groups.length) return null;
  const perGroup = groups.map((group) => {
    const sets = group
      .filter((f) => f.filterType === 'PROPERTY' && f.property === property && filterOperator(f) === 'IS_ANY_OF')
      .map((f) => f.operation.values);
    if (!sets.length) return null;
    return sets.reduce((acc, values) => acc.filter((v) => values.includes(v)));
  });
  if (perGroup.some((v) => v === null)) return null;
  return [...new Set(perGroup.flat())];
}

module.exports = {
  OPERATOR_TEXT,
  andGroups,
  describeFilter,
  describeTree,
  filterOperator,
  isNegative,
  negativeFilters,
  listIdsIn,
  filtersContradict,
  treesExclusive,
  requiredValues,
};
