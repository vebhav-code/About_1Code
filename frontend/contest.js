/* ===========================================
   1Code — Contest Page
   Session-based workspace: editor + Gemini chat
   API: /api/sessions/* (start, chat, save-code, submit)
=========================================== */

const API_BASE = (window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost")
  ? "http://127.0.0.1:8000"
  : "https://about-1code.onrender.com";
const params = new URLSearchParams(window.location.search);
const CHALLENGE_SLUG = params.get('slug');
if (!CHALLENGE_SLUG) {
  window.location.href = 'dashboard.html';
}
const currentUser = JSON.parse(localStorage.getItem('1code_user') || 'null');
if (!currentUser) {
  window.location.href = 'auth.html';
}

const AUTOSAVE_INTERVAL_MS = 5000;

let challengeId    = null;

let sessionId      = null;
let timerInterval  = null;
let saveInterval   = null;
let lastSavedCode  = "";
let isSubmitted    = false;

// sessionStorage keys scoped by slug so state from one challenge
// never leaks into a different challenge's page.
function ssKey(suffix) { return `challenge_${suffix}:${CHALLENGE_SLUG}`; }

let TEAM_ID = params.get('team_id') || sessionStorage.getItem(ssKey('team_id')) || null;
if (TEAM_ID) sessionStorage.setItem(ssKey('team_id'), TEAM_ID);
let teamWs = null;
let rtcPeers = {};
let localAudioStream = null;
let isMicMuted = true;

// ---------------------------------------------------------------------------
// INTERIM code sync (Task 5)
// Full-document broadcast over WebSocket, debounced 500 ms.
// TODO: replace with Yjs + y-websocket CRDT sync when infra is ready.
//   That will give per-character awareness, cursor positions (y-monaco
//   Awareness API), and conflict-free merges without needing the
//   "don't apply while typing" heuristic below.
// ---------------------------------------------------------------------------
let codeSyncTimeout          = null;   // debounce handle for outgoing sends
let cursorMoveTimeout        = null;
let promptTypingTimeout      = null;
let lastSyncedCode           = "";
const CODE_SYNC_DEBOUNCE     = 500;  // ms — send code diff after user pauses
const CURSOR_MOVE_DEBOUNCE   = 100;  // ms — update teammate cursor positions
const PROMPT_TYPING_DEBOUNCE = 300;  // ms — debounce typing preview updates
const PROMPT_TYPING_IDLE_MS  = 4000; // ms — clear stale typing preview

let remoteCursors = {};
let remoteTypingStates = {};
let promptTypingClearTimers = {};

let teamMembers = {};
// chat polling: used in team mode because the backend /chat endpoint returns
// Gemini's reply directly to the caller only (no WS broadcast yet).
// TODO: when the backend gains WS broadcast of assistant_reply messages,
//       remove the polling interval and handle the 'assistant_reply' WS event.
let chatPollingInterval = null;
let lastKnownChatMsgId  = 0;  // highest chat message id seen so far

// ---------------------------------------------------------------------------
// Bootstrap
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
    // ── Slug-mismatch guard ──────────────────────────────────────────────────
    // If the user is arriving from a *different* challenge, any old unscoped
    // keys (written by team-lobby.js before the ssKey migration, or by a
    // browser with a cached older contest.js) must be cleared so they cannot
    // pollute this challenge's workspace.
    const ctx = JSON.parse(sessionStorage.getItem('challenge_context') || 'null');
    if (ctx && ctx.slug !== CHALLENGE_SLUG) {
        // Wipe old unscoped keys unconditionally
        ['challenge_session_id','challenge_team_id','challenge_code','challenge_timer'].forEach(
            k => sessionStorage.removeItem(k)
        );
    }
    // Write / refresh context stamp for this challenge
    sessionStorage.setItem('challenge_context', JSON.stringify({ slug: CHALLENGE_SLUG }));
    // ────────────────────────────────────────────────────────────────────────

    const lbLink = document.querySelector('nav.nav-links a[href="leaderboard.html"]');
    if (lbLink && CHALLENGE_SLUG) {
        lbLink.href = `leaderboard.html?slug=${encodeURIComponent(CHALLENGE_SLUG)}`;
    }

    sessionId = sessionStorage.getItem(ssKey('session_id')) || null;

    initializeChallenge();
    initializeDownload();
    initializeStart();

    // If a session was already started (e.g. page reload), jump straight to workspace
    if (sessionId) {
        revealWorkspace(null, null);   // no starter code; editor restores from sessionStorage
        const savedCode = sessionStorage.getItem(ssKey('code')) || "";
        document.getElementById("codeEditor").value = savedCode;
        lastSavedCode = savedCode;
        const savedTime = parseInt(sessionStorage.getItem(ssKey('timer')) || "0", 10);
        startTimer(savedTime);
    }
});

// ---------------------------------------------------------------------------
// Load challenge details
// ---------------------------------------------------------------------------
async function initializeChallenge() {
    try {
        const res = await fetch(`${API_BASE}/challenge/${CHALLENGE_SLUG}/details`);
        if (!res.ok) return;
        const data = await res.json();
        if (data.id) {
            challengeId = data.id;
        }

        if (data.title) {
            const h1 = document.querySelector(".contest-hero h1");
            if (h1) h1.textContent = data.title;
        }
        if (data.difficulty) {
            const d1 = document.getElementById("metaDifficulty");
            const d2 = document.getElementById("infoDifficulty");
            if (d1) d1.textContent = data.difficulty;
            if (d2) d2.textContent = data.difficulty;
        }
        if (data.time_limit) {
            const tl = document.getElementById("metaTimeLimit");
            if (tl) tl.textContent = `${data.time_limit} Minutes`;
        }
        if (data.scenario) {
            const sc = document.getElementById("scenarioText");
            if (sc) sc.textContent = data.scenario;
        }

        // Team Mode Branching
        if (data.mode === "team" && !params.get("team_id") && !sessionId) {
            if (typeof window.openTeamChoiceModal === "function") {
                window.openTeamChoiceModal(data);
            }
        }
    } catch { /* fall back to hardcoded HTML */ }
}

// ---------------------------------------------------------------------------
// Download challenge ZIP
// ---------------------------------------------------------------------------
function initializeDownload() {
    const btn = document.getElementById("downloadChallenge");
    if (!btn) return;

    btn.addEventListener("click", async () => {
        btn.disabled = true;
        btn.textContent = "Downloading…";
        try {
            const res = await fetch(`${API_BASE}/challenge/${CHALLENGE_SLUG}/download`);
            if (!res.ok) { alert("Download failed: " + res.statusText); return; }
            const blob = await res.blob();
            const url  = URL.createObjectURL(blob);
            const a    = document.createElement("a");
            a.href = url; a.download = `${CHALLENGE_SLUG}.zip`;
            document.body.appendChild(a); a.click(); a.remove();
            URL.revokeObjectURL(url);
        } catch { alert("Could not reach the server."); }
        finally { btn.disabled = false; btn.textContent = "Download challenge.zip"; }
    });
}

// ---------------------------------------------------------------------------
// Start session
// ---------------------------------------------------------------------------
function initializeStart() {
    const startBtn = document.getElementById("startBtn");
    const initialForm = document.getElementById("startInitialForm");
    const hypothesisStep = document.getElementById("hypothesisStep");
    const hypothesisInput = document.getElementById("hypothesisInput");
    const beginBtn = document.getElementById("beginDebuggingBtn");
    const noticeEl = document.getElementById("startNotice");

    if (startBtn) {
        startBtn.addEventListener("click", () => {
            if (initialForm) initialForm.style.display = "none";
            else startBtn.style.display = "none";
            if (hypothesisStep) hypothesisStep.style.display = "flex";
            if (hypothesisInput) hypothesisInput.focus();
        });
    }

    if (beginBtn) {
        beginBtn.addEventListener("click", async () => {
            const hypothesisText = (hypothesisInput?.value || "").trim();
            if (!hypothesisText) {
                if (noticeEl) {
                    noticeEl.textContent = "Please write your initial hypothesis before beginning debugging.";
                    noticeEl.style.display = "block";
                } else {
                    alert("Please write your initial hypothesis before beginning debugging.");
                }
                hypothesisInput?.focus();
                return;
            }

            if (noticeEl) {
                noticeEl.style.display = "none";
                noticeEl.textContent = "";
            }

            beginBtn.disabled = true;
            beginBtn.textContent = "Starting…";

            if (!challengeId) {
                alert("Challenge details not loaded yet. Please refresh or try again.");
                beginBtn.disabled = false;
                beginBtn.textContent = "Begin Debugging";
                return;
            }

            try {
                const res = await fetch(`${API_BASE}/api/sessions/start`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        challenge_id: challengeId,
                        user_id: currentUser.user_id,
                        name: currentUser.name,
                        hypothesis: hypothesisText,
                    }),
                });

                if (!res.ok) {
                    const err = await res.json().catch(() => ({}));
                    if (res.status === 401) {
                        alert(err.detail || "Your session is invalid or from a different environment. Please log in again.");
                        localStorage.removeItem("1code_user");
                        window.location.href = "auth.html";
                        return;
                    }
                    if (res.status === 409 && noticeEl) {
                        noticeEl.textContent = err.detail || "You've already submitted this challenge.";
                        noticeEl.style.display = "block";
                    } else {
                        alert("Could not start session: " + (err.detail || res.statusText));
                    }
                    return;
                }

                const data = await res.json();
                sessionId = data.session_id;
                sessionStorage.setItem(ssKey('session_id'), sessionId);

                revealWorkspace(data.starter_code, data.challenge);
                startTimer((data.challenge?.time_limit ?? 45) * 60);
            } catch (err) {
                alert("Could not reach the server. Is the backend running?");
            } finally {
                beginBtn.disabled = false;
                beginBtn.textContent = "Begin Debugging";
            }
        });
    }
}

// ---------------------------------------------------------------------------
// Reveal workspace
// ---------------------------------------------------------------------------
function revealWorkspace(starterCode, challengeData) {
    const startSection     = document.getElementById("startSection");
    const workspaceSection = document.getElementById("workspaceSection");
    if (startSection)     startSection.style.display     = "none";
    if (workspaceSection) workspaceSection.style.display = "block";

    const editor = document.getElementById("codeEditor");
    if (editor && starterCode) {
        editor.value = starterCode;
        lastSavedCode = starterCode;
        sessionStorage.setItem(ssKey('code'), starterCode);
    }

    initializeChat();
    initializeAutoSave();
    initializeSubmitBtn();

    if (TEAM_ID) {
        document.body.classList.add("team-mode");
        document.getElementById("teamPresenceBar").style.display = "flex";
        setupTeamWorkspace();
    }
}

// ---------------------------------------------------------------------------
// Countdown timer
// ---------------------------------------------------------------------------
function startTimer(totalSeconds) {
    if (timerInterval) clearInterval(timerInterval);
    const timerEl = document.getElementById("contestTimer");
    const noteEl  = document.getElementById("timerNote");
    if (noteEl) noteEl.style.display = "none";

    function tick() {
        if (!timerEl) return;
        const m = Math.floor(totalSeconds / 60);
        const s = totalSeconds % 60;
        timerEl.textContent = `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
        if (totalSeconds <= 0) {
            clearInterval(timerInterval);
            timerEl.textContent = "Time's Up";
            timerEl.style.color = "var(--danger)";
        }
        sessionStorage.setItem(ssKey('timer'), totalSeconds);
        totalSeconds--;
    }
    tick();
    timerInterval = setInterval(tick, 1000);
}

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------
function initializeChat() {
    const form  = document.getElementById("chatForm");
    const input = document.getElementById("chatInput");
    if (!form) return;

    if (input && TEAM_ID) {
        input.addEventListener("input", () => {
            if (promptTypingTimeout) clearTimeout(promptTypingTimeout);
            promptTypingTimeout = setTimeout(() => {
                if (teamWs && teamWs.readyState === WebSocket.OPEN) {
                    teamWs.send(JSON.stringify({
                        type: "prompt_typing",
                        user_id: currentUser.user_id,
                        name: currentUser.name,
                        draft_text: input.value
                    }));
                }
            }, PROMPT_TYPING_DEBOUNCE);
        });
    }

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const msg = (input?.value || "").trim();
        if (!msg || !sessionId) return;

        input.value = "";
        const sendBtn = document.getElementById("sendBtn");
        if (sendBtn) sendBtn.disabled = true;

        if (TEAM_ID) {
            // ── TEAM PATH ──────────────────────────────────────────────────
            // 1. Show the message optimistically in the local UI immediately.
            appendChatBubble("user", msg, currentUser.name);

            // 2. Broadcast to teammates via WS so they also see it instantly
            //    (they won't re-render it from polling because lastKnownChatMsgId
            //     will advance past it once the poll runs).
            if (teamWs && teamWs.readyState === WebSocket.OPEN) {
                teamWs.send(JSON.stringify({
                    type: "chat_message",
                    message: msg,
                    name: currentUser.name,
                    user_id: currentUser.user_id
                }));
                teamWs.send(JSON.stringify({
                    type: "prompt_typing",
                    user_id: currentUser.user_id,
                    name: currentUser.name,
                    draft_text: ""
                }));
            }
            clearPromptTypingPreview(currentUser.user_id);

            // 3. POST to Gemini — reply goes into DB; polling will surface it
            //    for ALL members including this one.
            setTypingIndicator(true);
            try {
                const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/chat`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ message: msg, actor_user_id: currentUser.user_id }),
                });
                if (!res.ok) {
                    const err = await res.json().catch(() => ({}));
                    appendChatBubble("assistant", "⚠ " + (err.detail || "Something went wrong."));
                }
                // NOTE: we deliberately ignore data.reply here for team mode —
                // the polling loop will pick it up for all members simultaneously.
            } catch {
                appendChatBubble("assistant", "⚠ Could not reach the server.");
            } finally {
                setTypingIndicator(false);
                if (sendBtn) sendBtn.disabled = false;
                input.focus();
            }
        } else {
            // ── SOLO PATH (unchanged) ───────────────────────────────────────
            appendChatBubble("user", msg);
            setTypingIndicator(true);
            try {
                const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/chat`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ message: msg }),
                });
                if (!res.ok) {
                    const err = await res.json().catch(() => ({}));
                    appendChatBubble("assistant", "⚠ " + (err.detail || "Something went wrong."));
                    return;
                }
                const data = await res.json();
                appendChatBubble("assistant", data.reply);
            } catch {
                appendChatBubble("assistant", "⚠ Could not reach the server.");
            } finally {
                setTypingIndicator(false);
                if (sendBtn) sendBtn.disabled = false;
                input.focus();
            }
        }
    });
}

// ---------------------------------------------------------------------------
// Team: poll chat history so all members see new messages
// TODO: remove this polling when backend broadcasts 'assistant_reply' over WS.
// ---------------------------------------------------------------------------
function startChatPolling() {
    if (chatPollingInterval) clearInterval(chatPollingInterval);
    // Poll immediately, then every 3 s
    pollChatHistory();
    chatPollingInterval = setInterval(pollChatHistory, 3000);
}

async function pollChatHistory() {
    if (!sessionId) return;
    try {
        const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/messages`);
        if (!res.ok) return;
        const messages = await res.json();
        // Only append messages we haven't seen yet (by id)
        messages.forEach(m => {
            if (m.id > lastKnownChatMsgId) {
                lastKnownChatMsgId = m.id;
                // Skip user messages that we already showed optimistically from
                // our own send.  Show teammate user messages and ALL assistant
                // messages (Gemini replies).
                if (m.role === "assistant") {
                    setTypingIndicator(false);
                    appendChatBubble("assistant", m.content);
                } else if (m.role === "user" && m.user_id !== currentUser.user_id) {
                    // teammate's message — already visible via WS chat_message
                    // broadcast, but render here as a safety net if WS was slow.
                    // Dedup check: skip if already visible (look for a matching bubble).
                    // Simple approach: just skip — the WS delivery is fast enough.
                }
            }
        });
    } catch { /* silent — polling is best-effort */ }
}

function formatAssistantText(text) {
    if (!text) return "";

    const codeBlocks = [];
    let processed = String(text).replace(/```(\w*)\n?([\s\S]*?)```/g, (match, lang, code) => {
        const placeholder = `___CODEBLOCK_${codeBlocks.length}___`;
        const escapedCode = escapeHtml(code.trim());
        codeBlocks.push(`<pre><code class="language-${lang || 'text'}">${escapedCode}</code></pre>`);
        return placeholder;
    });

    processed = escapeHtml(processed);
    processed = processed.replace(/`([^`]+)`/g, (m, c) => `<code>${c}</code>`);
    processed = processed.replace(/\*\*([^*]+)\*\*/g, (m, b) => `<strong>${b}</strong>`);
    processed = processed.replace(/\n/g, "<br>");

    codeBlocks.forEach((blockHtml, i) => {
        processed = processed.replace(`___CODEBLOCK_${i}___`, blockHtml);
    });

    return processed;
}

function appendChatBubble(role, text, userName = null) {
    const container = document.getElementById("chatMessages");
    if (!container) return;

    let bubbleRole = role;
    if (role === "user" && userName && currentUser && userName !== currentUser.name) {
        bubbleRole = "teammate";
    }

    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${bubbleRole}`;

    let html = "";
    if (role === "assistant") {
        html = formatAssistantText(text);
    } else {
        html = escapeHtml(text).replace(/\n/g, "<br>");
    }

    if (userName && (bubbleRole === "user" || bubbleRole === "teammate")) {
        const icon = bubbleRole === "teammate" ? "👥" : "👤";
        html = `<div class="chat-user-name"><span>${icon}</span> ${escapeHtml(userName)}</div>` + html;
    } else if (role === "assistant") {
        html = `<div class="chat-assistant-name"><span>✨</span> AI Assistant (Gemini)</div>` + html;
    }

    bubble.innerHTML = html;

    container.appendChild(bubble);
    requestAnimationFrame(() => {
        container.scrollTop = container.scrollHeight;
    });
}

function setTypingIndicator(on) {
    const existing = document.getElementById("typingIndicator");
    if (on && !existing) {
        const indicator = document.createElement("div");
        indicator.id = "typingIndicator";
        indicator.className = "chat-bubble assistant typing";
        indicator.innerHTML = '<div class="chat-assistant-name"><span>✨</span> AI Assistant (Gemini)</div><div class="typing-dots"><span></span><span></span><span></span></div>';
        document.getElementById("chatMessages")?.appendChild(indicator);
        document.getElementById("chatMessages").scrollTop = 99999;
    } else if (!on && existing) {
        existing.remove();
    }
}

function updatePromptTypingPreview(userId, name, draftText) {
    if (!draftText) {
        clearPromptTypingPreview(userId);
        return;
    }
    remoteTypingStates[userId] = { name, draftText };
    const preview = document.getElementById("promptTypingPreview");
    if (!preview) return;
    const previews = Object.values(remoteTypingStates)
        .filter(s => s.draftText)
        .map(s => `${escapeHtml(s.name)} is typing: ${escapeHtml(s.draftText)}`);
    if (previews.length) {
        preview.textContent = previews.join(" \u2022 ");
        preview.style.display = "block";
    } else {
        preview.style.display = "none";
    }
    if (promptTypingClearTimers[userId]) {
        clearTimeout(promptTypingClearTimers[userId]);
    }
    promptTypingClearTimers[userId] = setTimeout(() => {
        delete remoteTypingStates[userId];
        updatePromptTypingPreview(userId, name, "");
    }, PROMPT_TYPING_IDLE_MS);
}

function clearPromptTypingPreview(userId) {
    delete remoteTypingStates[userId];
    if (promptTypingClearTimers[userId]) {
        clearTimeout(promptTypingClearTimers[userId]);
        delete promptTypingClearTimers[userId];
    }
    const preview = document.getElementById("promptTypingPreview");
    if (!preview) return;
    const previews = Object.values(remoteTypingStates)
        .filter(s => s.draftText)
        .map(s => `${escapeHtml(s.name)} is typing: ${escapeHtml(s.draftText)}`);
    if (previews.length) {
        preview.textContent = previews.join(" \u2022 ");
        preview.style.display = "block";
    } else {
        preview.style.display = "none";
    }
}

function getCaretCoordinates(textarea, position) {
    const style = getComputedStyle(textarea);
    const lineHeight = parseFloat(style.lineHeight) || parseFloat(style.fontSize) * 1.2;
    const paddingLeft = parseFloat(style.paddingLeft) || 0;
    const paddingTop = parseFloat(style.paddingTop) || 0;
    const charWidth = measureCharWidth(textarea, style);

    const before = textarea.value.slice(0, position);
    const row = (before.match(/\n/g) || []).length;
    const lastNewline = before.lastIndexOf("\n");
    const col = position - lastNewline - 1;

    return {
        top: Math.max(0, row * lineHeight - textarea.scrollTop + paddingTop),
        left: Math.max(0, col * charWidth - textarea.scrollLeft + paddingLeft)
    };
}

function measureCharWidth(textarea, style) {
    if (textarea._charWidth) return textarea._charWidth;
    const span = document.createElement("span");
    span.style.position = "absolute";
    span.style.visibility = "hidden";
    span.style.whiteSpace = "pre";
    span.style.fontFamily = style.fontFamily;
    span.style.fontSize = style.fontSize;
    span.style.fontWeight = style.fontWeight;
    span.style.letterSpacing = style.letterSpacing;
    span.textContent = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";
    document.body.appendChild(span);
    const width = span.getBoundingClientRect().width / span.textContent.length;
    document.body.removeChild(span);
    textarea._charWidth = width;
    return width;
}

function renderRemoteCursors() {
    const overlay = document.getElementById("cursorOverlay");
    const editor = document.getElementById("codeEditor");
    if (!overlay || !editor) return;
    overlay.innerHTML = "";

    Object.entries(remoteCursors).forEach(([userId, cursor]) => {
        if (parseInt(userId, 10) === currentUser.user_id) return;
        if (cursor.selection_start == null) return;
        const pos = Math.min(cursor.selection_start, editor.value.length);
        const coords = getCaretCoordinates(editor, pos);
        const cursorEl = document.createElement("div");
        cursorEl.className = "remote-cursor";
        cursorEl.style.top = `${coords.top}px`;
        cursorEl.style.left = `${coords.left}px`;
        cursorEl.innerHTML = `
            <span class="cursor-flag"></span>
            <span class="cursor-label">${escapeHtml(cursor.name || "Teammate")}</span>
        `;
        overlay.appendChild(cursorEl);
    });
}

function computeCodeDiff(oldText, newText) {
    if (oldText === newText) return null;
    let start = 0;
    while (start < oldText.length && start < newText.length && oldText[start] === newText[start]) {
        start += 1;
    }
    let endOld = oldText.length - 1;
    let endNew = newText.length - 1;
    while (endOld >= start && endNew >= start && oldText[endOld] === newText[endNew]) {
        endOld -= 1;
        endNew -= 1;
    }
    const deleteCount = Math.max(0, endOld - start + 1);
    const insertText = newText.slice(start, endNew + 1);
    return { start, deleteCount, insertText };
}

function applyCodeDiff(msg) {
    const editor = document.getElementById("codeEditor");
    if (!editor) return;
    const current = editor.value;
    const start = Math.min(Math.max(0, msg.start), current.length);
    const deleteCount = Math.max(0, msg.delete_count || 0);
    const before = current.slice(0, start);
    const after = current.slice(start + deleteCount);
    const newValue = before + (msg.insert_text || "") + after;
    if (newValue === current) return;
    const selStart = editor.selectionStart;
    const selEnd = editor.selectionEnd;
    const delta = (msg.insert_text || "").length - deleteCount;
    editor.value = newValue;
    lastSavedCode = newValue;
    sessionStorage.setItem(ssKey('code'), newValue);
    const restoreStart = selStart >= start ? Math.max(start, Math.min(selStart + delta, newValue.length)) : selStart;
    const restoreEnd = selEnd >= start ? Math.max(start, Math.min(selEnd + delta, newValue.length)) : selEnd;
    try {
        editor.setSelectionRange(restoreStart, restoreEnd);
    } catch { }
    showToast(`✏️ ${msg.name || "A teammate"} made edits`);
}

// ---------------------------------------------------------------------------
// Auto-save code
// ---------------------------------------------------------------------------
function initializeAutoSave() {
    const editor = document.getElementById("codeEditor");
    if (!editor) return;

    // Save on blur
    editor.addEventListener("blur", () => saveCode());

    // Save on interval
    saveInterval = setInterval(() => saveCode(), AUTOSAVE_INTERVAL_MS);

    // Persist to sessionStorage on every keystroke (cheap, local only)
    editor.addEventListener("input", () => {
        sessionStorage.setItem(ssKey('code'), editor.value);
    });
}

async function saveCode() {
    const editor = document.getElementById("codeEditor");
    if (!editor || !sessionId || isSubmitted) return;

    const code = editor.value;
    if (code === lastSavedCode) return;   // no change, skip network call

    setSaveStatus("Saving…");
    try {
        const payload = { code };
        if (TEAM_ID) payload.actor_user_id = currentUser.user_id;

        const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/save-code`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        if (res.ok) {
            lastSavedCode = code;
            setSaveStatus("Saved ✓");
        } else {
            setSaveStatus("Save failed");
        }
    } catch {
        setSaveStatus("Offline");
    }
}

function setSaveStatus(msg) {
    const el = document.getElementById("saveStatus");
    if (el) el.textContent = msg;
}

// ---------------------------------------------------------------------------
// Submit
// ---------------------------------------------------------------------------
function initializeSubmitBtn() {
    const btn = document.getElementById("submitBtn");
    if (!btn) return;

    updateSubmitButtonForTeamRole();

    btn.addEventListener("click", async () => {
        const currentUserId = currentUser?.user_id || currentUser?.id;
        if (TEAM_ID && teamLeaderUserId && currentUserId !== teamLeaderUserId) {
            alert(`Only ${teamLeaderName} (Team Leader) can submit this challenge for grading.`);
            return;
        }

        if (isSubmitted) return;
        if (!sessionId) { alert("No active session. Please start the challenge first."); return; }

        const confirmed = confirm(
            "Are you sure you want to submit for grading?\nThis is your ONE official submission."
        );
        if (!confirmed) return;

        // Trigger a final save first
        await saveCode();

        btn.disabled = true;
        btn.textContent = "Submitting…";

        try {
            const payload = {};
            if (TEAM_ID) payload.actor_user_id = currentUserId;
            const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/submit`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });

            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                alert("Submission failed: " + (err.detail || res.statusText));
                return;
            }

            const data = await res.json();
            isSubmitted = true;

            // Clear session state
            sessionStorage.removeItem(ssKey('session_id'));
            sessionStorage.removeItem(ssKey('team_id'));
            sessionStorage.removeItem(ssKey('code'));
            sessionStorage.removeItem(ssKey('timer'));
            if (timerInterval)      clearInterval(timerInterval);
            if (saveInterval)       clearInterval(saveInterval);
            if (chatPollingInterval) clearInterval(chatPollingInterval);
            if (teamWs && teamWs.readyState === WebSocket.OPEN) teamWs.close();

            // Redirect to result page
            window.location.href = `result.html?id=${data.submission_id}`;
        } catch (err) {
            alert("Could not reach the server. Is the backend running?");
        } finally {
            if (TEAM_ID && teamLeaderUserId && (currentUser?.user_id || currentUser?.id) !== teamLeaderUserId) {
                updateSubmitButtonForTeamRole();
            } else {
                btn.disabled  = false;
                btn.textContent = "Submit for Grading";
            }
        }
    });
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function escapeHtml(str) {
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

// ===========================================================================
// Team Workspace
// ===========================================================================

function setupTeamWorkspace() {
    // RECONNECT CHOICE: We reconnect the WebSocket on the workspace page rather
    // than trying to reuse the lobby's connection.  Browser navigation closes WS
    // connections, and passing a live socket across a full-page redirect is not
    // practical in a plain-HTML MPA.  The team_id is kept in sessionStorage so
    // this works even if the user manually refreshes the workspace page.
    const wsProtocol = API_BASE.startsWith("https") ? "wss:" : "ws:";
    const wsHost = API_BASE.replace(/^https?:\/\//, "");
    teamWs = new WebSocket(`${wsProtocol}//${wsHost}/api/teams/${TEAM_ID}/ws?user_id=${currentUser.user_id}`);

    teamWs.onopen = () => {
        console.log("[Team WS] connected in workspace");
        updateConnectionDot(true);
        // Send a join announcement so teammates' presence bars update
        teamWs.send(JSON.stringify({
            type: "member_joined",
            user_id: currentUser.user_id,
            name: currentUser.name
        }));
    };

    teamWs.onmessage = (e) => {
        try {
            const msg = JSON.parse(e.data);
            handleTeamWsMessage(msg);
        } catch (err) {
            console.error("[Team WS] parse error", err);
        }
    };

    teamWs.onclose = () => {
        console.log("[Team WS] closed");
        updateConnectionDot(false);
    };

    teamWs.onerror = () => updateConnectionDot(false);

    const editor = document.getElementById("codeEditor");
    if (editor) {
        lastSyncedCode = editor.value;

        const sendCodeDiff = () => {
            const current = editor.value;
            const patch = computeCodeDiff(lastSyncedCode, current);
            if (!patch || (patch.deleteCount === 0 && patch.insertText === "")) {
                lastSyncedCode = current;
                return;
            }
            if (teamWs && teamWs.readyState === WebSocket.OPEN) {
                teamWs.send(JSON.stringify({
                    type: "code_diff",
                    user_id: currentUser.user_id,
                    name: currentUser.name,
                    start: patch.start,
                    delete_count: patch.deleteCount,
                    insert_text: patch.insertText,
                    context: patch.context
                }));
            }
            lastSyncedCode = current;
        };

        const scheduleCodeDiff = () => {
            if (codeSyncTimeout) clearTimeout(codeSyncTimeout);
            codeSyncTimeout = setTimeout(sendCodeDiff, CODE_SYNC_DEBOUNCE);
        };

        const sendCursorMove = () => {
            if (teamWs && teamWs.readyState === WebSocket.OPEN) {
                teamWs.send(JSON.stringify({
                    type: "cursor_move",
                    user_id: currentUser.user_id,
                    name: currentUser.name,
                    selection_start: editor.selectionStart,
                    selection_end: editor.selectionEnd
                }));
            }
        };

        const scheduleCursorMove = () => {
            if (cursorMoveTimeout) clearTimeout(cursorMoveTimeout);
            cursorMoveTimeout = setTimeout(sendCursorMove, CURSOR_MOVE_DEBOUNCE);
        };

        editor.addEventListener("input", () => {
            scheduleCodeDiff();
            scheduleCursorMove();
        });
        editor.addEventListener("keydown", scheduleCursorMove);
        editor.addEventListener("click", scheduleCursorMove);
        editor.addEventListener("mouseup", scheduleCursorMove);
    }

    // ── Mic Button ──
    const micBtn = document.getElementById("toggleMicBtn");
    if (micBtn) micBtn.addEventListener("click", toggleMic);

    // ── Fetch current roster then start presence + chat ──
    fetchTeamMembers();
    startChatPolling();
}

let teamLeaderUserId = null;
let teamLeaderName = "Team Leader";

function updateSubmitButtonForTeamRole() {
    const btn = document.getElementById("submitBtn");
    if (!btn || !TEAM_ID) return;

    const currentUserId = currentUser?.user_id || currentUser?.id;
    if (teamLeaderUserId && currentUserId !== teamLeaderUserId) {
        btn.disabled = true;
        btn.title = `Only ${teamLeaderName} (Team Leader) can submit this challenge for grading.`;
        btn.innerHTML = `🔒 Only ${escapeHtml(teamLeaderName)} Can Submit`;
    }
}

async function fetchTeamMembers() {
    try {
        const res = await fetch(`${API_BASE}/api/teams/${TEAM_ID}`);
        if (res.ok) {
            const data = await res.json();
            teamLeaderUserId = data.leader_user_id || (data.members && data.members[0] ? data.members[0].user_id : null);
            data.members.forEach(m => {
                teamMembers[m.user_id] = { ...m, isMuted: true, isOnline: true };
                if (m.user_id === teamLeaderUserId) {
                    teamLeaderName = m.name;
                }
            });
            renderPresenceBar();
            updateSubmitButtonForTeamRole();
        }
    } catch (e) {
        console.error("Failed to fetch team members");
    }
}

function handleTeamWsMessage(msg) {
    switch (msg.type) {
        case "member_joined":
            // Merge into teamMembers (preserve existing mute state if known)
            teamMembers[msg.user_id] = {
                ...teamMembers[msg.user_id],
                user_id: msg.user_id,
                name: msg.name,
                isMuted: teamMembers[msg.user_id]?.isMuted ?? true,
                isOnline: true
            };
            renderPresenceBar();
            // If we are already unmuted, proactively call the newcomer so they
            // hear us — the initiator role avoids both sides creating offers simultaneously
            if (!isMicMuted && msg.user_id !== currentUser.user_id && !rtcPeers[msg.user_id]) {
                createPeerConnection(msg.user_id, /* isInitiator */ true);
            }
            break;

        case "member_left":
            if (teamMembers[msg.user_id]) {
                teamMembers[msg.user_id].isOnline = false;
            }
            renderPresenceBar();
            // Tear down RTC + audio element for this member
            teardownPeer(msg.user_id);
            break;

        case "mute_state":
            // msg.user_id is the member whose mute state changed
            if (teamMembers[msg.user_id]) {
                teamMembers[msg.user_id].isMuted = msg.is_muted;
                renderPresenceBar();
            }
            break;

        case "chat_message":
            // A teammate sent a message — show it in the chat panel with teammate styling.
            // We skip our own user_id because we already showed it optimistically.
            if (msg.user_id !== currentUser.user_id) {
                appendChatBubble("teammate", msg.message, msg.name);
            }
            break;

        case "assistant_reply":
            setTypingIndicator(false);
            if (msg.msg_id && msg.msg_id <= lastKnownChatMsgId) {
                break;
            }
            if (msg.msg_id) {
                lastKnownChatMsgId = Math.max(lastKnownChatMsgId, msg.msg_id);
            }
            appendChatBubble("assistant", msg.message);
            break;

        case "team_submitted":
            setTypingIndicator(false);
            sessionStorage.removeItem(ssKey('session_id'));
            sessionStorage.removeItem(ssKey('team_id'));
            sessionStorage.removeItem(ssKey('code'));
            sessionStorage.removeItem(ssKey('timer'));
            if (timerInterval)       clearInterval(timerInterval);
            if (saveInterval)        clearInterval(saveInterval);
            if (chatPollingInterval) clearInterval(chatPollingInterval);
            if (teamWs && teamWs.readyState === WebSocket.OPEN) teamWs.close();
            if (msg.submission_id) {
                window.location.href = `result.html?id=${msg.submission_id}`;
            }
            break;

        case "code_sync":
            if (msg.user_id === currentUser.user_id) break;
            {
                const editor = document.getElementById("codeEditor");
                if (editor && editor.value !== msg.code) {
                    const selStart = editor.selectionStart;
                    const selEnd   = editor.selectionEnd;

                    editor.value = msg.code;
                    lastSavedCode = msg.code;
                    lastSyncedCode = msg.code;
                    sessionStorage.setItem(ssKey('code'), msg.code);

                    try {
                        editor.setSelectionRange(
                            Math.min(selStart, msg.code.length),
                            Math.min(selEnd,   msg.code.length)
                        );
                    } catch { /* non-fatal */ }

                    showToast(`✏️ ${msg.name || "A teammate"} made changes`);
                }
            }
            break;

        case "code_diff":
            if (msg.user_id === currentUser.user_id) break;
            applyCodeDiff(msg);
            lastSyncedCode = document.getElementById("codeEditor")?.value || lastSyncedCode;
            break;

        case "cursor_move":
            if (msg.user_id === currentUser.user_id) break;
            remoteCursors[msg.user_id] = {
                name: msg.name,
                selection_start: msg.selection_start,
                selection_end: msg.selection_end
            };
            renderRemoteCursors();
            break;

        case "prompt_typing":
            if (msg.user_id === currentUser.user_id) break;
            updatePromptTypingPreview(msg.user_id, msg.name, msg.draft_text || "");
            break;

        case "member_offline":
            clearPromptTypingPreview(msg.user_id);
            delete remoteCursors[msg.user_id];
            renderRemoteCursors();
            if (teamMembers[msg.user_id]) {
                teamMembers[msg.user_id].isOnline = false;
            }
            renderPresenceBar();
            teardownPeer(msg.user_id);
            break;

        case "voice-offer":  handleVoiceOffer(msg);  break;
        case "voice-answer": handleVoiceAnswer(msg); break;
        case "voice-ice":    handleVoiceIce(msg);    break;
    }
}

function renderPresenceBar() {
    const container = document.getElementById("teamAvatars");
    if (!container) return;

    container.innerHTML = "";
    Object.values(teamMembers).forEach(m => {
        const isSelf    = m.user_id === currentUser.user_id;
        const initials  = (m.name || m.username || "U").substring(0, 2).toUpperCase();
        const classes   = [
            "team-avatar",
            m.isMuted    ? "muted"   : "",
            !m.isOnline  ? "offline" : "",
            isSelf       ? "self"    : ""
        ].filter(Boolean).join(" ");

        const div = document.createElement("div");
        div.className = classes;
        div.textContent = initials;
        div.title = (m.name || "Unknown") + (isSelf ? " (You)" : "") + (m.isMuted ? " — muted" : " — unmuted") + (!m.isOnline ? " — offline" : "");
        container.appendChild(div);
    });
}

function updateConnectionDot(connected) {
    const dot = document.getElementById("wsConnectionDot");
    if (!dot) return;
    dot.className = connected ? "ws-dot ws-dot--online" : "ws-dot ws-dot--offline";
    dot.title = connected ? "Live — connected" : "Disconnected";
}

function showToast(message, durationMs = 3000) {
    // Create a new toast each call so rapid-fire toasts stack and don't clobber each other
    const toast = document.createElement("div");
    toast.className = "team-toast";
    toast.textContent = message;
    document.body.appendChild(toast);

    // Animate in (next frame so the initial class takes effect first)
    requestAnimationFrame(() => toast.classList.add("team-toast--visible"));

    // Animate out then remove
    setTimeout(() => {
        toast.classList.remove("team-toast--visible");
        toast.addEventListener("transitionend", () => toast.remove(), { once: true });
    }, durationMs);
}

// ===========================================================================
// Task 6 — Group Voice: Mesh WebRTC
//
// Architecture: full mesh — every member has a direct RTCPeerConnection to
// every other member.  Signaling (offers / answers / ICE candidates) travels
// over the shared team WebSocket.
//
// WS message types defined here (sent by this client, expected from server):
//   voice-offer   { type, target_user_id, from_user_id, offer: RTCSessionDescription }
//   voice-answer  { type, target_user_id, from_user_id, answer: RTCSessionDescription }
//   voice-ice     { type, target_user_id, from_user_id, candidate: RTCIceCandidateInit }
//   mute_state    { type, user_id, is_muted }   ← also used for presence bar
// ===========================================================================

// ---------------------------------------------------------------------------
// Mic toggle — entry point for the mute/unmute button
// ---------------------------------------------------------------------------
async function toggleMic() {
    const btn = document.getElementById("toggleMicBtn");
    if (!btn) return;

    if (isMicMuted) {
        await unmuteMic(btn);
    } else {
        muteMic(btn);
    }

    // Broadcast new mute state to all teammates so their presence bars update
    wsSend({ type: "mute_state", user_id: currentUser.user_id, is_muted: isMicMuted });

    // Update own avatar in the presence bar immediately (no need to wait for echo)
    if (teamMembers[currentUser.user_id]) {
        teamMembers[currentUser.user_id].isMuted = isMicMuted;
        renderPresenceBar();
    }
}

async function unmuteMic(btn) {
    try {
        if (!localAudioStream) {
            // First unmute: request mic access
            localAudioStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
        }

        // (Re-)enable all audio tracks
        localAudioStream.getAudioTracks().forEach(t => { t.enabled = true; });

        // Add tracks to any existing peer connections that don't have them yet
        // (handles the case where we re-unmute after a previous mute)
        Object.entries(rtcPeers).forEach(([uid, pc]) => {
            const existingSenders = pc.getSenders().map(s => s.track);
            localAudioStream.getTracks().forEach(track => {
                if (!existingSenders.includes(track)) {
                    pc.addTrack(track, localAudioStream);
                }
            });
        });

        // Open new connections to anyone online who doesn't have one yet
        Object.values(teamMembers).forEach(m => {
            if (m.user_id !== currentUser.user_id && m.isOnline && !rtcPeers[m.user_id]) {
                createPeerConnection(m.user_id, /* isInitiator */ true);
            }
        });

        isMicMuted = false;
        btn.textContent = "🔊 Mute";
        btn.classList.remove("btn-ghost");
        btn.classList.add("btn-active-voice");

        // Clear any prior mic-error message
        hideMicError();

    } catch (err) {
        // Permission denied or no mic — show inline message, don't block anything
        console.warn("[Voice] getUserMedia failed:", err);
        showMicError("Mic access denied — you can still use chat and see code updates.");
        // Leave isMicMuted = true so button state is unchanged
    }
}

function muteMic(btn) {
    if (localAudioStream) {
        localAudioStream.getAudioTracks().forEach(t => { t.enabled = false; });
    }
    isMicMuted = true;
    btn.textContent = "🔇 Unmute";
    btn.classList.add("btn-ghost");
    btn.classList.remove("btn-active-voice");
}

// ---------------------------------------------------------------------------
// Inline mic error — shows below the presence bar, doesn't block the page
// ---------------------------------------------------------------------------
function showMicError(message) {
    let el = document.getElementById("micErrorMsg");
    if (!el) {
        el = document.createElement("p");
        el.id = "micErrorMsg";
        el.style.cssText =
            "margin:6px 0 0; font-size:0.8rem; color:#f87171;" +
            "text-align:center; padding:0 8px;";
        const bar = document.getElementById("teamPresenceBar");
        if (bar) bar.insertAdjacentElement("afterend", el);
    }
    el.textContent = message;
    el.style.display = "block";
}

function hideMicError() {
    const el = document.getElementById("micErrorMsg");
    if (el) el.style.display = "none";
}

// ---------------------------------------------------------------------------
// Peer connection lifecycle
// ---------------------------------------------------------------------------

/** STUN config — add TURN credentials here when available */
function getRTCConfig() {
    return {
        iceServers: [
            { urls: "stun:stun.l.google.com:19302" },
            { urls: "stun:stun1.l.google.com:19302" }
        ]
    };
}

/**
 * Create (or return existing) RTCPeerConnection to targetUserId.
 * If isInitiator=true, create and send an SDP offer immediately.
 */
function createPeerConnection(targetUserId, isInitiator) {
    if (rtcPeers[targetUserId]) return rtcPeers[targetUserId];

    const pc = new RTCPeerConnection(getRTCConfig());
    rtcPeers[targetUserId] = pc;

    // Add our local audio tracks if the mic is already on
    if (localAudioStream && !isMicMuted) {
        localAudioStream.getTracks().forEach(track => pc.addTrack(track, localAudioStream));
    }

    // Send ICE candidates as they are gathered
    pc.onicecandidate = ({ candidate }) => {
        if (candidate) {
            wsSend({
                type:           "voice-ice",
                target_user_id: targetUserId,
                from_user_id:   currentUser.user_id,
                candidate:      candidate.toJSON()
            });
        }
    };

    // Log connection state changes for debugging
    pc.onconnectionstatechange = () => {
        console.log(`[RTC ${targetUserId}] state →`, pc.connectionState);
        if (pc.connectionState === "failed" || pc.connectionState === "closed") {
            teardownPeer(targetUserId);
        }
    };

    // Attach incoming audio to an <audio> element
    pc.ontrack = ({ streams }) => {
        const stream = streams[0];
        if (!stream) return;
        const audioId = `peer-audio-${targetUserId}`;
        let audioEl = document.getElementById(audioId);
        if (!audioEl) {
            audioEl = document.createElement("audio");
            audioEl.id = audioId;
            audioEl.autoplay = true;
            // Keep out of tab-order / accessibility tree
            audioEl.setAttribute("aria-hidden", "true");
            document.body.appendChild(audioEl);
        }
        audioEl.srcObject = stream;
    };

    // Initiator creates and sends the offer
    if (isInitiator) {
        pc.createOffer()
            .then(offer => pc.setLocalDescription(offer))
            .then(() => {
                wsSend({
                    type:           "voice-offer",
                    target_user_id: targetUserId,
                    from_user_id:   currentUser.user_id,
                    offer:          pc.localDescription
                });
            })
            .catch(err => console.error(`[RTC ${targetUserId}] offer failed:`, err));
    }

    return pc;
}

/**
 * Tear down the peer connection to userId and clean up the audio element.
 * Safe to call multiple times.
 */
function teardownPeer(userId) {
    const pc = rtcPeers[userId];
    if (pc) {
        pc.onicecandidate    = null;
        pc.ontrack           = null;
        pc.onconnectionstatechange = null;
        try { pc.close(); } catch { /* already closed */ }
        delete rtcPeers[userId];
    }

    // Remove the injected <audio> element
    const audioEl = document.getElementById(`peer-audio-${userId}`);
    if (audioEl) audioEl.remove();
}

// ---------------------------------------------------------------------------
// WS signaling handlers
// ---------------------------------------------------------------------------

async function handleVoiceOffer(msg) {
    // Accept offers even when muted — we still want to hear the other side.
    // We just won't add our own tracks until the user unmutes.
    const pc = createPeerConnection(msg.from_user_id, /* isInitiator */ false);

    try {
        await pc.setRemoteDescription(new RTCSessionDescription(msg.offer));
        const answer = await pc.createAnswer();
        await pc.setLocalDescription(answer);
        wsSend({
            type:           "voice-answer",
            target_user_id: msg.from_user_id,
            from_user_id:   currentUser.user_id,
            answer:         pc.localDescription
        });
    } catch (err) {
        console.error(`[RTC ${msg.from_user_id}] answer failed:`, err);
        teardownPeer(msg.from_user_id);
    }
}

async function handleVoiceAnswer(msg) {
    const pc = rtcPeers[msg.from_user_id];
    if (!pc) return;
    try {
        await pc.setRemoteDescription(new RTCSessionDescription(msg.answer));
    } catch (err) {
        console.error(`[RTC ${msg.from_user_id}] setRemoteDescription(answer) failed:`, err);
    }
}

async function handleVoiceIce(msg) {
    const pc = rtcPeers[msg.from_user_id];
    if (!pc || !msg.candidate) return;
    try {
        await pc.addIceCandidate(new RTCIceCandidate(msg.candidate));
    } catch (err) {
        // Chrome sometimes fires spurious errors on already-closed connections — ignore
        console.warn(`[RTC ${msg.from_user_id}] addIceCandidate error:`, err);
    }
}

// ---------------------------------------------------------------------------
// Convenience wrapper: send over WS only if connected
// ---------------------------------------------------------------------------
function wsSend(payload) {
    if (teamWs && teamWs.readyState === WebSocket.OPEN) {
        teamWs.send(JSON.stringify(payload));
    }
}
