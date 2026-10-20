import { useEffect, useState } from 'react';

const POLL_DELAY_MS = 1500;

export async function apiRequest(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
  });
  let body;
  try {
    body = await response.json();
  } catch {
    throw new Error('The server did not return JSON. Check that the Python ledger server is running.');
  }
  if (!response.ok) {
    throw new Error(body.error || `Request failed (${response.status}).`);
  }
  return body;
}

export function useLedger() {
  const [ledger, setLedger] = useState(null);
  const [connection, setConnection] = useState('loading');
  const [error, setError] = useState('');
  const [lastReceived, setLastReceived] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let stopped = false;
    let timer;
    let controller;
    let requestTimeout;

    async function readLedger() {
      controller = new AbortController();
      requestTimeout = window.setTimeout(() => controller.abort(), 5000);
      try {
        const result = await apiRequest('/api/ledger', { signal: controller.signal });
        if (stopped) return;
        setLedger(result);
        setConnection('online');
        setError('');
        setLastReceived(new Date());
      } catch (requestError) {
        if (stopped) return;
        setConnection('offline');
        setError(requestError.name === 'AbortError' ? 'The ledger server did not respond within five seconds.' : requestError.message);
      } finally {
        window.clearTimeout(requestTimeout);
        // Wait until this request finishes: a slow server must not pile up polls.
        if (!stopped) timer = window.setTimeout(readLedger, POLL_DELAY_MS);
      }
    }

    readLedger();
    return () => {
      stopped = true;
      controller?.abort();
      window.clearTimeout(requestTimeout);
      window.clearTimeout(timer);
    };
  }, [refreshKey]);

  return { ledger, connection, error, lastReceived, refresh: () => setRefreshKey(value => value + 1) };
}
