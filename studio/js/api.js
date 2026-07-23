// API Base URL
const BASE_URL =
  import.meta.env?.VITE_API_URL ||
  'https://about-1code.onrender.com';

async function apiFetch(path, options = {}) {
  const { headers = {}, ...restOptions } = options;

  const customHeaders = {
    Accept: 'application/json',
    ...headers,
  };

  const adminKey = localStorage.getItem('1code_admin_key');

  if (path.startsWith('/api/admin') && adminKey) {
    customHeaders['X-Admin-Key'] = adminKey;
  }

  const url = `${BASE_URL}${path}`;

  // Debug (remove after testing)
  console.log('Fetching:', url);

  const res = await fetch(url, {
    credentials: 'include',
    ...restOptions,
    headers: customHeaders,
  });

  if (!res.ok) {
    const payload = await res.json().catch(() => null);

    throw new Error(
      payload?.detail ||
      `HTTP ${res.status}: ${res.statusText}`
    );
  }

  return res.json();
}

// =======================
// Admin APIs
// =======================

export const getAdminChallenges = () =>
  apiFetch('/api/admin/challenges');

export const getAdminChallenge = (id) =>
  apiFetch(`/api/admin/challenges/${id}`);

export const getAdminChallengeById = getAdminChallenge;

export const createChallenge = (payload) =>
  apiFetch('/api/admin/challenges', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

export const updateAdminChallenge = (id, payload) =>
  apiFetch(`/api/admin/challenges/${id}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

export const deleteAdminChallenge = (id) =>
  apiFetch(`/api/admin/challenges/${id}`, {
    method: 'DELETE',
  });

// =======================
// User APIs
// =======================

export const getSubmissions = () =>
  apiFetch('/api/submissions');

export const getSubmissionDetail = (id) =>
  apiFetch(`/api/submissions/${id}`);

export const getEvaluation = (id) =>
  apiFetch(`/api/evaluate/${id}`);

export const getLeaderboard = () =>
  apiFetch('/api/leaderboard');

export const getLeaderboardStats = () =>
  apiFetch('/api/leaderboard/stats');

export const getLeaderboardBySlug = (slug) =>
  apiFetch(
    `/api/leaderboard/stats?challenge_slug=${encodeURIComponent(slug)}`
  );
