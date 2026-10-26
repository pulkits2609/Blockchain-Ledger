import { useState } from 'react';
import { useLedger } from '../api.js';
import Chain from './Chain.jsx';
import SnapshotControls from './SnapshotControls.jsx';
import { ledgerRevision } from '../snapshotStatus.js';

export default function LedgerViewer({ ledgerId, onBack }) {
  const { ledger, connection, error, lastReceived, refresh } = useLedger(ledgerId);
  const [selectedIndex, setSelectedIndex] = useState(null);
  const [report, setReport] = useState(null);
  const savedBlocks = Array.isArray(ledger?.blocks) ? ledger.blocks : [];
  const blocks = savedBlocks.filter(block => block && typeof block === 'object' && !Array.isArray(block)
    && Number.isSafeInteger(block.index) && block.index >= 0
    && typeof block.hash === 'string' && typeof block.previous_hash === 'string');
  const malformedCount = savedBlocks.length - blocks.length;
  const connected = connection === 'online';
  const invalid = ledger?.verification?.valid === false;
  const missing = (report?.block_statuses || []).filter(item => item.status === 'changed'
    && !blocks.some(block => block.index === item.index));
  let status = 'Connecting…';
  if (connected) status = invalid ? 'Chain needs attention' : 'Live chain';
  if (connection === 'offline') status = 'Offline · saved view';
  return <section>
    <button className="back-link" onClick={onBack}>← All ledgers</button>
    <header className="toolbar">
      <div className="heading"><h1>{ledger?.ledger?.name || 'Ledger'}</h1><span className={`live-status ${connected && !invalid ? 'live' : ''}`} role="status"><i/>{status}</span></div>
      <SnapshotControls ledgerId={ledgerId} connected={connected} canDownload={connected && !invalid} headHash={ledger?.verification?.head_hash} revisionKey={ledgerRevision(ledger)} report={report} onReport={setReport}/>
    </header>
    {ledger?.ledger?.description && <p className="muted">{ledger.ledger.description}</p>}
    <p className="chain-note">{blocks.length} blocks · {ledger?.ledger?.state || 'loading'} · click a block to open it<span>Downloads are encrypted separately for this ledger.</span></p>
    {report && <div className="comparison-legend" aria-label="Snapshot comparison legend"><span className="legend-verified">Green · verified in this snapshot</span><span className="legend-changed">Red · changed or invalid</span><span className="legend-missing">Muted red · not in this snapshot</span><p>Newer blocks absent from an older download are not evidence of tampering.</p></div>}
    {connection === 'offline' && <div className="notice warning" role="alert"><p>{error} {lastReceived && `Last received ${lastReceived.toLocaleTimeString()}.`}</p><button onClick={refresh}>Reconnect</button></div>}
    {invalid && <div className="notice warning" role="alert"><strong>The saved chain did not pass verification.</strong><ul>{(ledger.verification.errors || []).map((finding, index) => <li key={index}>Block {finding.index ?? '—'}: {finding.message}</li>)}</ul></div>}
    {malformedCount > 0 && <p className="notice warning">{malformedCount} malformed record(s) cannot be displayed. Saved data has not been changed.</p>}
    <Chain ledgerId={ledgerId} blocks={blocks} report={report} selectedIndex={selectedIndex} onSelect={index => setSelectedIndex(current => current === index ? null : index)} canDownload={connected && !invalid}/>
    {missing.map(item => <details className="missing-record" key={item.index}><summary>Block #{item.index} is missing or cannot be displayed in the current ledger</summary><p>{item.message}</p><pre>{JSON.stringify(report.snapshot_blocks?.find(block => block.index === item.index), null, 2)}</pre></details>)}
    {report && <details className="snapshot-contents"><summary>Data contained in your saved snapshot</summary><p>These are the authenticated records read from the downloaded file, not new records imported into the server.</p><pre tabIndex="0">{JSON.stringify(report.snapshot_blocks || [], null, 2)}</pre></details>}
    {blocks.length === 0 && <p className="empty-chain">{connection === 'loading' ? 'Reading the chain…' : 'No blocks to display yet.'}</p>}
  </section>;
}
