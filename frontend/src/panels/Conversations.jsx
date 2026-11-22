import React, { useEffect, useState } from 'react';
import { conversations } from '../services/api';
import { CheckCircle, XCircle, RefreshCw } from 'lucide-react';

function Evidence({ turn }) {
  const details = {
    context: turn.context,
    evidence: turn.evidence,
    epistemic_field: turn.epistemic_field,
    speech_error: turn.speech_error,
    foundation_sha256: turn.inculcation_sha256,
  };
  return <details style={{ marginTop: 10 }}>
    <summary className="text-xs text-muted" style={{ cursor: 'pointer' }}>Evidence and context</summary>
    <pre className="text-xs" style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', marginTop: 8, color: 'var(--color-text-secondary)' }}>
      {JSON.stringify(details, null, 2)}
    </pre>
  </details>;
}

function Message({ message }) {
  const owner = message.speaker === 'owner' || message.speaker === 'visitor';
  return <div className={`flex ${owner ? 'justify-start' : 'justify-end'}`}>
    <div className="p-3 rounded-lg" style={{
      maxWidth: '82%',
      background: owner ? 'var(--color-surface-raised)' : 'var(--color-accent)',
      color: owner ? 'var(--color-text)' : 'white',
      borderRadius: owner ? '4px 12px 12px 12px' : '12px 4px 12px 12px',
    }}>
      <div className="text-xs opacity-70 mb-1">{owner ? 'You' : 'CALI'}</div>
      <div className="text-sm" style={{ whiteSpace: 'pre-wrap' }}>{message.text}</div>
    </div>
  </div>;
}

export default function Conversations({ profileId }) {
  const [list, setList] = useState([]);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    setError('');
    try {
      const data = await conversations.list(profileId);
      setList(data);
      setSelected(current => current && data.find(item => item.session_id === current.session_id) || data[0] || null);
    } catch (reason) {
      setError(String(reason));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, [profileId]);

  const renderTurns = selected?.turns?.length
    ? selected.turns.map(turn => (
      <div key={turn.turn_id} className="card" style={{ padding: 14 }}>
        <div className="text-xs text-muted" style={{ marginBottom: 8 }}>Turn {turn.turn_id}</div>
        <div className="flex flex-col gap-3">{(turn.transcript || []).map((message, index) => <Message key={index} message={message} />)}</div>
        <Evidence turn={turn} />
      </div>
    ))
    : (selected?.transcript || []).map((message, index) => <Message key={index} message={message} />);

  return <div className="p-6" style={{ maxWidth: 1200 }}>
    <div className="flex justify-between items-center" style={{ marginBottom: 4 }}>
      <div>
        <h1 style={{ fontSize: 22, fontWeight: 600 }}>Conversations</h1>
        <p className="text-secondary">Owner speech, CALI responses, and retained context/evidence per session.</p>
      </div>
      <button className="btn btn-secondary" onClick={() => void load()} disabled={loading}><RefreshCw size={14} /> Refresh</button>
    </div>
    {error && <p role="alert" className="text-warning" style={{ marginTop: 12 }}>{error}</p>}

    <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 24, marginTop: 24 }}>
      <div className="card" style={{ padding: 12, maxHeight: 'calc(100vh - 200px)', overflow: 'auto' }}>
        <div className="card-title" style={{ marginBottom: 12, fontSize: 13 }}>Sessions</div>
        {!list.length && <div className="text-sm text-secondary">No retained or live conversation turns yet.</div>}
        {list.map(sess => <button key={sess.session_id} onClick={() => setSelected(sess)} style={{
          width: '100%', textAlign: 'left', padding: '10px 12px', borderRadius: 8, border: '1px solid',
          borderColor: selected?.session_id === sess.session_id ? 'var(--color-accent)' : 'transparent',
          background: selected?.session_id === sess.session_id ? 'rgba(124,58,237,0.1)' : 'transparent',
          cursor: 'pointer', marginBottom: 4,
        }}>
          <div className="flex justify-between items-center">
            <span className="text-xs text-muted">{sess.session_id}</span>
            {sess.outcome === 'abandoned' ? <XCircle size={12} className="text-danger" /> : <CheckCircle size={12} className="text-success" />}
          </div>
          <div className="text-xs text-secondary mt-1">{sess.live ? 'Live Communication session' : new Date(sess.started_at).toLocaleString()}</div>
        </button>)}
      </div>

      <div>
        {selected ? <div className="flex flex-col gap-3">
          <div className="card">
            <div className="card-header">
              <div>
                <div className="card-title">{selected.session_id}</div>
                <div className="text-xs text-muted">{selected.live ? 'Live transcript from Orbot Communication' : `Outcome: ${selected.outcome || 'recorded'}`}</div>
              </div>
            </div>
            {renderTurns}
            {!selected.turns?.length && !selected.transcript?.length && <div className="text-secondary">This session has no transcript entries.</div>}
          </div>
        </div> : <div className="card text-secondary text-center p-12">Select a conversation to view both sides and its evidence.</div>}
      </div>
    </div>
  </div>;
}
