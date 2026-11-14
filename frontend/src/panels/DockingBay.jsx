import React, { useEffect, useState } from 'react';
import { invoke, isTauri } from '@tauri-apps/api/core';
import { Plug, Unplug, RefreshCw, Pause, Play, BookOpen, LocateFixed, Crosshair } from 'lucide-react';
import orbImage from '../assets/orbot.png';
import VoiceStatus from '../components/VoiceStatus';

export default function DockingBay() {
  const [peer, setPeer] = useState(null);
  const [error, setError] = useState('');
  const [startup, setStartup] = useState(null);
  async function refresh() {
    if (!isTauri()) { setPeer(null); return; }
    try { setStartup(await invoke('startup_status')); setPeer(JSON.parse(await invoke('peer_status'))); }
    catch { setPeer(null); }
  }
  useEffect(() => { refresh(); const interval = setInterval(refresh, 2000); return () => clearInterval(interval); }, []);
  async function act(command) {
    try { setError(''); await invoke(command); await refresh(); }
    catch (reason) { setError(String(reason)); }
  }
  async function presentation(action) {
    try { setError(''); await invoke('presentation_control', { action }); await refresh(); }
    catch (reason) { setError(String(reason)); }
  }
  return <div className="docking-screen p-6">
    <h1 style={{fontSize:24,marginBottom:8}}>Orbot Docking Station</h1>
    <p className="text-secondary">Orbot starts here, docked. Launching and docking preserve the same cognitive session.</p>
    <div className="docking-bay">
      <div className={'orb-seat ' + (peer?.docked ? 'occupied' : '')}>
        {peer?.docked ? <img src={orbImage} alt="Orbot docked in the station" /> : <Plug size={48} aria-label="Empty docking bay" />}
      </div>
    </div>
    <div className="docking-controls">
      <h2>{peer ? (peer.docked ? 'Docked' : (startup?.ready ? 'Operational' : 'Starting')) : 'Waiting for Orbot'}</h2>
      <p className="text-secondary">{isTauri() ? `Startup: ${startup?.phase || 'checking'}` : 'Browser preview. Native startup and lifecycle controls require Tauri.'}</p>
      {startup?.error && <p role="alert" className="text-danger">{startup.error}</p>}
      <div className="flex gap-3" style={{justifyContent:'center',marginTop:24}}>
        <button className="btn btn-primary" disabled={!peer || peer.docked} onClick={() => act('dock_orbot')}><Plug size={16} /> Dock Orbot</button>
        <button className="btn btn-secondary" disabled={!startup?.ready || !peer || !peer.docked} onClick={() => act('undock_orbot')}><Unplug size={16} /> Launch Orbot</button>
        {startup?.phase === 'failed' && <button className="btn btn-secondary" onClick={() => act('retry_startup')}>Retry startup</button>}
        <button className="btn btn-secondary" onClick={refresh}><RefreshCw size={16} /> Refresh</button>
      </div>
      <div className="flex gap-3" style={{justifyContent:'center',marginTop:12}}>
        <button className="btn btn-secondary" disabled={!peer || peer.docked} onClick={() => presentation('hold')}><Pause size={16} /> Hold Orb position</button>
        <button className="btn btn-secondary" disabled={!peer || peer.docked} onClick={() => presentation('guided')}><LocateFixed size={16} /> Guide near cursor</button>
        <button className="btn btn-secondary" disabled={!peer || peer.docked} onClick={() => presentation('resume')}><Play size={16} /> Resume ambient movement</button>
        <button className="btn btn-secondary" disabled={!peer || peer.docked} onClick={() => presentation('morb')}><Crosshair size={16} /> Guide MORB to cursor</button>
        <button className="btn btn-secondary" disabled={!peer} onClick={() => presentation('research')}><BookOpen size={16} /> Research and retained sources</button>
      </div>
      {error && <p role="alert" className="text-danger" style={{marginTop:16}}>{error}</p>}
    </div>
    <div className="card" style={{marginTop:16}}>
      <h3>Live motion authority</h3>
      <p role="status" className="text-secondary" style={{marginTop:8}}>
        {peer?.motion?.runtime === 'motion'
          ? `Presentation: ${peer.motion.authority} · ${peer.motion.presentation_active ? 'active' : 'inactive'} · MORBs: ${peer.motion.morb_assignments} · execution permission: disabled`
          : 'Motion authority status unavailable; no active state can be confirmed.'}
      </p>
      {peer?.motion_transport?.consecutive_failures > 0 && <p role="alert" className="text-danger">
        Motion requests failing ({peer.motion_transport.consecutive_failures} consecutive). Last category: {peer.motion_transport.last_failure}.
      </p>}
      {peer?.motion_transport?.failures_total > 0 && <p className="text-xs text-muted">
        Total recorded motion transport failures: {peer.motion_transport.failures_total}
      </p>}
      <p className="text-xs text-muted" style={{marginTop:8}}>
        MORB placement is owner-directed, visual only, and does not click or verify the cursor target.
      </p>
    </div>
    <VoiceStatus docked={!peer || peer.docked} />
    <div className="card"><h3>AIMS memory</h3><p className="text-secondary" style={{marginTop:8}}>Working memory stays inside the current session. Explicitly retained records and configuration are saved through Orbot's AIMS Vault service. The station does not own a second memory database.</p></div>
  </div>;
}
