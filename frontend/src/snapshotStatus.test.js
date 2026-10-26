import test from 'node:test';
import assert from 'node:assert/strict';
import { ledgerRevision, snapshotStatus, statusLabel } from './snapshotStatus.js';

test('snapshot colours distinguish verified, changed and absent records', () => {
  const report = { block_statuses: [{ index: 0, status: 'verified' }, { index: 1, status: 'changed' }, { index: 2, status: 'not_in_snapshot' }] };
  assert.equal(snapshotStatus(report, 0).status, 'verified');
  assert.equal(snapshotStatus(report, 1).status, 'changed');
  assert.equal(snapshotStatus(report, 2).status, 'not_in_snapshot');
  assert.equal(statusLabel('not_in_snapshot'), 'Not in this snapshot');
  assert.notEqual(statusLabel('changed'), statusLabel('not_in_snapshot'));
});

test('untrusted files or malformed status values cannot colour individual blocks', () => {
  assert.equal(snapshotStatus(null, 0), null);
  assert.equal(snapshotStatus({ valid: false, errors: [{ index: 0 }] }, 0), null);
  assert.equal(snapshotStatus({ block_statuses: [{ index: 0, status: 'anything' }] }, 0), null);
  assert.equal(snapshotStatus({ block_statuses: [] }, 0), null);
  assert.equal(statusLabel('anything'), '');
});

test('historical changes invalidate comparison even when the stored head hash is unchanged', () => {
  const original = { blocks: [{ index: 0, data: { value: 1 } }], verification: { valid: false, head_hash: 'unchanged', errors: [] }, updated_at_ms: 1 };
  const changed = structuredClone(original);
  changed.blocks[0].data.value = 2;
  assert.notEqual(ledgerRevision(original), ledgerRevision(changed));
  const newRead = { ...original, updated_at_ms: 2 };
  assert.equal(ledgerRevision(original), ledgerRevision(newRead));
});
