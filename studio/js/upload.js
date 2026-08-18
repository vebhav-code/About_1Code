import { createChallenge } from './api.js';

export function initUpload() {
  const form = document.getElementById('create-challenge-form');
  const errorMsg = document.getElementById('upload-error');
  const submitBtn = document.getElementById('submit-challenge');
  const modeSelect = document.getElementById('mode');
  const teamSizeGroup = document.getElementById('team-size-group');
  const teamSizeInput = document.getElementById('team_size');

  if (!form) return;

  if (modeSelect && teamSizeGroup) {
    const updateTeamSizeVisibility = () => {
      if (modeSelect.value === 'team') {
        teamSizeGroup.style.display = 'block';
        if (!teamSizeInput.value || parseInt(teamSizeInput.value, 10) < 2) {
          teamSizeInput.value = '4';
        }
      } else {
        teamSizeGroup.style.display = 'none';
        teamSizeInput.value = '1';
      }
    };
    modeSelect.addEventListener('change', updateTeamSizeVisibility);
    updateTeamSizeVisibility();
  }

  const addConstraintBtn = document.getElementById('add-constraint-btn');
  const constraintsContainer = document.getElementById('constraints-container');

  function createConstraintRow(text = '') {
    if (!constraintsContainer) return;
    const row = document.createElement('div');
    row.className = 'constraint-row';
    row.style.cssText = 'display:flex; gap:8px; align-items:center;';
    row.innerHTML = `
      <input type="text" class="constraint-input form-control" value="${text.replace(/"/g, '&quot;')}" placeholder="e.g. Must work fully offline" style="flex:1; padding:6px 10px; border:1px solid var(--border); border-radius:4px; font-size:0.85rem;" />
      <button type="button" class="button remove-constraint-btn" style="padding:4px 8px; font-size:0.75rem; background:rgba(239,68,68,0.2); color:#fca5a5; border:1px solid rgba(239,68,68,0.4);">✕</button>
    `;

    row.querySelector('.remove-constraint-btn').addEventListener('click', () => {
      row.remove();
    });

    constraintsContainer.appendChild(row);
  }

  if (addConstraintBtn && constraintsContainer) {
    addConstraintBtn.addEventListener('click', () => createConstraintRow());
    // Pre-populate with default constraints for convenience
    createConstraintRow('Must work fully offline');
    createConstraintRow('Must support multiple languages');
    createConstraintRow('Response latency should be low');
  }

  const titleInput = document.getElementById('title');
  const slugInput = document.getElementById('slug');
  let userEditedSlug = false;

  if (slugInput) {
    slugInput.addEventListener('input', () => {
      userEditedSlug = true;
    });
  }

  if (titleInput && slugInput) {
    titleInput.addEventListener('input', () => {
      if (!userEditedSlug) {
        slugInput.value = titleInput.value
          .toLowerCase()
          .trim()
          .replace(/[^a-z0-9]+/g, '-')
          .replace(/(^-|-$)+/g, '');
      }
    });
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (errorMsg) errorMsg.hidden = true;
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Saving...';
    }

    const formData = new FormData(form);
    const mode = formData.get('mode') || 'individual';
    let team_size = parseInt(formData.get('team_size'), 10) || 1;
    if (mode === 'individual') {
      team_size = 1;
    }

    // Collect constraints list
    const constraintInputs = constraintsContainer ? Array.from(constraintsContainer.querySelectorAll('.constraint-input')) : [];
    const constraintsList = constraintInputs
      .map(input => (input.value || '').trim())
      .filter(val => val.length > 0);

    const payload = {
      title: formData.get('title'),
      slug: (formData.get('slug') || '').trim(),
      category: formData.get('category'),
      difficulty: formData.get('difficulty'),
      time_limit: parseInt(formData.get('time_limit'), 10) || 45,
      mode: mode,
      team_size: team_size,
      description: formData.get('description'),
      scenario: formData.get('scenario'),
      rules: formData.get('rules'),
      constraints: constraintsList,
      official_solution: formData.get('official_solution') || ''
    };

    try {
      await createChallenge(payload);
      if (window.showToast) window.showToast('Challenge created successfully!', 'success');
      window.location.hash = 'challenges';
    } catch (error) {
      const msg = error.message || 'Failed to create challenge';
      if (errorMsg) {
        errorMsg.textContent = msg;
        errorMsg.hidden = false;
        errorMsg.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
      if (window.showToast) {
        window.showToast(msg, 'error');
      }
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Create Challenge';
      }
    }
  });
}
