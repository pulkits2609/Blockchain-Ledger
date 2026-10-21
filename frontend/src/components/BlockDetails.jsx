import { useState } from 'react';
import { blockTitle } from '../ledgerHelpers.js';
import { downloadSnapshot } from '../api.js';

export default function BlockDetails({ block, canDownload }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function download() {
    setBusy(true);
    setError('');
    try {
      await downloadSnapshot(block.index);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  return <section className="block-details" id={`details-${block.index}`} aria-label={`${blockTitle(block)} details`}>
    <div className="details-heading"><h2>{blockTitle(block)}</h2><button onClick={download} disabled={!canDownload || busy}>{busy ? 'Downloading…' : 'Download this block'}</button></div>
    {error && <p className="inline-error" role="alert">{error}</p>}
    <dl className="hashes"><div><dt>Hash · SHA-256</dt><dd>{block.hash}</dd></div><div><dt>Previous hash</dt><dd>{block.previous_hash}</dd></div></dl>
    <p className="json-label">Complete stored block · read only</p>
    <pre tabIndex="0">{JSON.stringify(block, null, 2)}</pre>
  </section>;
}
