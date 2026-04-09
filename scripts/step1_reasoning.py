"""
step1_reasoning.py
Input  : 10 raw pipe-separated question lines (from Claude OCR)
Model  : qwen3:14b  (Ollama local)
Output : 10 corrected + evaluated pipe-separated lines
"""

import json
import logging
import requests
from scripts.utils import extract_pipe_lines, HEADER

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a technical content editor for a competitive exam platform.
Your task is to format questions and explanations for maximum compatibility with a KaTeX-enabled Markdown renderer.

Formatting Rules:

Strict KaTeX Usage:
Enclose all numbers, mathematical operators ($+$, $-$, $\\times$, $\\div$, $=$, $>$, $<$), variables ($x$, $y$, $z$, $M$, $N$), and geometric symbols ($\\angle$, $\\triangle$, $^\\circ$) inside single dollar signs: $...$.

Zero Gap Policy:
There must be NO space between the dollar signs and the characters inside.
Correct: $x+y=10$
Incorrect: $ x + y = 10 $

Plain Text Handling:
Do NOT use KaTeX for simple prose.
Keep punctuation (commas, periods, parentheses) outside KaTeX unless part of a mathematical structure.

Currency/Symbols:
Use standard characters for currency in plain text except ₹ which must be written as $\\text{Rs.}$.
Do NOT use backslashes to escape currency symbols.

Line Breaks:
Use the <br> tag for every line break in Explanation.
MUST USE IT WHEREVER REQUIRED.
Never allow <br> inside a $...$ block.

Tables (MANDATORY FORMAT):
If a table exists, use the following inline overflow format:
<div style="width:100%;overflow-x:auto;"><table style="border-collapse:collapse;min-width:700px;width:max-content;"><tr><td style="border:1px solid #000;padding:6px;text-align:center;font-weight:bold;">...</td></tr></table></div>
The entire table block must remain inline and must not break across lines.
Every numerical value or variable inside a table cell must be wrapped in $...$."""

USER_TEMPLATE = """TASK: Validate AND CORRECT the given RRB NTPC Graduate Level PYQs (Hindi Medium). Fix ALL errors and output ONLY the corrected pipe-separated format.

FORMAT: Exactly 11 columns with " | " (space-pipe-space) separator:
No | Section | Sub-Section | Question | Answer 1 | Answer 2 | Answer 3 | Answer 4 | Correct Answer | Explanation | Difficulty

VALIDATION CHECKLIST (FIX ALL ISSUES):

FORMAT CHECK:
- Exactly 11 columns, pipe separator MUST be exactly " | " (space-pipe-space)
- One question per line only
- {{Image}} placeholders must be correctly placed where diagrams/figures exist

SECTION & SYLLABUS ACCURACY:
Section MUST be exactly one of: गणित | सामान्य बुद्धिमत्ता और तर्क | सामान्य जागरूकता
Sub-Section MUST match the closest topic from the official Hindi RRB NTPC Graduate Level syllabus.
Section and Sub-Section names MUST be written in Hindi only.
Question text must be complete, meaningful, and EXACTLY as given in Hindi.
Do NOT translate, rephrase, summarise, or rewrite Hindi question text or answer options.

ANSWER OPTIONS CHECK:
- Exactly 4 answer options must be present
- No duplicated or missing options
- Option numbering (1., 2., 3., 4.) must NOT appear inside the pipe-separated output

KATEX STRICT CHECK (MANDATORY):
EVERY mathematical expression, number, operator, Greek letter, scientific symbol, unit, currency sign, subscript/superscript, or non-ASCII character MUST be written in KaTeX using inline $...$ with NO spaces inside.
Fix examples: $x^ 2$ → $x^2$ | H₂O → $H_2O$ | ½ → $\\frac{{1}}{{2}}$ | π → $\\pi$ | ₹ → $\\text{{Rs.}}$

CONTENT ACCURACY CHECK:
- Independently verify every question
- Do NOT trust the given correct answer blindly
- If mathematically incorrect → mark Correct Answer as UNCERTAIN
- Correct Answer must be ONLY 1 / 2 / 3 / 4 / UNCERTAIN

EXPLANATION QUALITY (HINDI):
- Written in clear student-friendly Hindi for RRB NTPC aspirants
- Use KaTeX for EVERY symbol, number, formula, unit, percentage, currency
- Fix incorrect, vague, or incomplete explanations
- Use <br> wherever line breaks are required
- Do NOT include option numbers in explanation

DIFFICULTY: Assign exactly one of: Easy | Medium | Hard

RRB NTPC SECTIONS REFERENCE (HINDI):
गणित: संख्या पद्धति, दशमलव, भिन्न, लघुत्तम समापवर्त्य, महत्तम समापवर्तक, अनुपात और समानुपात, प्रतिशत, क्षेत्रमिति, समय और कार्य, समय और दूरी, साधारण और चक्रवृद्धि ब्याज, लाभ और हानि, प्रारंभिक बीजगणित, ज्यामिति और त्रिकोणमिति, प्रारंभिक सांख्यिकी
सामान्य बुद्धिमत्ता और तर्क: सादृश्यता, संख्या एवं वर्णमाला श्रृंखला, कोडिंग और डिकोडिंग, गणितीय संक्रियाएं, समानताएं और अंतर, संबंध, विश्लेषणात्मक तर्क, न्यायवाक्य, जंबलिंग, वेन आरेख, पहेली, डेटा पर्याप्तता, कथन–निष्कर्ष, निर्णय लेना, मानचित्र, ग्राफ एवं आंकड़ों की व्याख्या
सामान्य जागरूकता: राष्ट्रीय एवं अंतर्राष्ट्रीय महत्व की समसामयिक घटनाएं, खेल एवं क्रीड़ा, भारत एवं विश्व की कला और संस्कृति, भारतीय साहित्य, भारत के स्मारक और ऐतिहासिक स्थल, सामान्य विज्ञान एवं जीवन विज्ञान, भारत का इतिहास एवं स्वतंत्रता संग्राम, भारत एवं विश्व का भौतिक/सामाजिक/आर्थिक भूगोल, भारतीय राजनीति एवं शासन, सामान्य वैज्ञानिक एवं तकनीकी विकास, संयुक्त राष्ट्र एवं अन्य महत्वपूर्ण विश्व संगठन, पर्यावरण संबंधी मुद्दे, कंप्यूटर एवं कंप्यूटर अनुप्रयोगों की मूल बातें, भारतीय अर्थव्यवस्था, प्रसिद्ध हस्तियाँ, प्रमुख सरकारी कार्यक्रम

OUTPUT RULE (ABSOLUTE):
- Output ONLY the corrected questions in pipe-separated format
- One question per line
- Inside a single grey code block
- NO extra text, NO reports, NO commentary
- Do NOT rephrase question text or answer options

Input questions ({n} total):
{questions}"""


def call_ollama(prompt: str, model: str, base_url: str, temperature: float = 0.1) -> str:
    url = f"{base_url}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_ctx": 8192,
            "num_predict": 4096,
            "top_p": 0.9,
        }
    }
    try:
        resp = requests.post(url, json=payload, timeout=300)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "")
    except requests.exceptions.Timeout:
        log.error("Ollama timeout for step1")
        return ""
    except requests.exceptions.ConnectionError:
        log.error("Cannot connect to Ollama. Is it running? → ollama serve")
        return ""
    except Exception as e:
        log.error(f"Ollama error (step1): {e}")
        return ""


def run_reasoning_batch(
    lines: list[str],
    model: str,
    base_url: str,
    batch_num: int = 0
) -> list[str]:
    """
    Send a batch of raw pipe lines to Qwen3 for reasoning + evaluation.
    Returns corrected pipe lines (same count if all valid, else padded/trimmed).
    """
    questions_text = "\n".join(lines)
    prompt = USER_TEMPLATE.format(n=len(lines), questions=questions_text)

    raw_response = call_ollama(prompt, model, base_url)

    if not raw_response.strip():
        log.warning(f"[Batch {batch_num}] Empty response from {model} – returning originals")
        return lines

    extracted = extract_pipe_lines(raw_response)

    if not extracted:
        log.warning(f"[Batch {batch_num}] No valid pipe lines extracted. Raw preview:\n{raw_response[:300]}")
        return lines

    if len(extracted) != len(lines):
        log.warning(
            f"[Batch {batch_num}] Count mismatch: input={len(lines)}, extracted={len(extracted)}. "
            "Using what we have."
        )

    log.debug(f"[Batch {batch_num}] Reasoning complete: {len(extracted)} lines")
    return extracted