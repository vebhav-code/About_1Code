/* ===========================================
   1Code — Contest Page
   Session-based workspace: editor + Gemini chat
   API: /api/sessions/* (start, chat, save-code, submit)
=========================================== */

const API_BASE = "https://about-1code.onrender.com";
const params = new URLSearchParams(window.location.search);
const CHALLENGE_SLUG = params.get('slug');
if (!CHALLENGE_SLUG) {
  // no slug in the URL — redirect back to the dashboard instead of
  // silently trying to load an undefined challenge
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

// ---------------------------------------------------------------------------
// Bootstrap
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
    sessionId = sessionStorage.getItem("challenge_session_id") || null;

    initializeChallenge();
    initializeDownload();
    initializeStart();

    // If a session was already started (e.g. page reload), jump straight to workspace
    if (sessionId) {
        revealWorkspace(null, null);   // no starter code; editor restores from sessionStorage
        const savedCode = sessionStorage.getItem("challenge_code") || "";
        document.getElementById("codeEditor").value = savedCode;
        lastSavedCode = savedCode;
        const savedTime = parseInt(sessionStorage.getItem("challenge_timer") || "0", 10);
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
                sessionStorage.setItem("challenge_session_id", sessionId);

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
        sessionStorage.setItem("challenge_code", starterCode);
    }

    initializeChat();
    initializeAutoSave();
    initializeSubmitBtn();
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
        sessionStorage.setItem("challenge_timer", totalSeconds);
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

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const msg = (input?.value || "").trim();
        if (!msg || !sessionId) return;

        input.value = "";
        appendChatBubble("user", msg);
        setTypingIndicator(true);

        const sendBtn = document.getElementById("sendBtn");
        if (sendBtn) sendBtn.disabled = true;

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
    });
}

function appendChatBubble(role, text) {
    const container = document.getElementById("chatMessages");
    if (!container) return;

    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${role}`;

    // Simple newline → <br> for readability
    bubble.innerHTML = escapeHtml(text).replace(/\n/g, "<br>");

    container.appendChild(bubble);
    container.scrollTop = container.scrollHeight;
}

function setTypingIndicator(on) {
    const existing = document.getElementById("typingIndicator");
    if (on && !existing) {
        const indicator = document.createElement("div");
        indicator.id = "typingIndicator";
        indicator.className = "chat-bubble assistant typing";
        indicator.innerHTML = '<span></span><span></span><span></span>';
        document.getElementById("chatMessages")?.appendChild(indicator);
        document.getElementById("chatMessages").scrollTop = 99999;
    } else if (!on && existing) {
        existing.remove();
    }
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
        sessionStorage.setItem("challenge_code", editor.value);
    });
}

async function saveCode() {
    const editor = document.getElementById("codeEditor");
    if (!editor || !sessionId || isSubmitted) return;

    const code = editor.value;
    if (code === lastSavedCode) return;   // no change, skip network call

    setSaveStatus("Saving…");
    try {
        const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/save-code`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ code }),
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

    btn.addEventListener("click", async () => {
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
            const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/submit`, {
                method: "POST",
            });

            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                alert("Submission failed: " + (err.detail || res.statusText));
                return;
            }

            const data = await res.json();
            isSubmitted = true;

            // Clear session state
            sessionStorage.removeItem("challenge_session_id");
            sessionStorage.removeItem("challenge_code");
            sessionStorage.removeItem("challenge_timer");
            if (timerInterval) clearInterval(timerInterval);
            if (saveInterval)  clearInterval(saveInterval);

            // Redirect to result page
            window.location.href = `result.html?id=${data.submission_id}`;
        } catch (err) {
            alert("Could not reach the server. Is the backend running?");
        } finally {
            btn.disabled  = false;
            btn.textContent = "Submit for Grading";
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
