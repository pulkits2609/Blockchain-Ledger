export function snapshotStatus(report, index) {
  if (!report || !Array.isArray(report.block_statuses)) return null;
  const finding = report.block_statuses.find(item => item && item.index === index);
  if (!finding || !['verified', 'changed', 'not_in_snapshot'].includes(finding.status)) return null;
  return finding;
}

export function statusLabel(status) {
  if (status === 'verified') return 'Verified in snapshot';
  if (status === 'changed') return 'Changed or invalid';
  if (status === 'not_in_snapshot') return 'Not in this snapshot';
  return '';
}

export function ledgerRevision(ledger) {
  // A historical edit may leave the stored final hash unchanged.
  return JSON.stringify({ blocks: ledger?.blocks || [], verification: ledger?.verification || null });
}
