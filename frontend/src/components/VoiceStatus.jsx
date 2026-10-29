import React, { useState, useEffect } from 'react';
import { invoke, isTauri } from '@tauri-apps/api/core';

export default function VoiceStatus({docked}) {
  const [metrics,setMetrics]=useState({}), [error,setError]=useState(''), [pending,setPending]=useState(false);
  const [clock,setClock]=useState(Date.now());
  useEffect(()=>{
    let active=true,timer;
    async function poll(){
      try { const result=await invoke('voice_status');if(active){setMetrics(result||{});setClock(Date.now());} }
      catch {if(active)setMetrics({});}
      if(active)timer=setTimeout(poll,2000);
    }
    if(isTauri())poll();
    return ()=>{active=false;clearTimeout(timer);};
  },[]);
  const value=key=>metrics['voice.'+key]?.value;
  const client=metrics['voice.client.state'];
  const fresh=client?.measured_at && clock-Date.parse(client.measured_at)<15000;
  async function control(action){
    setPending(true);setError('');
    try{await invoke('voice_control',{action});}catch(reason){setError(String(reason));}finally{setPending(false);}
  }
  async function selectInput(deviceId){
    const selected=(value('client.input_devices')||[]).find(device=>device.device_id===deviceId);
    if(!selected)return;
    setPending(true);setError('');
    try{await invoke('set_microphone',{deviceId:selected.device_id,label:selected.label});}
    catch(reason){setError(String(reason));}finally{setPending(false);}
  }
  const issue=value('client.error_message') || value('last_error');
  return <section className="card" style={{textAlign:'left',width:'100%'}}>
    <h3>Voice conversation</h3>
    <p>{fresh ? `${docked ? 'Docked' : 'Operational'}   ${value('client.state')}` : 'Waiting for a current microphone/playback report'}</p>
    <p className="text-secondary">Runtime: {value('server_stage') || 'Ready for speech'}    Qwen3-TTS: {value('tts_loaded') ? 'Loaded' : 'Loads on first reply'} ({value('tts_device') || 'device pending'})</p>
    {value('client.input_label') && <p className="text-secondary">Microphone: {value('client.input_label')}{fresh && value('client.microphone') ? '    Capturing' : '    Capture inactive or unconfirmed'}</p>}
    <label style={{display:'block',marginTop:12}}>Microphone input
      <select className="select" disabled={pending} value={(value('client.input_devices')||[]).find(device=>device.label===value('client.input_label'))?.device_id || ''} onChange={event=>selectInput(event.target.value)}>
        <option value="">Choose an explicit microphone...</option>
        {(value('client.input_devices')||[]).map(device=><option key={device.device_id} value={device.device_id}>{device.label}</option>)}
      </select>
    </label>
    <button className="btn btn-ghost" disabled={pending} onClick={()=>control('refresh_devices')}>Refresh microphones</button>
    {issue && <p role="alert" className="text-warning">{issue}</p>}
    {error && <p role="alert" className="text-danger">{error}</p>}
    <div className="flex gap-3" style={{marginTop:12}}>
      <button className="btn btn-secondary" disabled={!isTauri() || pending} onClick={()=>control('start')}>Start listening</button>
      <button className="btn btn-secondary" disabled={!isTauri() || pending} onClick={()=>control('pause')}>Pause voice</button>
      <button className="btn btn-secondary" disabled={!isTauri() || pending} onClick={()=>control('cancel')}>Cancel reply</button>
    </div>
    <p className="text-xs text-muted" style={{marginTop:10}}>Speak while docked or operational, then pause. Speak or click to interrupt playback. Docking preserves voice and session. Pause voice or Cancel reply are explicit controls. WebView playback events do not prove physical speaker output.</p>
  </section>;
}
