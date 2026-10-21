import { useState } from 'react';
import { useLedger } from './api.js';
import Chain from './components/Chain.jsx';
import SnapshotControls from './components/SnapshotControls.jsx';

export default function App() {
  const { ledger, connection, error, lastReceived, refresh } = useLedger();
  const [selectedIndex, setSelectedIndex] = useState(null);
  const savedBlocks = Array.isArray(ledger?.blocks) ? ledger.blocks : [];
  // Keep broken records in the findings without rendering unsafe card values.
  const blocks = savedBlocks.filter(block => block && typeof block === 'object' && !Array.isArray(block)
    && Number.isSafeInteger(block.index) && block.index >= 0
    && typeof block.hash === 'string' && typeof block.previous_hash === 'string');
  const malformedCount = savedBlocks.length - blocks.length;
  const connected = connection === 'online';
  const invalid = ledger?.verification?.valid === false;
  let status = 'Connecting…';
  if (connected) status = invalid ? 'Chain needs attention' : 'Live chain';
  if (connection === 'offline') status = 'Offline · saved view';

  return <main className="ledger-page">
    <header className="toolbar">
      <div className="heading"><h1>Ledger</h1><span className={`live-status ${connected && !invalid ? 'live' : ''}`} role="status"><i/>{status}</span></div>
      <SnapshotControls connected={connected} canDownload={connected && !invalid}/>
    </header>
    <p className="chain-note">{blocks.length} blocks · click a block to open it<span>Downloads are encrypted. The server validates your saved copy.</span></p>
    {connection === 'offline' && <div className="notice warning" role="alert"><p>{error} {lastReceived && `Last received ${lastReceived.toLocaleTimeString()}.`}</p><button onClick={refresh}>Reconnect</button></div>}
    {invalid && <div className="notice warning" role="alert"><strong>The saved chain did not pass verification.</strong><ul>{(ledger.verification.errors || []).map((finding, index) => <li key={index}>Block {finding.index ?? '—'}: {finding.message}</li>)}</ul></div>}
    {malformedCount > 0 && <p className="notice warning">{malformedCount} malformed record(s) cannot be displayed. Saved data has not been changed.</p>}
    <Chain blocks={blocks} selectedIndex={selectedIndex} onSelect={index => setSelectedIndex(current => current === index ? null : index)} canDownload={connected && !invalid}/>
    {blocks.length === 0 && <p className="empty-chain">{connection === 'loading' ? 'Reading the chain…' : 'No blocks to display yet.'}</p>}
  </main>;
}
