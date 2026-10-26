import { useEffect, useRef, useState } from 'react';
import { apiRequest, downloadSnapshot, ledgerPath } from '../api.js';

const MaximumSnapshotBytes = 8 * 1024 * 1024;

export default function SnapshotControls({ ledgerId, connected, canDownload, headHash, revisionKey, report, onReport }) {
  const fileInput = useRef(null);
  const request = useRef(null);
  const revision = useRef(0);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    // Clear old colours even if an interior edit left the stored final hash unchanged.
    revision.current += 1;
    request.current?.abort();
    onReport(null);
    setError('');
    setBusy('');
    return () => { revision.current += 1; request.current?.abort(); };
  }, [ledgerId, connected, canDownload, headHash, revisionKey, onReport]);

  async function download() {
    setBusy('download'); setError('');
    try {
      await downloadSnapshot(ledgerId);
    } catch (requestError) {
      setError(requestError.message);
    } finally { setBusy(''); }
  }

  async function validate(event) {
    const file = event.target.files[0];
    event.target.value = '';
    if (!file) return;
    setError(''); onReport(null);
    if (!file.size || file.size > MaximumSnapshotBytes) {
      setError('Choose a nonempty ledger file smaller than 8 MiB.');
      return;
    }
    const currentRevision = ++revision.current;
    request.current?.abort();
    request.current = new AbortController();
    setBusy('validate');
    try {
      const result = await apiRequest(`${ledgerPath(ledgerId)}/validate-snapshot`, {
        method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: file,
        signal: request.current.signal,
      });
      if (revision.current !== currentRevision) return;
      if (result.compared_head && headHash && result.compared_head !== headHash) {
        throw new Error('The chain changed while checking. Wait for the live view to update and check the file again.');
      }
      onReport(result);
    } catch (requestError) {
      if (revision.current !== currentRevision || requestError.name === 'AbortError') return;
      // An unauthenticated encrypted file cannot identify a trustworthy block index.
      setError(`${requestError.message} No individual block is marked as changed from this file.`);
    } finally {
      if (revision.current === currentRevision) setBusy('');
    }
  }

  function dismiss() {
    setError(''); onReport(null);
  }
  return <div className="snapshot-controls">
    <div className="toolbar-actions"><button onClick={download} disabled={!canDownload || Boolean(busy)}>{busy === 'download' ? 'Downloading…' : 'Download ledger'}</button><button onClick={() => fileInput.current.click()} disabled={!connected || Boolean(busy)}>{busy === 'validate' ? 'Checking…' : 'Validate file'}</button><input ref={fileInput} className="file-input" type="file" accept=".ledger" aria-label="Choose encrypted ledger file" onChange={validate}/></div>
    {(error || report) && <section className={`validation-result ${error || !report?.valid ? 'warning' : ''}`} aria-live="polite">
      <button className="dismiss" onClick={dismiss} aria-label="Dismiss validation result">×</button>
      {error ? <p role="alert">{error}</p> : <><strong>{report.valid ? 'Saved records match' : 'Differences found'}</strong><p>{report.message}</p><small>{report.checked_blocks} saved blocks checked · {report.server_blocks} blocks on server{report.new_blocks > 0 ? ` · ${report.new_blocks} newer blocks` : ''}</small>{Array.isArray(report.errors) && report.errors.length > 0 && <ul>{report.errors.map((finding, index) => <li key={index}>Block {finding.index ?? '—'}: {finding.message}</li>)}</ul>}</>}
    </section>}
  </div>;
}
