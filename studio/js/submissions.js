import { getSubmissions, getSubmissionDetail, getEvaluation } from './api.js';

const fmt = (d) => d ? new Date(d).toLocaleString('en-GB', { day:'2-digit', month:'short', year:'numeric', hour:'2-digit', minute:'2-digit' }) : '--';

function getStatusBadge(status) {
  const s = (status || '').toLowerCase();
  if (s === 'evaluated') return `<span class="badge badge-evaluated">Evaluated</span>`;
  if (s === 'scored')    return `<span class="badge badge-success">Scored</span>`;
  return `<span class="badge badge-pending">Pending</span>`;
}

function renderSubmissionRow(record) {
  return `
    <tr data-id="${record.id}">
      <td>#${record.id}</td>
      <td><span style="font-weight:600">${record.name || 'Anonymous'}</span></td>
      <td><span class="mono">${record.challenge_slug}</span></td>
      <td>${record.score != null ? `<strong>${record.score}</strong>` : '—'}</td>
      <td>${fmt(record.created_at)}</td>
      <td>${getStatusBadge(record.status)}</td>
      <td>
        <button class="button button-ghost button-sm" data-action="view" data-id="${record.id}">
          View Review
        </button>
      </td>
    </tr>
  `;
}

export async function initSubmissions() {
  const tableBody = document.getElementById('submission-list');
  if (!tableBody) return;

  const records = await getSubmissions().catch(() => []);
  
  if (!records.length) {
    tableBody.innerHTML = '<tr><td colspan="7" class="table-empty">No submissions available.</td></tr>';
    return;
  }

  tableBody.innerHTML = records.map(renderSubmissionRow).join('');

  // Attach action button listeners
  tableBody.querySelectorAll('[data-action="view"]').forEach(btn => {
    btn.addEventListener('click', () => {
      openReviewModal(Number(btn.dataset.id));
    });
  });
}

async function openReviewModal(submissionId) {
  const existing = document.getElementById('review-modal');
  if (existing) existing.remove();

  // Create modal skeleton with loader
  const backdrop = document.createElement('div');
  backdrop.id = 'review-modal';
  backdrop.className = 'modal-backdrop';
  backdrop.innerHTML = `
    <div class="modal" style="max-width: 680px;">
      <div class="modal-header">
        <h3 class="modal-title">Evaluation Details</h3>
        <button class="modal-close" id="review-close-btn">✕</button>
      </div>
      <div class="modal-body" id="review-modal-body">
        <div class="page-loading"><div class="spinner"></div></div>
      </div>
    </div>`;

  document.body.appendChild(backdrop);

  const close = () => backdrop.remove();
  document.getElementById('review-close-btn').addEventListener('click', close);
  backdrop.addEventListener('click', (e) => { if (e.target === backdrop) close(); });

  try {
    // 1. Fetch submission details
    const sub = await getSubmissionDetail(submissionId).catch(() => null);
    if (!sub) throw new Error('Failed to load submission details.');

    // 2. Fetch evaluation details if available
    const evaluation = await getEvaluation(submissionId).catch(() => null);

    const modalBody = document.getElementById('review-modal-body');
    if (!modalBody) return;

    let evalDetailsHtml = '';
    if (evaluation) {
      const rubricScores = [
        { label: 'Hypothesis (Root Cause)', val: evaluation.hypothesis, max: 20 },
        { label: 'Prompt Quality', val: evaluation.prompt_quality, max: 25 },
        { label: 'AI Collaboration', val: evaluation.ai_collaboration, max: 20 },
        { label: 'Code Correctness', val: evaluation.code_correctness, max: 25 },
        { label: 'Problem Solving', val: evaluation.problem_solving, max: 10 }
      ];

      evalDetailsHtml = `
        <div style="margin-top: 16px;">
          <h4 style="font-size:0.9rem;font-weight:700;margin-bottom:12px;color:var(--text)">Gemini Rubric Scores</h4>
          <div style="display:flex;flex-direction:column;gap:12px">
            ${rubricScores.map(score => {
              const pct = (score.val / score.max) * 100;
              return `
                <div>
                  <div style="display:flex;justify-content:space-between;font-size:0.78rem;margin-bottom:4px">
                    <span style="color:var(--text-secondary)">${score.label}</span>
                    <strong style="color:var(--accent-bright)">${score.val} / ${score.max}</strong>
                  </div>
                  <div class="progress-track" style="height:6px">
                    <div class="progress-fill" style="width:${pct}%;background:linear-gradient(90deg, var(--accent), var(--accent-bright))"></div>
                  </div>
                </div>`;
            }).join('')}
          </div>
        </div>

        <div class="divider" style="margin:20px 0"></div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
          <div>
            <h5 style="font-size:0.83rem;font-weight:700;color:var(--success);margin-bottom:8px">Strengths</h5>
            <ul style="list-style:disc;padding-left:16px;font-size:0.83rem;color:var(--text-secondary);display:flex;flex-direction:column;gap:4px">
              ${(evaluation.strengths || []).map(s => `<li>${s}</li>`).join('') || '<li>No strengths noted.</li>'}
            </ul>
          </div>
          <div>
            <h5 style="font-size:0.83rem;font-weight:700;color:var(--danger);margin-bottom:8px">Key Improvements</h5>
            <ul style="list-style:disc;padding-left:16px;font-size:0.83rem;color:var(--text-secondary);display:flex;flex-direction:column;gap:4px">
              ${(evaluation.improvements || []).map(i => `<li>${i}</li>`).join('') || '<li>No improvements noted.</li>'}
            </ul>
          </div>
        </div>
      `;
    } else {
      evalDetailsHtml = `
        <div style="background:var(--bg-muted);border:1px solid var(--border);padding:14px;border-radius:var(--radius);margin-top:16px">
          <p style="font-size:0.83rem;color:var(--text-secondary);line-height:1.5">
            Evaluation data unavailable for this submission.
          </p>
        </div>`;
    }

    modalBody.innerHTML = `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
        <div class="preview-field">
          <span class="preview-field-label">User Name</span>
          <span class="preview-field-value" style="font-weight:600">${sub.name || 'Anonymous'}</span>
        </div>
        <div class="preview-field">
          <span class="preview-field-label">Submission Score</span>
          <span class="preview-field-value" style="font-weight:700;color:var(--success)">${sub.overall_score || 0} / 100</span>
        </div>
        <div class="preview-field preview-field-full">
          <span class="preview-field-label">Overall Feedback</span>
          <p style="font-size:0.85rem;color:var(--text-secondary);line-height:1.6">${sub.feedback || 'No feedback available.'}</p>
        </div>
      </div>

      <div class="divider" style="margin:20px 0"></div>

      ${evalDetailsHtml}

      <div class="modal-footer">
        <button class="button button-secondary" id="review-ok-btn">Close</button>
      </div>
    `;

    document.getElementById('review-ok-btn')?.addEventListener('click', close);



  } catch (err) {
    document.getElementById('review-modal-body').innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">⚠️</div>
        <h4>Error loading details</h4>
        <p>${err.message}</p>
      </div>`;
  }
}
