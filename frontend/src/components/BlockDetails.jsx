import { useState } from 'react';
import { blockTitle } from '../ledgerHelpers.js';
import { downloadSnapshot } from '../api.js';
import { snapshotStatus, statusLabel } from '../snapshotStatus.js';

export default function BlockDetails({ ledgerId, block, canDownload, report }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const status = snapshotStatus(report, block.index);
  const saved = report?.snapshot_blocks?.find(item => item.index === block.index);
  async function download() {
    setBusy(true); setError('');
    try { await downloadSnapshot(ledgerId, block.index); }
    catch (requestError) { setError(requestError.message); }
    finally { setBusy(false); }
  }
  return <section className="block-details" id={`details-${block.index}`} aria-label={`${blockTitle(block)} details`}>
    <div className="details-heading"><h2>{blockTitle(block)}</h2><button onClick={download} disabled={!canDownload || busy}>{busy ? 'Downloading…' : 'Download this block'}</button></div>
    {status && <p className={`block-verdict ${status.status}`}><strong>{statusLabel(status.status)}</strong> · {status.message}</p>}
    {error && <p className="inline-error" role="alert">{error}</p>}
    <dl className="hashes"><div><dt>Hash · SHA-256</dt><dd>{block.hash}</dd></div><div><dt>Previous hash</dt><dd>{block.previous_hash}</dd></div></dl>
    <p className="json-label">Current stored block · read only</p>
    <pre tabIndex="0">{JSON.stringify(block, null, 2)}</pre>
    {saved && status?.status === 'changed' && <><p className="json-label">The same block in your authenticated snapshot</p><pre tabIndex="0">{JSON.stringify(saved, null, 2)}</pre></>}
  </section>;
}
