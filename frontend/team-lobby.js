/* =========================================================
   1Code — Team Lobby
   Handles waiting for members, mic check, and starting team sessions
   ========================================================= */

const API_BASE = (window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost")
  ? "http://127.0.0.1:8000"
  : "https://about-1code.onrender.com";

const params = new URLSearchParams(window.location.search);
const CHALLENGE_SLUG = params.get('slug');
const TEAM_ID = params.get('team_id');
const session = JSON.parse(localStorage.getItem("1code_user") || "null");
const userId = session?.user_id || session?.id;

// Keys scoped by slug — must match the ssKey() helper in contest.js
function ssKey(suffix) { return `challenge_${suffix}:${CHALLENGE_SLUG}`; }

if (!session || !userId || !TEAM_ID) {
  window.location.href = "dashboard.html";
}

let ws = null;
let teamData = null;
let isLeader = false;
let micStream = null;
let audioContext = null;
let drawRequest = null;

document.addEventListener("DOMContentLoaded", async () => {
  await fetchTeamData();
  setupInviteLink();
  connectWebSocket();
  setupStartButton();
  setupMicCheck();
  setupUserSearch();
});

async function fetchTeamData() {
  try {
    const res = await fetch(`${API_BASE}/api/teams/${TEAM_ID}`);
    if (!res.ok) throw new Error("Failed to load team data");
    
    teamData = await res.json();
    isLeader = teamData.members && teamData.members[0] && teamData.members[0].user_id === userId; 
    // Assuming first member is leader or leader_user_id is available. 
    // Wait, the prompt says "compare current user_id to leader_user_id from the team payload"
    if (teamData.leader_user_id) {
        isLeader = teamData.leader_user_id === userId;
    } else if (teamData.leader_id) {
        isLeader = teamData.leader_id === userId;
    } else if (teamData.members && teamData.members.length > 0) {
        // Fallback
        isLeader = teamData.members[0].user_id === userId;
    }

    document.getElementById("lobbyTitle").textContent = teamData.name || `Team ${TEAM_ID}`;
    renderRoster(teamData.members || []);
    updateStartButtonState(teamData.members?.length || 0);
    // Re-render leader UI every time team data refreshes (covers WS-driven re-fetches)
    refreshLeaderUI();

  } catch (err) {
    showError("Could not load team. It might not exist.");
  }
}

function renderRoster(members) {
  const rosterList = document.getElementById("rosterList");
  rosterList.innerHTML = "";
  
  members.forEach(m => {
    const isLocalUser = m.user_id === userId;
    const isMemberLeader = (teamData.leader_user_id && m.user_id === teamData.leader_user_id) || (teamData.leader_id && m.user_id === teamData.leader_id) || (!teamData.leader_user_id && members[0].user_id === m.user_id);
    
    const div = document.createElement("div");
    div.className = "roster-item";
    
    const initials = (m.name || m.username || "U").substring(0, 2).toUpperCase();
    
    div.innerHTML = `
      <div class="roster-avatar">${initials}</div>
      <div class="roster-name">
        ${escapeHtml(m.name || m.username || 'Anonymous')}
        ${isLocalUser ? '<span style="font-size:0.8em; color:var(--text-muted);">(You)</span>' : ''}
      </div>
      ${isMemberLeader ? '<div class="roster-badge">Leader</div>' : ''}
    `;
    rosterList.appendChild(div);
  });
  
  const countSpan = document.getElementById("rosterCount");
  countSpan.textContent = `${members.length}/${teamData.team_size || 4}`;
}

function setupInviteLink() {
  if (!teamData) return;
  const code = teamData.invite_code || "";
  const input = document.getElementById("inviteCodeInput");
  input.value = code;
  
  document.getElementById("copyInviteBtn").addEventListener("click", () => {
    navigator.clipboard.writeText(code).then(() => {
      const btn = document.getElementById("copyInviteBtn");
      btn.textContent = "Copied!";
      setTimeout(() => btn.textContent = "Copy", 2000);
    });
  });
}

function connectWebSocket() {
  // Using ws:// or wss:// based on current protocol, but since API_BASE might have http:
  const wsProtocol = API_BASE.startsWith("https") ? "wss:" : "ws:";
  const wsHost = API_BASE.replace(/^https?:\/\//, "");
  ws = new WebSocket(`${wsProtocol}//${wsHost}/api/teams/${TEAM_ID}/ws?user_id=${userId}`);

  ws.onopen = () => {
    console.log("Team WS connected");
  };

  ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);
      handleWsMessage(msg);
    } catch (err) {
      console.error("WS Parse Error", err);
    }
  };

  ws.onclose = () => {
    console.log("Team WS closed");
  };
}

function handleWsMessage(msg) {
  if (msg.type === "member_joined") {
    if (!teamData || !Array.isArray(teamData.members)) {
      fetchTeamData();
    } else {
      const exists = teamData.members.some(m => m.user_id === msg.user_id);
      if (!exists && msg.user_id) {
        teamData.members.push({ user_id: msg.user_id, name: msg.name || "Anonymous" });
      }
      renderRoster(teamData.members);
      updateStartButtonState(teamData.members.length);
      refreshLeaderUI();
    }
  } else if (msg.type === "member_left") {
    if (!teamData || !Array.isArray(teamData.members)) {
      fetchTeamData();
    } else {
      teamData.members = teamData.members.filter(m => m.user_id !== msg.user_id);
      renderRoster(teamData.members);
      updateStartButtonState(teamData.members.length);
      refreshLeaderUI();
    }
  } else if (msg.type === "team_started") {
    // auto-navigate to workspace for non-leaders (and leader if they missed the POST response)
    sessionStorage.setItem(ssKey('session_id'), msg.session_id);
    if (msg.starter_code) {
      sessionStorage.setItem(ssKey('code'), msg.starter_code);
      try {
        const parsed = (typeof msg.starter_code === "string" && msg.starter_code.trim().startsWith("{")) ? JSON.parse(msg.starter_code) : (typeof msg.starter_code === "object" ? msg.starter_code : null);
        if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
          sessionStorage.setItem(ssKey('project_files'), JSON.stringify(parsed));
          const keys = Object.keys(parsed);
          if (keys.length > 0) {
            sessionStorage.setItem(ssKey('active_filename'), keys[0]);
            sessionStorage.setItem(ssKey('code'), parsed[keys[0]] || "");
          }
        }
      } catch (e) {}
    }
    if (msg.challenge && msg.challenge.time_limit) {
      sessionStorage.setItem(ssKey('timer'), msg.challenge.time_limit * 60);
    }
    // Stamp context so the slug-mismatch guard in contest.js is a no-op
    sessionStorage.setItem('challenge_context', JSON.stringify({ slug: CHALLENGE_SLUG }));
    window.location.href = `contest.html?slug=${encodeURIComponent(CHALLENGE_SLUG)}&team_id=${TEAM_ID}`;
  }
}

function setupStartButton() {
  const btn = document.getElementById("startChallengeBtn");

  // Visibility is managed by refreshLeaderUI(); just wire the click listener here.
  refreshLeaderUI();

  btn.addEventListener("click", async () => {
    if (btn.disabled) return;
    btn.disabled = true;
    btn.textContent = "Starting...";
    
    try {
      const res = await fetch(`${API_BASE}/api/teams/${TEAM_ID}/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to start team");
      
      // On success, navigate immediately
      sessionStorage.setItem(ssKey('session_id'), data.session_id);
      if (data.starter_code) {
        sessionStorage.setItem(ssKey('code'), data.starter_code);
        try {
          const parsed = (typeof data.starter_code === "string" && data.starter_code.trim().startsWith("{")) ? JSON.parse(data.starter_code) : (typeof data.starter_code === "object" ? data.starter_code : null);
          if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
            sessionStorage.setItem(ssKey('project_files'), JSON.stringify(parsed));
            const keys = Object.keys(parsed);
            if (keys.length > 0) {
              sessionStorage.setItem(ssKey('active_filename'), keys[0]);
              sessionStorage.setItem(ssKey('code'), parsed[keys[0]] || "");
            }
          }
        } catch (e) {}
      }
      if (data.challenge && data.challenge.time_limit) {
        sessionStorage.setItem(ssKey('timer'), data.challenge.time_limit * 60);
      }
      // Stamp context so the slug-mismatch guard in contest.js is a no-op
      sessionStorage.setItem('challenge_context', JSON.stringify({ slug: CHALLENGE_SLUG }));
      window.location.href = `contest.html?slug=${encodeURIComponent(CHALLENGE_SLUG)}&team_id=${TEAM_ID}`;
      
    } catch (err) {
      showError(err.message);
      btn.disabled = false;
      btn.textContent = "Start Challenge";
    }
  });
}

/**
 * Sync the Start-button / wait-message visibility to the current value of
 * `isLeader`. Safe to call repeatedly — it only touches display styles,
 * never re-attaches listeners.
 */
function refreshLeaderUI() {
  const btn = document.getElementById("startChallengeBtn");
  const waitMsg = document.getElementById("waitMessage");
  const searchSec = document.getElementById("leaderSearchSection");
  if (!btn || !waitMsg) return;

  if (isLeader) {
    btn.style.display = "block";
    waitMsg.style.display = "none";
    if (searchSec) searchSec.style.display = "block";
  } else {
    btn.style.display = "none";
    waitMsg.style.display = "block";
    if (searchSec) searchSec.style.display = "none";
  }
}

function updateStartButtonState(memberCount) {
  const btn = document.getElementById("startChallengeBtn");
  if (isLeader) {
    if (memberCount < 2) {
      btn.disabled = true;
      btn.title = "Need at least 2 members to start";
    } else {
      btn.disabled = false;
      btn.title = "";
    }
  }
}

async function setupMicCheck() {
  const levelBar = document.getElementById("micLevelBar");
  const label = document.getElementById("micCheckLabel");
  let isTesting = false;

  try {
    micStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const analyser = audioContext.createAnalyser();
    const source = audioContext.createMediaStreamSource(micStream);
    source.connect(analyser);
    analyser.fftSize = 256;
    
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    
    isTesting = true;
    if (label) label.textContent = "🎙️ Mic Working";
    
    function draw() {
      if (!isTesting) return;
      drawRequest = requestAnimationFrame(draw);
      
      analyser.getByteFrequencyData(dataArray);
      let sum = 0;
      for (let i = 0; i < bufferLength; i++) {
        sum += dataArray[i];
      }
      let avg = sum / bufferLength;
      let percent = Math.min(100, Math.max(0, (avg / 128) * 100));
      levelBar.style.width = percent + "%";
    }
    
    draw();
    
    // Auto stop after 10s to prevent stream hanging
    setTimeout(() => {
      if (isTesting) stopMicCheck();
    }, 10000);
    
  } catch (err) {
    if (label) label.textContent = "⚠️ Mic Access Denied";
    // We don't alert here to avoid blocking the page
  }

  function stopMicCheck() {
    isTesting = false;
    levelBar.style.width = "0%";
    if (label && label.textContent !== "⚠️ Mic Access Denied") {
      label.textContent = "🎙️ Mic Checked";
    }
    
    if (drawRequest) {
      cancelAnimationFrame(drawRequest);
      drawRequest = null;
    }
    
    if (micStream) {
      micStream.getTracks().forEach(track => track.stop());
      micStream = null;
    }
    if (audioContext) {
      audioContext.close();
      audioContext = null;
    }
  }
}

function showError(msg) {
  const errDiv = document.getElementById("lobbyError");
  errDiv.textContent = msg;
  errDiv.style.display = "block";
}

function escapeHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

let searchDebounceTimeout = null;

function setupUserSearch() {
  const input = document.getElementById("userSearchInput");
  const resultsContainer = document.getElementById("userSearchResults");
  if (!input || !resultsContainer) return;

  input.addEventListener("input", () => {
    if (searchDebounceTimeout) clearTimeout(searchDebounceTimeout);
    const q = input.value.trim();
    if (q.length < 2) {
      resultsContainer.innerHTML = "";
      return;
    }
    searchDebounceTimeout = setTimeout(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/users/search?q=${encodeURIComponent(q)}&current_user_id=${userId}`);
        if (!res.ok) return;
        const users = await res.json();
        renderSearchResults(users);
      } catch (e) {
        console.error("User search failed", e);
      }
    }, 300);
  });
}

function renderSearchResults(users) {
  const container = document.getElementById("userSearchResults");
  if (!container) return;
  container.innerHTML = "";

  if (!users || users.length === 0) {
    container.innerHTML = `<div style="font-size: 0.8rem; color: var(--text-muted, #94a3b8); padding: 4px 0;">No matching registered users found.</div>`;
    return;
  }

  users.forEach(u => {
    const row = document.createElement("div");
    row.style.cssText = "display: flex; justify-content: space-between; align-items: center; background: rgba(255,255,255,0.05); padding: 6px 10px; border-radius: 6px;";
    
    row.innerHTML = `
      <span style="font-size: 0.85rem; font-weight: 500;">${escapeHtml(u.name)}</span>
      <button class="btn btn-ghost" style="padding: 3px 10px; font-size: 0.75rem;" data-user-id="${u.id}">Invite</button>
    `;

    const inviteBtn = row.querySelector("button");
    inviteBtn.addEventListener("click", async () => {
      inviteBtn.disabled = true;
      inviteBtn.textContent = "Inviting...";
      try {
        const res = await fetch(`${API_BASE}/api/teams/${TEAM_ID}/invite?invited_user_id=${u.id}&inviter_user_id=${userId}`, {
          method: "POST"
        });
        const data = await res.json();
        if (!res.ok) {
          alert(data.detail || "Failed to send invite");
          inviteBtn.disabled = false;
          inviteBtn.textContent = "Invite";
          return;
        }
        inviteBtn.textContent = "Invited ✓";
        inviteBtn.style.color = "#10b981";
      } catch (err) {
        alert("Could not reach server");
        inviteBtn.disabled = false;
        inviteBtn.textContent = "Invite";
      }
    });

    container.appendChild(row);
  });
}

