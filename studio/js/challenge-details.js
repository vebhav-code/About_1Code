import { getAdminChallengeById, updateAdminChallenge, getLeaderboardBySlug } from './api.js';

export async function initChallengeDetails(id) {
  let details = await getAdminChallengeById(id).catch(() => null);
  if (!details) {
    document.getElementById('page-content').innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">⚠️</div>
        <h4>Challenge not found</h4>
        <p>The requested challenge does not exist or has been deleted.</p>
      </div>`;
    return;
  }

  const renderDetails = () => {
    document.getElementById('challenge-title').textContent = details.title;
    document.getElementById('challenge-description').textContent = details.description || 'No description provided.';
    document.getElementById('challenge-scenario').textContent = details.scenario || 'No scenario provided.';
    document.getElementById('challenge-rules').textContent = Array.isArray(details.rules) ? details.rules.join(', ') : details.rules || 'No rules provided.';
    document.getElementById('challenge-difficulty').innerHTML = getDifficultyBadge(details.difficulty);
    document.getElementById('challenge-time').textContent = `${details.time_limit || 45} minutes`;
    document.getElementById('challenge-status').innerHTML = details.is_active 
      ? `<span class="badge badge-active">Active</span>` 
      : `<span class="badge badge-inactive">Inactive</span>`;

    const createdAtElement = document.getElementById('challenge-created');
    if (createdAtElement && details.created_at) {
      createdAtElement.textContent = new Date(details.created_at).toLocaleString();
    }

    const slugElement = document.getElementById('challenge-slug');
    if (slugElement) {
      slugElement.textContent = details.slug;
    }

    // Toggle button texts/states
    const activateBtn = document.getElementById('activate-challenge');
    const deactivateBtn = document.getElementById('deactivate-challenge');
    if (activateBtn && deactivateBtn) {
      activateBtn.hidden = details.is_active;
      deactivateBtn.hidden = !details.is_active;
    }
  };

  function getDifficultyBadge(diff) {
    const d = (diff || '').toLowerCase();
    if (d === 'easy')   return `<span class="badge badge-easy">Easy</span>`;
    if (d === 'medium') return `<span class="badge badge-medium">Medium</span>`;
    if (d === 'hard')   return `<span class="badge badge-hard">Hard</span>`;
    return `<span class="badge badge-neutral">${diff || 'N/A'}</span>`;
  }

  // Initial render
  renderDetails();

  // Load stats
  const stats = await getLeaderboardBySlug(details.slug).catch(() => []);
  const challengeStats = stats.find(s => s.challenge_slug === details.slug) || { total_participants: 0, average_score: 0.0 };
  
  const participantsEl = document.getElementById('stat-participants');
  const averageEl = document.getElementById('stat-average');
  if (participantsEl) participantsEl.textContent = challengeStats.total_participants;
  if (averageEl) averageEl.textContent = challengeStats.average_score.toFixed(1);

  // Download actions
  const addDownloadHandler = (buttonId, pathSuffix) => {
    const button = document.getElementById(buttonId);
    if (!button) return;
    // Replace old handler
    const newBtn = button.cloneNode(true);
    button.parentNode.replaceChild(newBtn, button);
    newBtn.addEventListener('click', () => {
      window.location.href = `/challenge/${details.slug}/${pathSuffix}`;
    });
  };

  addDownloadHandler('download-reference', 'download');

  // Edit Challenge action
  const editBtn = document.getElementById('edit-challenge');
  if (editBtn) {
    editBtn.addEventListener('click', () => {
      openEditModal();
    });
  }

  // Activate / Deactivate actions
  const toggleStatus = async (isActive) => {
    try {
      const updated = await updateAdminChallenge(details.id, { is_active: isActive });
      details = updated;
      renderDetails();
      window.showToast(`Challenge ${isActive ? 'activated' : 'deactivated'} successfully.`, 'success');
    } catch (err) {
      window.showToast(err.message, 'error');
    }
  };

  const activateBtn = document.getElementById('activate-challenge');
  if (activateBtn) {
    activateBtn.addEventListener('click', () => toggleStatus(true));
  }

  const deactivateBtn = document.getElementById('deactivate-challenge');
  if (deactivateBtn) {
    deactivateBtn.addEventListener('click', () => toggleStatus(false));
  }

  function openEditModal() {
    const existing = document.getElementById('edit-modal');
    if (existing) existing.remove();

    const backdrop = document.createElement('div');
    backdrop.id = 'edit-modal';
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal">
        <div class="modal-header">
          <h3 class="modal-title">Edit Challenge</h3>
          <button class="modal-close" id="edit-close-btn">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label" for="edit-title">Title</label>
            <input type="text" id="edit-title" class="form-input" value="${details.title.replace(/"/g, '&quot;')}">
          </div>
          <div class="form-group">
            <label class="form-label" for="edit-difficulty">Difficulty</label>
            <select id="edit-difficulty" class="form-select">
              <option value="Easy" ${details.difficulty === 'Easy' ? 'selected' : ''}>Easy</option>
              <option value="Medium" ${details.difficulty === 'Medium' ? 'selected' : ''}>Medium</option>
              <option value="Hard" ${details.difficulty === 'Hard' ? 'selected' : ''}>Hard</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label" for="edit-time">Time Limit (minutes)</label>
            <input type="number" id="edit-time" class="form-input" value="${details.time_limit || 45}">
          </div>
          <div class="form-group">
            <label class="form-label" for="edit-description">Description</label>
            <textarea id="edit-description" class="form-textarea">${details.description || ''}</textarea>
          </div>
          <div class="form-group">
            <label class="form-label" for="edit-scenario">Scenario</label>
            <textarea id="edit-scenario" class="form-textarea">${details.scenario || ''}</textarea>
          </div>
          <div class="form-group">
            <label class="form-label" for="edit-rules">Rules</label>
            <textarea id="edit-rules" class="form-textarea">${details.rules || ''}</textarea>
          </div>
          <div class="form-group">
            <label class="form-label" for="edit-starter-code">Starter Code</label>
            <textarea id="edit-starter-code" class="form-textarea" style="font-family:monospace;">${details.starter_code || ''}</textarea>
          </div>
          <div class="form-group">
            <label class="form-label" for="edit-official-solution">Official Solution</label>
            <textarea id="edit-official-solution" class="form-textarea" style="font-family:monospace;">${details.official_solution || ''}</textarea>
          </div>
        </div>
        <div class="modal-footer">
          <button class="button button-ghost" id="edit-cancel-btn">Cancel</button>
          <button class="button button-primary" id="edit-save-btn">Save Changes</button>
        </div>
      </div>`;

    document.body.appendChild(backdrop);

    const close = () => backdrop.remove();
    document.getElementById('edit-close-btn').addEventListener('click', close);
    document.getElementById('edit-cancel-btn').addEventListener('click', close);
    backdrop.addEventListener('click', (e) => { if (e.target === backdrop) close(); });

    document.getElementById('edit-save-btn').addEventListener('click', async () => {
      const saveBtn = document.getElementById('edit-save-btn');
      saveBtn.textContent = 'Saving...';
      saveBtn.disabled = true;

      const payload = {
        title: document.getElementById('edit-title').value,
        difficulty: document.getElementById('edit-difficulty').value,
        time_limit: parseInt(document.getElementById('edit-time').value, 10) || 45,
        description: document.getElementById('edit-description').value,
        scenario: document.getElementById('edit-scenario').value,
        rules: document.getElementById('edit-rules').value,
        starter_code: document.getElementById('edit-starter-code').value,
        official_solution: document.getElementById('edit-official-solution').value
      };

      try {
        const updated = await updateAdminChallenge(details.id, payload);
        details = updated;
        renderDetails();
        window.showToast('Challenge updated successfully.', 'success');
        close();
      } catch (err) {
        window.showToast(err.message, 'error');
        saveBtn.textContent = 'Save Changes';
        saveBtn.disabled = false;
      }
    });
  }
}
