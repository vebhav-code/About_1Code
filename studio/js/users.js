import { getAdminUsers, getAdminUser, banAdminUser, unbanAdminUser } from './api.js';

const fmtDate = (d) => d ? new Date(d).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) : '--';

function roleBadge(isAdmin) {
  if (isAdmin) {
    return `<span class="badge badge-info" style="background:rgba(59,130,246,0.15);color:#60A5FA;border:1px solid rgba(59,130,246,0.3);">Admin</span>`;
  }
  return `<span class="badge badge-neutral">User</span>`;
}

function statusBadge(isBanned) {
  if (isBanned) {
    return `<span class="badge badge-danger" style="background:rgba(239,68,68,0.15);color:#F87171;border:1px solid rgba(239,68,68,0.3);">Banned</span>`;
  }
  return `<span class="badge badge-active">Active</span>`;
}

let _searchDebounce = null;

function renderUserTable(users) {
  const tbody = document.getElementById('user-list');
  if (!tbody) return;

  if (!users || !users.length) {
    tbody.innerHTML = `<tr class="table-empty"><td colspan="8">No users found.</td></tr>`;
    return;
  }

  tbody.innerHTML = users.map(u => `
    <tr data-user-id="${u.id}">
      <td><span class="mono">#${u.id}</span></td>
      <td><span style="font-weight:600">${escapeHtml(u.name)}</span></td>
      <td><span class="mono" style="font-size:0.82rem;color:var(--text-secondary)">${escapeHtml(u.email)}</span></td>
      <td>${roleBadge(u.is_admin)}</td>
      <td>${statusBadge(u.is_banned)}</td>
      <td>${fmtDate(u.created_at)}</td>
      <td>${u.total_completed || u.total_attempted || 0}</td>
      <td>
        <div class="action-row">
          <button class="button button-ghost button-sm" data-action="profile" data-id="${u.id}">Profile</button>
          ${u.is_admin
            ? `<button class="button button-ghost button-sm" disabled title="Admins cannot be banned" style="opacity:0.5;cursor:not-allowed">Ban</button>`
            : u.is_banned
              ? `<button class="button button-ghost button-sm" data-action="unban" data-id="${u.id}" data-name="${escapeHtml(u.name)}" style="color:var(--success)">Unban</button>`
              : `<button class="button button-danger button-sm" data-action="ban" data-id="${u.id}" data-name="${escapeHtml(u.name)}">Ban</button>`
          }
        </div>
      </td>
    </tr>
  `).join('');

  // Event bindings
  tbody.querySelectorAll('[data-action="profile"]').forEach(btn => {
    btn.addEventListener('click', () => openProfileModal(Number(btn.dataset.id)));
  });

  tbody.querySelectorAll('[data-action="ban"]').forEach(btn => {
    btn.addEventListener('click', () => openBanModal(Number(btn.dataset.id), btn.dataset.name));
  });

  tbody.querySelectorAll('[data-action="unban"]').forEach(btn => {
    btn.addEventListener('click', () => handleUnban(Number(btn.dataset.id), btn.dataset.name));
  });
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

async function openProfileModal(userId) {
  const existing = document.getElementById('user-profile-modal');
  if (existing) existing.remove();

  const backdrop = document.createElement('div');
  backdrop.id = 'user-profile-modal';
  backdrop.className = 'modal-backdrop';
  backdrop.innerHTML = `
    <div class="modal" style="max-width:640px;width:90%;">
      <div class="modal-header">
        <h3 class="modal-title">User Profile</h3>
        <button class="modal-close" id="profile-close-btn">✕</button>
      </div>
      <div class="modal-body" id="profile-modal-body" style="max-height:70vh;overflow-y:auto;">
        <p style="color:var(--text-muted);text-align:center;padding:24px;">Loading user profile details...</p>
      </div>
      <div class="modal-footer">
        <button class="button button-ghost" id="profile-done-btn">Close</button>
      </div>
    </div>`;

  document.body.appendChild(backdrop);

  const close = () => backdrop.remove();
  document.getElementById('profile-close-btn').addEventListener('click', close);
  document.getElementById('profile-done-btn').addEventListener('click', close);
  backdrop.addEventListener('click', (e) => { if (e.target === backdrop) close(); });

  try {
    const p = await getAdminUser(userId);
    const bodyEl = document.getElementById('profile-modal-body');
    if (!bodyEl) return;

    const historyRows = (p.history || []).map(h => `
      <tr>
        <td>${escapeHtml(h.challenge_title || 'Challenge')}</td>
        <td>${h.score || 0}/100</td>
        <td>${h.late ? '<span class="badge badge-inactive">Late</span>' : '<span class="badge badge-active">On Time</span>'}</td>
        <td>${fmtDate(h.submitted_at)}</td>
      </tr>
    `).join('');

    bodyEl.innerHTML = `
      <div style="display:flex;align-items:center;gap:16px;margin-bottom:20px;padding-bottom:16px;border-bottom:1px solid var(--border)">
        <div style="width:52px;height:52px;border-radius:50%;background:var(--primary);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:1.4rem;">
          ${(p.name || 'U')[0].toUpperCase()}
        </div>
        <div>
          <h4 style="margin:0 0 4px 0;font-size:1.1rem">${escapeHtml(p.name)}</h4>
          <p style="margin:0;font-size:0.85rem;color:var(--text-secondary);">${escapeHtml(p.email)}</p>
          <div style="margin-top:6px;display:flex;gap:8px;align-items:center;">
            ${roleBadge(p.is_admin)}
            ${statusBadge(p.is_banned)}
          </div>
        </div>
      </div>

      ${p.is_banned ? `
        <div style="background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);border-radius:6px;padding:12px 16px;margin-bottom:20px;">
          <strong style="color:#F87171;display:block;margin-bottom:4px;">🚫 Account Banned</strong>
          <span style="font-size:0.85rem;color:var(--text-secondary);">Reason: ${escapeHtml(p.banned_reason || 'None specified')}</span><br/>
          <span style="font-size:0.75rem;color:var(--text-muted);">Banned on: ${fmtDate(p.banned_at)}</span>
        </div>
      ` : ''}

      <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(130px, 1fr));gap:12px;margin-bottom:24px;">
        <div style="background:var(--bg-muted);padding:12px;border-radius:6px;border:1px solid var(--border);text-align:center;">
          <span style="font-size:0.75rem;color:var(--text-muted);display:block;">Global Rank</span>
          <strong style="font-size:1.2rem;color:var(--text-main);">${p.rank ? '#' + p.rank : 'Unranked'}</strong>
        </div>
        <div style="background:var(--bg-muted);padding:12px;border-radius:6px;border:1px solid var(--border);text-align:center;">
          <span style="font-size:0.75rem;color:var(--text-muted);display:block;">Avg Score</span>
          <strong style="font-size:1.2rem;color:var(--text-main);">${p.average_score || 0}</strong>
        </div>
        <div style="background:var(--bg-muted);padding:12px;border-radius:6px;border:1px solid var(--border);text-align:center;">
          <span style="font-size:0.75rem;color:var(--text-muted);display:block;">Completed</span>
          <strong style="font-size:1.2rem;color:var(--text-main);">${p.total_completed || 0} / ${p.total_attempted || 0}</strong>
        </div>
        <div style="background:var(--bg-muted);padding:12px;border-radius:6px;border:1px solid var(--border);text-align:center;">
          <span style="font-size:0.75rem;color:var(--text-muted);display:block;">Current Streak</span>
          <strong style="font-size:1.2rem;color:var(--text-main);">${p.current_streak || 0}d</strong>
        </div>
      </div>

      <h5 style="margin:0 0 10px 0;font-size:0.9rem;color:var(--text-secondary);">Submission History</h5>
      ${(p.history && p.history.length) ? `
        <table style="width:100%;font-size:0.83rem;">
          <thead>
            <tr>
              <th>Challenge</th>
              <th>Score</th>
              <th>Timing</th>
              <th>Date</th>
            </tr>
          </thead>
          <tbody>${historyRows}</tbody>
        </table>
      ` : '<p style="font-size:0.85rem;color:var(--text-muted);">No submissions recorded yet.</p>'}
    `;
  } catch (err) {
    const bodyEl = document.getElementById('profile-modal-body');
    if (bodyEl) {
      bodyEl.innerHTML = `<p style="color:var(--danger);text-align:center;padding:24px;">Failed to load user profile: ${escapeHtml(err.message)}</p>`;
    }
  }
}

function openBanModal(userId, userName) {
  const existing = document.getElementById('ban-modal');
  if (existing) existing.remove();

  const backdrop = document.createElement('div');
  backdrop.id = 'ban-modal';
  backdrop.className = 'modal-backdrop';
  backdrop.innerHTML = `
    <div class="modal" style="max-width:480px;">
      <div class="modal-header">
        <h3 class="modal-title">Ban User Account</h3>
        <button class="modal-close" id="ban-close-btn">✕</button>
      </div>
      <div class="modal-body">
        <p style="color:var(--text-secondary);line-height:1.6;margin-bottom:16px;">
          Are you sure you want to suspend <strong style="color:var(--danger)">${escapeHtml(userName)}</strong>?
          The user will be prevented from logging in.
        </p>
        <label style="display:block;font-size:0.8rem;font-weight:600;color:var(--text-secondary);margin-bottom:6px;">Reason for Ban (Optional):</label>
        <input type="text" id="ban-reason-input" class="form-input" placeholder="e.g., Terms violation, suspicious activity..." style="width:100%;box-sizing:border-box;" />
      </div>
      <div class="modal-footer">
        <button class="button button-ghost" id="ban-cancel-btn">Cancel</button>
        <button class="button button-danger" id="ban-confirm-btn">Confirm Ban</button>
      </div>
    </div>`;

  document.body.appendChild(backdrop);

  const close = () => backdrop.remove();
  document.getElementById('ban-close-btn').addEventListener('click', close);
  document.getElementById('ban-cancel-btn').addEventListener('click', close);
  backdrop.addEventListener('click', (e) => { if (e.target === backdrop) close(); });

  document.getElementById('ban-confirm-btn').addEventListener('click', async () => {
    const btn = document.getElementById('ban-confirm-btn');
    const reasonInput = document.getElementById('ban-reason-input');
    const reason = reasonInput ? reasonInput.value.trim() : '';

    btn.textContent = 'Processing…';
    btn.disabled = true;

    try {
      await banAdminUser(userId, reason);
      window.showToast(`User ${userName} has been banned.`, 'success');
      close();
      loadUsers();
    } catch (err) {
      window.showToast(err.message, 'error');
      btn.textContent = 'Confirm Ban';
      btn.disabled = false;
    }
  });
}

async function handleUnban(userId, userName) {
  try {
    await unbanAdminUser(userId);
    window.showToast(`User ${userName} has been unbanned.`, 'success');
    loadUsers();
  } catch (err) {
    window.showToast(err.message, 'error');
  }
}

async function loadUsers(query = '') {
  try {
    const users = await getAdminUsers(query);
    renderUserTable(users);
  } catch (err) {
    const tbody = document.getElementById('user-list');
    if (tbody) {
      tbody.innerHTML = `<tr class="table-empty"><td colspan="8" style="color:var(--danger)">Failed to load users: ${escapeHtml(err.message)}</td></tr>`;
    }
  }
}

export async function initUsers() {
  loadUsers();

  const searchInput = document.getElementById('user-search');
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      if (_searchDebounce) clearTimeout(_searchDebounce);
      _searchDebounce = setTimeout(() => {
        loadUsers(searchInput.value.trim());
      }, 300);
    });
  }
}
