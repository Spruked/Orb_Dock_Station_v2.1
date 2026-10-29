const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
let sessionPromise = null;

export function beginMemorySession() {
  if (!sessionPromise) {
    sessionStorage.removeItem('aims_session');
    sessionPromise = fetch(`${API_BASE}/memory/start`, {
      method:'POST', headers:{'Content-Type':'application/json', Authorization:`Bearer ${localStorage.getItem('orb_token')}`}, body:'{}',
    }).then(async response => {
      if (!response.ok) throw new Error('AIMS session unavailable');
      const data = await response.json();
      sessionStorage.setItem('aims_session', data.session_id);
      return data.session_id;
    }).catch(error => {sessionPromise=null; throw error;});
  }
  return sessionPromise;
}

export function endMemorySession() {
  const pending = sessionPromise;
  sessionPromise=null;
  sessionStorage.removeItem('aims_session');
  if (pending) pending.then(session => fetch(`${API_BASE}/memory/end`, {
    method:'POST', headers:{'Content-Type':'application/json',Authorization:`Bearer ${localStorage.getItem('orb_token')}`},
    body:JSON.stringify({session_id:session}),keepalive:true,
  })).catch(() => {});
}

async function api(path, opts = {}) {
  const token = localStorage.getItem('orb_token');
  if (token && !path.startsWith('/auth') && !path.startsWith('/memory') && !path.startsWith('/diagnostics')) await beginMemorySession();
  const res = await fetch(`${API_BASE}${path}`, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...(sessionStorage.getItem('aims_session') && {'X-Orbot-Session':sessionStorage.getItem('aims_session')}),
      ...opts.headers,
    },
  });
  if (res.status === 401) {
    localStorage.removeItem('orb_token');
    window.location.reload();
  }
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text);
  }
  return res.json();
}

export const auth = {
  login: (email, password) => api('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
};

export const profiles = {
  list: () => api('/profiles'),
  get: (id) => api(`/profiles/${id}`),
  update: (id, data) => api(`/profiles/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  publish: (id, summary) => api(`/profiles/${id}/publish`, { method: 'POST', body: JSON.stringify({ change_summary: summary }) }),
  versions: (id) => api(`/profiles/${id}/versions`),
  diff: (id) => api(`/profiles/${id}/diff`),
  restore: (id, version) => api(`/profiles/${id}/restore/${version}`, { method: 'POST' }),
};

export const speech = {
  get: (id) => api(`/speech/${id}`),
  update: (id, data) => api(`/speech/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  testGreeting: (id) => api(`/speech/${id}/test-greeting`, { method: 'POST' }),
  testTone: (id) => api(`/speech/${id}/test-tone`, { method: 'POST' }),
};

export const behavior = {
  getPersonality: (id) => api(`/behavior/${id}/personality`),
  updatePersonality: (id, data) => api(`/behavior/${id}/personality`, { method: 'PATCH', body: JSON.stringify(data) }),
  getDirectives: (id) => api(`/behavior/${id}/directives`),
  updateDirectives: (id, data) => api(`/behavior/${id}/directives`, { method: 'PATCH', body: JSON.stringify(data) }),
};

export const intelligence = {
  get: (id) => api(`/intelligence/${id}`),
  update: (id, data) => api(`/intelligence/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  getLanes: (id) => api(`/intelligence/${id}/lanes`),
  updateLane: (id, laneName, config) => api(`/intelligence/${id}/lanes/${laneName}`, { method: 'PATCH', body: JSON.stringify(config) }),
  activateLane: (id, laneName) => api(`/intelligence/${id}/lanes/${laneName}/activate`, { method: 'POST' }),
  testLane: (id, laneName) => api(`/intelligence/${id}/lanes/${laneName}/test`, { method: 'POST' }),
  testLaneResponse: (id, laneName, prompt) => api(`/intelligence/${id}/lanes/${laneName}/test-response`, { method: 'POST', body: JSON.stringify({ prompt }) }),
  restoreRecommended: (id) => api(`/intelligence/${id}/restore-recommended`, { method: 'POST' }),
  gatewayHealth: () => api('/intelligence/health/gateway'),
};

export const tools = {
  get: (id) => api(`/tools/${id}`),
  update: (id, data) => api(`/tools/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
};

export const appearance = {
  desktopPreferences: () => api('/appearance/desktop/preferences'),
  saveDesktopPreferences: (id, value, expectedEntryId) => api(`/appearance/desktop/preferences/${id}`, { method: 'PUT', body: JSON.stringify({value, expected_entry_id: expectedEntryId}) }),
  get: (id) => api(`/appearance/${id}`),
  update: (id, data) => api(`/appearance/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  getSkins: (id) => api(`/appearance/${id}/skins`),
  createSkin: (id, skin) => api(`/appearance/${id}/skins`, { method: 'POST', body: JSON.stringify(skin) }),
  updateSkin: (id, skinId, skin) => api(`/appearance/${id}/skins/${skinId}`, { method: 'PATCH', body: JSON.stringify(skin) }),
  activateSkin: (id, skinId) => api(`/appearance/${id}/skins/${skinId}/activate`, { method: 'POST' }),
  restoreFactory: (id) => api(`/appearance/${id}/skins/restore-factory`, { method: 'POST' }),
  setMotionPreview: (id, state) => api(`/appearance/${id}/motion-preview`, { method: 'POST', body: JSON.stringify({ state }) }),
};

export const liveTest = {
  start: (profileId) => api(`/live-test/${profileId}/start`, { method: 'POST' }),
  control: (sessionId, action, extra = {}) => api(`/live-test/${sessionId}/control`, { method: 'POST', body: JSON.stringify({ action, ...extra }) }),
  speak: (sessionId, text) => api(`/live-test/${sessionId}/speak`, { method: 'POST', body: JSON.stringify({ text }) }),
  getSession: (sessionId) => api(`/live-test/${sessionId}`),
  stream: (sessionId) => api(`/live-test/${sessionId}/stream`),
};

export const diagnostics = {
  snapshot: () => api('/diagnostics/snapshot'),
  health: () => api('/diagnostics/health'),
  pointer: () => api('/diagnostics/pointer'),
  recovery: () => api('/diagnostics/pointer/recovery', { method: 'POST' }),
  gateway: () => api('/diagnostics/gateway'),
  issues: () => api('/diagnostics/issues'),
};

export const statistics = {
  list: (profileId) => api(`/statistics?profile_id=${profileId}`),
  latest: (profileId) => api(`/statistics/latest?profile_id=${profileId}`),
};

export const conversations = {
  list: (profileId) => api(`/conversations?profile_id=${profileId}`),
};

export const tryItLive = {
  preview: (id) => api(`/try-it-live/${id}/preview`),
  testConversation: (id) => api(`/try-it-live/${id}/test-conversation`, { method: 'POST' }),
  testTools: (id) => api(`/try-it-live/${id}/test-tools`, { method: 'POST' }),
};
