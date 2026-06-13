import { state, setToken } from './state.js';

export function authHeaders() {
  const headers = { Accept: 'application/json' };
  if (state.token) {
    headers.Authorization = `Bearer ${state.token}`;
  }
  return headers;
}

export async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      ...authHeaders(),
      ...(options.headers || {}),
    },
  });

  const payload = await response.json().catch(() => ({}));

  if (response.status === 401) {
    setToken(null);
    window.dispatchEvent(new CustomEvent('session-expired'));
    throw new Error('Sesión expirada');
  }

  if (!response.ok) {
    throw new Error(payload.error || payload.detail || `HTTP ${response.status}`);
  }

  return payload;
}

export async function postJson(url, payload, options = {}) {
  return fetchJson(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    ...options,
  });
}

export async function deleteJson(url, options = {}) {
  return fetchJson(url, { method: 'DELETE', ...options });
}
