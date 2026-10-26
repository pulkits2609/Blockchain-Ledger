import { useState } from 'react';
import { apiRequest } from '../api.js';

const FieldTypes = ['string', 'integer', 'boolean', 'object', 'array'];

export default function CreateLedger({ onCreated, onCancel }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [fields, setFields] = useState([{ name: 'title', type: 'string', required: true }]);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  function change(index, key, value) {
    setConfirmed(false);
    setFields(current => current.map((field, position) => position === index ? { ...field, [key]: value } : field));
  }
  async function create(event) {
    event.preventDefault();
    if (!confirmed) return;
    setBusy(true); setError('');
    try {
      const result = await apiRequest('/api/ledgers', { method: 'POST', body: JSON.stringify({ name, description, fields }) });
      onCreated(result);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  return <section className="form-panel">
    <h2>Create a ledger</h2>
    <form onSubmit={create}>
      <label>Name<input required maxLength={80} value={name} onChange={event => setName(event.target.value)}/></label>
      <label>Description<textarea maxLength={500} value={description} onChange={event => setDescription(event.target.value)}/></label>
      <h3>Block data structure</h3><p className="muted">Each new record must follow these fields. Use integer units for fractional amounts; floating-point values are not supported. Objects and arrays contain JSON values.</p>
      <div className="schema-fields">{fields.map((field, index) => <div className="schema-field" key={index}>
        <label>Field name<input required pattern="[A-Za-z_][A-Za-z0-9_]*" maxLength={64} value={field.name} onChange={event => change(index, 'name', event.target.value)}/></label>
        <label>Type<select value={field.type} onChange={event => change(index, 'type', event.target.value)}>{FieldTypes.map(type => <option key={type}>{type}</option>)}</select></label>
        <label className="check-label"><input type="checkbox" checked={field.required} onChange={event => change(index, 'required', event.target.checked)}/>Required</label>
        <button type="button" disabled={fields.length === 1 || busy} onClick={() => { setFields(current => current.filter((_, position) => position !== index)); setConfirmed(false); }}>Remove</button>
      </div>)}</div>
      <button type="button" disabled={fields.length >= 32 || busy} onClick={() => { setFields(current => [...current, { name: '', type: 'string', required: true }]); setConfirmed(false); }}>Add field</button>
      <label className="check-label schema-confirm"><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)}/>I understand that genesis and this structure cannot be changed after creation.</label>
      {error && <p className="inline-error" role="alert">{error}</p>}
      <div className="button-row"><button className="primary" disabled={busy || !confirmed}>{busy ? 'Creating…' : 'Create ledger'}</button><button type="button" disabled={busy} onClick={onCancel}>Cancel</button></div>
    </form>
  </section>;
}
