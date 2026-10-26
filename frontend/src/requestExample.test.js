import test from 'node:test';
import assert from 'node:assert/strict';
import { exampleData } from './requestExample.js';
import { blockTitle } from './ledgerHelpers.js';

test('request examples use flat schema fields and omit optional fields by default', () => {
  const fields = [{ name: 'body', type: 'string', required: true }, { name: 'note', type: 'string', required: false }];
  assert.deepEqual(exampleData(fields), { body: 'example' });
  assert.deepEqual(exampleData(fields, true), { body: 'example', note: 'example' });
  assert.deepEqual(exampleData([{ name: 'note', type: 'string', required: false }]), {});
});

test('custom data and record_id names remain user fields with correctly typed samples', () => {
  assert.deepEqual(exampleData([{ name: 'data', type: 'object' }, { name: 'record_id', type: 'string' },
    { name: 'enabled', type: 'boolean' }, { name: 'count', type: 'integer' }, { name: 'items', type: 'array' }]),
  { data: {}, record_id: 'example', enabled: true, count: 1, items: [] });
  assert.equal(JSON.parse(JSON.stringify(exampleData([{ name: '__proto__', type: 'string' }]))).__proto__, 'example');
});

test('block titles use generic record identifiers', () => {
  assert.equal(blockTitle({ index: 0, record_id: 'genesis' }), 'Genesis block');
  assert.equal(blockTitle({ index: 1, record_id: 'document-001' }), 'document-001');
  assert.equal(blockTitle({ index: 2 }), 'Block 2');
});
