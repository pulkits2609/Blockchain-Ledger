import { useRef, useState } from 'react';
import { apiRequest, downloadSnapshot } from '../api.js';

const MaximumSnapshotBytes = 8 * 1024 * 1024;

export default function SnapshotControls({ connected, canDownload }) {
  const fileInput = useRef(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [report, setReport] = useState(null);

  async function download() {
    setBusy('download');
    setError('');
    try {
      await downloadSnapshot();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy('');
    }
  }

  async function validate(event) {
    const file = event.target.files[0];
    // Reset so the same file can be checked again after the server changes.
    event.target.value = '';
    if (!file) return;
    setError('');
    setReport(null);
    if (file.size > MaximumSnapshotBytes) {
      setError('Choose a ledger file smaller than 8 MiB.');
      return;
    }
    setBusy('validate');
    try {
      const result = await apiRequest('/api/validate-snapshot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/octet-stream' },
        body: file,
      });
      setReport(result);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy('');
    }
  }

  return <div className="snapshot-controls">
    <div className="toolbar-actions"><button onClick={download} disabled={!canDownload || Boolean(busy)}>{busy === 'download' ? 'Downloading…' : 'Download ledger'}</button><button onClick={() => fileInput.current.click()} disabled={!connected || Boolean(busy)}>{busy === 'validate' ? 'Checking…' : 'Validate file'}</button><input ref={fileInput} className="file-input" type="file" accept=".ledger" aria-label="Choose encrypted ledger file" onChange={validate}/></div>
    {(error || report) && <section className={`validation-result ${error || !report?.valid ? 'warning' : ''}`} aria-live="polite">
      <button className="dismiss" onClick={() => { setError(''); setReport(null); }} aria-label="Dismiss validation result">×</button>
      {error ? <p role="alert">{error}</p> : <><strong>{report.valid ? 'Saved copy matches' : 'Saved copy did not validate'}</strong><p>{report.message}</p><small>{report.checked_blocks} saved blocks checked · {report.server_blocks} blocks on server{report.valid && report.new_blocks > 0 ? ` · ${report.new_blocks} newer blocks` : ''}</small>{Array.isArray(report.errors) && report.errors.length > 0 && <ul>{report.errors.map((finding, index) => <li key={index}>Block {finding.index ?? '—'}: {finding.message}</li>)}</ul>}</>}
    </section>}
  </div>;
}
