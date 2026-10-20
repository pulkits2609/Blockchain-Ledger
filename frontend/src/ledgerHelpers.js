export function dateText(timestamp) {
  if (timestamp === null || timestamp === undefined) return '—';
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString(undefined, { month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

export function shortHash(hash = '') {
  return typeof hash === 'string' && hash ? `${hash.slice(0, 10)}…${hash.slice(-6)}` : '—';
}

export function isGenesis(block) {
  return block.index === 0;
}

export function blockTitle(block) {
  return isGenesis(block) ? 'Genesis block' : typeof block.match_id === 'string' && block.match_id ? block.match_id : `Block ${block.index}`;
}

export function freshExample() {
  return {
    match_id: `MATCH-DEMO-${Date.now()}`,
    data: {
      duration_seconds: 180,
      winning_team: 1,
      team_scores: [8, 5],
      players: [
        { name: 'Pulkit', team: 1, kills: 8, deaths: 5 },
        { name: 'Player 2', team: 2, kills: 5, deaths: 8 },
      ],
    },
  };
}

export function displayValue(value) {
  if (value === undefined || value === null) return '—';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

