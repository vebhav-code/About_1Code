/* =========================================================
   1Code — Team Choice Modal Component
   Handles Create/Join Team workflows for Team Mode challenges
   ========================================================= */

const API_BASE = (window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost")
  ? "http://127.0.0.1:8000"
  : "https://about-1code.onrender.com";

let pollInterval = null;

export function openTeamChoiceModal(challenge) {
  const session = JSON.parse(localStorage.getItem("1code_user") || "null");
  const userId = session?.user_id || session?.id;

  if (!session || !userId) {
    alert("Please sign in to join or create a team challenge.");
    window.location.href = "auth.html";
    return;
  }

  // Remove existing modal if any
  const existing = document.getElementById("teamChoiceModalBackdrop");
  if (existing) existing.remove();

  // Create modal markup
  const backdrop = document.createElement("div");
  backdrop.id = "teamChoiceModalBackdrop";
  backdrop.className = "team-modal-backdrop";

  backdrop.innerHTML = `
    <div class="team-modal-card">
      <div class="team-modal-header">
        <div>
          <div class="team-modal-title">
            👥 ${escapeHtml(challenge.title || 'Team Challenge')}
          </div>
          <div class="team-modal-subtitle">
            Team Mode · ${challenge.team_size || 4} Players per Team
          </div>
        </div>
        <button class="team-modal-close" id="teamModalCloseBtn" aria-label="Close">✕</button>
      </div>

      <div class="team-tab-nav">
        <button class="team-tab-btn active" id="tabBtnCreate" type="button">
          ➕ Create Team
        </button>
        <button class="team-tab-btn" id="tabBtnJoin" type="button">
          🔍 Join Team
        </button>
      </div>

      <!-- CREATE TEAM TAB -->
      <div id="tabContentCreate" class="team-tab-content">
        <div id="createAlert" class="team-alert team-alert-error"></div>
        <form id="createTeamForm">
          <div class="team-form-group">
            <label for="teamNameInput" class="team-form-label">Team Name</label>
            <input 
              type="text" 
              id="teamNameInput" 
              class="team-form-input" 
              placeholder="e.g. Code Ninjas" 
              required 
              maxlength="40" 
              autocomplete="off"
            />
          </div>
          <button type="submit" id="createTeamSubmitBtn" class="btn btn-primary" style="width:100%; padding:12px; margin-top:6px;">
            Create & Enter Lobby
          </button>
        </form>
      </div>

      <!-- JOIN TEAM TAB -->
      <div id="tabContentJoin" class="team-tab-content" style="display:none;">
        <div id="joinAlert" class="team-alert team-alert-error"></div>

        <div style="margin-bottom:8px; font-size:0.8rem; color:var(--text-secondary,#9BA3C0); display:flex; justify-content:space-between; align-items:center;">
          <span>Open Teams</span>
          <span id="teamsPollingStatus" style="font-size:0.75rem; color:var(--text-muted,#656E8C);">● Live</span>
        </div>

        <div id="openTeamsList" class="team-list-container">
          <div style="color:var(--text-muted); font-size:0.85rem; padding:12px; text-align:center;">
            Loading open teams…
          </div>
        </div>

        <div class="invite-code-divider">OR JOIN BY CODE</div>

        <form id="joinCodeForm" style="display:flex; gap:10px;">
          <input 
            type="text" 
            id="inviteCodeInput" 
            class="team-form-input" 
            placeholder="Enter invite code..." 
            style="flex:1;" 
            autocomplete="off"
          />
          <button type="submit" id="joinCodeSubmitBtn" class="btn btn-ghost" style="padding:10px 16px; font-size:0.85rem; white-space:nowrap;">
            Join Code
          </button>
        </form>
      </div>
    </div>
  `;

  document.body.appendChild(backdrop);

  // Close handlers
  const closeModal = () => {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
    backdrop.remove();
  };

  document.getElementById("teamModalCloseBtn").addEventListener("click", closeModal);
  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop) closeModal();
  });

  // Tab switching
  const tabBtnCreate = document.getElementById("tabBtnCreate");
  const tabBtnJoin = document.getElementById("tabBtnJoin");
  const tabContentCreate = document.getElementById("tabContentCreate");
  const tabContentJoin = document.getElementById("tabContentJoin");

  const switchTab = (tab) => {
    if (tab === "create") {
      tabBtnCreate.classList.add("active");
      tabBtnJoin.classList.remove("active");
      tabContentCreate.style.display = "block";
      tabContentJoin.style.display = "none";
      if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
      }
    } else {
      tabBtnJoin.classList.add("active");
      tabBtnCreate.classList.remove("active");
      tabContentJoin.style.display = "block";
      tabContentCreate.style.display = "none";
      loadOpenTeams(challenge.slug, userId);
      if (!pollInterval) {
        pollInterval = setInterval(() => loadOpenTeams(challenge.slug, userId), 3500);
      }
    }
  };

  tabBtnCreate.addEventListener("click", () => switchTab("create"));
  tabBtnJoin.addEventListener("click", () => switchTab("join"));

  // Handle Create Team submit
  const createForm = document.getElementById("createTeamForm");
  const createAlert = document.getElementById("createAlert");
  const createSubmitBtn = document.getElementById("createTeamSubmitBtn");

  createForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    createAlert.style.display = "none";
    const teamName = document.getElementById("teamNameInput").value.trim();

    if (!teamName) return;

    createSubmitBtn.disabled = true;
    createSubmitBtn.textContent = "Creating...";

    try {
      const res = await fetch(`${API_BASE}/api/teams`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          challenge_id: challenge.id,
          user_id: userId,
          team_name: teamName
        })
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(formatApiError(data.detail, "Failed to create team"));
      }

      closeModal();
      const teamId = data.team_id || data.id;
      window.location.href = `team-lobby.html?slug=${encodeURIComponent(challenge.slug)}&team_id=${teamId}`;
    } catch (err) {
      createAlert.textContent = err.message || "Could not create team. Please try again.";
      createAlert.style.display = "block";
      createSubmitBtn.disabled = false;
      createSubmitBtn.textContent = "Create & Enter Lobby";
    }
  });

  // Handle Join by Code form
  const joinCodeForm = document.getElementById("joinCodeForm");
  const joinAlert = document.getElementById("joinAlert");

  joinCodeForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    joinAlert.style.display = "none";
    const code = document.getElementById("inviteCodeInput").value.trim();
    if (!code) return;

    const joinCodeBtn = document.getElementById("joinCodeSubmitBtn");
    joinCodeBtn.disabled = true;

    try {
      const res = await fetch(`${API_BASE}/api/teams/join`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          invite_code: code,
          user_id: userId
        })
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(formatApiError(data.detail, "Failed to join team"));
      }

      closeModal();
      const teamId = data.team_id || data.id;
      window.location.href = `team-lobby.html?slug=${encodeURIComponent(challenge.slug)}&team_id=${teamId}`;
    } catch (err) {
      joinAlert.textContent = err.message || "Invalid or expired invite code.";
      joinAlert.style.display = "block";
      joinCodeBtn.disabled = false;
    }
  });
}

// Fetch and render open teams
async function loadOpenTeams(slug, userId) {
  const container = document.getElementById("openTeamsList");
  const joinAlert = document.getElementById("joinAlert");
  if (!container) return;

  try {
    const url = `${API_BASE}/api/challenge/${encodeURIComponent(slug)}/teams${userId ? `?user_id=${encodeURIComponent(userId)}` : ''}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("Failed to load open teams");
    const teams = await res.json();

    if (!teams.length) {
      container.innerHTML = `
        <div style="color:var(--text-muted); font-size:0.85rem; padding:16px; text-align:center;">
          No open teams yet. Create one or ask your team leader for an invite code!
        </div>`;
      return;
    }

    container.innerHTML = teams.map((t) => {
      const isFull = (t.member_count || 0) >= (t.team_size || 4);
      const badgeClass = isFull ? "team-badge-full" : "";
      const tId = t.team_id || t.id;
      
      return `
        <div class="team-row">
          <div class="team-row-info">
            <span class="team-row-name">${escapeHtml(t.name || 'Team')}</span>
            <span class="team-row-leader">Leader: ${escapeHtml(t.leader_name || 'Anonymous')}</span>
          </div>
          <div class="team-row-actions">
            <span class="team-badge-size ${badgeClass}">
              ${t.member_count || 1}/${t.team_size || 4}
            </span>
            <button 
              class="btn btn-ghost join-team-btn" 
              data-team-id="${tId}" 
              ${isFull ? 'disabled' : ''} 
              style="padding:6px 12px; font-size:0.8rem;"
            >
              ${isFull ? 'Full' : 'Join'}
            </button>
          </div>
        </div>
      `;
    }).join("");

    // Bind Join buttons
    container.querySelectorAll(".join-team-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const teamId = parseInt(btn.dataset.teamId, 10);
        if (!teamId) return;

        btn.disabled = true;
        btn.textContent = "Joining…";
        if (joinAlert) joinAlert.style.display = "none";

        try {
          const res = await fetch(`${API_BASE}/api/teams/join`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              team_id: teamId,
              user_id: userId
            })
          });

          const data = await res.json().catch(() => ({}));
          if (!res.ok) {
            throw new Error(formatApiError(data.detail, "Could not join team"));
          }

          if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
          }
          const backdrop = document.getElementById("teamChoiceModalBackdrop");
          if (backdrop) backdrop.remove();

          const resTeamId = data.team_id || data.id;
          window.location.href = `team-lobby.html?slug=${encodeURIComponent(slug)}&team_id=${resTeamId}`;
        } catch (err) {
          if (joinAlert) {
            joinAlert.textContent = err.message || "Failed to join team.";
            joinAlert.style.display = "block";
          }
          btn.disabled = false;
          btn.textContent = "Join";
        }
      });
    });

  } catch (err) {
    container.innerHTML = `
      <div style="color:var(--danger,#F87171); font-size:0.85rem; padding:12px; text-align:center;">
        Could not load open teams.
      </div>`;
  }
}

function formatApiError(detail, fallbackMsg = "An error occurred") {
  if (!detail) return fallbackMsg;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((err) => {
      const loc = Array.isArray(err.loc) ? err.loc.filter(l => l !== "body").join(".") : "";
      return err.msg ? `${loc ? loc + ": " : ""}${err.msg}` : JSON.stringify(err);
    }).join("; ");
  }
  if (typeof detail === "object") {
    return detail.msg || JSON.stringify(detail);
  }
  return String(detail);
}

function escapeHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// Make available globally on window as well for easy access without ES import
if (typeof window !== "undefined") {
  window.openTeamChoiceModal = openTeamChoiceModal;
}
