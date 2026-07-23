/* =========================================================
   1Code — Landing Page Interactions
   Vanilla JS only. IntersectionObserver drives all scroll
   animation; no external libraries.
   ========================================================= */

document.addEventListener('DOMContentLoaded', () => {

  /* ---------- generic scroll reveal ---------- */
  const revealEls = document.querySelectorAll('.reveal, .wf-step');
  const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('in-view');
        revealObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.15, rootMargin: '0px 0px -60px 0px' });

  revealEls.forEach(el => revealObserver.observe(el));

  /* ---------- workflow steps stagger slightly by index ---------- */
  document.querySelectorAll('.wf-step').forEach((step, i) => {
    step.style.transitionDelay = `${Math.min(i, 4) * 60}ms`;
  });

  /* ---------- mobile nav toggle ---------- */
  const navToggle = document.getElementById('navToggle');
  const navLinks = document.getElementById('navLinks');
  if (navToggle && navLinks) {
    navToggle.addEventListener('click', () => {
      navLinks.classList.toggle('open');
      navToggle.classList.toggle('active');
    });
    navLinks.querySelectorAll('a').forEach(a => {
      a.addEventListener('click', () => navLinks.classList.remove('open'));
    });
  }

  /* ---------- FAQ accordion ---------- */
  document.querySelectorAll('.faq-item').forEach(item => {
    const question = item.querySelector('.faq-question');
    question.addEventListener('click', () => {
      const wasOpen = item.classList.contains('open');
      document.querySelectorAll('.faq-item.open').forEach(open => open.classList.remove('open'));
      if (!wasOpen) item.classList.add('open');
    });
  });

  /* ---------- AI evaluation: animated bars + count-up ---------- */
  const evalDashboard = document.getElementById('evalDashboard');
  if (evalDashboard) {
    let hasRun = false;
    const evalObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting && !hasRun) {
          hasRun = true;
          runEvaluationAnimation();
          evalObserver.disconnect();
        }
      });
    }, { threshold: 0.3 });
    evalObserver.observe(evalDashboard);
  }

  function runEvaluationAnimation() {
    // progress bars
    document.querySelectorAll('.eval-fill').forEach(fill => {
      const target = fill.dataset.target;
      requestAnimationFrame(() => { fill.style.width = `${target}%`; });
    });

    // percentage counters next to each bar
    document.querySelectorAll('.eval-pct').forEach(pct => {
      const target = parseInt(pct.dataset.target, 10);
      countUp(pct, target, val => `${val}%`);
    });

    // overall score
    const overallEl = document.getElementById('overallScore');
    if (overallEl) countUp(overallEl, 91, val => `${val}`);
  }

  function countUp(el, target, formatter) {
    const duration = 1200;
    const stepTime = 16;
    let current = 0;
    const increment = target / (duration / stepTime);
    const timer = setInterval(() => {
      current += increment;
      if (current >= target) {
        current = target;
        clearInterval(timer);
      }
      el.textContent = formatter(Math.round(current));
    }, stepTime);
  }

  /* ---------- challenge download (demo — no real file) ---------- */
  const downloadBtn = document.getElementById('downloadBtn');
  if (downloadBtn) {
    downloadBtn.addEventListener('click', () => {
      const original = downloadBtn.innerHTML;
      downloadBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none"><path d="M5 12l5 5L19 7" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg> Prepared — connect a backend to serve this';
      downloadBtn.disabled = true;
      setTimeout(() => {
        downloadBtn.innerHTML = original;
        downloadBtn.disabled = false;
      }, 2200);
    });
  }

  /* ---------- upload card (demo — visual only) ---------- */
  const uploadCard = document.getElementById('uploadCard');
  if (uploadCard) {
    uploadCard.addEventListener('click', () => {
      uploadCard.style.borderColor = 'var(--purple)';
      const hint = uploadCard.querySelector('.upload-hint');
      const originalText = hint.textContent;
      hint.textContent = 'Wire this up to a real file input when the backend is ready';
      setTimeout(() => {
        uploadCard.style.borderColor = '';
        hint.textContent = originalText;
      }, 2200);
    });

    ['dragenter', 'dragover'].forEach(evt => {
      uploadCard.addEventListener(evt, (e) => {
        e.preventDefault();
        uploadCard.style.borderColor = 'var(--blue)';
      });
    });
    ['dragleave', 'drop'].forEach(evt => {
      uploadCard.addEventListener(evt, (e) => {
        e.preventDefault();
        uploadCard.style.borderColor = '';
      });
    });
  }

});
/* =========================================================
   Challenge Button Navigation
========================================================= */

const challengeBtn = document.getElementById("challengeBtn");

if (challengeBtn) {

    challengeBtn.addEventListener("click", () => {

        window.location.href = "contest.html";

    });

}