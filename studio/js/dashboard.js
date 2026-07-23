import { getAdminChallenges, getLeaderboardStats, getSubmissions } from './api.js';

const fmt = (d) => d ? new Date(d).toLocaleDateString('en-GB', { day:'2-digit', month:'short', year:'numeric' }) : '--';

function diffBadge(diff) {
  const d = (diff || '').toLowerCase();
  if (d === 'easy')   return `<span class="badge badge-easy">Easy</span>`;
  if (d === 'medium') return `<span class="badge badge-medium">Medium</span>`;
  if (d === 'hard')   return `<span class="badge badge-hard">Hard</span>`;
  return `<span class="badge badge-neutral">${diff || 'N/A'}</span>`;
}

export async function initDashboard() {
  const [challenges, stats, submissions] = await Promise.allSettled([
    getAdminChallenges(),
    getLeaderboardStats(),
    getSubmissions(),
  ]);

  const ch   = challenges.status  === 'fulfilled' ? challenges.value  : [];
  const st   = stats.status       === 'fulfilled' ? stats.value       : [];
  const subs = submissions.status === 'fulfilled' ? submissions.value : [];

  // Stats
  const totalChallenges   = ch.length;
  const activeChallenges  = ch.filter(c => c.is_active).length;
  const totalSubmissions  = subs.length;
  const avgScore = st.length
    ? (st.reduce((s, r) => s + (r.average_score || 0), 0) / st.length).toFixed(1)
    : '—';

  document.getElementById('stat-total-challenges').textContent  = totalChallenges;
  document.getElementById('stat-active-challenges').textContent = activeChallenges;
  document.getElementById('stat-total-submissions').textContent = totalSubmissions;
  document.getElementById('stat-average-score').textContent     = avgScore;

  // Recent challenges table
  const challengeTbody = document.getElementById('dashboard-challenges');
  if (challengeTbody) {
    const rows = ch.slice(0, 5).map(c => `
      <tr>
        <td><span class="mono">${c.slug}</span></td>
        <td>${c.title}</td>
        <td>${diffBadge(c.difficulty)}</td>
        <td><span class="badge ${c.is_active ? 'badge-active' : 'badge-inactive'}">${c.is_active ? 'Active' : 'Inactive'}</span></td>
        <td>${fmt(c.created_at)}</td>
      </tr>`).join('');
    challengeTbody.innerHTML = rows || `<tr class="table-empty"><td colspan="5">No challenges uploaded yet.</td></tr>`;
  }

  // Recent submissions table
  const subTbody = document.getElementById('dashboard-submissions');
  if (subTbody) {
    const rows = subs.slice(0, 5).map(s => {
      const statusClass = s.status === 'evaluated' ? 'badge-evaluated' : s.status === 'scored' ? 'badge-success' : 'badge-pending';
      return `
        <tr>
          <td>#${s.id}</td>
          <td>${s.name || '—'}</td>
          <td><span class="mono">${s.challenge_slug}</span></td>
          <td>${s.score != null ? `<strong>${s.score}</strong>` : '—'}</td>
          <td><span class="badge ${statusClass}">${s.status}</span></td>
        </tr>`;
    }).join('');
    subTbody.innerHTML = rows || `<tr class="table-empty"><td colspan="5">No submissions yet.</td></tr>`;
  }

  // Quick action buttons
  document.getElementById('qa-upload')?.addEventListener('click',      () => window.location.hash = 'upload-challenge');
  document.getElementById('qa-challenges')?.addEventListener('click',  () => window.location.hash = 'challenges');
  document.getElementById('qa-submissions')?.addEventListener('click', () => window.location.hash = 'submissions');
  document.getElementById('qa-analytics')?.addEventListener('click',   () => window.location.hash = 'analytics');
  document.getElementById('dashboard-view-challenges')?.addEventListener('click', () => window.location.hash = 'challenges');
  document.getElementById('dashboard-view-submissions')?.addEventListener('click', () => window.location.hash = 'submissions');
}
