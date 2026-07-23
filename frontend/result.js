/* ===========================================
   1Code — Result Page
   Loads evaluation data from the backend and
   renders scores, strengths, improvements and
   overall feedback into the existing HTML.
=========================================== */

const API_BASE = "http://localhost:8000";

document.addEventListener("DOMContentLoaded", async () => {
    // Support both ?id=N (session submit redirect) and legacy sessionStorage path
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
        // --- Try fetching an existing evaluation first (GET) ---
        let res = await fetch(`${API_BASE}/api/evaluate/${submissionId}`);

        // If none exists yet (404), trigger the Gemini evaluation (POST)
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
    // --- Overall score circle ---
    const scoreSpan = document.querySelector(".score-circle span");
    if (scoreSpan) scoreSpan.textContent = data.total_score;

    // --- Score circle label ---
    const scoreLabel = document.querySelector(".overall-score-card > p");
    if (scoreLabel) {
        if (data.total_score >= 90) scoreLabel.textContent = "Outstanding Debugging Performance";
        else if (data.total_score >= 75) scoreLabel.textContent = "Great Debugging Performance";
        else if (data.total_score >= 60) scoreLabel.textContent = "Good Debugging Performance";
        else scoreLabel.textContent = "Keep Practising — You'll Get There";
    }

    // --- Late submission badge ---
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

    // --- Score breakdown rows ---
    const rows = document.querySelectorAll(".score-row");
    const breakdown = [
        { label: "Hypothesis Quality",  score: data.hypothesis,       max: 20 },
        { label: "Prompt Quality",      score: data.prompt_quality,   max: 25 },
        { label: "AI Collaboration",    score: data.ai_collaboration, max: 20 },
        { label: "Code Correctness",    score: data.code_correctness, max: 25 },
        { label: "Problem Solving",     score: data.problem_solving,  max: 10 },
    ];

    rows.forEach((row, i) => {
        if (!breakdown[i]) return;
        const labelEl = row.querySelector("span");
        const valueEl = row.querySelector("strong");
        if (labelEl) labelEl.textContent = breakdown[i].label;
        if (valueEl)
            valueEl.textContent = `${breakdown[i].score} / ${breakdown[i].max}`;
    });

    // --- Strengths list ---
    const strengthsHeading = findHeading("Strengths");
    if (strengthsHeading) {
        const ul = getOrCreateUl(strengthsHeading);
        ul.innerHTML = (data.strengths || [])
            .map((s) => `<li>${escapeHtml(s)}</li>`)
            .join("");
    }

    // --- Improvements / Suggestions list ---
    const improvementsHeading =
        findHeading("Suggestions") || findHeading("Improvements");
    if (improvementsHeading) {
        const ul = getOrCreateUl(improvementsHeading);
        ul.innerHTML = (data.improvements || [])
            .map((s) => `<li>${escapeHtml(s)}</li>`)
            .join("");
    }

    // --- Overall feedback paragraph ---
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

/* ===========================================
   Helpers
=========================================== */
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