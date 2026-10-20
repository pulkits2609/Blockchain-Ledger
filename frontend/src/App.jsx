import { useEffect, useState } from 'react';
import { apiRequest, useLedger } from './api.js';
import { blockTitle } from './ledgerHelpers.js';
import { BrandMark, VerificationReport } from './components/Common.jsx';
import Explorer from './components/Explorer.jsx';
import VerificationLab from './components/VerificationLab.jsx';
import ApiGuide from './components/ApiGuide.jsx';
import SubmitModal from './components/SubmitModal.jsx';

export default function App() {
  const { ledger, connection, error, lastReceived, refresh } = useLedger();
  const [view, setView] = useState('explorer');
  const [selectedIndex, setSelectedIndex] = useState(null);
  const [showSubmit, setShowSubmit] = useState(false);
  const [notice, setNotice] = useState('');
  const [verifying, setVerifying] = useState(false);
  const [verifyReport, setVerifyReport] = useState(null);
  const [verificationError, setVerificationError] = useState('');
  const savedBlocks = Array.isArray(ledger?.blocks) ? ledger.blocks : [];
  // Broken records remain in the verifier's findings, but cannot become clickable cards.
  const blocks = savedBlocks.filter(block => block && typeof block === 'object' && !Array.isArray(block) && Number.isSafeInteger(block.index) && block.index >= 0 && typeof block.hash === 'string' && typeof block.previous_hash === 'string');
  const malformedCount = savedBlocks.length - blocks.length;
  const ledgerSignature = JSON.stringify([savedBlocks, ledger?.verification]);
  useEffect(() => {
    setVerifyReport(null);
    setVerificationError('');
  }, [ledgerSignature, connection]);
  const titles = { explorer: ['Live ledger', 'Final results. A history you can inspect.'], verification: ['Verification lab', 'Follow the hashes. Understand the evidence.'], api: ['Connect your application', 'A separate ledger, with one simple entry point.'] };

  async function verifySaved() {
    setVerifying(true);
    setVerificationError('');
    setVerifyReport(null);
    try {
      const report = await apiRequest('/api/verify', { method: 'POST', body: '{}' });
      setVerifyReport(report);
      refresh();
    } catch (requestError) {
      setVerificationError(requestError.message);
    } finally {
      setVerifying(false);
    }
  }

  function saved(result) {
    setShowSubmit(false);
    setView('explorer');
    setSelectedIndex(result.block.index);
    setNotice(result.duplicate ? `Already recorded: ${blockTitle(result.block)}. No duplicate block was added.` : `${blockTitle(result.block)} recorded as block #${result.block.index}.`);
    setVerifyReport(null);
    refresh();
  }

  return <div className="app-shell"><aside className="sidebar"><a className="brand" href="#explorer" onClick={event => { event.preventDefault(); setView('explorer'); }}><BrandMark/><span>ledger<span className="brand-dot">.</span><small>MATCH RESULT ARCHIVE</small></span></a><div className="sidebar-rule"/><div className="nav-caption">WORKSPACE</div><nav aria-label="Main navigation">{[['explorer', '▦', 'Ledger explorer'], ['verification', '◈', 'Verification lab'], ['api', '⌁', 'API & integration']].map(([id, icon, title]) => <button key={id} onClick={() => { setView(id); setNotice(''); }} className={view === id ? 'active-nav' : ''} aria-current={view === id ? 'page' : undefined}><span aria-hidden="true">{icon}</span>{title}{view === id && <span className="nav-indicator"/>}</button>)}</nav><div className="sidebar-bottom"><div className="project-label"><span className="tiny-dot"/> SINGLE-WRITER LEDGER</div><p>Transparent records.<br/>Verifiable history.</p><div className="sidebar-footnote">Academic prototype <span>v0.1</span></div></div></aside>
    <main className="main-content"><div className="topbar"><div className="breadcrumb">WORKSPACE <span>/</span> {view === 'explorer' ? 'EXPLORER' : view === 'verification' ? 'VERIFICATION' : 'INTEGRATION'}</div><div className={`connection ${connection}`}><span className="tiny-dot"/>{connection === 'online' ? 'Live · updates every 1.5s' : connection === 'loading' ? 'Connecting to server…' : 'Offline · updates paused'}</div></div><header className="page-heading"><div><div className="eyebrow">PRIVATE CHAIN / MATCH RECORDS</div><h1>{titles[view][0]}</h1><p>{titles[view][1]}</p></div><button className="primary-button new-result-button" onClick={() => setShowSubmit(true)} disabled={connection !== 'online'}><span aria-hidden="true">+</span> New result</button></header>
      {connection === 'offline' && <div className="connection-error" role="alert"><div><strong>Ledger server unavailable{ledger ? ' · showing the last received data' : ''}</strong><p>{error} {lastReceived && `Last response: ${lastReceived.toLocaleTimeString()}.`}</p></div><button className="secondary-button" onClick={refresh}>Retry connection</button></div>}
      {notice && <div className="success-notice" role="status"><span>✓ {notice}</span><button className="text-button" onClick={() => setNotice('')} aria-label="Dismiss recording notice">Dismiss</button></div>}
      {verificationError && view === 'explorer' && <div className="error-box" role="alert">{verificationError}</div>}
      {connection === 'online' && ledger?.verification?.valid === false && <VerificationReport report={ledger.verification}/>}
      {malformedCount > 0 && <div className="error-box">{malformedCount} malformed record(s) cannot be displayed as blocks. Review the verification findings; saved data has not been changed.</div>}
      {view === 'explorer' && <Explorer blocks={blocks} verification={ledger?.verification} connection={connection} selectedIndex={selectedIndex} setSelectedIndex={setSelectedIndex} onVerify={verifySaved} verifying={verifying} verifyReport={verifyReport}/>}
      {view === 'verification' && <VerificationLab blocks={blocks} connected={connection === 'online'} onVerify={verifySaved} verifying={verifying} verifyReport={verifyReport} verificationError={verificationError}/>}
      {view === 'api' && <ApiGuide onSubmit={() => setShowSubmit(true)}/>}
      <footer className="page-footer"><span>Centralized by design. Independently verifiable.</span><span>{connection === 'online' && lastReceived ? `Last received ${lastReceived.toLocaleTimeString()}` : 'Awaiting a live server response'}</span></footer>
    </main>{showSubmit && <SubmitModal onClose={() => setShowSubmit(false)} onSaved={saved}/>}</div>;
}
