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

  const addFileBtn = document.getElementById('add-file-btn');
  const filesContainer = document.getElementById('project-files-container');
  let fileCount = 0;

  function createFileCard(filename = '', starterContent = '', solutionContent = '') {
    fileCount++;
    const card = document.createElement('div');
    card.className = 'file-card';
    card.style.cssText = 'border:1px solid var(--border); border-radius:6px; padding:12px; background:rgba(0,0,0,0.2); position:relative;';
    card.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
        <label style="font-weight:600; font-size:0.85rem;">Filename</label>
        <button type="button" class="button remove-file-btn" style="padding:2px 8px; font-size:0.75rem; background:rgba(239,68,68,0.2); color:#fca5a5; border:1px solid rgba(239,68,68,0.4);">Delete File</button>
      </div>
      <input type="text" class="file-name-input form-control" value="${filename}" placeholder="e.g. api.py or validator.py" required style="width:100%; padding:6px; margin-bottom:10px; font-family:monospace; font-size:0.85rem;" />
      
      <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px;">
        <div>
          <label style="font-weight:600; font-size:0.8rem; display:block; margin-bottom:4px;">Starter Content (Broken)</label>
          <textarea class="file-starter-input form-control" rows="6" placeholder="Broken starter code teams will start with..." style="width:100%; padding:6px; font-family:monospace; font-size:0.8rem;">${starterContent}</textarea>
        </div>
        <div>
          <label style="font-weight:600; font-size:0.8rem; display:block; margin-bottom:4px;">Official Solution (Fixed)</label>
          <textarea class="file-solution-input form-control" rows="6" placeholder="Reference solution code..." style="width:100%; padding:6px; font-family:monospace; font-size:0.8rem;">${solutionContent}</textarea>
        </div>
      </div>
    `;

    card.querySelector('.remove-file-btn').addEventListener('click', () => {
      card.remove();
    });

    filesContainer.appendChild(card);
  }

  if (addFileBtn && filesContainer) {
    addFileBtn.addEventListener('click', () => createFileCard());
    // Pre-populate with 2 initial file cards for convenience (e.g. api.py and test_api.py)
    createFileCard('api.py', '# Write buggy API code here\n', '# Correct API code\n');
    createFileCard('test_api.py', 'def test_solution():\n    assert True\n', 'def test_solution():\n    assert True\n');
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

    // Collect project files from cards
    const fileCards = filesContainer ? Array.from(filesContainer.querySelectorAll('.file-card')) : [];
    const filesList = [];

    fileCards.forEach((card, index) => {
      const nameInput = card.querySelector('.file-name-input');
      const starterInput = card.querySelector('.file-starter-input');
      const solutionInput = card.querySelector('.file-solution-input');
      const nameVal = (nameInput?.value || '').trim();
      if (nameVal) {
        filesList.push({
          filename: nameVal,
          starter_content: starterInput?.value || '',
          solution_content: solutionInput?.value || '',
          file_order: index
        });
      }
    });

    const payload = {
      title: formData.get('title'),
      slug: formData.get('slug'),
      category: formData.get('category'),
      difficulty: formData.get('difficulty'),
      time_limit: parseInt(formData.get('time_limit'), 10) || 45,
      mode: mode,
      team_size: team_size,
      description: formData.get('description'),
      scenario: formData.get('scenario'),
      rules: formData.get('rules'),
      run_command: formData.get('run_command') || 'pytest',
      files: filesList,
      starter_code: formData.get('starter_code') || '',
      official_solution: formData.get('official_solution') || ''
    };

    try {
      await createChallenge(payload);
      window.showToast('Challenge created successfully!', 'success');
      window.location.hash = 'challenges';
    } catch (error) {
      if (errorMsg) {
        errorMsg.textContent = error.message || 'Failed to create challenge';
        errorMsg.hidden = false;
      } else {
        window.showToast(error.message, 'error');
      }
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Create Challenge';
      }
    }
  });
}

