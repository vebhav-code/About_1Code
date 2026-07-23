/* ===========================================
   1Code — Leaderboard Page
   Fetches live rankings and stats from
   the FastAPI backend and renders them into
   the existing table structure.
=========================================== */

const API_BASE = "http://localhost:8000";

const MEDAL = ["🥇", "🥈", "🥉"];

document.addEventListener("DOMContentLoaded", async () => {
    await Promise.all([loadLeaderboard(), loadStats()]);
});

/* ===========================================
   Load Top-100 Rankings
=========================================== */
async function loadLeaderboard() {
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

    try {
        const res = await fetch(`${API_BASE}/api/leaderboard`);

        if (!res.ok) {
            throw new Error(`Server returned ${res.status}`);
        }

        const entries = await res.json();

        if (!entries.length) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="5" style="text-align:center;padding:50px;
                        color:var(--text-secondary);">
                        No submissions yet — be the first!
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

                return `
                    <tr>
                        <td>${rankDisplay}</td>
                        <td>${escapeHtml(entry.name)}</td>
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
                    Failed to load leaderboard. Is the backend running?
                </td>
            </tr>`;
    }
}

/* ===========================================
   Load Challenge Stats Banner
=========================================== */
async function loadStats() {
    try {
        const res = await fetch(`${API_BASE}/api/leaderboard/stats`);
        if (!res.ok) return;

        const statsList = await res.json();
        if (!statsList.length) return;

        const stats = statsList[0]; // first (or only) challenge

        // Only inject the stats banner if it doesn't already exist
        if (document.getElementById("statsBanner")) return;

        const banner = document.createElement("div");
        banner.id = "statsBanner";
        banner.className = "glass-card";
        banner.style.cssText =
            "display:flex;flex-wrap:wrap;gap:16px;justify-content:center;" +
            "padding:24px 30px;margin-bottom:30px;text-align:center;";

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
                <div style="min-width:130px;">
                    <div style="font-size:.78rem;text-transform:uppercase;
                                letter-spacing:.07em;color:var(--text-secondary);
                                margin-bottom:6px;">
                        ${escapeHtml(String(item.label))}
                    </div>
                    <div style="font-size:1.25rem;font-weight:700;
                                color:var(--text-primary,#fff);">
                        ${escapeHtml(String(item.value))}
                    </div>
                </div>`
            )
            .join("");

        const container = document.querySelector(
            ".leaderboard-section .contest-container"
        );
        if (container) {
            const card = container.querySelector(".glass-card.leaderboard-card");
            if (card) container.insertBefore(banner, card);
        }
    } catch {
        // Stats are optional — fail silently
    }
}

/* ===========================================
   Helpers
=========================================== */
function escapeHtml(str) {
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}