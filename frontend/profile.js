const API_BASE = (
  window.location.hostname === '127.0.0.1' ||
  window.location.hostname === 'localhost' ||
  window.location.protocol === 'file:' ||
  !window.location.hostname
)
  ? 'http://127.0.0.1:8000'
  : 'https://about-1code.onrender.com';

let currentProfile = null;
let showAllHistory = false;

function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString();
}

function getInitials(name) {
  if (!name) return '?';
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
}

function getFullAvatarUrl(url) {
  if (!url) return null;
  if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('data:')) {
    return url;
  }
  return `${API_BASE}${url.startsWith('/') ? '' : '/'}${url}`;
}

async function loadProfile() {
  const session = JSON.parse(localStorage.getItem('1code_user') || 'null');
  const urlParams = new URLSearchParams(window.location.search);
  let targetUserId = urlParams.get('user_id') || session?.user_id;

  if (!targetUserId) {
    targetUserId = 1; // Default to user #1 if not logged in so profile displays real backend data
  }

  try {
    const res = await fetch(`${API_BASE}/api/users/${targetUserId}/profile`);
    if (res.status === 404) {
      // This user_id doesn't exist in the current database — almost
      // always a stale login from a different environment (local vs
      // deployed, or a database that's since been reset). Clear it and
      // send them back to log in fresh, instead of showing a broken page.
      localStorage.removeItem('1code_user');
      window.location.href = 'auth.html';
      return;
    }

    if (!res.ok) {
      document.getElementById('sidebarName').textContent = 'User #' + targetUserId;
      document.getElementById('sidebarBio').textContent = 'Profile data unavailable (HTTP ' + res.status + ')';
      return;
    }

    currentProfile = await res.json();
    const profile = currentProfile;

    // 1. Sidebar Identity Card
    document.getElementById('sidebarName').textContent = profile.name || 'User';
    document.getElementById('sidebarBio').textContent = profile.bio || (session?.user_id == targetUserId ? 'No bio added yet. Click Edit Profile to add one.' : 'No bio provided.');
    document.getElementById('metaJoined').textContent = formatDate(profile.joined_at);
    document.getElementById('metaRank').textContent = profile.rank ? `#${profile.rank}` : 'Unranked';
    document.getElementById('metaPercentile').textContent = profile.percentile ? `Top ${profile.percentile}%` : 'N/A';
    
    const attempted = profile.total_attempted ?? 0;
    const completed = profile.total_completed ?? 0;
    document.getElementById('metaRatio').textContent = `${completed} / ${attempted}`;
    const rate = attempted > 0 ? Math.round((completed / attempted) * 100) : 0;
    document.getElementById('metaRate').textContent = `${rate}%`;
    document.getElementById('metaAvgScore').textContent = profile.average_score ?? 0;
    document.getElementById('metaPoints').textContent = profile.weighted_points ?? 0;

    const sidebarAvatar = document.getElementById('sidebarAvatar');
    if (sidebarAvatar) {
      const fullAvatarUrl = getFullAvatarUrl(profile.avatar_url);
      if (fullAvatarUrl) {
        sidebarAvatar.innerHTML = `<img src="${fullAvatarUrl}" alt="${profile.name || 'Avatar'}" onerror="this.onerror=null; this.parentElement.textContent='${getInitials(profile.name)}';">`;
      } else {
        sidebarAvatar.textContent = getInitials(profile.name);
      }
    }

    const editBtn = document.getElementById('editProfileBtn');
    if (editBtn) {
      // Show edit profile button if logged in as this user, or if viewing default profile
      if (session?.user_id && session.user_id == targetUserId) {
        editBtn.style.display = 'inline-flex';
      } else {
        editBtn.style.display = 'none';
      }
    }

    // 2. Difficulty Ring & Breakdown
    renderDifficultyBreakdown(profile.difficulty_breakdown, completed);

    // 3. Streak & Activity Heatmap
    document.getElementById('currentStreakVal').textContent = `${profile.current_streak ?? 0} ${profile.current_streak === 1 ? 'day' : 'days'}`;
    document.getElementById('longestStreakVal').textContent = `${profile.longest_streak ?? 0} ${profile.longest_streak === 1 ? 'day' : 'days'}`;
    renderHeatmap(profile.visit_calendar || []);

    // 4. Category Breakdown
    renderCategoryBreakdown(profile.category_breakdown || []);

    // 5. Badges
    renderBadges(profile.badges || []);

    // 6. History Table
    renderHistoryTable(profile.history || []);
  } catch (err) {
    console.error('Failed to load profile from backend:', err);
    document.getElementById('sidebarName').textContent = 'Connection Error';
    document.getElementById('sidebarBio').textContent = 'Could not fetch profile from ' + API_BASE;
  }
}

function renderDifficultyBreakdown(diffData, totalCompleted) {
  const easy = diffData?.Easy || { solved: 0, total: 0 };
  const medium = diffData?.Medium || { solved: 0, total: 0 };
  const hard = diffData?.Hard || { solved: 0, total: 0 };

  document.getElementById('donutTotalNum').textContent = totalCompleted;

  // Text values
  document.getElementById('diffEasyVal').textContent = `${easy.solved} / ${easy.total}`;
  document.getElementById('diffMediumVal').textContent = `${medium.solved} / ${medium.total}`;
  document.getElementById('diffHardVal').textContent = `${hard.solved} / ${hard.total}`;

  // Progress bars
  document.getElementById('diffEasyBar').style.width = `${easy.total ? Math.min(100, Math.round((easy.solved / easy.total) * 100)) : 0}%`;
  document.getElementById('diffMediumBar').style.width = `${medium.total ? Math.min(100, Math.round((medium.solved / medium.total) * 100)) : 0}%`;
  document.getElementById('diffHardBar').style.width = `${hard.total ? Math.min(100, Math.round((hard.solved / hard.total) * 100)) : 0}%`;

  // Inline SVG Donut Ring rendering
  const svg = document.getElementById('donutSvg');
  if (!svg) return;

  const totalSolved = easy.solved + medium.solved + hard.solved;
  const baseCircle = '<circle cx="21" cy="21" r="15.91549430918954" fill="transparent" stroke="rgba(255,255,255,0.06)" stroke-width="4"></circle>';

  if (totalSolved === 0) {
    svg.innerHTML = baseCircle;
    return;
  }

  const easyPct = (easy.solved / totalSolved) * 100;
  const mediumPct = (medium.solved / totalSolved) * 100;
  const hardPct = (hard.solved / totalSolved) * 100;

  let circlesHTML = baseCircle;
  let offset = 0;

  if (easyPct > 0) {
    circlesHTML += `<circle cx="21" cy="21" r="15.91549430918954" fill="transparent" stroke="#34D399" stroke-width="4" stroke-dasharray="${easyPct} ${100 - easyPct}" stroke-dashoffset="-${offset}"></circle>`;
    offset += easyPct;
  }
  if (mediumPct > 0) {
    circlesHTML += `<circle cx="21" cy="21" r="15.91549430918954" fill="transparent" stroke="#F5A623" stroke-width="4" stroke-dasharray="${mediumPct} ${100 - mediumPct}" stroke-dashoffset="-${offset}"></circle>`;
    offset += mediumPct;
  }
  if (hardPct > 0) {
    circlesHTML += `<circle cx="21" cy="21" r="15.91549430918954" fill="transparent" stroke="#F87171" stroke-width="4" stroke-dasharray="${hardPct} ${100 - hardPct}" stroke-dashoffset="-${offset}"></circle>`;
  }

  svg.innerHTML = circlesHTML;
}

function renderHeatmap(calendarData) {
  const grid = document.getElementById('heatmapGrid');
  const subtext = document.getElementById('heatmapSubtext');
  if (!grid) return;

  const activeCount = calendarData.filter(d => d.active).length;
  if (subtext) {
    subtext.textContent = `${activeCount} active ${activeCount === 1 ? 'day' : 'days'} in past 90 days`;
  }

  grid.innerHTML = calendarData.map((item) => {
    const formattedDate = formatDate(item.date);
    const statusText = item.active ? 'Visited / Active' : 'No visit';
    const activeClass = item.active ? 'active' : '';
    return `<div class="heatmap-cell ${activeClass}" title="${formattedDate}: ${statusText}"></div>`;
  }).join('');
}

function renderCategoryBreakdown(categories) {
  const categoryList = document.getElementById('categoryList');
  if (!categoryList) return;

  if (!categories?.length) {
    categoryList.innerHTML = '<p style="color: var(--text-secondary); font-size: 0.9rem;">No completed challenges yet.</p>';
    return;
  }

  categoryList.innerHTML = categories.map((item) => {
    const width = Math.min(100, Math.max(8, item.average_score));
    return `
      <div class="category-row">
        <div class="category-label">
          <span style="font-weight: 500;">${item.category}</span>
          <span class="meta-val">${item.average_score} avg (${item.count} solved)</span>
        </div>
        <div class="bar-track">
          <div class="bar-fill" style="width: ${width}%"></div>
        </div>
      </div>
    `;
  }).join('');
}

function renderBadges(badges) {
  const badgeList = document.getElementById('badgeList');
  if (!badgeList) return;

  if (!badges?.length) {
    badgeList.innerHTML = '<p style="color: var(--text-secondary); font-size: 0.9rem;">No badges earned yet.</p>';
    return;
  }

  badgeList.innerHTML = badges.map((badge) => `
    <div class="badge-chip" title="${badge.description || ''}">${badge.name}</div>
  `).join('');
}

function renderHistoryTable(history) {
  const wrap = document.getElementById('historyTableWrap');
  const footer = document.getElementById('historyFooter');
  const toggleBtn = document.getElementById('toggleHistoryBtn');
  if (!wrap) return;

  if (!history?.length) {
    wrap.innerHTML = '<p style="color: var(--text-secondary); font-size: 0.9rem;">No submission history yet.</p>';
    if (footer) footer.style.display = 'none';
    return;
  }

  const itemsToShow = showAllHistory ? history : history.slice(0, 5);

  wrap.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Challenge</th>
          <th>Difficulty</th>
          <th>Mode</th>
          <th>Score</th>
          <th>Submitted</th>
        </tr>
      </thead>
      <tbody>
        ${itemsToShow.map((item) => `
          <tr>
            <td><a class="table-link" href="result.html?id=${item.submission_id}">${item.challenge_title}</a></td>
            <td>${item.difficulty || '—'}</td>
            <td>${item.mode || 'individual'}</td>
            <td><span class="meta-val">${item.score ?? '—'}</span></td>
            <td>${formatDate(item.submitted_at)}</td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;

  if (history.length > 5) {
    if (footer) footer.style.display = 'block';
    if (toggleBtn) {
      toggleBtn.textContent = showAllHistory ? 'Show Less' : `View All Submissions (${history.length})`;
      toggleBtn.onclick = () => {
        showAllHistory = !showAllHistory;
        renderHistoryTable(history);
      };
    }
  } else if (footer) {
    footer.style.display = 'none';
  }
}

// Edit Modal Logic
function initEditModal() {
  const modal = document.getElementById('editModal');
  const editBtn = document.getElementById('editProfileBtn');
  const closeBtn = document.getElementById('closeModalBtn');
  const cancelBtn = document.getElementById('cancelModalBtn');
  const form = document.getElementById('editProfileForm');
  const bioInput = document.getElementById('bioInput');
  const bioCharCount = document.getElementById('bioCharCount');
  const avatarUrlInput = document.getElementById('avatarUrlInput');
  const avatarFileInput = document.getElementById('avatarFileInput');
  const modalAlert = document.getElementById('modalAlert');

  if (!modal || !editBtn) return;

  const openModal = () => {
    modalAlert.style.display = 'none';
    modalAlert.textContent = '';
    bioInput.value = currentProfile?.bio || '';
    avatarUrlInput.value = currentProfile?.avatar_url || '';
    avatarFileInput.value = '';
    bioCharCount.textContent = `${bioInput.value.length} / 280`;
    modal.style.display = 'flex';
  };

  const closeModal = () => {
    modal.style.display = 'none';
  };

  editBtn.addEventListener('click', openModal);
  if (closeBtn) closeBtn.addEventListener('click', closeModal);
  if (cancelBtn) cancelBtn.addEventListener('click', closeModal);

  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeModal();
  });

  if (bioInput && bioCharCount) {
    bioInput.addEventListener('input', () => {
      bioCharCount.textContent = `${bioInput.value.length} / 280`;
    });
  }

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      modalAlert.style.display = 'none';
      modalAlert.textContent = '';

      const session = JSON.parse(localStorage.getItem('1code_user') || 'null');
      const targetUserId = session?.user_id || currentProfile?.user_id || 1;

      const saveBtn = document.getElementById('saveProfileBtn');
      if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.textContent = 'Saving...';
      }

      try {
        let avatarUrl = avatarUrlInput.value.trim() || null;

        // Step 1: Upload file if selected
        if (avatarFileInput?.files?.length > 0) {
          const formData = new FormData();
          formData.append('file', avatarFileInput.files[0]);

          const uploadRes = await fetch(`${API_BASE}/api/users/${targetUserId}/avatar`, {
            method: 'POST',
            body: formData,
          });

          if (!uploadRes.ok) {
            const errData = await uploadRes.json().catch(() => ({}));
            throw new Error(errData.detail || 'Failed to upload avatar image');
          }
          const updatedProfile = await uploadRes.json();
          avatarUrl = updatedProfile.avatar_url;
        }

        // Step 2: PATCH bio and avatar_url
        const patchRes = await fetch(`${API_BASE}/api/users/${targetUserId}/profile`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            bio: bioInput.value.trim(),
            avatar_url: avatarUrl,
          }),
        });

        if (!patchRes.ok) {
          const errData = await patchRes.json().catch(() => ({}));
          throw new Error(errData.detail || 'Failed to update profile');
        }

        closeModal();
        await loadProfile();
      } catch (err) {
        modalAlert.textContent = err.message;
        modalAlert.style.display = 'block';
      } finally {
        if (saveBtn) {
          saveBtn.disabled = false;
          saveBtn.textContent = 'Save Changes';
        }
      }
    });
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    loadProfile();
    initEditModal();
  });
} else {
  loadProfile();
  initEditModal();
}
