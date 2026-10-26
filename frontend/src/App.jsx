import { useEffect, useState } from 'react';
import { apiRequest } from './api.js';
import Account from './components/Account.jsx';
import LedgerList from './components/LedgerList.jsx';
import LedgerManager from './components/LedgerManager.jsx';
import LedgerViewer from './components/LedgerViewer.jsx';

export default function App() {
  const [user, setUser] = useState(null);
  const [page, setPage] = useState('home');
  const [ledgerId, setLedgerId] = useState(null);
  const [error, setError] = useState('');
  const [sessionLoading, setSessionLoading] = useState(true);

  useEffect(() => {
    function expired() {
      setUser(null);
      setPage('account');
      setError('Your session ended. Log in again to manage your ledgers.');
    }
    window.addEventListener('session-expired', expired);
    return () => window.removeEventListener('session-expired', expired);
  }, []);

  useEffect(() => {
    let stopped = false;
    apiRequest('/api/me').then(result => {
      if (!stopped) setUser(result.user);
    }).catch(requestError => {
      if (!stopped) setError(requestError.message);
    }).finally(() => {
      if (!stopped) setSessionLoading(false);
    });
    return () => { stopped = true; };
  }, []);

  function navigate(next) {
    setError('');
    setPage(next);
  }

  async function logout() {
    try {
      await apiRequest('/api/logout', { method: 'POST', body: '{}' });
      setUser(null);
      navigate('home');
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  return <main className="ledger-page">
    <nav className="page-nav" aria-label="Main navigation">
      <button onClick={() => navigate('home')}>Home</button>
      <div className="nav-account">
        {user ? <><span>{user.username}{user.is_admin ? ' - Admin' : ''}</span><button onClick={() => navigate('manage')}>{user.is_admin ? 'Manage ledgers' : 'My ledgers'}</button><button onClick={logout}>Log out</button></>
          : <button disabled={sessionLoading} onClick={() => navigate('account')}>Log in</button>}
      </div>
    </nav>
    {error && <p className="notice warning" role="alert">{error}</p>}
    {page === 'home' && <section className="welcome">
      <h1 className="brand-heading"><img src="/ledger-mark.svg" width="48" height="48" alt=""/>Ledger</h1><p>Explore linked records, or sign in to create your own ledger.</p>
      <div className="welcome-options">
        <button onClick={() => navigate('browse')}><strong>View ledgers</strong><span>Browse public records and check a saved snapshot. No account needed.</span></button>
        <button disabled={sessionLoading} onClick={() => navigate(user ? 'manage' : 'account')}><strong>{user ? 'My ledgers' : 'Log in / Create account'}</strong><span>Create a ledger with your own block structure and a private write token.</span></button>
      </div>
    </section>}
    {page === 'account' && <Account onSuccess={nextUser => { setUser(nextUser); navigate('manage'); }}/>}
    {page === 'browse' && <LedgerList onOpen={id => { setLedgerId(id); navigate('view'); }}/>}
    {page === 'manage' && user && <LedgerManager key={user.id} user={user} onOpen={id => { setLedgerId(id); navigate('view'); }}/>}
    {page === 'view' && ledgerId && <LedgerViewer key={ledgerId} ledgerId={ledgerId} onBack={() => navigate('browse')}/>}
  </main>;
}
