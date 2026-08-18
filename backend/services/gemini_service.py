"""
services/gemini_service.py
Gemini AI integration for evaluating free-text approach architecture submissions
and providing a sounding-board assistant for contestants.
Uses the current google.genai SDK (google-genai package).
"""

import os
import json
import asyncio
import logging
import time
import re
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

from config import GEMINI_API_KEY, GEMINI_MODEL

try:
    from google import genai
    from google.genai import types
except ImportError:
    import google.generativeai as genai
    types = None


def _get_client():
    """Return a configured Gemini client, raising clearly if key is missing."""
    key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
    if not key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GEMINI_API_KEY is not configured in the .env file."
        )

    if hasattr(genai, "Client"):
        return genai.Client(api_key=key)

    if hasattr(genai, "configure"):
        genai.configure(api_key=key)
        return genai

    raise RuntimeError("Unsupported google-generativeai package")


def _parse_json_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return json.loads(text)


def _call_gemini(client, prompt: str, response_mime_type: str = "application/json") -> str:
    """Call Gemini using whichever SDK is installed, with a single retry for 429 errors."""
    for attempt in range(2):
        try:
            if hasattr(client, "models") and hasattr(client.models, "generate_content"):
                response = client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type=response_mime_type
                    ),
                )
                return response.text.strip()

            if hasattr(client, "GenerativeModel"):
                model = client.GenerativeModel(GEMINI_MODEL)
                response = model.generate_content(prompt)
                return response.text.strip()

            raise RuntimeError("Unsupported Gemini SDK")
        except Exception as e:
            err_str = str(e)
            is_429 = "429" in err_str or "Quota" in err_str or getattr(e, "code", None) == 429
            if attempt == 0 and is_429:
                delay = 10.0
                retry_match = re.search(r"retryDelay[\"']?\s*:\s*[\"']?([\d.]+)s?", err_str, re.IGNORECASE)
                if retry_match:
                    try:
                        delay = float(retry_match.group(1))
                    except ValueError:
                        pass
                logger.warning(f"Gemini API returned 429 rate limit. Retrying after sleeping {delay}s in worker thread.")
                time.sleep(delay)
                continue
            if is_429:
                raise HTTPException(status_code=429, detail="Gemini API rate limit exceeded. Please try again later.")
            raise


def _parse_constraints_list(raw_constraints) -> list[str]:
    if not raw_constraints:
        return []
    if isinstance(raw_constraints, list):
        return raw_constraints
    if isinstance(raw_constraints, str):
        try:
            parsed = json.loads(raw_constraints)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


async def evaluate_submission_with_gemini(
    approach_text: str,
    challenge,
    chat_transcript: str = "(no chat messages)",
    official_solution_content: str = "",
    hypothesis_content: str = "(no hypothesis provided)",
    is_late: bool = False,
    elapsed_minutes: float = 0.0,
) -> dict:
    """
    Build an evaluation prompt for an Approach Mode submission, call Gemini,
    and parse the structured JSON response.
    Returns the evaluation dict.
    """
    client = _get_client()

    time_limit = getattr(challenge, "time_limit", 45) or 45
    late_note = (
        f"\nNote: this submission was completed {elapsed_minutes:.0f} minutes after the {time_limit}-minute limit — "
        f"factor this into your overall_feedback if relevant, but do not penalize numeric scores for lateness alone."
        if is_late
        else ""
    )

    constraints_list = _parse_constraints_list(getattr(challenge, "constraints", None))
    if constraints_list:
        constraints_formatted = "\n".join(f"{idx+1}. {c}" for idx, c in enumerate(constraints_list))
    else:
        constraints_formatted = "(no explicit constraints specified)"

    ref_notes = official_solution_content.strip() or challenge.official_solution or "No reference notes provided."

    prompt = f"""You are an expert software architect and grading agent for 1Code.
Evaluate the user's architectural approach write-up and return ONLY a JSON object — no markdown fences, no extra text.

### CHALLENGE CONTEXT
- Title: {challenge.title}
- Slug: {challenge.slug}
- Category: {getattr(challenge, 'category', 'General')}
- Difficulty: {challenge.difficulty}
- Scenario: {challenge.scenario or "No scenario provided."}{late_note}

### STATED REQUIREMENTS / CONSTRAINTS
{constraints_formatted}

### REFERENCE APPROACH NOTES (Grading calibration context — one possible valid approach, not the only correct answer. Do not penalize taking a different valid route):
{ref_notes}

### USER'S INITIAL HYPOTHESIS / FRAMING (written before developing full approach)
{hypothesis_content}

### USER'S SUBMITTED ARCHITECTURAL APPROACH
{approach_text if approach_text.strip() else "(No approach write-up provided)"}

### AI Sounding-Board Discussion Transcript:
{chat_transcript}

### SCORING RUBRIC (Total 100 marks)
1. optimization      — max 25 marks  (how efficient and well-optimized the proposed architecture is against each stated constraint)
2. open_source_usage — max 25 marks  (appropriate, specific selection and integration of real open-source tools, libraries, or models)
3. topic_knowledge   — max 25 marks  (demonstrated depth of domain understanding and architectural tradeoffs)
4. prompt_quality    — max 25 marks  (clarity, structure, coherence, and completeness of the write-up itself)

### REQUIRED JSON OUTPUT FORMAT
{{
  "optimization": <int 0-25>,
  "open_source_usage": <int 0-25>,
  "topic_knowledge": <int 0-25>,
  "prompt_quality": <int 0-25>,
  "total_score": <int 0-100>,
  "strengths": ["<strength 1>", "<strength 2>"],
  "improvements": ["<improvement 1>", "<improvement 2>"],
  "overall_feedback": "<2-4 sentence summary of evaluation>"
}}"""

    try:
        start_time = time.perf_counter()
        logger.info(f"Starting Gemini approach evaluation request (prompt length: {len(prompt)})...")
        text = await asyncio.to_thread(_call_gemini, client, prompt)
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(f"Gemini evaluation call completed in {duration_ms:.2f} ms")

        result = _parse_json_response(text)

    except json.JSONDecodeError as je:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini returned invalid JSON: {je}. Raw: {text[:500]}"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini API error: {str(e)}"
        )

    int_keys = ["optimization", "open_source_usage", "topic_knowledge", "prompt_quality", "total_score"]
    list_keys = ["strengths", "improvements"]

    for k in int_keys:
        result.setdefault(k, 0)
        result[k] = int(result[k])

    for k in list_keys:
        if not isinstance(result.get(k), list):
            result[k] = []

    result.setdefault("overall_feedback", "No feedback provided.")
    return result


async def chat_with_gemini(
    scenario: str,
    current_approach: str,
    message: str,
    constraints: list[str] | None = None,
    history: list[dict] | None = None,
) -> str:
    """
    Helper Gemini call using a discussion/sounding-board partner persona.
    Helps the contestant think through tradeoffs and constraints without writing their solution for them.
    Returns a plain-text reply string.
    """
    client = _get_client()

    approach_preview = current_approach[:3000] + "\n...(truncated)" if len(current_approach) > 3000 else current_approach

    constraints_text = ""
    if constraints:
        constraints_text = "\nCONSTRAINTS TO CONSIDER:\n" + "\n".join(f"- {c}" for c in constraints)

    history_text = ""
    if history:
        turns = [f"{'User' if h['role'] == 'user' else 'Assistant'}: {h['content']}" for h in history[-10:]]
        history_text = "\n\nPrevious conversation:\n" + "\n".join(turns)

    prompt = f"""You are a helpful software architecture sounding board and technical mentor for 1Code contestants.
The contestant is working on an architectural approach challenge:

SCENARIO:
{scenario}{constraints_text}

THEIR CURRENT DRAFT APPROACH:
{approach_preview if approach_preview.strip() else "(No approach written yet)"}
{history_text}

Current contestant message: {message}

Respond as an expert systems architect and sounding-board partner:
- Ask clarifying questions about their proposed components or tradeoffs.
- Discuss relevant open-source libraries, frameworks, or design patterns they might consider.
- Do NOT write out the full approach solution for them. Guide them to refine and detail their own plan.
Keep your response concise, conversational, and constructive. Plain text only, no markdown formatting."""

    try:
        start_time = time.perf_counter()
        logger.info(f"Starting Gemini architecture chat request (message length: {len(message)})...")
        reply = await asyncio.to_thread(_call_gemini, client, prompt, response_mime_type="text/plain")
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(f"Gemini chat call completed in {duration_ms:.2f} ms")
        return reply
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini chat error: {str(e)}"
        )
