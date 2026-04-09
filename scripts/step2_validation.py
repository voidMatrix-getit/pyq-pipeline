"""
step2_validation.py
Input  : 10 pipe-separated lines from Step 1 (Qwen3 output)
Model  : gemma3:12b  (Ollama local) — good at fact-checking, logic verification
Output : 10 verified pipe-separated lines (UNCERTAIN resolved or flagged)
"""

import logging
import requests
from scripts.utils import extract_pipe_lines, parse_pipe_line, serialize_row, COLUMNS

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior fact-checker and answer validator for RRB NTPC Graduate Level exam questions (Hindi Medium).

YOUR TASKS:
1. Verify each Correct Answer (1/2/3/4) against its Explanation logically.
2. If Correct Answer = UNCERTAIN → resolve it. If still unclear after reasoning, keep UNCERTAIN.
3. Check completeness: Question, all 4 Answer options, Correct Answer, Explanation must be non-empty.
4. Verify Explanation fully supports the marked Correct Answer. Fix mismatches.
5. KaTeX check: All math, numbers, %, symbols must use $...$. No spaces inside $...$. Fix if broken.
6. Explanation must be in Hindi. Use <br> for line breaks in Explanation. Never <br> inside $...$.
7. Do NOT rephrase, translate, or rewrite question text or answer options.
8. Section must be one of: गणित | सामान्य बुद्धिमत्ता और तर्क | सामान्य जागरूकता

OUTPUT RULES:
- Output ONLY pipe-separated lines. NO prose, NO markdown, NO headers, NO commentary.
- Exactly 11 columns with " | " (space-pipe-space) separator:
  No | Section | Sub-Section | Question | Answer 1 | Answer 2 | Answer 3 | Answer 4 | Correct Answer | Explanation | Difficulty
- Correct Answer column: ONLY 1 / 2 / 3 / 4 / UNCERTAIN
- One line per question, no blank lines."""

USER_TEMPLATE = """Validate and verify the following {n} RRB NTPC questions.
Resolve UNCERTAIN answers where possible. Fix explanation-answer mismatches. Fix broken KaTeX.

{questions}"""


def call_ollama(prompt: str, model: str, base_url: str) -> str:
    url = f"{base_url}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "options": {
            "temperature": 0.05,   # near-deterministic for validation
            "num_ctx": 8192,
            "num_predict": 4096,
        }
    }
    try:
        resp = requests.post(url, json=payload, timeout=300)
        resp.raise_for_status()
        return resp.json().get("response", "")
    except requests.exceptions.Timeout:
        log.error("Ollama timeout for step2")
        return ""
    except requests.exceptions.ConnectionError:
        log.error("Cannot connect to Ollama.")
        return ""
    except Exception as e:
        log.error(f"Ollama error (step2): {e}")
        return ""


def audit_uncertain(lines: list[str]) -> dict:
    """Return summary of UNCERTAIN and empty-field issues."""
    issues = {"uncertain": [], "incomplete": []}
    for i, line in enumerate(lines, 1):
        row = parse_pipe_line(line)
        if row is None:
            issues["incomplete"].append(i)
            continue
        ca = row.get("Correct Answer", "").strip().upper()
        if ca == "UNCERTAIN":
            issues["uncertain"].append(i)
        # check for invalid correct answer values
        if ca not in ("1", "2", "3", "4", "UNCERTAIN", ""):
            issues["incomplete"].append(i)
        missing = [c for c in COLUMNS if not row.get(c, "").strip()]
        if missing:
            issues["incomplete"].append(i)
    return issues


def run_validation_batch(
    lines: list[str],
    model: str,
    base_url: str,
    batch_num: int = 0
) -> list[str]:
    questions_text = "\n".join(lines)
    prompt = USER_TEMPLATE.format(n=len(lines), questions=questions_text)

    raw_response = call_ollama(prompt, model, base_url)

    if not raw_response.strip():
        log.warning(f"[Batch {batch_num}] Empty validation response – returning step1 output")
        return lines

    extracted = extract_pipe_lines(raw_response)

    if not extracted:
        log.warning(f"[Batch {batch_num}] No valid pipe lines from validator. Returning step1 output.")
        return lines

    if len(extracted) != len(lines):
        log.warning(
            f"[Batch {batch_num}] Validation count mismatch: "
            f"input={len(lines)}, output={len(extracted)}"
        )

    # Audit
    audit = audit_uncertain(extracted)
    if audit["uncertain"]:
        log.warning(f"[Batch {batch_num}] Still UNCERTAIN at positions: {audit['uncertain']}")
    if audit["incomplete"]:
        log.warning(f"[Batch {batch_num}] Incomplete rows: {audit['incomplete']}")

    log.debug(f"[Batch {batch_num}] Validation complete: {len(extracted)} lines")
    return extracted