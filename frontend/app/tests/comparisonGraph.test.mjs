import test from 'node:test';
import assert from 'node:assert/strict';
import { comparisonEdgeGroups } from '../src/sdn-selector-v2/comparisonGraph.js';

const result = { alternativas: [
  { id: 'hops', status: 'available', edge_ids: ['common', 'h'] },
  { id: 'delay', status: 'available', edge_ids: ['common', 'd'] },
  { id: 'capacity', status: 'available', edge_ids: ['common', 'c'] },
  { id: 'ml', status: 'available', edge_ids: ['common', 'm'] },
] };

test('agrupa tramos compartidos sin duplicar el enlace fisico', () => {
  const groups = comparisonEdgeGroups(result, { hops: true, delay: true, capacity: true, ml: true });
  assert.equal(groups.size, 5);
  assert.deepEqual(groups.get('common'), ['hops', 'delay', 'capacity', 'ml']);
});
test('ver una sola alternativa elimina tramos y estilos de las ocultas', () => {
  const groups = comparisonEdgeGroups(result, { delay: true });
  assert.deepEqual([...groups.keys()], ['common', 'd']);
  assert.deepEqual(groups.get('common'), ['delay']);
});
test('no dibuja alternativas no disponibles', () => {
  assert.equal(comparisonEdgeGroups({ alternativas: [{ id: 'ml', status: 'unavailable', edge_ids: ['x'] }] }, { ml: true }).size, 0);
});
