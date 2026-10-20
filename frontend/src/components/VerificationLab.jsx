import { useState } from 'react';
import { apiRequest } from '../api.js';
import { blockTitle, isGenesis } from '../ledgerHelpers.js';
import { VerificationReport } from './Common.jsx';

export default function VerificationLab({ blocks, connected, onVerify, verifying, verifyReport, verificationError }) {
  const [copyBlocks, setCopyBlocks] = useState(null);
  const [copyIndex, setCopyIndex] = useState(null);
  const [editedData, setEditedData] = useState('');
  const [copyReport, setCopyReport] = useState(null);
  const [copyError, setCopyError] = useState('');
  const [checkingCopy, setCheckingCopy] = useState(false);
  const [checkpointMessage, setCheckpointMessage] = useState('');

  function createCopy() {
    const copy = structuredClone(blocks);
    const firstMatch = copy.find(block => !isGenesis(block));
    setCopyBlocks(copy);
    setCopyIndex(firstMatch?.index ?? null);
    setEditedData(firstMatch ? JSON.stringify(firstMatch.data, null, 2) : '');
    setCopyReport(null);
    setCopyError('');
  }

  function chooseBlock(index) {
    const block = copyBlocks.find(item => item.index === Number(index));
    setCopyIndex(block.index);
    setEditedData(JSON.stringify(block.data, null, 2));
    setCopyReport(null);
  }

  async function verifyCopy() {
    setCopyError('');
    setCopyReport(null);
    try {
      const data = JSON.parse(editedData);
      if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('Result data must be a JSON object.');
      // Keep the edited JSON text intact so Python can reject duplicate keys and
      // unsupported numbers instead of accepting JavaScript-normalized values.
      const records = copyBlocks.map(block => {
        if (block.index !== copyIndex) return JSON.stringify(block);
        const { data: originalData, ...fields } = block;
        const serializedFields = JSON.stringify(fields);
        return serializedFields.slice(0, -1) + ',"data":' + editedData + '}';
      });
      const requestBody = '{"blocks":[' + records.join(',') + ']}';
      setCheckingCopy(true);
      const report = await apiRequest('/api/verify', { method: 'POST', body: requestBody });
      setCopyReport(report);
    } catch (error) {
      setCopyError(error.message);
    } finally {
      setCheckingCopy(false);
    }
  }

  async function downloadCheckpoint() {
    setCheckpointMessage('');
    try {
      const checkpoint = await apiRequest('/api/checkpoint');
      const url = URL.createObjectURL(new Blob([JSON.stringify(checkpoint, null, 2) + '\n'], { type: 'application/json' }));
      const link = document.createElement('a');
      link.href = url;
      link.download = `ledger-checkpoint-${checkpoint.index}.json`;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      setCheckpointMessage('Checkpoint downloaded. Keep a trusted copy outside the ledger folder.');
    } catch (error) {
      setCheckpointMessage(error.message);
    }
  }

  return <div className="lab-layout"><section className="panel lab-panel"><div className="panel-heading"><div><div className="eyebrow">01 / CHECK THE ORIGINAL</div><h2>Verify saved history</h2></div></div><p>Recalculate each record’s hash, then check its index and link to the previous record. This reads the ledger on disk without changing it.</p><button className="primary-button" onClick={onVerify} disabled={!connected || verifying}>{verifying ? 'Verifying…' : 'Verify saved chain'}</button>{verificationError && <div className="error-box" role="alert">{verificationError}</div>}<VerificationReport report={verifyReport}/><div className="explanation"><h3>What does “valid” mean?</h3><p>The supplied records are internally consistent. A local hash chain does not stop its owner from rebuilding all the hashes after editing history.</p></div><div className="checkpoint-box"><div><h3>Keep a trusted fingerprint</h3><p>Export the current index and hash for independent comparison later. Downloading alone does not make a checkpoint trusted.</p></div><button className="secondary-button" onClick={downloadCheckpoint} disabled={!connected}>Export checkpoint ↓</button></div>{checkpointMessage && <p className="action-message" role="status">{checkpointMessage}</p>}</section>
      <section className="panel lab-panel"><div className="panel-heading"><div><div className="eyebrow">02 / TRY A SAFE EXPERIMENT</div><h2>The tamper lab <span className="quiet-badge">COPY ONLY</span></h2></div></div><p>Change a score in a browser-only copy, leaving its stored hash untouched. Verification should identify the mismatch. The saved ledger is never edited.</p><button className="secondary-button" onClick={createCopy} disabled={!connected || blocks.length < 2 || checkingCopy}>{copyBlocks ? 'Reset from saved chain' : 'Create a test copy'}</button>{blocks.length < 2 && <p className="muted small">Record at least one match to try this experiment.</p>}
      {copyBlocks && copyIndex !== null && <div className="copy-editor"><label htmlFor="copy-block">Record to change</label><select id="copy-block" value={copyIndex} onChange={event => chooseBlock(event.target.value)} disabled={checkingCopy}>{copyBlocks.filter(block => !isGenesis(block)).map(block => <option key={block.index} value={block.index}>#{block.index} · {blockTitle(block)}</option>)}</select><label htmlFor="copy-data">Result data in the test copy</label><textarea id="copy-data" spellCheck="false" rows={12} value={editedData} onChange={event => { setEditedData(event.target.value); setCopyReport(null); }} disabled={checkingCopy}/><button className="primary-button" onClick={verifyCopy} disabled={!connected || checkingCopy}>{checkingCopy ? 'Checking copy…' : 'Verify edited copy'}</button>{copyError && <div className="error-box" role="alert">{copyError}</div>}<VerificationReport report={copyReport}/></div>}
      </section></div>;
}

