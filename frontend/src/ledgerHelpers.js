export function dateText(timestamp) {
  if (timestamp === null || timestamp === undefined) return '—';
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString(undefined, { month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

export function shortHash(hash = '') {
  return typeof hash === 'string' && hash ? `${hash.slice(0, 10)}…${hash.slice(-6)}` : '—';
}

export function blockTitle(block) {
  if (block.index === 0) return 'Genesis block';
  if (typeof block.record_id === 'string' && block.record_id) return block.record_id;
  return `Block ${block.index}`;
}
