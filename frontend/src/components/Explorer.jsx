import { useState } from 'react';
import { blockTitle, dateText, displayValue, isGenesis, shortHash } from '../ledgerHelpers.js';
import { CopyButton, VerificationReport } from './Common.jsx';

function ResultContent({ block }) {
  const data = block.data;
  const isObject = data && typeof data === 'object' && !Array.isArray(data);
  const scores = isObject && data.team_scores;
  const players = isObject && data.players;
  const knownDuration = isObject && Number.isSafeInteger(data.duration_seconds);
  const knownWinner = isObject && (data.winning_team === null || Number.isSafeInteger(data.winning_team));
  const scoreList = Array.isArray(scores) && scores.every(score => Number.isSafeInteger(score));
  const playerList = Array.isArray(players) && players.every(player => player && typeof player === 'object' && !Array.isArray(player));
  return <>
    {knownDuration && <div className="detail-inline"><span>Duration</span><strong>{data.duration_seconds} seconds</strong></div>}
    {knownWinner && <div className="detail-inline"><span>Outcome</span><strong>{data.winning_team === null || data.winning_team === 0 ? 'Draw' : `Team ${data.winning_team} wins`}</strong></div>}
    {scoreList && scores.length > 0 && <div className="team-scores">{scores.map((score, index) => <div key={index}><span>TEAM {index + 1}</span><strong>{score}</strong></div>)}</div>}
    {playerList && players.length > 0 && <div className="small-table-wrap"><table className="players-table"><thead><tr><th>Player</th><th>Team</th><th>K</th><th>D</th></tr></thead><tbody>{players.map((player, index) => <tr key={index}><td>{displayValue(player.name ?? player.player_id ?? `Player ${index + 1}`)}</td><td>{displayValue(player.team)}</td><td>{displayValue(player.kills)}</td><td>{displayValue(player.deaths)}</td></tr>)}</tbody></table></div>}
    <div className="section-label payload-label">{isGenesis(block) ? 'GENESIS DATA' : 'COMPLETE RESULT DATA'}</div>
    <pre className="json-box">{JSON.stringify(data, null, 2) ?? 'No data field'}</pre>
  </>;
}

function BlockDetail({ block, connected }) {
  const [tab, setTab] = useState('result');
  if (!block) return <section className="panel detail-panel"><div className="empty-state"><span className="empty-number">[ ]</span><h3>No block selected</h3><p>Blocks appear here when the ledger server is available.</p></div></section>;
  return <section className="panel detail-panel" aria-label="Selected block details">
    <div className="panel-heading"><div><div className="eyebrow">SELECTED BLOCK</div><h2>{blockTitle(block)}</h2></div><span className="index-tag">#{String(block.index).padStart(3, '0')}</span></div>
    <div className="tabs" role="tablist" aria-label="Block detail format">
      <button role="tab" aria-selected={tab === 'result'} aria-controls="block-result" id="result-tab" onClick={() => setTab('result')}>Result</button>
      <button role="tab" aria-selected={tab === 'json'} aria-controls="block-json" id="json-tab" onClick={() => setTab('json')}>Raw JSON</button>
    </div>
    <div className="detail-body">
      <div className="detail-inline"><span>Recorded</span><strong>{isGenesis(block) ? 'Deterministic genesis' : dateText(block.timestamp_ms)}</strong></div>
      <div className="hash-field"><div><span className="section-label">BLOCK HASH · SHA-256</span><CopyButton value={block.hash || ''} label="Copy hash" /></div><code>{block.hash || '—'}</code></div>
      <div className="hash-field previous"><span className="section-label">PREVIOUS HASH</span><code>{block.previous_hash || '—'}</code></div>
      {!connected && <div className="inline-warning">Saved view · reconnect to check the current chain.</div>}
      {tab === 'result' ? <div role="tabpanel" id="block-result" aria-labelledby="result-tab"><ResultContent block={block}/></div> : <div role="tabpanel" id="block-json" aria-labelledby="json-tab"><div className="raw-heading"><span className="section-label">STORED RECORD</span><CopyButton value={JSON.stringify(block, null, 2)} label="Copy JSON"/></div><pre className="json-box">{JSON.stringify(block, null, 2)}</pre></div>}
    </div>
  </section>;
}

export default function Explorer({ blocks, verification, connection, selectedIndex, setSelectedIndex, onVerify, verifying, verifyReport }) {
  const [search, setSearch] = useState('');
  const selectedBlock = blocks.find(block => block.index === selectedIndex) || blocks.at(-1);
  const matches = blocks.filter(block => !isGenesis(block));
  const filtered = [...matches].reverse().filter(block => blockTitle(block).toLowerCase().includes(search.toLowerCase()));
  const latest = blocks.at(-1);
  const online = connection === 'online';
  let validity = 'Waiting';
  if (online && verification) validity = verification.valid ? 'Verified' : 'Needs attention';
  if (connection === 'offline') validity = 'Unconfirmed';

  return <>
    <div className="summary-grid">
      <div className="summary-card"><div className="section-label">RECORDED MATCHES <span>↗</span></div><div className="summary-value">{blocks.length ? matches.length.toLocaleString() : '—'}<span>matches</span></div><p>{matches.length ? 'Finalized results, linked in order.' : 'Your first result starts the history.'}</p></div>
      <div className="summary-card"><div className="section-label">CHAIN INTEGRITY <span>◇</span></div><div className={`summary-value status-value ${online && verification?.valid ? 'teal-text' : ''}`}>{validity}</div><p>{online ? `${verification?.checked_blocks ?? 0} blocks checked against their hashes.` : 'A live connection is needed to verify.'}</p></div>
      <div className="summary-card"><div className="section-label">LATEST BLOCK <span>⌁</span></div><div className="summary-value">{latest ? `#${String(latest.index).padStart(3, '0')}` : '—'}<span>{latest && isGenesis(latest) ? 'genesis' : 'chain head'}</span></div><p className="mono">{latest ? shortHash(latest.hash) : 'Waiting for the ledger server.'}</p></div>
    </div>

    <section className="chain-section" aria-label="Linked block timeline"><div className="section-heading"><div><h2>The chain</h2><p>One completed match. One linked record.</p></div><span className="quiet-badge">SHA-256 LINKED</span></div>
      {blocks.length > 0 ? <div className="chain-strip">{blocks.map(block => <button type="button" key={block.index} className={`chain-block ${selectedBlock?.index === block.index ? 'selected' : ''}`} onClick={() => setSelectedIndex(block.index)} aria-pressed={selectedBlock?.index === block.index}><span className="chain-block-top">{isGenesis(block) ? 'ORIGIN' : 'MATCH RECORD'}<span>#{String(block.index).padStart(3, '0')}</span></span><strong>{blockTitle(block)}</strong><code>{shortHash(block.hash)}</code><span className="chain-block-bottom">{isGenesis(block) ? 'Fixed starting point' : dateText(block.timestamp_ms)}<span aria-hidden="true">↗</span></span></button>)}</div> : <div className="chain-placeholder">{connection === 'loading' ? 'Reading saved blocks…' : 'Start the ledger server to view the chain. No sample records are added automatically.'}</div>}
    </section>

    <div className="explorer-grid"><section className="panel history-panel"><div className="panel-heading"><div><div className="eyebrow">RECORDED RESULTS</div><h2>Match history <span className="count-pill">{matches.length}</span></h2></div></div><div className="search-wrap"><span aria-hidden="true">⌕</span><input aria-label="Search match ID" placeholder="Search by match ID…" value={search} onChange={event => setSearch(event.target.value)}/>{search && <button className="text-button" onClick={() => setSearch('')} aria-label="Clear search">Clear</button>}</div>
      <div className="history-table-wrap"><table className="history-table"><thead><tr><th>RECORD / MATCH</th><th>RECORDED</th><th>HASH</th><th><span className="sr-only">Open</span></th></tr></thead><tbody>{filtered.map(block => <tr key={block.index} className={selectedBlock?.index === block.index ? 'active-row' : ''}><td><button className="record-link" onClick={() => setSelectedIndex(block.index)}><span className="row-index">#{String(block.index).padStart(3, '0')}</span><strong>{blockTitle(block)}</strong></button></td><td>{dateText(block.timestamp_ms)}</td><td className="mono">{block.hash?.slice(0, 8)}…</td><td><button className="row-open" aria-label={`View ${blockTitle(block)}`} onClick={() => setSelectedIndex(block.index)}>↗</button></td></tr>)}</tbody></table></div>
      {filtered.length === 0 && <div className="empty-state"><span className="empty-number">{search ? '⌕' : '01'}</span><h3>{search ? 'No matching records' : 'Ready for the first match'}</h3><p>{search ? 'Try another match ID or clear your search.' : 'Submit a finalized result to create a block. The genesis block is already the starting point.'}</p></div>}
      <div className="history-footer"><span>Newest results first</span><button className="text-button" onClick={onVerify} disabled={!online || verifying}>{verifying ? 'Checking…' : 'Verify saved chain →'}</button></div>
      {verifyReport && <div className="inline-report"><VerificationReport report={verifyReport}/></div>}
    </section><BlockDetail block={selectedBlock} connected={online}/></div>
  </>;
}
