import test from 'node:test';
import assert from 'node:assert/strict';
import { exampleData } from './requestExample.js';

test('request examples use flat schema fields and omit optional fields by default', () => {
  const fields = [{ name: 'body', type: 'string', required: true }, { name: 'note', type: 'string', required: false }];
  assert.deepEqual(exampleData(fields), { body: 'example' });
  assert.deepEqual(exampleData(fields, true), { body: 'example', note: 'example' });
  assert.deepEqual(exampleData([{ name: 'note', type: 'string', required: false }]), {});
});

test('custom data and match_id names remain user fields with correctly typed samples', () => {
  assert.deepEqual(exampleData([{ name: 'data', type: 'object' }, { name: 'match_id', type: 'string' },
    { name: 'enabled', type: 'boolean' }, { name: 'count', type: 'integer' }, { name: 'items', type: 'array' }]),
  { data: {}, match_id: 'example', enabled: true, count: 1, items: [] });
  assert.equal(JSON.parse(JSON.stringify(exampleData([{ name: '__proto__', type: 'string' }]))).__proto__, 'example');
});
