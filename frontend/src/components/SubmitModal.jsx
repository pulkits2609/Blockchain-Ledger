import { useEffect, useRef, useState } from 'react';
import { apiRequest } from '../api.js';
import { freshExample } from '../ledgerHelpers.js';

export default function SubmitModal({ onClose, onSaved }) {
  const [text, setText] = useState(() => JSON.stringify(freshExample(), null, 2));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const dialogRef = useRef(null);
  const closeRef = useRef(onClose);
  const savingRef = useRef(false);
  closeRef.current = onClose;
  savingRef.current = saving;

  useEffect(() => {
    const previousFocus = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    dialogRef.current.querySelector('textarea').focus();
    function handleKey(event) {
      if (event.key === 'Escape' && !savingRef.current) closeRef.current();
      if (event.key !== 'Tab') return;
      const focusable = [...dialogRef.current.querySelectorAll('button:not(:disabled), textarea:not(:disabled), a[href]')];
      const first = focusable[0];
      const last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }
    document.addEventListener('keydown', handleKey);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', handleKey);
      previousFocus?.focus();
    };
  }, []);

  async function submit(event) {
    event.preventDefault();
    setError('');
    try {
      const request = JSON.parse(text);
      if (!request || typeof request !== 'object' || Array.isArray(request)) throw new Error('The request must be a JSON object.');
      if (typeof request.match_id !== 'string' || !request.match_id.trim()) throw new Error('Add a non-empty match_id string.');
      if (!request.data || typeof request.data !== 'object' || Array.isArray(request.data)) throw new Error('Add a data object containing the result.');
      setSaving(true);
      const result = await apiRequest('/api/blocks', { method: 'POST', body: text });
      onSaved(result);
    } catch (requestError) {
      setError(requestError.message);
      setSaving(false);
    }
  }

  return <div className="modal-backdrop"><section ref={dialogRef} className="modal" role="dialog" aria-modal="true" aria-labelledby="submit-title"><div className="modal-heading"><div><div className="eyebrow">APPEND A REAL RECORD</div><h2 id="submit-title">New match result</h2></div><button className="close-button" onClick={onClose} disabled={saving} aria-label="Close result submission">×</button></div><p>Edit the example or paste a finalized result. Submitting writes to the saved ledger; it is not a preview.</p><form onSubmit={submit}><label htmlFor="result-json">JSON request body</label><textarea id="result-json" value={text} onChange={event => setText(event.target.value)} spellCheck="false" rows={16} disabled={saving}/>{error && <div className="error-box" role="alert">{error}</div>}<div className="modal-footer"><button type="button" className="secondary-button" onClick={onClose} disabled={saving}>Cancel</button><button type="submit" className="primary-button" disabled={saving}>{saving ? 'Recording…' : 'Record result →'}</button></div></form></section></div>;
}
