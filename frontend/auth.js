/* =========================================================
   1Code — Auth page logic
   Handles tab switching + talks to the FastAPI backend for
   register/login. No JWT/session — per project scope, we just
   store {user_id, name} in localStorage after a successful call.
   ========================================================= */

// Update this once the backend is deployed to Render.
const API_BASE = 'RENDER_URL';

document.addEventListener('DOMContentLoaded', () => {

  const tabs = document.querySelectorAll('.auth-tab');
  const indicator = document.getElementById('tabIndicator');
  const forms = document.querySelectorAll('.auth-form');
  const switchSpans = document.querySelectorAll('.auth-switch [data-show-on]');
  const errorEl = document.getElementById('authError');

  function setTab(name) {
    tabs.forEach(t => t.classList.toggle('active', t.dataset.tab === name));
    forms.forEach(f => f.classList.toggle('active', f.dataset.form === name));
    switchSpans.forEach(s => s.hidden = s.dataset.showOn !== name);
    indicator.classList.toggle('to-register', name === 'register');
    hideError();
  }

  tabs.forEach(tab => {
    tab.addEventListener('click', () => setTab(tab.dataset.tab));
  });
  document.querySelectorAll('[data-switch-to]').forEach(btn => {
    btn.addEventListener('click', () => setTab(btn.dataset.switchTo));
  });

  function showError(message) {
    errorEl.textContent = message;
    errorEl.hidden = false;
  }
  function hideError() {
    errorEl.hidden = true;
  }

  function setLoading(form, loading) {
    const btn = form.querySelector('.auth-submit');
    const text = btn.querySelector('.btn-text');
    const spinner = btn.querySelector('.btn-spinner');
    btn.disabled = loading;
    spinner.hidden = !loading;
    text.style.opacity = loading ? '0.6' : '1';
  }

  function saveSession(user) {
    localStorage.setItem('1code_user', JSON.stringify(user));
  }

  /* ---------- LOGIN ---------- */
  const loginForm = document.getElementById('loginForm');
  loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    hideError();
    setLoading(loginForm, true);

    const payload = {
      email: document.getElementById('loginEmail').value.trim(),
      password: document.getElementById('loginPassword').value,
    };

    try {
      const res = await fetch(`${API_BASE}/api/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (res.status === 401) {
        showError('Invalid Credentials');
        return;
      }
      if (!res.ok) {
        showError('Something went wrong. Please try again.');
        return;
      }

      const data = await res.json();
      saveSession({ user_id: data.user_id, name: data.name });
      window.location.href = 'contest.html';

    } catch (err) {
      showError('Could not reach the server. Is the backend running?');
    } finally {
      setLoading(loginForm, false);
    }
  });

  /* ---------- REGISTER ---------- */
  const registerForm = document.getElementById('registerForm');
  registerForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    hideError();
    setLoading(registerForm, true);

    const payload = {
      name: document.getElementById('registerName').value.trim(),
      email: document.getElementById('registerEmail').value.trim(),
      password: document.getElementById('registerPassword').value,
    };

    try {
      const res = await fetch(`${API_BASE}/api/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (res.status === 400) {
        const data = await res.json().catch(() => ({}));
        showError(data.detail || 'That email is already registered.');
        return;
      }
      if (!res.ok) {
        showError('Something went wrong. Please try again.');
        return;
      }

      const data = await res.json();
      // Registration doubles as login for this prototype — no separate
      // session step exists, so we go straight to the dashboard.
      saveSession({ user_id: data.id, name: data.name });
      window.location.href = 'contest.html';

    } catch (err) {
      showError('Could not reach the server. Is the backend running?');
    } finally {
      setLoading(registerForm, false);
    }
  });

});