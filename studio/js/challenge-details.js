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
    
    const constraintsEl = document.getElementById('challenge-constraints');
    if (constraintsEl) {
      constraintsEl.innerHTML = '';
      const constraintsList = Array.isArray(details.constraints) ? details.constraints : [];
      if (constraintsList.length > 0) {
        constraintsList.forEach(c => {
          const li = document.createElement('li');
          li.textContent = c;
          constraintsEl.appendChild(li);
        });
      } else {
        constraintsEl.innerHTML = '<li>No explicit constraints specified.</li>';
      }
    }

    document.getElementById('challenge-rules').textContent = Array.isArray(details.rules) ? details.rules.join(', ') : details.rules || 'No rules provided.';
    document.getElementById('challenge-difficulty').innerHTML = getDifficultyBadge(details.difficulty);
    const modeEl = document.getElementById('challenge-mode');
    if (modeEl) {
      const isTeam = details.mode === 'team';
      const modeStr = isTeam ? `Team (${details.team_size || 4})` : 'Individual';
      const badgeClass = isTeam ? 'badge-info' : 'badge-neutral';
      modeEl.innerHTML = `<span class="badge ${badgeClass}">${modeStr}</span>`;
    }
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

  renderDetails();

  const stats = await getLeaderboardBySlug(details.slug).catch(() => []);
  const challengeStats = stats.find(s => s.challenge_slug === details.slug) || { total_participants: 0, average_score: 0.0 };
  
  const participantsEl = document.getElementById('stat-participants');
  const averageEl = document.getElementById('stat-average');
  if (participantsEl) participantsEl.textContent = challengeStats.total_participants;
  if (averageEl) averageEl.textContent = challengeStats.average_score.toFixed(1);

  const addDownloadHandler = (buttonId, pathSuffix) => {
    const button = document.getElementById(buttonId);
    if (!button) return;
    const newBtn = button.cloneNode(true);
    button.parentNode.replaceChild(newBtn, button);
    newBtn.addEventListener('click', () => {
      window.location.href = `/challenge/${details.slug}/${pathSuffix}`;
    });
  };

  addDownloadHandler('download-reference', 'download');

  const editBtn = document.getElementById('edit-challenge');
  if (editBtn) {
    editBtn.addEventListener('click', () => {
      openEditModal();
    });
  }

  const toggleStatus = async (isActive) => {
    try {
      const updated = await updateAdminChallenge(details.id, { is_active: isActive });
      details = updated;
      renderDetails();
      if (window.showToast) window.showToast(`Challenge ${isActive ? 'activated' : 'deactivated'} successfully.`, 'success');
    } catch (err) {
      if (window.showToast) window.showToast(err.message, 'error');
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
            <label class="form-label" for="edit-mode">Mode</label>
            <select id="edit-mode" class="form-select">
              <option value="individual" ${(details.mode || 'individual') === 'individual' ? 'selected' : ''}>Individual</option>
              <option value="team" ${details.mode === 'team' ? 'selected' : ''}>Team</option>
            </select>
          </div>
          <div class="form-group" id="edit-team-size-group" style="${details.mode === 'team' ? '' : 'display:none;'}">
            <label class="form-label" for="edit-team-size">Team Size</label>
            <input type="number" id="edit-team-size" class="form-input" min="2" max="8" value="${details.team_size || 4}">
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

          <!-- Constraints Section -->
          <div style="border:1px solid var(--border); border-radius:6px; padding:12px; background:rgba(255,255,255,0.02); margin-bottom:14px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
              <label class="form-label" style="margin:0; font-weight:700;">Explicit Constraints</label>
              <button type="button" id="edit-add-constraint-btn" class="button" style="padding:4px 10px; font-size:0.8rem;">+ Add Constraint</button>
            </div>
            <div id="edit-constraints-container" style="display:flex; flex-direction:column; gap:8px;"></div>
          </div>

          <div class="form-group">
            <label class="form-label" for="edit-official-solution">Reference Approach Notes (Grading Calibration)</label>
            <textarea id="edit-official-solution" class="form-textarea">${details.official_solution || ''}</textarea>
          </div>
        </div>
        <div class="modal-footer">
          <button class="button button-ghost" id="edit-cancel-btn">Cancel</button>
          <button class="button button-primary" id="edit-save-btn">Save Changes</button>
        </div>
      </div>`;

    document.body.appendChild(backdrop);

    const editConstraintsContainer = document.getElementById('edit-constraints-container');
    const editAddConstraintBtn = document.getElementById('edit-add-constraint-btn');

    function createEditConstraintRow(text = '') {
      const row = document.createElement('div');
      row.className = 'constraint-row';
      row.style.cssText = 'display:flex; gap:8px; align-items:center;';
      row.innerHTML = `
        <input type="text" class="constraint-input form-input" value="${text.replace(/"/g, '&quot;')}" placeholder="e.g. Must work offline" style="flex:1; font-size:0.8rem;" />
        <button type="button" class="button remove-constraint-btn" style="padding:2px 8px; font-size:0.75rem; background:rgba(239,68,68,0.2); color:#fca5a5;">✕</button>
      `;
      row.querySelector('.remove-constraint-btn').addEventListener('click', () => row.remove());
      editConstraintsContainer.appendChild(row);
    }

    if (editAddConstraintBtn && editConstraintsContainer) {
      editAddConstraintBtn.addEventListener('click', () => createEditConstraintRow());
      const currentConstraints = Array.isArray(details.constraints) ? details.constraints : [];
      currentConstraints.forEach(c => createEditConstraintRow(c));
    }

    const close = () => backdrop.remove();
    document.getElementById('edit-close-btn').addEventListener('click', close);
    document.getElementById('edit-cancel-btn').addEventListener('click', close);
    backdrop.addEventListener('click', (e) => { if (e.target === backdrop) close(); });

    const editModeSelect = document.getElementById('edit-mode');
    const editTeamGroup = document.getElementById('edit-team-size-group');
    const editTeamInput = document.getElementById('edit-team-size');
    if (editModeSelect && editTeamGroup) {
      editModeSelect.addEventListener('change', () => {
        if (editModeSelect.value === 'team') {
          editTeamGroup.style.display = '';
          if (!editTeamInput.value || parseInt(editTeamInput.value, 10) < 2) {
            editTeamInput.value = '4';
          }
        } else {
          editTeamGroup.style.display = 'none';
          editTeamInput.value = '1';
        }
      });
    }

    document.getElementById('edit-save-btn').addEventListener('click', async () => {
      const saveBtn = document.getElementById('edit-save-btn');
      saveBtn.textContent = 'Saving...';
      saveBtn.disabled = true;

      const mode = document.getElementById('edit-mode').value;
      let team_size = parseInt(document.getElementById('edit-team-size').value, 10) || 1;
      if (mode === 'individual') team_size = 1;

      const constraintInputs = editConstraintsContainer ? Array.from(editConstraintsContainer.querySelectorAll('.constraint-input')) : [];
      const constraintsList = constraintInputs
        .map(input => (input.value || '').trim())
        .filter(val => val.length > 0);

      const payload = {
        title: document.getElementById('edit-title').value,
        difficulty: document.getElementById('edit-difficulty').value,
        time_limit: parseInt(document.getElementById('edit-time').value, 10) || 45,
        mode: mode,
        team_size: team_size,
        description: document.getElementById('edit-description').value,
        scenario: document.getElementById('edit-scenario').value,
        rules: document.getElementById('edit-rules').value,
        constraints: constraintsList,
        official_solution: document.getElementById('edit-official-solution').value
      };

      try {
        const updated = await updateAdminChallenge(details.id, payload);
        details = updated;
        renderDetails();
        if (window.showToast) window.showToast('Challenge updated successfully.', 'success');
        close();
      } catch (err) {
        if (window.showToast) window.showToast(err.message, 'error');
        saveBtn.textContent = 'Save Changes';
        saveBtn.disabled = false;
      }
    });

  }
}
