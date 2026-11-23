import React, { useState, useEffect, useRef } from 'react';
import { diagnostics } from '../services/api';
export default function Diagnostics() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [clock, setClock] = useState(Date.now());
  const [activeSection, setActiveSection] = useState('');
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem('orb-diagnostics-chat') || '[]'); } catch { return []; }
  });
  const [chatSessionId, setChatSessionId] = useState(() => sessionStorage.getItem('orb-diagnostics-chat-session') || '');
  const [chatBusy, setChatBusy] = useState(false);
  const [chatError, setChatError] = useState('');
  const [chatSessions, setChatSessions] = useState([]);
  const [chatRecords, setChatRecords] = useState(null);
  const [chatProvider, setChatProvider] = useState('Provider/model: awaiting response');
  const [chatCollapsed, setChatCollapsed] = useState(false);
  const chatAbort = useRef(null);
  useEffect(() => {
    let active = true, timer;
    async function load() {
      try { const result = await diagnostics.snapshot(); if (active) { setData(result); setError(''); } }
      catch { if (active) setError('Telemetry unavailable; previous measurements may be stale.'); }
      if (active) timer = setTimeout(load, 5000);
    }
    load();
    const tick = setInterval(() => setClock(Date.now()), 1000);
    async function loadDurableChat() {
      try {
        const result = await diagnostics.chatSessions();
        const sessions = result.sessions || [];
        setChatSessions(sessions);
        const preferred = chatSessionId || sessions[0]?.session_id;
        if (preferred) {
          const session = await diagnostics.chatSession(preferred);
          setChatSessionId(preferred);
          setChatMessages((session.messages || []).map(item => ({ ...item, role: item.actor || item.role })));
          const latest = [...(session.messages || [])].reverse().find(item => item.actor === 'cali');
          if (latest) setChatProvider(`Provider/model: ${latest.provider || 'unknown'} / ${latest.model || 'unknown'}`);
        }
      } catch { /* telemetry remains usable if the durable chat store is unavailable */ }
    }
    void loadDurableChat();
    return () => { active = false; clearTimeout(timer); clearInterval(tick); };
  }, []);
  useEffect(() => {
    try { sessionStorage.setItem('orb-diagnostics-chat', JSON.stringify(chatMessages)); } catch {}
  }, [chatMessages]);
  useEffect(() => {
    try {
      if (chatSessionId) sessionStorage.setItem('orb-diagnostics-chat-session', chatSessionId);
    } catch {}
  }, [chatSessionId]);
  const sections = Object.entries(data?.sections || {});
  const selected = sections.find(([section]) => section === activeSection)?.[0] || sections[0]?.[0] || '';
  const selectedMeasurements = selected ? data?.sections?.[selected] || {} : {};
  const contextCapturedAt = data?.collected_at || '';
  async function sendChat(event) {
    event?.preventDefault();
    const message = chatInput.trim();
    if (!message || chatBusy) return;
    setChatInput(''); setChatError(''); setChatBusy(true);
    const userMessage = { role: 'owner', text: message, at: new Date().toISOString(), section: selected, capturedAt: contextCapturedAt };
    setChatMessages(current => [...current, userMessage]);
    try {
      chatAbort.current = new AbortController();
      const result = await diagnostics.chat({
        message,
        session_id: chatSessionId || undefined,
        section: selected,
        captured_at: contextCapturedAt || undefined,
        measurements: selectedMeasurements,
      }, chatAbort.current.signal);
      if (result.session_id && !chatSessionId) setChatSessionId(result.session_id);
      setChatProvider(`Provider/model: ${result.provider || 'unknown'} / ${result.model || 'unknown'}`);
      setChatMessages(current => [...current, { role: 'cali', text: result.text || 'CALI returned no diagnostic text.', at: result.captured_at || new Date().toISOString(), section: selected, capturedAt: contextCapturedAt, provider: result.provider, model: result.model }]);
      const sessions = await diagnostics.chatSessions();
      setChatSessions(sessions.sessions || []);
    } catch (reason) {
      if (reason?.name !== 'AbortError') setChatError(String(reason));
      else setChatError('Generation cancelled.');
    }
    finally { chatAbort.current = null; setChatBusy(false); }
  }
  function cancelChat() {
    chatAbort.current?.abort();
  }
  async function reopenChat(id) {
    if (!id) return;
    try {
      const session = await diagnostics.chatSession(id);
      setChatSessionId(id); setChatMessages((session.messages || []).map(item => ({ ...item, role: item.actor || item.role }))); setChatRecords(null); setChatError('');
      const latest = [...(session.messages || [])].reverse().find(item => item.actor === 'cali');
      if (latest) setChatProvider(`Provider/model: ${latest.provider || 'unknown'} / ${latest.model || 'unknown'}`);
    } catch (reason) { setChatError(String(reason)); }
  }
  async function loadChatRecords(kind) {
    if (!chatSessionId) return;
    try {
      const result = kind === 'development' ? await diagnostics.chatDevelopmentLog(chatSessionId) : await diagnostics.chatGlyphTrace(chatSessionId);
      setChatRecords({ kind, items: result.events || [] });
    } catch (reason) { setChatError(String(reason)); }
  }
  async function copyBrief() {
    try {
      const exported = chatSessionId ? await diagnostics.chatExport(chatSessionId) : null;
      const transcript = chatMessages.map(item => `${item.role === 'owner' ? 'Owner' : 'CALI'} (${item.at})\n${item.text}`).join('\n\n');
      const context = selected ? `Current context: ${selected} captured ${contextCapturedAt || 'unknown'}\n\n` : '';
      await navigator.clipboard?.writeText(exported ? JSON.stringify(exported, null, 2) : `${context}${transcript}`);
    } catch (reason) { setChatError(String(reason)); }
  }
  async function copyResponse(text) {
    try { await navigator.clipboard?.writeText(text); }
    catch (reason) { setChatError(String(reason)); }
  }
  return <div className="p-6 diagnostics-workspace" style={{ width: '100%', maxWidth: 'none', boxSizing: 'border-box' }}>
    <h1>Diagnostics</h1><p className="text-secondary">Measured evidence and explicit unknowns. Refreshes every five seconds.</p>
    {error && <p role="alert">{error}</p>}{!data && <p>Measurements: unknown</p>}
    {sections.length > 0 && <div className="diagnostic-tabs" role="tablist" aria-label="Diagnostic sections">
      {sections.map(([section]) => <button key={section} role="tab" aria-selected={selected === section}
        className={`diagnostic-tab ${selected === section ? 'diagnostic-tab-active' : ''}`}
        onClick={() => setActiveSection(section)}>{section}</button>)}
    </div>}
    {sections.filter(([section]) => section === selected).map(([section, metrics]) => <section className="card mb-4" key={section}>
      <h2 className="card-title">{section}</h2><div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', textAlign: 'left' }}><thead><tr><th aria-label="Health" /><th>Measurement</th><th>Value</th><th>Measured / age</th><th>Source</th></tr></thead>
      <tbody>{Object.entries(metrics).map(([key, item]) => {
        const age = item.measured_at ? Math.max(0, (clock - Date.parse(item.measured_at)) / 1000) : null;
        const stale = age !== null && age > data.stale_after_seconds;
        const known = item.status === 'measured' && item.value !== null;
        const healthy = known && !stale && item.value !== false && item.value !== 'false' && item.value !== 'disabled';
        const reason = item.reason || (healthy ? 'Verified measurement' : known ? 'Measured unhealthy or disabled' : 'No verified measurement');
        return <tr key={key} title={reason}>
          <td style={{ padding: '8px 6px', width: 28 }}><span className={`health-light ${healthy ? 'health-light-green' : 'health-light-red'}`} aria-label={healthy ? 'healthy' : 'not healthy'} /></td>
          <td style={{ padding: '8px 6px' }}>{key.replaceAll('_', ' ')}</td>
          <td>{!known ? 'unknown' : stale ? 'unknown (stale)' : typeof item.value === 'object' ? JSON.stringify(item.value) : String(item.value)}</td>
          <td>{age === null ? 'unknown' : <>{new Date(item.measured_at).toLocaleString()} / {Math.floor(age)}s{stale && <div>Last value: {JSON.stringify(item.value)}</div>}</>}</td>
          <td>{item.source}</td></tr>;
      })}</tbody></table></div></section>)}
    <section className="card diagnostics-chat" aria-label="CALI Admin Diagnostic Chat">
      <div className="card-header">
        <div>
          <h2 className="card-title">CALI Admin Diagnostic Chat</h2>
          <div className="text-xs text-muted" style={{ marginTop: 4 }}>Admin only · existing reasoning pathway · speech and execution disabled</div>
        </div>
        <div className="flex gap-2 items-center">
          <select className="select" aria-label="Diagnostic session" value={chatSessionId} onChange={event => void reopenChat(event.target.value)}>
            <option value="">New diagnostic session</option>
            {chatSessions.map(session => <option key={session.session_id} value={session.session_id}>{new Date(session.updated_at).toLocaleString()} · {session.session_id.slice(0, 8)}</option>)}
          </select>
        <button className="btn btn-ghost" type="button" onClick={() => setChatCollapsed(value => !value)}>{chatCollapsed ? 'Expand' : 'Collapse'}</button>
        <button className="btn btn-ghost" type="button" onClick={() => void copyBrief()} disabled={!chatMessages.length}>Export / copy brief</button>
        </div>
      </div>
      {!chatCollapsed && <>
      <div className="diagnostics-chat-context">
        Context attached: {selected || 'none'}{contextCapturedAt ? `, captured ${new Date(contextCapturedAt).toLocaleTimeString()}` : ', no fresh snapshot'} · {chatProvider}
      </div>
      <div className="diagnostics-chat-transcript" aria-live="polite">
        {!chatMessages.length && <div className="text-secondary">Ask CALI about the measurements, or paste analysis from GPT or Codex.</div>}
        {chatMessages.map((item, index) => <div className={`diagnostics-chat-message diagnostics-chat-${item.role}`} key={`${item.at}-${index}`}>
          <div className="flex justify-between items-center text-xs text-muted"><span>{item.role === 'owner' ? 'Owner' : 'CALI'} · {new Date(item.at).toLocaleTimeString()}</span>{item.role === 'cali' && <button className="btn btn-ghost" type="button" onClick={() => void copyResponse(item.text)}>Copy</button>}</div>
          <div style={{ whiteSpace: 'pre-wrap' }}>{item.text}</div>
          {item.section && <div className="text-xs text-muted" style={{ marginTop: 6 }}>Context: {item.section} · {item.capturedAt ? new Date(item.capturedAt).toLocaleTimeString() : 'unknown'}</div>}
        </div>)}
        {chatBusy && <div className="text-secondary">CALI is analyzing the attached evidence…</div>}
      </div>
      {chatError && <div role="alert" className="text-warning" style={{ margin: '10px 0' }}>{chatError}</div>}
      <form onSubmit={sendChat}>
        <textarea className="textarea" rows={5} maxLength={2000} value={chatInput} onChange={event => setChatInput(event.target.value)}
          onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void sendChat(event); } }}
          placeholder="Ask CALI about diagnostics, or paste analysis from GPT or Codex…" disabled={chatBusy} />
        <div className="flex justify-between items-center" style={{ marginTop: 8 }}>
          <span className="text-xs text-muted">Enter to send · Shift+Enter for a new line · {chatInput.length}/2,000 characters</span>
          <div className="flex gap-2">
            {chatBusy && <button className="btn btn-ghost" type="button" onClick={cancelChat}>Cancel generation</button>}
            <button className="btn btn-primary" type="submit" disabled={chatBusy || !chatInput.trim()}>Send</button>
          </div>
        </div>
      </form>
      <div className="flex gap-2" style={{ marginTop: 10 }}>
        <button className="btn btn-ghost" type="button" onClick={() => void loadChatRecords('development')} disabled={!chatSessionId}>Development log</button>
        <button className="btn btn-ghost" type="button" onClick={() => void loadChatRecords('glyph')} disabled={!chatSessionId}>Glyph Trace</button>
      </div>
      {chatRecords && <pre className="diagnostics-chat-records">{JSON.stringify(chatRecords.items, null, 2)}</pre>}
      </>}
    </section>
  </div>;
}
