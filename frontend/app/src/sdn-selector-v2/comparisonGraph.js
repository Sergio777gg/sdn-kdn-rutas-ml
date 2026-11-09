export const COMPARISON_ROUTES = [
  { id: 'hops', label: 'Menos saltos', color: '#34d399', line: 'solid' },
  { id: 'delay', label: 'Menor retardo configurado', color: '#fb923c', line: 'dotted' },
  { id: 'capacity', label: 'Inversa de capacidad', color: '#38bdf8', line: 'solid' },
  { id: 'ml', label: 'Inteligente ML', color: '#c084fc', line: 'dashed' },
];

export function comparisonEdgeGroups(result, visibility) {
  const groups = new Map();
  for (const route of result?.alternativas || []) {
    if (route.status !== 'available' || !visibility[route.id]) continue;
    for (const id of new Set(route.edge_ids)) {
      if (!groups.has(id)) groups.set(id, []);
      groups.get(id).push(route.id);
    }
  }
  return groups;
}
