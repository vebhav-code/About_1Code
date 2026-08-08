/* ===========================================
   1Code — Challenge-Scoped Leaderboard Page
   Fetches live rankings and stats from
   the FastAPI backend for a specific challenge.
=========================================== */

const API_BASE = (window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost")
  ? "http://127.0.0.1:8000"
  : "https://about-1code.onrender.com";

const MEDAL = ["🥇", "🥈", "🥉"];
const params = new URLSearchParams(window.location.search);
const challengeSlug = params.get("slug");
const user = JSON.parse(localStorage.getItem("1code_user") || "null");
const userId = user?.user_id || user?.id;

let currentMode = "individual";

document.addEventListener("DOMContentLoaded", async () => {
    if (!challengeSlug) {
        renderChallengePicker();
        return;
    }
    setupModeToggle();
    await Promise.all([loadLeaderboard(), loadStats()]);
});

async function renderChallengePicker() {
    const container = document.querySelector(".leaderboard-section .contest-container");
    if (!container) return;

    const heroH1 = document.querySelector(".contest-hero h1");
    if (heroH1) heroH1.textContent = "Leaderboards";
    const heroP = document.querySelector(".contest-hero p");
    if (heroP) heroP.textContent = "Select a challenge to view its top developers and rankings.";

    container.innerHTML = `
      <div class="glass-card" style="padding: 36px; text-align: center; max-width: 540px; margin: 20px auto;">
        <h3 style="font-family: var(--font-display); font-size: 1.4rem; margin-bottom: 10px;">Select a Challenge</h3>
        <p style="color: var(--text-secondary); margin-bottom: 24px; font-size: 0.95rem;">Choose a challenge to view its per-challenge rankings and participant stats.</p>
        <select id="challengePickerSelect" class="team-form-input" style="padding: 12px 16px; margin-bottom: 24px; width: 100%; box-sizing: border-box;">
          <option value="">Loading challenges...</option>
        </select>
        <div>
          <a href="dashboard.html" class="btn btn-ghost">← Back to Dashboard</a>
        </div>
      </div>
    `;

    try {
        const res = await fetch(`${API_BASE}/challenges`);
        if (!res.ok) throw new Error();
        const challenges = await res.json();
        const select = document.getElementById("challengePickerSelect");
        if (select) {
            select.innerHTML = `<option value="">-- Choose a Challenge --</option>` +
              challenges.map(c => `<option value="${escapeHtml(c.slug)}">${escapeHtml(c.title)} (${c.difficulty || 'Medium'})</option>`).join("");
            select.addEventListener("change", (e) => {
                const selectedSlug = e.target.value;
                if (selectedSlug) {
                    window.location.href = `leaderboard.html?slug=${encodeURIComponent(selectedSlug)}`;
                }
            });
        }
    } catch {
        container.innerHTML = `<p style="color: var(--danger); text-align: center;">Could not load challenges. Please check server status.</p>`;
    }
}

function setupModeToggle() {
    const tabIndividual = document.getElementById("tabIndividual");
    const tabTeam = document.getElementById("tabTeam");

    if (!tabIndividual || !tabTeam) return;

    tabIndividual.addEventListener("click", async () => {
        if (currentMode === "individual") return;
        currentMode = "individual";
        tabIndividual.classList.add("active");
        tabTeam.classList.remove("active");
        await loadLeaderboard();
    });

    tabTeam.addEventListener("click", async () => {
        if (currentMode === "team") return;
        currentMode = "team";
        tabTeam.classList.add("active");
        tabIndividual.classList.remove("active");
        await loadLeaderboard();
    });
}

/* ===========================================
   Load Challenge-Scoped Rankings
=========================================== */
async function loadLeaderboard() {
    if (!challengeSlug) return;

    const tbody = document.querySelector("table tbody");
    if (!tbody) return;

    // Show skeleton loader
    tbody.innerHTML = `
        <tr>
            <td colspan="5" style="text-align:center;padding:50px;
                color:var(--text-secondary);letter-spacing:.05em;">
                Loading rankings…
            </td>
        </tr>`;

    const colHeaderName = document.getElementById("colHeaderName");
    if (colHeaderName) {
        colHeaderName.textContent = currentMode === "team" ? "Team" : "Developer";
    }

    try {
        const url = `${API_BASE}/api/leaderboard?challenge_slug=${encodeURIComponent(challengeSlug)}&mode=${currentMode}${userId ? `&user_id=${userId}` : ''}`;
        const res = await fetch(url);

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || `Server returned ${res.status}`);
        }

        const data = await res.json();
        const entries = data.entries || [];
        const myRank = data.my_rank;

        if (data.challenge_title) {
            const heroH1 = document.querySelector(".contest-hero h1");
            if (heroH1) heroH1.textContent = `${data.challenge_title} Leaderboard`;
        }

        renderUserRankBanner(myRank, data.challenge_slug || challengeSlug);

        if (!entries.length) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="5" style="text-align:center;padding:50px;
                        color:var(--text-secondary);">
                        No ${currentMode === "team" ? "team" : ""} submissions yet for this challenge — be the first!
                    </td>
                </tr>`;
            return;
        }

        tbody.innerHTML = entries
            .map((entry) => {
                const rankDisplay =
                    entry.rank <= 3
                        ? MEDAL[entry.rank - 1]
                        : entry.rank;

                let nameDisplay = "";
                if (currentMode === "team" || entry.team_name) {
                    const tName = entry.team_name || entry.name;
                    const membersList = (entry.members && entry.members.length > 0)
                        ? entry.members.join(", ")
                        : "";
                    nameDisplay = `
                        <div>
                            <div style="font-weight:600;">👥 ${escapeHtml(tName)}</div>
                            ${membersList ? `<div style="font-size:0.75rem;color:var(--text-secondary);margin-top:2px;" title="Members: ${escapeHtml(membersList)}">Members: ${escapeHtml(membersList)}</div>` : ''}
                        </div>`;
                } else {
                    nameDisplay = escapeHtml(entry.name);
                }

                return `
                    <tr>
                        <td>${rankDisplay}</td>
                        <td>${nameDisplay}</td>
                        <td>${escapeHtml(entry.challenge)}</td>
                        <td><strong style="color:#5B8DEF;">${entry.score}</strong></td>
                        <td style="font-family:'JetBrains Mono',monospace;font-size:.85rem;">
                            ${escapeHtml(entry.submission_time)}
                        </td>
                    </tr>`;
            })
            .join("");

    } catch (err) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" style="text-align:center;padding:40px;
                    color:#f87171;">
                    ${escapeHtml(err.message || "Failed to load leaderboard. Is the backend running?")}
                </td>
            </tr>`;
    }
}

function renderUserRankBanner(myRank, slug) {
    let banner = document.getElementById("userRankBanner");
    if (!banner) {
        banner = document.createElement("div");
        banner.id = "userRankBanner";
        const container = document.querySelector(".leaderboard-section .contest-container");
        const card = container?.querySelector(".glass-card.leaderboard-card");
        if (container && card) {
            container.insertBefore(banner, card);
        }
    }

    if (!myRank) {
        banner.style.display = "none";
        return;
    }

    banner.style.display = "flex";
    banner.className = "glass-card";
    banner.style.cssText = "padding: 16px 24px; margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;";

    if (myRank.participated) {
        banner.innerHTML = `
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 1.4rem;">🎯</span>
                <div>
                    <div style="font-weight: 600; font-size: 0.95rem; color: #a5f3fc;">Your Ranking (${currentMode === 'team' ? 'Team' : 'Individual'})</div>
                    <div style="font-size: 0.85rem; color: var(--text-secondary);">Rank: <strong>#${myRank.rank}</strong> &nbsp;•&nbsp; Score: <strong>${myRank.score} / 100</strong></div>
                </div>
            </div>
            <a href="contest.html?slug=${encodeURIComponent(slug)}" class="btn btn-ghost" style="padding: 6px 14px; font-size: 0.85rem;">View Attempt →</a>
        `;
    } else {
        banner.innerHTML = `
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 1.4rem;">ℹ️</span>
                <div>
                    <div style="font-weight: 600; font-size: 0.95rem; color: var(--text-primary);">You haven't attempted this challenge yet</div>
                    <div style="font-size: 0.85rem; color: var(--text-secondary);">Complete this challenge to earn your place on the leaderboard.</div>
                </div>
            </div>
            <a href="contest.html?slug=${encodeURIComponent(slug)}" class="btn btn-primary" style="padding: 8px 18px; font-size: 0.85rem;">Attempt Challenge →</a>
        `;
    }
}

/* ===========================================
   Load Challenge Stats Banner
=========================================== */
async function loadStats() {
    if (!challengeSlug) return;
    try {
        const res = await fetch(`${API_BASE}/api/leaderboard/stats?challenge_slug=${encodeURIComponent(challengeSlug)}`);
        if (!res.ok) return;

        const statsList = await res.json();
        if (!statsList || !statsList.length) return;

        const stats = statsList[0];

        let banner = document.getElementById("statsBanner");
        if (!banner) {
            banner = document.createElement("div");
            banner.id = "statsBanner";
            banner.className = "glass-card";
            banner.style.cssText =
                "display:flex;flex-wrap:wrap;gap:16px;justify-content:center;" +
                "padding:20px 24px;margin-bottom:20px;text-align:center;";

            const container = document.querySelector(
                ".leaderboard-section .contest-container"
            );
            const card = container?.querySelector(".glass-card.leaderboard-card");
            if (container && card) container.insertBefore(banner, card);
        }

        const items = [
            { label: "Challenge",        value: stats.challenge_name },
            { label: "Participants",     value: stats.total_participants },
            { label: "Average Score",    value: stats.average_score + " / 100" },
            { label: "Highest Score",    value: stats.highest_score },
            { label: "Lowest Score",     value: stats.lowest_score },
        ];

        banner.innerHTML = items
            .map(
                (item) => `
                <div style="min-width:120px;">
                    <div style="font-size:.75rem;text-transform:uppercase;
                                letter-spacing:.07em;color:var(--text-secondary);
                                margin-bottom:4px;">
                        ${escapeHtml(String(item.label))}
                    </div>
                    <div style="font-size:1.15rem;font-weight:700;
                                color:var(--text-primary,#fff);">
                        ${escapeHtml(String(item.value))}
                    </div>
                </div>`
            )
            .join("");
    } catch {
        // fail silently
    }
}

/* ===========================================
   Helpers
=========================================== */
function escapeHtml(str) {
    return String(str || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}