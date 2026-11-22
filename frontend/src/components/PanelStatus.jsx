import React from 'react';

export default function PanelStatus({ hasData, loading = false, error = '', children }) {
  const state = loading ? 'Loading' : error ? (hasData ? 'Stale' : 'Offline') : hasData ? 'Connected' : 'Unavailable';
  return <>
    <div className="card" role="status" style={{ marginBottom: 16, borderColor: error ? 'var(--color-warning)' : 'var(--color-border)' }}>
      <div className="flex justify-between items-center">
        <strong>{state}</strong>
        <span className="badge">{hasData ? (error ? 'Last known values' : 'Live data') : 'No saved data'}</span>
      </div>
      <div className="text-secondary text-sm" style={{ marginTop: 6 }}>
        {error ? `${error} Configuration controls remain visible; protected writes require an authorized live service.` : hasData ? 'Values are available for viewing and editing.' : 'This field has no saved value. It is unavailable until a profile service provides one.'}
      </div>
    </div>
    {children}
  </>;
}
