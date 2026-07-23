import { createChallenge } from './api.js';

export function initUpload() {
  const form = document.getElementById('create-challenge-form');
  const errorMsg = document.getElementById('upload-error');
  const submitBtn = document.getElementById('submit-challenge');

  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (errorMsg) errorMsg.hidden = true;
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Saving...';
    }

    const formData = new FormData(form);
    const payload = {
      title: formData.get('title'),
      slug: formData.get('slug'),
      category: formData.get('category'),
      difficulty: formData.get('difficulty'),
      time_limit: parseInt(formData.get('time_limit'), 10) || 45,
      description: formData.get('description'),
      scenario: formData.get('scenario'),
      rules: formData.get('rules'),
      starter_code: formData.get('starter_code'),
      official_solution: formData.get('official_solution')
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
