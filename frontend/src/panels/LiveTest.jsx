import React, { useState } from 'react';
import { liveTest } from '../services/api';

export default function LiveTest({ profileId }) {
  const [session, setSession] = useState(null);
  const [text, setText] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function start() {
    if (!profileId) return;
    setBusy(true); setError('');
    try { setSession(await liveTest.start(profileId)); } catch (reason) { setError(String(reason)); } finally { setBusy(false); }
  }

  async function speak(event) {
    event.preventDefault();
    if (!session || !text.trim()) return;
    setBusy(true); setError('');
    try { setSession(await liveTest.speak(session.session_id, text.trim())); setText(''); } catch (reason) { setError(String(reason)); } finally { setBusy(false); }
  }

  return <div className="p-6" style={{maxWidth:900}}>
    <h1>Live Test</h1>
    <div className="card" style={{marginTop:16}}>
      <h2>Real Orbot runtime session</h2>
      <p className="text-secondary">This panel uses the authenticated Communication runtime. It does not generate simulated speech, intent, tools, pointer targets, or success results.</p>
      {!session && <button className="btn btn-primary" disabled={!profileId || busy} onClick={start}>{busy ? 'Starting…' : 'Start real session'}</button>}
      {session && <>
        <p className="text-secondary">Session: {session.session_id} · {session.status}</p>
        <form onSubmit={speak} className="flex gap-3" style={{marginTop:16}}>
          <input className="input" value={text} onChange={event => setText(event.target.value)} placeholder="Send text to CALI" />
          <button className="btn btn-primary" disabled={busy || !text.trim()}>{busy ? 'Waiting…' : 'Send'}</button>
        </form>
        {session.transcript?.length > 0 && <div style={{marginTop:16}}>{session.transcript.map((item, index) => <p key={index}><strong>{item.speaker}:</strong> {item.text}</p>)}</div>}
      </>}
      {error && <p role="alert" style={{marginTop:16}}>{error}</p>}
    </div>
  </div>;
}
