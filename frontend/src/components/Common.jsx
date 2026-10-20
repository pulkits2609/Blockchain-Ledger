import { useEffect, useState } from 'react';

export function CopyButton({ value, label = 'Copy', className = 'text-button' }) {
  const [message, setMessage] = useState('');
  useEffect(() => {
    if (!message) return;
    const timer = window.setTimeout(() => setMessage(''), 2300);
    return () => window.clearTimeout(timer);
  }, [message]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setMessage('Copied');
    } catch {
      setMessage('Copy unavailable');
    }
  }
  return <button type="button" className={className} onClick={copy} aria-label={label}>{message || label}</button>;
}

export function BrandMark() {
  return <svg width="32" height="34" viewBox="0 0 32 34" fill="none" aria-hidden="true"><path d="M16 2 29 9.5v15L16 32 3 24.5v-15L16 2Z" stroke="currentColor" strokeWidth="1.5"/><path d="m3 9.5 13 7.6 13-7.6M16 17v15M9.5 5.8l13 7.6v7.8l-6.5 3.7-6.5-3.7v-7.8L16 9.6" stroke="currentColor" strokeWidth="1.5"/></svg>;
}

export function VerificationReport({ report, busy = false }) {
  if (busy) return <div className="notice">Recalculating hashes and checking links…</div>;
  if (!report) return null;
  const valid = report.valid === true;
  return <div className={`verification-report ${valid ? 'is-valid' : 'is-invalid'}`} role="status">
    <span className="report-symbol" aria-hidden="true">{valid ? '✓' : '!'}</span>
    <div>
      <strong>{valid ? 'Chain is internally consistent' : 'Verification found an inconsistency'}</strong>
      <p>{report.checked_blocks ?? 0} blocks checked. {valid ? 'Stored hashes and previous-hash links agree.' : 'Review the exact findings below.'}</p>
      {!valid && <ul>{(report.errors || []).map((error, index) => <li key={index}>{error.index !== null && error.index !== undefined ? `Block ${error.index}: ` : ''}{error.message}</li>)}</ul>}
    </div>
  </div>;
}

