import { useEffect, useState } from 'react';
import { apiRequest, ledgerPath } from '../api.js';
import { LedgerRows } from './LedgerList.jsx';
import CreateLedger from './CreateLedger.jsx';

function Integration({ ledger, initial, onClose }) {
  const [details, setDetails] = useState(initial || null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (initial) return undefined;
    const controller = new AbortController();
    apiRequest(`${ledgerPath(ledger.id)}/credentials`, { signal: controller.signal }).then(setDetails).catch(requestError => {
      if (!controller.signal.aborted) setError(requestError.message);
    });
    return () => controller.abort();
  }, [ledger.id, initial]);

  async function rotate() {
    if (!window.confirm('Replace this ledger’s write token? The old token will stop working immediately.')) return;
    setBusy(true); setError('');
    try {
      setDetails(await apiRequest(`${ledgerPath(ledger.id)}/rotate-token`, { method: 'POST', body: '{}' }));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }
  const path = details?.write_path;
  const endpoint = path ? new URL(path, window.location.origin).href : '';
  return <section className="form-panel integration-panel">
    <div className="details-heading"><h2>Integration · {ledger.name}</h2><button onClick={onClose}>Close</button></div>
    <p>Only you, the creator, can open these integration settings. Keep the bearer token private.</p>
    {error && <p className="inline-error" role="alert">{error}</p>}
    {endpoint && <label>Write endpoint<input readOnly value={endpoint}/></label>}
    {details?.write_token ? <><p className="notice warning">Save this token now. It is shown only until you close this panel. It is not saved in browser storage.</p><label>Bearer token<textarea readOnly spellCheck="false" value={details.write_token}/></label></> : details && <p className="muted">The saved token cannot be retrieved. {details.token_hint && `Hint: ${details.token_hint}`} Rotate it if you have lost it.</p>}
    {endpoint && <details><summary>Request format</summary><p>Send JSON using your secret token as the Authorization header. The data object must follow the ledger’s fixed structure.</p><pre>{`POST ${endpoint}\nAuthorization: Bearer YOUR_SECRET_TOKEN\nContent-Type: application/json\n\n${JSON.stringify({ match_id: 'record-001', data: Object.fromEntries((ledger.fields || []).map(field => [field.name, field.type === 'integer' ? 1 : field.type === 'boolean' ? true : field.type === 'object' ? {} : field.type === 'array' ? [] : 'example'])) }, null, 2)}`}</pre></details>}
    <button disabled={busy || !details} onClick={rotate}>{busy ? 'Replacing…' : 'Rotate write token'}</button>
  </section>;
}

function AdminEdit({ ledger, onSaved, onClose }) {
  const [name, setName] = useState(ledger.name);
  const [description, setDescription] = useState(ledger.description);
  const [state, setState] = useState(ledger.state);
  const [confirmation, setConfirmation] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      await apiRequest(ledgerPath(ledger.id), { method: 'PATCH', body: JSON.stringify({ name, description, state }) });
      onSaved();
    } catch (requestError) { setError(requestError.message); } finally { setBusy(false); }
  }
  async function remove() {
    if (confirmation !== ledger.name) return;
    setBusy(true); setError('');
    try {
      await apiRequest(ledgerPath(ledger.id), { method: 'DELETE', body: JSON.stringify({ confirm: confirmation }) });
      onSaved();
    } catch (requestError) { setError(requestError.message); } finally { setBusy(false); }
  }
  return <section className="form-panel">
    <div className="details-heading"><h2>Manage · {ledger.name}</h2><button disabled={busy} onClick={onClose}>Close</button></div>
    <p>Admin changes affect the ledger’s label and availability. Stored blocks and their structure remain immutable.</p>
    <form onSubmit={submit}>
      <label>Name<input required maxLength={80} value={name} onChange={event => setName(event.target.value)}/></label>
      <label>Description<textarea maxLength={500} value={description} onChange={event => setDescription(event.target.value)}/></label>
      <label>State<select value={state} onChange={event => setState(event.target.value)}><option value="active">Active · writes allowed</option><option value="read_only">Read-only · no new blocks</option><option value="archived">Archived · no new blocks</option></select></label>
      <button disabled={busy}>Save changes</button>
    </form>
    <details className="delete-section"><summary>Delete this ledger</summary><p>Deleting removes this ledger and its encryption key. Its downloaded snapshots can no longer be validated. This cannot be undone.</p><label>Type “{ledger.name}” to confirm<input value={confirmation} onChange={event => setConfirmation(event.target.value)}/></label><button className="danger" disabled={busy || confirmation !== ledger.name} onClick={remove}>Delete ledger permanently</button></details>
    {error && <p className="inline-error" role="alert">{error}</p>}
  </section>;
}

export default function LedgerManager({ user, onOpen }) {
  const [ledgers, setLedgers] = useState([]);
  const [refresh, setRefresh] = useState(0);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);
  const [integration, setIntegration] = useState(null);
  const [editing, setEditing] = useState(null);
  useEffect(() => {
    const controller = new AbortController();
    setBusy(true);
    apiRequest('/api/my-ledgers', { signal: controller.signal }).then(result => {
      setLedgers(result.ledgers); setError('');
    }).catch(requestError => {
      if (!controller.signal.aborted) setError(requestError.message);
    }).finally(() => { if (!controller.signal.aborted) setBusy(false); });
    return () => controller.abort();
  }, [refresh]);
  function changed() { setEditing(null); setRefresh(value => value + 1); }
  return <section>
    <header className="toolbar"><h1>{user.is_admin ? 'Manage all ledgers' : 'My ledgers'}</h1><div className="button-row"><button disabled={busy} onClick={() => setRefresh(value => value + 1)}>Refresh</button><button className="primary" onClick={() => { setCreating(true); setIntegration(null); setEditing(null); }}>Create ledger</button></div></header>
    {error && <p className="notice warning" role="alert">{error}</p>}
    {creating && <CreateLedger onCancel={() => setCreating(false)} onCreated={result => { setCreating(false); setIntegration({ ledger: result.ledger, initial: result }); setRefresh(value => value + 1); }}/>}
    {integration && <Integration key={integration.ledger.id} ledger={integration.ledger} initial={integration.initial} onClose={() => setIntegration(null)}/>}
    {editing && <AdminEdit key={editing.id} ledger={editing} onSaved={changed} onClose={() => setEditing(null)}/>}
    {busy && <p>Loading your ledgers…</p>}
    <LedgerRows ledgers={ledgers} onOpen={onOpen}>{ledger => <>
      {(ledger.is_owner || (!user.is_admin && ledger.is_owner !== false)) && <button onClick={() => { setIntegration({ ledger }); setEditing(null); setCreating(false); }}>Integration</button>}
      {user.is_admin && <button onClick={() => { setEditing(ledger); setIntegration(null); setCreating(false); }}>Manage</button>}
    </>}</LedgerRows>
    {!busy && !ledgers.length && <p className="empty-chain">You have not created a ledger yet.</p>}
  </section>;
}



