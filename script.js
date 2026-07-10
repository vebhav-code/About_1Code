/* =========================================================
   1Code — interactive scenario demo
   Flow: Diagnose → Locate the fault → Prompt it → Score
   Fully client-side for the prototype. Scoring is a stand-in
   rubric — the real product swaps this for an AI-judge call
   over the same rubric shape.
   ========================================================= */

document.addEventListener('DOMContentLoaded', () => {

  /* ---------- HERO: typewriter + trace line ---------- */
  const heroLines = [
    'checking token expiry format…',
    'comparing units: seconds vs ms…',
    'root cause: unit mismatch in setTimeout'
  ];
  const typewriterEl = document.getElementById('heroTypewriter');
  const traceLine = document.getElementById('traceLine');

  if (typewriterEl) runTypewriter(heroLines, typewriterEl);
  if (traceLine) animateTrace(traceLine);

  function runTypewriter(lines, el) {
    let lineIndex = 0, charIndex = 0, deleting = false;
    function tick() {
      const current = lines[lineIndex];
      el.textContent = deleting
        ? current.slice(0, charIndex--)
        : current.slice(0, charIndex++);

      let delay = deleting ? 22 : 38;

      if (!deleting && charIndex === current.length + 1) {
        delay = 1400;
        deleting = true;
      } else if (deleting && charIndex < 0) {
        deleting = false;
        charIndex = 0;
        lineIndex = (lineIndex + 1) % lines.length;
        delay = 300;
      }
      setTimeout(tick, delay);
    }
    tick();
  }

  function animateTrace(polyline) {
    const width = 600, points = 40;
    let t = 0;
    function frame() {
      let d = '';
      for (let i = 0; i <= points; i++) {
        const x = (width / points) * i;
        const settle = Math.min(t / 120, 1); // noise fades as "scan settles"
        const noise = (1 - settle) * Math.sin(i * 0.9 + t * 0.15) * 22
                    + (1 - settle) * (Math.random() - 0.5) * 10;
        const y = 45 + noise;
        d += `${x},${y} `;
      }
      polyline.setAttribute('points', d.trim());
      t++;
      if (t < 260) requestAnimationFrame(frame);
      else polyline.setAttribute('points', `0,45 ${width},45`);
    }
    frame();
  }

  /* ---------- DEMO STATE MACHINE ---------- */
  const demoShell = document.querySelector('.demo-shell');
  if (!demoShell) return;

  const steps = demoShell.querySelectorAll('.demo-step');
  const progressSteps = demoShell.querySelectorAll('.demo-progress .step');

  function goToStep(n) {
    steps.forEach(s => s.classList.toggle('active', Number(s.dataset.step) === n));
    progressSteps.forEach(p => {
      const stepNum = Number(p.dataset.step);
      p.classList.toggle('active', stepNum === n);
      p.classList.toggle('done', stepNum < n);
    });
    demoShell.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  document.getElementById('toStep2').addEventListener('click', () => goToStep(2));
  document.getElementById('toStep3').addEventListener('click', () => goToStep(3));
  document.getElementById('toStep4').addEventListener('click', () => {
    goToStep(4);
    runScoring();
  });
  demoShell.querySelectorAll('[data-back]').forEach(btn => {
    btn.addEventListener('click', () => goToStep(Number(btn.dataset.back)));
  });
  document.getElementById('restartDemo').addEventListener('click', resetDemo);

  /* ---------- dynamic "add another" inputs ---------- */
  document.getElementById('addDiagnosis').addEventListener('click', () => {
    addInput('diagnosisInputs', 'input', 'diagnosis-input',
      'e.g. session cookie not persisted across requests');
  });

  function addInput(containerId, tag, className, placeholder) {
    const container = document.getElementById(containerId);
    const el = document.createElement(tag);
    el.className = `text-input ${className}`;
    el.placeholder = placeholder;
    if (tag === 'textarea') el.rows = 3;
    container.appendChild(el);
    el.focus();
  }

  /* ---------- "Fix it" rounds (prompt / why / code) ---------- */
  let roundCount = 1;
  const addRoundBtn = document.getElementById('addRound');
  if (addRoundBtn) {
    addRoundBtn.addEventListener('click', () => {
      roundCount++;
      const container = document.getElementById('fixRounds');
      const round = document.createElement('div');
      round.className = 'fix-round';
      round.dataset.round = roundCount;
      round.innerHTML = `
        <span class="round-label">ATTEMPT ${roundCount}</span>

        <label class="block-label"><span class="block-tag">01</span> The prompt you'd give an AI</label>
        <textarea class="text-input prompt-input" rows="3" placeholder="What did you change in the prompt this time, based on what the last attempt got wrong?"></textarea>

        <label class="block-label"><span class="block-tag">02</span> Why this prompt — your reasoning</label>
        <textarea class="text-input why-input" rows="2" placeholder="What did attempt 1 miss, and why does this prompt address it?"></textarea>

        <label class="block-label"><span class="block-tag">03</span> The fixed code you got back</label>
        <textarea class="text-input code-input" rows="6" placeholder="Paste the updated code here."></textarea>
      `;
      container.appendChild(round);
      round.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  }

  /* ---------- SCORING ----------
     Lightweight keyword rubric standing in for the real
     AI-judge call. Weighted across: diagnosis accuracy (25),
     prompt precision (25), reasoning quality (20), fixed-code
     correctness (30). Real product swaps this function's body
     for a fetch() to the backend, same output shape.
  */
  const DIAGNOSIS_KEYWORDS = ['timeout','timer','unit','second','millisecond','ms ','expire','token','race','cleartimeout','memory leak','refresh'];
  const PROMPT_KEYWORDS = ['millisecond','unit','convert','settimeout','cleartimeout','logout','leak','expiresin','refresh',' ms'];
  const WHY_KEYWORDS = ['because','since','reason','unit','second','millisecond','mismatch','leak','stale','cleanup','fires','logout'];
  const CODE_KEYWORDS = ['cleartimeout', '1000'];

  function runScoring() {
    const scoreNumEl = document.getElementById('scoreNum');
    const scoreRing = document.querySelector('.score-ring');
    const headlineEl = document.getElementById('scoreHeadline');
    const listEl = document.getElementById('scoreList');

    headlineEl.textContent = 'Grading your approach…';
    listEl.innerHTML = '';
    scoreNumEl.textContent = '0';
    scoreRing.style.borderTopColor = 'var(--border)';

    const diagnosisTexts = Array.from(document.querySelectorAll('.diagnosis-input'))
      .map(i => i.value.trim().toLowerCase()).filter(Boolean);
    const promptTexts = Array.from(document.querySelectorAll('.prompt-input'))
      .map(i => i.value.trim().toLowerCase()).filter(Boolean);
    const whyTexts = Array.from(document.querySelectorAll('.why-input'))
      .map(i => i.value.trim().toLowerCase()).filter(Boolean);
    const codeTexts = Array.from(document.querySelectorAll('.code-input'))
      .map(i => i.value.trim().toLowerCase()).filter(Boolean);
    const roundCountUsed = document.querySelectorAll('.fix-round').length;

    // --- diagnosis score (max 25) ---
    let diagnosisHits = 0;
    diagnosisTexts.forEach(t => { if (DIAGNOSIS_KEYWORDS.some(k => t.includes(k))) diagnosisHits++; });
    const diagnosisScore = diagnosisTexts.length === 0 ? 0
      : Math.min(25, diagnosisHits * 10 + Math.min(diagnosisTexts.length, 3) * 2);

    // --- prompt score (max 25) ---
    let promptHits = 0;
    promptTexts.forEach(t => { if (PROMPT_KEYWORDS.some(k => t.includes(k))) promptHits++; });
    const promptSpecific = promptTexts.some(t => t.split(' ').length > 15);
    const promptScore = promptTexts.length === 0 ? 0
      : Math.min(25, promptHits * 9 + (promptSpecific ? 7 : 0));

    // --- reasoning score (max 20) ---
    let whyHits = 0;
    whyTexts.forEach(t => { if (WHY_KEYWORDS.some(k => t.includes(k))) whyHits++; });
    const whySubstantive = whyTexts.some(t => t.split(' ').length > 10);
    const whyScore = whyTexts.length === 0 ? 0
      : Math.min(20, whyHits * 8 + (whySubstantive ? 6 : 0));

    // --- fixed-code score (max 30) ---
    const hasClearTimeout = codeTexts.some(t => t.includes('cleartimeout'));
    const hasUnitFix = codeTexts.some(t => t.includes('1000'));
    const codeScore = codeTexts.length === 0 ? 0
      : (hasClearTimeout ? 15 : 0) + (hasUnitFix ? 15 : 0);

    const iterationBonus = roundCountUsed > 1 ? 5 : 0;
    const total = Math.min(100, diagnosisScore + promptScore + whyScore + codeScore + iterationBonus);

    // --- feedback copy ---
    const feedback = [];
    feedback.push(diagnosisScore >= 18
      ? 'Your hypotheses named the real fault class — unit/timing mismatch.'
      : 'None of your hypotheses named the timer-unit mismatch directly — that\'s the actual root cause here.');

    feedback.push(promptScore >= 18
      ? 'Your prompt pointed at the exact line and the wrong behavior, not just "fix this bug".'
      : 'Your prompt could be more specific: name the exact line, the wrong unit, and what should happen instead.');

    feedback.push(whyScore >= 14
      ? 'Your reasoning explained *why* the prompt targets the real cause — that\'s what a reviewer would want to see.'
      : 'Add more reasoning: explain why this specific fix addresses the 40-second symptom, not just what to change.');

    feedback.push(hasClearTimeout && hasUnitFix
      ? 'Your fixed code addressed both faults: the unit conversion and the missing clearTimeout on logout.'
      : hasUnitFix
        ? 'Your code fixed the unit mismatch, but the stale timer still isn\'t cleared on logout — that\'s a second, separate leak.'
        : hasClearTimeout
          ? 'Your code cleared the timer on logout, but the seconds-vs-milliseconds conversion is still missing.'
          : 'The fixed code didn\'t address either underlying fault — the unit conversion and the missing clearTimeout.');

    if (iterationBonus) feedback.push('Bonus: you iterated to a second attempt instead of stopping at the first try — that\'s rewarded.');

    // animate the count-up
    let current = 0;
    const duration = 900;
    const stepTime = 16;
    const increment = total / (duration / stepTime);
    const counter = setInterval(() => {
      current += increment;
      if (current >= total) {
        current = total;
        clearInterval(counter);
        headlineEl.textContent = headlineFor(total);
        listEl.innerHTML = feedback.map(f => `<li>${f}</li>`).join('');
        scoreRing.style.borderTopColor = colorFor(total);
      }
      scoreNumEl.textContent = Math.round(current);
    }, stepTime);
  }

  function headlineFor(score) {
    if (score >= 80) return 'Strong diagnostic instinct.';
    if (score >= 55) return 'Solid approach, room to sharpen the prompt.';
    return 'Approach needs more specificity — try again.';
  }
  function colorFor(score) {
    if (score >= 80) return '#4FD1C5';
    if (score >= 55) return '#F5A623';
    return '#F97066';
  }

  function resetDemo() {
    document.getElementById('diagnosisInputs').innerHTML =
      '<input type="text" class="text-input diagnosis-input" placeholder="e.g. token expiry set shorter than session refresh interval">';

    roundCount = 1;
    document.getElementById('fixRounds').innerHTML = `
      <div class="fix-round" data-round="1">
        <span class="round-label">ATTEMPT 1</span>

        <label class="block-label"><span class="block-tag">01</span> The prompt you'd give an AI</label>
        <textarea class="text-input prompt-input" rows="3" placeholder="e.g. In scheduleRefresh, expiresIn is in seconds but setTimeout expects milliseconds — convert it. Also clear refreshTimer inside logout() so the old timer can't fire after the user signs out."></textarea>

        <label class="block-label"><span class="block-tag">02</span> Why this prompt — your reasoning</label>
        <textarea class="text-input why-input" rows="2" placeholder="e.g. The 40-second logout matches a seconds-value being read as milliseconds — that's ~1000x too fast. The missing clearTimeout is a separate leak that fires after logout."></textarea>

        <label class="block-label"><span class="block-tag">03</span> The fixed code you got back</label>
        <textarea class="text-input code-input" rows="6" placeholder="Paste the code the AI returned (or the fix you wrote yourself) here."></textarea>
      </div>`;

    goToStep(1);
  }

});