import { getLeaderboard } from './api.js';

function getRankBadge(rank) {
  if (rank === 1) return `<span class="rank-badge rank-1">1</span>`;
  if (rank === 2) return `<span class="rank-badge rank-2">2</span>`;
  if (rank === 3) return `<span class="rank-badge rank-3">3</span>`;
  return `<span class="rank-badge rank-other">${rank}</span>`;
}

function renderLeaderboardRow(item) {
  return `
    <tr>
      <td>${getRankBadge(item.rank)}</td>
      <td><span style="font-weight:600">${item.name || 'Anonymous'}</span></td>
      <td><span class="text-accent" style="font-weight:700;font-size:0.95rem">${item.score}</span></td>
      <td>${item.challenge}</td>
      <td style="color:var(--text-secondary)">${item.submission_time}</td>
    </tr>
  `;
}

export async function initLeaderboard() {
  const tableBody = document.getElementById('leaderboard-list');
  if (!tableBody) return;

  const data = await getLeaderboard().catch(() => []);
  
  if (!data.length) {
    tableBody.innerHTML = '<tr><td colspan="5" class="table-empty">No ranking data available yet.</td></tr>';
    return;
  }

  tableBody.innerHTML = data.map(renderLeaderboardRow).join('');

  // Handle local searching/filtering
  const searchInput = document.getElementById('leaderboard-search');
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      const q = searchInput.value.toLowerCase();
      const filtered = data.filter(item =>
        item.name.toLowerCase().includes(q) ||
        item.challenge.toLowerCase().includes(q)
      );
      tableBody.innerHTML = filtered.map(renderLeaderboardRow).join('') || '<tr><td colspan="5" class="table-empty">No matching users found.</td></tr>';
    });
  }
}
