import { getAdminChallenges, getLeaderboardStats } from './api.js';

export async function initAnalytics() {
  const [challenges, stats] = await Promise.all([
    getAdminChallenges().catch(() => []),
    getLeaderboardStats().catch(() => [])
  ]);

  // Aggregate values
  const totalUsers = stats.reduce((sum, row) => sum + (row.total_participants || 0), 0);
  const totalChallenges = challenges.length;
  
  let avgScoreSum = 0;
  let avgCount = 0;
  let mostAttempted = null;

  stats.forEach(row => {
    avgScoreSum += (row.average_score || 0);
    avgCount++;
    if (!mostAttempted || row.total_participants > mostAttempted.total_participants) {
      mostAttempted = row;
    }
  });

  const averageScore = avgCount ? (avgScoreSum / avgCount).toFixed(1) : '0.0';
  const mostAttemptedName = mostAttempted ? mostAttempted.challenge_name : 'None';

  // Set top metric cards
  document.getElementById('analytics-users').textContent = totalUsers;
  document.getElementById('analytics-challenges').textContent = totalChallenges;
  document.getElementById('analytics-average').textContent = averageScore;
  document.getElementById('analytics-most-attempted').textContent = mostAttemptedName;

  // Render detailed challenge statistics list
  const tbody = document.getElementById('analytics-stats-tbody');
  if (tbody) {
    if (!stats.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="table-empty">No performance data available.</td></tr>';
      return;
    }

    tbody.innerHTML = stats.map(row => `
      <tr>
        <td>
          <span style="font-weight:600;display:block;color:var(--text)">${row.challenge_name}</span>
          <span class="mono" style="font-size:0.75rem;color:var(--muted)">${row.challenge_slug || ''}</span>
        </td>
        <td><strong>${row.total_participants}</strong></td>
        <td><span class="text-accent" style="font-weight:600">${row.average_score.toFixed(1)}</span></td>
        <td><span class="text-success" style="font-weight:600">${row.highest_score}</span></td>
        <td><span class="text-danger" style="font-weight:600">${row.lowest_score}</span></td>
      </tr>
    `).join('');
  }
}
