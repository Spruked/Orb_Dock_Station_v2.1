import React, { useState, useEffect } from 'react';
import { diagnostics } from '../services/api';
export default function Diagnostics() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [clock, setClock] = useState(Date.now());
  useEffect(() => {
    let active = true, timer;
    async function load() {
      try { const result = await diagnostics.snapshot(); if (active) { setData(result); setError(''); } }
      catch { if (active) setError('Telemetry unavailable; previous measurements may be stale.'); }
      if (active) timer = setTimeout(load, 5000);
    }
    load();
    const tick = setInterval(() => setClock(Date.now()), 1000);
    return () => { active = false; clearTimeout(timer); clearInterval(tick); };
  }, []);
  return <div className="p-6" style={{ maxWidth: 1100 }}>
    <h1>Diagnostics</h1><p className="text-secondary">Measured evidence and explicit unknowns. Refreshes every five seconds.</p>
    {error && <p role="alert">{error}</p>}{!data && <p>Measurements: unknown</p>}
    {Object.entries(data?.sections || {}).map(([section, metrics]) => <section className="card mb-4" key={section}>
      <h2 className="card-title">{section}</h2><div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', textAlign: 'left' }}><thead><tr><th>Measurement</th><th>Value</th><th>Measured / age</th><th>Source</th></tr></thead>
      <tbody>{Object.entries(metrics).map(([key, item]) => {
        const age = item.measured_at ? Math.max(0, (clock - Date.parse(item.measured_at)) / 1000) : null;
        const stale = age !== null && age > data.stale_after_seconds;
        const known = item.status === 'measured' && item.value !== null;
        return <tr key={key} title={item.reason || ''}><td style={{ padding: '8px 6px' }}>{key.replaceAll('_', ' ')}</td>
          <td>{!known ? 'unknown' : stale ? 'unknown (stale)' : typeof item.value === 'object' ? JSON.stringify(item.value) : String(item.value)}</td>
          <td>{age === null ? 'unknown' : <>{new Date(item.measured_at).toLocaleString()} / {Math.floor(age)}s{stale && <div>Last value: {JSON.stringify(item.value)}</div>}</>}</td>
          <td>{item.source}</td></tr>;
      })}</tbody></table></div></section>)}
  </div>;
}
