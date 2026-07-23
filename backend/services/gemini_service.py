"""
services/gemini_service.py
Gemini AI integration for extracting, reading, and evaluating challenge submissions.
Uses the current google.genai SDK (google-genai package).
"""

import os
import json
import zipfile
import shutil
from pathlib import Path
from fastapi import HTTPException, status

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


import time
import re

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
                time.sleep(delay)
                continue
            if is_429:
                raise HTTPException(status_code=429, detail="Gemini API rate limit exceeded. Please try again later.")
            raise


def extract_zip(zip_path: Path) -> Path:
    """Extract a ZIP archive into an 'extracted' sub-directory and return its path."""
    extract_to = zip_path.parent / "extracted"
    extract_to.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_to)
    return extract_to


def cleanup_extracted(extract_dir: Path):
    """Delete the temporary extracted directory."""
    if extract_dir and extract_dir.exists() and extract_dir.is_dir():
        shutil.rmtree(extract_dir)


def read_source_files(directory: Path) -> str:
    """Recursively read all UTF-8 text files, skipping binaries and build folders."""
    EXCLUDE_DIRS = {"node_modules", ".git", "__pycache__", "venv", ".venv", "dist", "build"}
    EXCLUDE_EXT  = {".zip", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf",
                    ".gz", ".tar", ".bin", ".exe", ".lock"}

    parts = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in EXCLUDE_EXT:
            continue
        try:
            content = path.read_text(encoding="utf-8")
            rel = path.relative_to(directory).as_posix()
            parts.append(f"File: {rel}\n{'-'*40}\n{content}\n{'='*40}\n")
        except (UnicodeDecodeError, PermissionError):
            continue  # skip binary / unreadable files

    return "\n".join(parts) if parts else "(no readable source files found)"


def read_official_solution(challenge) -> str:
    return challenge.official_solution or "No official solution reference is available for this challenge."


async def evaluate_submission_with_gemini(
    submission,
    challenge,
    db_log_content: str,
    user_code_content: str,
    official_solution_content: str,
    hypothesis_content: str = "(no hypothesis provided)",
    is_late: bool = False,
    elapsed_minutes: float = 0.0,
) -> dict:
    """
    Build an evaluation prompt, call Gemini, and parse the structured JSON response.
    Returns the evaluation dict.
    """
    client = _get_client()

    time_limit = getattr(challenge, "time_limit", 45) or 45
    late_note = (
        f"\nNote: this submission was completed {elapsed_minutes:.0f} minutes after the {time_limit}-minute limit — "
        f"factor this into your overall_feedback if relevant, but do not penalize the numeric scores for lateness alone."
        if is_late
        else ""
    )

    prompt = f"""
You are an expert AI code reviewer and grading agent for 1Code, an AI-native debugging platform.
Evaluate the user's submission and return ONLY a JSON object — no markdown, no extra text.

### CHALLENGE CONTEXT
- Title: {challenge.title}
- Slug: {challenge.slug}
- Difficulty: {challenge.difficulty}
- Scenario: {challenge.scenario or "No description provided."}{late_note}

### OFFICIAL SOLUTION (expected correct code)
{official_solution_content}

### USER'S INITIAL HYPOTHESIS (written before seeing any code)
{hypothesis_content}

### USER'S FIXED PROJECT SOURCE CODE
{user_code_content}

### USER'S DEBUG LOG (debug_log.txt)
{db_log_content}

### SCORING RUBRIC (Total 100 marks)
1. hypothesis      — max 20 marks  (quality of initial hypotheses before viewing code)
2. prompt_quality  — max 25 marks  (clarity, context, and structure of AI prompts)
3. ai_collaboration— max 20 marks  (how well the user guided and verified AI responses)
4. code_correctness— max 25 marks  (final fix compared to official solution)
5. problem_solving — max 10 marks  (root cause identification and verification steps)

### REQUIRED JSON OUTPUT FORMAT
{{
  "hypothesis": <int 0-20>,
  "prompt_quality": <int 0-25>,
  "ai_collaboration": <int 0-20>,
  "code_correctness": <int 0-25>,
  "problem_solving": <int 0-10>,
  "total_score": <int 0-100>,
  "strengths": ["<strength 1>", "<strength 2>"],
  "improvements": ["<improvement 1>", "<improvement 2>"],
  "overall_feedback": "<2-4 sentence summary>"
}}
"""

    try:
        text = _call_gemini(client, prompt)
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

    # Ensure all required keys exist with safe defaults
    int_keys   = ["hypothesis", "prompt_quality", "ai_collaboration",
                   "code_correctness", "problem_solving", "total_score"]
    list_keys  = ["strengths", "improvements"]

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
    current_code: str,
    message: str,
) -> str:
    """
    Helper (non-grading) Gemini call using a pairing-partner persona.
    Guides the user through debugging without handing them the full solution.
    Returns a plain-text reply string.
    """
    client = _get_client()

    # Truncate code context to avoid token limits while still being useful
    code_preview = current_code[:3000] + "\n...(truncated)" if len(current_code) > 3000 else current_code

    prompt = f"""You are a helpful coding assistant and expert debugging partner for 1Code.
The user is working on the following challenge:

SCENARIO:
{scenario}

THEIR CURRENT CODE:
{code_preview if code_preview.strip() else "(No code written yet)"}

USER MESSAGE:
{message}

Respond as a real pairing partner would: ask clarifying questions, suggest what to look for,
explain concepts clearly. Do NOT hand them the complete fixed solution outright — guide them
to find and understand the issue themselves. Keep your response concise and conversational.
Plain text only, no markdown formatting."""

    try:
        reply = _call_gemini(client, prompt, response_mime_type="text/plain")
        return reply
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini chat error: {str(e)}"
        )
