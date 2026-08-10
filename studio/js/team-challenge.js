import { createChallenge } from './api.js';

export function initTeamChallenge() {
  const form = document.getElementById('create-team-challenge-form');
  const errorMsg = document.getElementById('team-upload-error');
  const submitBtn = document.getElementById('submit-team-challenge');

  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (errorMsg) errorMsg.hidden = true;
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Saving...';
    }

    const formData = new FormData(form);
    const taskDescription = (formData.get('task_description') || '').trim();
    const teamSize = parseInt(formData.get('team_size'), 10) || 4;

    const payload = {
      title: (formData.get('title') || '').trim(),
      slug: (formData.get('slug') || '').trim(),
      category: formData.get('category'),
      difficulty: formData.get('difficulty'),
      time_limit: parseInt(formData.get('time_limit'), 10) || 60,
      mode: 'team',
      team_size: teamSize,
      challenge_format: 'build',
      description: taskDescription,
      scenario: taskDescription,
      rules: 'Build a complete, working project from scratch that satisfies the task description. Work together with your team in the live multi-file editor.',
      run_command: 'pytest',
      starter_code: '',
      official_solution: '',
      files: []
    };

    try {
      await createChallenge(payload);
      if (typeof window.showToast === 'function') {
        window.showToast('Build Team Challenge created successfully!', 'success');
      }
      window.location.hash = 'challenges';
    } catch (error) {
      if (errorMsg) {
        errorMsg.textContent = error.message || 'Failed to create team challenge';
        errorMsg.hidden = false;
      } else if (typeof window.showToast === 'function') {
        window.showToast(error.message, 'error');
      }
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Create Team Build Challenge';
      }
    }
  });
}
