import { getAdminChallenges, updateAdminChallenge, deleteAdminChallenge } from './api.js';

const fmt = (d) => d ? new Date(d).toLocaleDateString('en-GB', { day:'2-digit', month:'short', year:'numeric' }) : '--';

function diffBadge(diff) {
  const d = (diff || '').toLowerCase();
  if (d === 'easy')   return `<span class="badge badge-easy">Easy</span>`;
  if (d === 'medium') return `<span class="badge badge-medium">Medium</span>`;
  if (d === 'hard')   return `<span class="badge badge-hard">Hard</span>`;
  return `<span class="badge badge-neutral">${diff || 'N/A'}</span>`;
}

let _allChallenges = [];

function renderChallenges(challenges) {
  const tbody = document.getElementById('challenge-list');
  if (!tbody) return;

  if (!challenges.length) {
    tbody.innerHTML = `<tr class="table-empty"><td colspan="6">No challenges found. Upload one to get started.</td></tr>`;
    return;
  }

  tbody.innerHTML = challenges.map(c => `
    <tr data-id="${c.id}">
      <td><span class="mono">${c.slug}</span></td>
      <td><span style="font-weight:600">${c.title}</span></td>
      <td>${diffBadge(c.difficulty)}</td>
      <td><span class="badge ${c.is_active ? 'badge-active' : 'badge-inactive'}">${c.is_active ? 'Active' : 'Inactive'}</span></td>
      <td>${fmt(c.created_at)}</td>
      <td>
        <div class="action-row">
          <button class="button button-ghost button-sm" data-action="view"   data-id="${c.id}">Details</button>
          <button class="button button-ghost button-sm" data-action="toggle" data-id="${c.id}" data-active="${c.is_active}">${c.is_active ? 'Deactivate' : 'Activate'}</button>
          <button class="button button-danger button-sm" data-action="delete" data-id="${c.id}" data-title="${c.title.replace(/"/g,'&quot;')}">Delete</button>
        </div>
      </td>
    </tr>`).join('');

  // Bind events
  tbody.querySelectorAll('[data-action="view"]').forEach(btn => {
    btn.addEventListener('click', () => window.location.hash = `challenge/${btn.dataset.id}`);
  });

  tbody.querySelectorAll('[data-action="toggle"]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id       = Number(btn.dataset.id);
      const isActive = btn.dataset.active === 'true';
      try {
        await updateAdminChallenge(id, { is_active: !isActive });
        window.showToast(`Challenge ${isActive ? 'deactivated' : 'activated'} successfully.`, 'success');
        reload();
      } catch (err) {
        window.showToast(err.message, 'error');
      }
    });
  });

  tbody.querySelectorAll('[data-action="delete"]').forEach(btn => {
    btn.addEventListener('click', () => {
      openDeleteModal(Number(btn.dataset.id), btn.dataset.title);
    });
  });
}

function openDeleteModal(id, title) {
  const existing = document.getElementById('delete-modal');
  if (existing) existing.remove();

  const backdrop = document.createElement('div');
  backdrop.id = 'delete-modal';
  backdrop.className = 'modal-backdrop';
  backdrop.innerHTML = `
    <div class="modal">
      <div class="modal-header">
        <h3 class="modal-title">Delete Challenge</h3>
        <button class="modal-close" id="modal-close-btn">✕</button>
      </div>
      <div class="modal-body">
        <p style="color:var(--text-secondary);line-height:1.6">
          Are you sure you want to delete <strong style="color:var(--danger)">${title}</strong>?
          This will mark the challenge as inactive. This action cannot be undone.
        </p>
      </div>
      <div class="modal-footer">
        <button class="button button-ghost" id="modal-cancel-btn">Cancel</button>
        <button class="button button-danger" id="modal-confirm-btn">Delete Challenge</button>
      </div>
    </div>`;

  document.body.appendChild(backdrop);

  const close = () => backdrop.remove();
  document.getElementById('modal-close-btn').addEventListener('click', close);
  document.getElementById('modal-cancel-btn').addEventListener('click', close);
  backdrop.addEventListener('click', (e) => { if (e.target === backdrop) close(); });

  document.getElementById('modal-confirm-btn').addEventListener('click', async () => {
    const btn = document.getElementById('modal-confirm-btn');
    btn.textContent = 'Deleting…';
    btn.disabled = true;
    try {
      await deleteAdminChallenge(id);
      window.showToast('Challenge deleted successfully.', 'success');
      close();
      reload();
    } catch (err) {
      window.showToast(err.message, 'error');
      btn.textContent = 'Delete Challenge';
      btn.disabled = false;
    }
  });
}

async function reload() {
  _allChallenges = await getAdminChallenges().catch(() => []);
  renderChallenges(_allChallenges);
}

export async function initChallenges() {
  _allChallenges = await getAdminChallenges().catch(() => []);
  renderChallenges(_allChallenges);

  document.getElementById('new-challenge')?.addEventListener('click', () => {
    window.location.hash = 'upload-challenge';
  });

  // Search filter
  const searchInput = document.getElementById('challenge-search');
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      const q = searchInput.value.toLowerCase();
      const filtered = _allChallenges.filter(c =>
        c.title.toLowerCase().includes(q) ||
        c.slug.toLowerCase().includes(q) ||
        (c.difficulty || '').toLowerCase().includes(q)
      );
      renderChallenges(filtered);
    });
  }

  // Status filter
  const statusFilter = document.getElementById('challenge-filter');
  if (statusFilter) {
    statusFilter.addEventListener('change', () => {
      const val = statusFilter.value;
      const filtered = val === 'all' ? _allChallenges
        : val === 'active'   ? _allChallenges.filter(c => c.is_active)
        : _allChallenges.filter(c => !c.is_active);
      renderChallenges(filtered);
    });
  }
}
