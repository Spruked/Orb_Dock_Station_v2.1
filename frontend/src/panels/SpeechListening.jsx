import React, { useState, useEffect } from 'react';
import { speech, voiceLibrary } from '../services/api';
import { Play, AlertCircle, CheckCircle } from 'lucide-react';
import PanelStatus from '../components/PanelStatus';

export default function SpeechListening({ profileId }) {
  const [settings, setSettings] = useState(null);
  const [saving, setSaving] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [voices, setVoices] = useState([]);
  const [previewUrls, setPreviewUrls] = useState({});

  useEffect(() => {
    if (profileId) { load(); voiceLibrary.list().then(async result => { const next = result.voices || []; setVoices(next); const urls = {}; await Promise.all(next.map(async voice => { try { urls[voice.id] = await voiceLibrary.preview(voice.id); } catch {} })); setPreviewUrls(urls); }).catch(() => {}); }
  }, [profileId]);

  async function load() {
    setLoading(true); setError('');
    try { setSettings(await speech.get(profileId)); }
    catch (reason) { setError(String(reason)); }
    finally { setLoading(false); }
  }

  async function save(patch) {
    if (!settings || !profileId || error) return;
    setSaving(true);
    const updated = { ...settings, ...patch };
    await speech.update(profileId, updated);
    setSettings(updated);
    setSaving(false);
  }

  async function testGreeting() {
    try { setTestResult(await speech.testGreeting(profileId)); }
    catch (reason) { setTestResult({test_type:'greeting',passed:false,notes:String(reason)}); }
  }

  async function testTone() {
    const res = await speech.testTone(profileId);
    setTestResult(res);
  }

  const values = settings || {};
  async function selectVoice(id) { try { await voiceLibrary.select(profileId, id); setSettings({...settings, voice_id:id}); } catch (reason) { setError(String(reason)); } }

  return (
    <div className="p-6" style={{ maxWidth: 900 }}>
      <h1 style={{ fontSize: 22, fontWeight: 600, marginBottom: 4 }}>Speech & Listening</h1>
      <p className="text-secondary mb-6">Configure Orbot speech settings. VoiceStudio provides both recognition and speech generation; Nemotron is used for reasoning.</p>
      <PanelStatus hasData={Boolean(settings)} loading={loading} error={error}>{null}</PanelStatus>

      <div className="flex flex-col gap-4">
        <div className="card">
          <div className="card-title mb-2">My ORB — Voice Selection</div>
          <p className="text-secondary mb-4">Previewing never changes the active voice. Only a verified OmniVoice profile can be selected.</p>
          <div className="flex flex-col gap-2">
            {voices.map(voice => <div key={voice.id} className="flex items-center gap-3" style={{padding:'8px 0', borderBottom:'1px solid var(--color-border-subtle)'}}>
              <div style={{flex:1}}><div>{voice.name} {voice.id === values.voice_id && <span className="text-success">(selected)</span>}</div><div className="text-xs text-muted">{voice.status === 'synthesizable' ? `OmniVoice profile ${voice.profile_id}` : 'Preview only — synthesis profile not verified'}</div></div>
              <audio controls preload="none" src={previewUrls[voice.id]} style={{width:180}} />
              <button className="btn btn-secondary" disabled={voice.status !== 'synthesizable'} onClick={() => selectVoice(voice.id)}>Select</button>
            </div>)}
          </div>
        </div>
        <div className="card" style={{ borderColor: 'var(--color-accent)' }}>
          <div className="card-title">Operational voice pipeline</div>
          <p className="text-secondary" style={{ marginTop: 8 }}>VoiceStudio STT → NVIDIA Nemotron reasoning → VoiceStudio OmniVoice TTS</p>
          <p className="text-xs text-muted" style={{ marginTop: 6 }}>Qwen3-TTS is not used for normal CALI conversations.</p>
        </div>
        <div className="card">
          <div className="card-title mb-4">Greeting</div>
          <textarea 
            className="textarea" 
            rows={3}
            value={values.greeting_text ?? ''} disabled={!settings || Boolean(error)}
            onChange={e => save({ greeting_text: e.target.value })}
          />
          <div className="flex gap-2 mt-3">
            <button className="btn btn-primary" onClick={testGreeting} disabled={!settings || Boolean(error)}>
              <Play size={14} /> Test Greeting
            </button>
            <button className="btn btn-ghost" onClick={testTone} disabled={!settings || Boolean(error)}>
              <AlertCircle size={14} /> Tone Check
            </button>
          </div>
          {testResult && (
            <div className={`mt-3 p-3 rounded-md ${testResult.passed ? 'text-success' : 'text-warning'}`} style={{ background: 'var(--color-surface-raised)' }}>
              <div className="flex items-center gap-2 font-medium">
                {testResult.passed ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
                {testResult.test_type === 'greeting' ? 'Greeting synthesis' : 'Settings check'}: {testResult.passed ? 'Passed' : 'Flagged'}
              </div>
              <div className="text-sm mt-1">{testResult.notes}</div>
              {testResult.audio_url && <audio controls src={testResult.audio_url} style={{marginTop:12,maxWidth:'100%'}} />}
              {testResult.tone_flags?.length > 0 && (
                <div className="text-xs mt-2 text-warning">Flags: {testResult.tone_flags.join(', ')}</div>
              )}
            </div>
          )}
        </div>

        <div className="card">
          <div className="card-header">
            <div className="card-title">Interruption</div>
            <div 
              className={`toggle ${values.allow_interruption ? 'active' : ''}`}
              onClick={() => save({ allow_interruption: !values.allow_interruption })}
              aria-disabled={!settings || Boolean(error)}
            />
          </div>
          {settings && values.allow_interruption && (
            <div className="mt-3">
              <label className="text-xs text-muted">Sensitivity</label>
              <input 
                type="range" min={0} max={1} step={0.1}
                value={values.interruption_sensitivity ?? ''} disabled={!settings || Boolean(error)}
                onChange={e => save({ interruption_sensitivity: parseFloat(e.target.value) })}
              />
              <div className="flex justify-between text-xs text-muted mt-1">
                <span>Low</span>
                <span>{values.interruption_sensitivity ?? 'unavailable'}</span>
                <span>High</span>
              </div>
            </div>
          )}
        </div>

        <div className="card">
          <div className="card-title mb-4">Timing</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <div>
              <label className="text-xs text-muted">Pause timeout (ms)</label>
              <input 
                className="input" type="number"
                value={values.pause_timeout_ms ?? ''} disabled={!settings || Boolean(error)}
                onChange={e => save({ pause_timeout_ms: parseInt(e.target.value) })}
              />
            </div>
            <div>
              <label className="text-xs text-muted">Prefix padding (ms)</label>
              <input 
                className="input" type="number"
                value={values.prefix_padding_ms ?? ''} disabled={!settings || Boolean(error)}
                onChange={e => save({ prefix_padding_ms: parseInt(e.target.value) })}
              />
            </div>
            <div>
              <label className="text-xs text-muted">Microphone sensitivity</label>
              <input 
                type="range" min={0} max={1} step={0.1}
                value={values.microphone_sensitivity ?? ''} disabled={!settings || Boolean(error)}
                onChange={e => save({ microphone_sensitivity: parseFloat(e.target.value) })}
              />
            </div>
            <div>
              <label className="text-xs text-muted">Re-engage delay (ms)</label>
              <input 
                className="input" type="number"
                value={values.reengage_delay_ms ?? ''} disabled={!settings || Boolean(error)}
                onChange={e => save({ reengage_delay_ms: parseInt(e.target.value) })}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
