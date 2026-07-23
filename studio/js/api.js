// =========================
// API Base URL
// =========================
// Use the Render backend everywhere except when running the site locally.
const BASE_URL = (window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost')
  ? 'http://127.0.0.1:8000'
  : 'https://about-1code.onrender.com';

async function apiFetch(path, options = {}) {
  const { headers, ...restOptions } = options;
  const customHeaders = { Accept: 'application/json', ...headers };
  const adminKey = localStorage.getItem('1code_admin_key');
  if (path.startsWith('/api/admin') && adminKey) {
    customHeaders['X-Admin-Key'] = adminKey;
  }

  const res = await fetch(BASE_URL + path, {
    credentials: 'include',
    ...restOptions,
    headers: customHeaders,
  });

  if (!res.ok) {
    const payload = await res.json().catch(() => null);
    throw new Error(payload?.detail || res.statusText || 'Request failed');
  }

  return res.json();
}

export const getAdminChallenges = () => apiFetch('/api/admin/challenges');
export const getAdminChallenge = (id) => apiFetch(`/api/admin/challenges/${id}`);
export const getAdminChallengeById = getAdminChallenge;

export const createChallenge = (payload) =>
  apiFetch('/api/admin/challenges', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

export const updateAdminChallenge = (id, payload) =>
  apiFetch(`/api/admin/challenges/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

export const deleteAdminChallenge = (id) =>
  apiFetch(`/api/admin/challenges/${id}`, { method: 'DELETE' });

export const getSubmissions = () => apiFetch('/api/submissions');
export const getSubmissionDetail = (id) => apiFetch(`/api/submissions/${id}`);
export const getEvaluation = (id) => apiFetch(`/api/evaluate/${id}`);
export const getLeaderboard = () => apiFetch('/api/leaderboard');
export const getLeaderboardStats = () => apiFetch('/api/leaderboard/stats');
export const getLeaderboardBySlug = (slug) => apiFetch(`/api/leaderboard/stats?challenge_slug=${encodeURIComponent(slug)}`);
