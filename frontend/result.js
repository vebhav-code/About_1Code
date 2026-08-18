/* ===========================================
   1Code — Result Page
   Loads evaluation data from the backend and
   renders scores, strengths, improvements and
   overall feedback into the existing HTML.
=========================================== */

const API_BASE = (window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost")
  ? "http://127.0.0.1:8000"
  : "https://about-1code.onrender.com";

document.addEventListener("DOMContentLoaded", async () => {
    const urlParams    = new URLSearchParams(window.location.search);
    const submissionId = urlParams.get("id") || sessionStorage.getItem("submission_id");

    if (!submissionId) {
        showError(
            "No submission found. Please complete a challenge first.",
            "contest.html"
        );
        return;
    }

    showLoading(true);

    try {
        let res = await fetch(`${API_BASE}/api/evaluate/${submissionId}`);

        if (res.status === 404) {
            res = await fetch(
                `${API_BASE}/api/evaluate/${submissionId}`,
                { method: "POST" }
            );
        }

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Evaluation failed.");
        }

        const data = await res.json();
        renderResult(data);
    } catch (err) {
        showError("Could not load your result: " + err.message, "contest.html");
    } finally {
        showLoading(false);
    }
});

/* ===========================================
   Render evaluation data into the HTML
=========================================== */
function renderResult(data) {
    const submittedBy = document.getElementById("submittedBy");
    if (submittedBy) {
        if (data.team_name) {
            const members = data.members || [];
            const memberChips = members.map(m => {
                const initials = (m.name || "?").substring(0, 2).toUpperCase();
                return `<span style="
                    display:inline-flex; align-items:center; gap:6px;
                    background:rgba(91,141,239,0.12); border:1px solid rgba(91,141,239,0.25);
                    border-radius:20px; padding:3px 12px 3px 4px; font-size:0.85rem;
                ">
                    <span style="
                        width:22px; height:22px; border-radius:50%;
                        background:rgba(91,141,239,0.3); display:inline-flex;
                        align-items:center; justify-content:center;
                        font-size:0.7rem; font-weight:600;
                    ">${escapeHtml(initials)}</span>
                    ${escapeHtml(m.name)}
                </span>`;
            }).join(" ");

            submittedBy.innerHTML =
                `👥 Team <strong>${escapeHtml(data.team_name)}</strong>` +
                (memberChips ? `<div style="margin-top:8px; display:flex; flex-wrap:wrap; gap:6px; justify-content:center;">${memberChips}</div>` : "");
        } else if (data.user_name) {
            submittedBy.innerHTML = `👤 Submitted by <strong>${escapeHtml(data.user_name)}</strong>`;
        }
    }

    const scoreSpan = document.querySelector(".score-circle span");
    if (scoreSpan) scoreSpan.textContent = data.total_score;

    const scoreLabel = document.querySelector(".overall-score-card > p");
    if (scoreLabel) {
        if (data.total_score >= 90) scoreLabel.textContent = "Outstanding Architecture Proposal";
        else if (data.total_score >= 75) scoreLabel.textContent = "Great Architecture Proposal";
        else if (data.total_score >= 60) scoreLabel.textContent = "Good Architecture Proposal";
        else scoreLabel.textContent = "Keep Practising — Refine Your Strategy";
    }

    if (data.late) {
        let lateBadge = document.getElementById("lateBadge");
        if (!lateBadge) {
            lateBadge = document.createElement("div");
            lateBadge.id = "lateBadge";
            lateBadge.className = "late-badge";
            const scoreCard = document.querySelector(".overall-score-card");
            if (scoreCard) {
                scoreCard.appendChild(lateBadge);
            }
        }
        lateBadge.innerHTML = `<svg viewBox="0 0 24 24" fill="none" style="width:14px;height:14px;"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2"/><path d="M12 7v5l3 3" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg> Submitted after time limit`;
    }

    const rows = document.querySelectorAll("#scoreBreakdownCard .score-row");
    const breakdown = [
        { label: "Optimization against Constraints", score: data.optimization != null ? data.optimization : (data.code_correctness || 0), max: 25 },
        { label: "Open-Source Tools & Libraries",   score: data.open_source_usage != null ? data.open_source_usage : (data.ai_collaboration || 0), max: 25 },
        { label: "Topic & Domain Knowledge",        score: data.topic_knowledge != null ? data.topic_knowledge : (data.problem_understanding || data.hypothesis || 0), max: 25 },
        { label: "Approach Write-up Quality",       score: data.prompt_quality != null ? data.prompt_quality : 0, max: 25 },
    ];

    rows.forEach((row, i) => {
        if (!breakdown[i]) return;
        const labelEl = row.querySelector("span");
        const valueEl = row.querySelector("strong");
        if (labelEl) labelEl.textContent = breakdown[i].label;
        if (valueEl) valueEl.textContent = `${breakdown[i].score} / ${breakdown[i].max}`;
    });

    const strengthsHeading = findHeading("Strengths");
    if (strengthsHeading) {
        const ul = getOrCreateUl(strengthsHeading);
        ul.innerHTML = (data.strengths || [])
            .map((s) => `<li>${escapeHtml(s)}</li>`)
            .join("") || "<li>No strengths noted.</li>";
    }

    const improvementsHeading =
        findHeading("Suggestions") || findHeading("Improvements");
    if (improvementsHeading) {
        const ul = getOrCreateUl(improvementsHeading);
        ul.innerHTML = (data.improvements || [])
            .map((s) => `<li>${escapeHtml(s)}</li>`)
            .join("") || "<li>No suggestions noted.</li>";
    }

    if (data.overall_feedback) {
        let feedbackEl = document.getElementById("overallFeedback");
        if (!feedbackEl) {
            feedbackEl = document.createElement("p");
            feedbackEl.id = "overallFeedback";
            feedbackEl.style.cssText =
                "margin-top:20px;line-height:1.7;color:var(--text-secondary);";
            const feedbackCard = improvementsHeading
                ? improvementsHeading.closest(".result-card")
                : null;
            if (feedbackCard) feedbackCard.appendChild(feedbackEl);
        }
        feedbackEl.textContent = data.overall_feedback;
    }
}

function findHeading(text) {
    return [...document.querySelectorAll("h3")].find(
        (el) => el.textContent.trim() === text
    );
}

function getOrCreateUl(headingEl) {
    let ul = headingEl.nextElementSibling;
    if (!ul || ul.tagName !== "UL") {
        ul = document.createElement("ul");
        headingEl.insertAdjacentElement("afterend", ul);
    }
    return ul;
}

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}

function showLoading(on) {
    let el = document.getElementById("resultLoader");
    if (!el && on) {
        el = document.createElement("div");
        el.id = "resultLoader";
        el.style.cssText =
            "text-align:center;padding:60px 20px;font-size:1.1rem;color:var(--text-secondary);";
        el.innerHTML = `
            <div style="display:inline-block;width:40px;height:40px;
                        border:3px solid rgba(255,255,255,.15);
                        border-top-color:#5B8DEF;border-radius:50%;
                        animation:spin 0.8s linear infinite;margin-bottom:20px;">
            </div>
            <p>Fetching your Gemini evaluation…</p>
        `;
        if (!document.getElementById("spinStyle")) {
            const style = document.createElement("style");
            style.id = "spinStyle";
            style.textContent = "@keyframes spin{to{transform:rotate(360deg)}}";
            document.head.appendChild(style);
        }
        const section = document.querySelector(".result-section .contest-container");
        if (section) section.prepend(el);
    }
    if (el) el.style.display = on ? "block" : "none";
}

function showError(message, redirectHref) {
    const section = document.querySelector(".result-section .contest-container");
    if (section) {
        section.innerHTML = `
            <div class="glass-card result-card" style="text-align:center;padding:50px 30px;">
                <h2 style="margin-bottom:20px;">Oops!</h2>
                <p style="color:var(--text-secondary);margin-bottom:30px;">${escapeHtml(message)}</p>
                ${redirectHref
                    ? `<a href="${redirectHref}" class="btn btn-primary">Go Back</a>`
                    : ""}
            </div>
        `;
    }
}