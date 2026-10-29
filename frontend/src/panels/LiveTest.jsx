import React from 'react';

export default function LiveTest() {
  return <div className="p-6" style={{maxWidth:900}}>
    <h1>Live Test</h1>
    <div className="card" style={{marginTop:16}}>
      <h2>Live Test is not connected</h2>
      <p className="text-secondary">The legacy website simulation is unavailable in the native Dock Station. It did not exercise Orbot's active cognition or execution controls.</p>
      <p className="text-secondary">Launch Orbot from the Docking Bay for a real interaction. Diagnostics reports the available runtime measurements. Testing a draft profile against the active runtime still requires integration.</p>
    </div>
  </div>;
}
