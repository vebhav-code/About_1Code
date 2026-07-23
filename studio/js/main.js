import { initDashboard }       from './dashboard.js';
import { initUpload }          from './upload.js';
import { initChallenges }      from './challenges.js';
import { initChallengeDetails } from './challenge-details.js';
import { initSubmissions }     from './submissions.js';
import { initAnalytics }       from './analytics.js';
import { initLeaderboard }     from './leaderboard.js';

// ─── Authentication Guard ───────────────────────────
const adminKey = localStorage.getItem('1code_admin_key');
const session = sessionStorage.getItem('admin_user');
if (!adminKey) {
  window.location.replace('login.html');
} else {
  const user = session ? JSON.parse(session) : { name: 'Admin User' };
  const nameEl = document.getElementById('user-display-name');
  const avatarEl = document.getElementById('avatar-letter');
  if (nameEl) nameEl.textContent = user.name || 'Admin User';
  if (avatarEl && user.name) avatarEl.textContent = user.name[0].toUpperCase();
}

// ─── DOM refs ──────────────────────────────────────
const pageContent  = document.getElementById('page-content');
const pageTitle    = document.getElementById('page-title');
const pageBreadcrumb = document.getElementById('page-breadcrumb');
const pageLoading  = document.getElementById('page-loading');
const navLinks     = document.querySelectorAll('.studio-nav .nav-link');
const quickUpload  = document.getElementById('quick-upload');

// ─── Route map ─────────────────────────────────────
const ROUTES = {
  dashboard:        { title: 'Dashboard',       breadcrumb: 'Overview',     init: initDashboard,       fragment: 'pages/dashboard.html' },
  'upload-challenge':{ title: 'Upload Challenge', breadcrumb: 'Upload',      init: initUpload,          fragment: 'pages/upload-challenge.html' },
  challenges:       { title: 'Challenges',      breadcrumb: 'Manage',       init: initChallenges,      fragment: 'pages/challenges.html' },
  submissions:      { title: 'Submissions',     breadcrumb: 'Review',       init: initSubmissions,     fragment: 'pages/submissions.html' },
  analytics:        { title: 'Analytics',       breadcrumb: 'Insights',     init: initAnalytics,       fragment: 'pages/analytics.html' },
  leaderboard:      { title: 'Leaderboard',     breadcrumb: 'Rankings',     init: initLeaderboard,     fragment: 'pages/leaderboard.html' },
  'challenge-details':{ title: 'Challenge Details', breadcrumb: 'Challenges', init: initChallengeDetails, fragment: 'pages/challenge-details.html' },
  settings:         { title: 'Settings',        breadcrumb: 'Config',       init: null,                fragment: 'pages/settings.html' },
};

// ─── Toast ─────────────────────────────────────────
export function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const icons = { success: '✓', error: '✕', info: 'ℹ' };
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span class="toast-icon">${icons[type] || icons.info}</span><span class="toast-message">${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(8px)';
    setTimeout(() => toast.remove(), 350);
  }, 3500);
}
window.showToast = showToast;

// ─── Navigation ─────────────────────────────────────
function setActiveNav(page) {
  navLinks.forEach(btn => {
    const isActive = btn.dataset.page === page ||
      (page === 'challenge-details' && btn.dataset.page === 'challenges');
    btn.classList.toggle('active', isActive);
  });
}

function getCurrentRoute() {
  const hash = window.location.hash.slice(1);
  if (hash.startsWith('challenge/')) {
    return { page: 'challenge-details', param: hash.split('/')[1] };
  }
  return { page: hash || 'dashboard', param: null };
}

export function navigateTo(page, param) {
  if (param) {
    window.location.hash = `${page}/${param}`;
  } else {
    window.location.hash = page;
  }
}
window.navigateTo = navigateTo;

// ─── Page loader ────────────────────────────────────
let _fragmentCache = {};

async function loadPage(page, param = null) {
  const route = ROUTES[page] || ROUTES.dashboard;

  pageTitle.textContent     = route.title;
  pageBreadcrumb.textContent = route.breadcrumb || 'Studio';
  setActiveNav(page);

  // Show loading
  pageLoading.hidden = false;
  pageContent.style.opacity = '0';

  try {
    if (!route.fragment) {
      pageContent.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">🚧</div>
          <h4>Under Construction</h4>
          <p>This section is coming soon.</p>
        </div>`;
      return;
    }

    // Use cache for fragments
    if (!_fragmentCache[route.fragment]) {
      const res = await fetch(route.fragment);
      if (!res.ok) throw new Error(`Failed to load ${route.fragment}`);
      _fragmentCache[route.fragment] = await res.text();
    }

    pageContent.innerHTML = _fragmentCache[route.fragment];

    if (typeof route.init === 'function') {
      await route.init(param);
    }
  } catch (err) {
    pageContent.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">⚠️</div>
        <h4>Failed to load page</h4>
        <p>${err.message}</p>
      </div>`;
  } finally {
    pageLoading.hidden = true;
    pageContent.style.opacity = '1';
    pageContent.style.transition = 'opacity 0.2s ease';
  }
}

// ─── Event listeners ────────────────────────────────
window.addEventListener('hashchange', () => {
  _fragmentCache = {}; // clear cache on nav to force fresh init
  const { page, param } = getCurrentRoute();
  loadPage(page, param);
});

navLinks.forEach(btn => {
  btn.addEventListener('click', () => {
    _fragmentCache = {};
    navigateTo(btn.dataset.page);
  });
});

quickUpload?.addEventListener('click', () => {
  _fragmentCache = {};
  navigateTo('upload-challenge');
});

// ─── Boot ───────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
  const { page, param } = getCurrentRoute();
  loadPage(page, param);

  // Wire up Logout
  document.getElementById('logout-btn')?.addEventListener('click', () => {
    localStorage.removeItem('1code_admin_key');
    sessionStorage.removeItem('admin_user');
    window.location.replace('login.html');
  });
});
