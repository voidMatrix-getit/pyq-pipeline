"""
ocr_prompt.py
Generates the exact Claude prompt to paste when doing manual OCR.
Run: python ocr_prompt.py
Copies prompt to clipboard (Windows) and prints it.
"""

import subprocess
import sys

SYSTEM_PROMPT = """You are a strict OCR and question formatter for RRB NTPC exam question banks (Hindi Medium).

TASK: Extract questions from the uploaded image/PDF and output them in EXACT pipe-separated format.

OUTPUT FORMAT (mandatory, 11 columns, " | " space-pipe-space separator):
No | Section | Sub-Section | Question | Answer 1 | Answer 2 | Answer 3 | Answer 4 | Correct Answer | Explanation | Difficulty

COLUMN RULES:
- No            : Serial number (1, 2, 3...)
- Section       : MUST be exactly one of (in Hindi): गणित | सामान्य बुद्धिमत्ता और तर्क | सामान्य जागरूकता
- Sub-Section   : Closest matching topic from RRB NTPC syllabus — written in Hindi
- Question      : EXACT question text in Hindi — do NOT rephrase, translate, or simplify
- Answer 1–4    : All 4 answer options exactly as printed
- Correct Answer: Write ONLY 1 / 2 / 3 / 4 (matching the correct option number), OR write UNCERTAIN if answer not printed
- Explanation   : Hindi explanation. For math: show key steps. Use $...$ for all numbers/symbols/%. Use <br> for line breaks.
- Difficulty    : Easy / Medium / Hard

KATEX RULES (strictly enforce):
- ALL numbers, %, fractions, equations, units, symbols → inside $...$
- NO spaces inside $...$
- Examples: $25\\%$  $\\frac{1}{2}$  $x^2+y^2$  $\\sqrt{16}$  $\\text{Rs.}1200$  $H_2O$
- Use $\\text{Rs.}$ for the rupee symbol
- Use <br> for line breaks in Explanation — NEVER inside $...$

RRB NTPC SECTIONS (HINDI):
गणित: संख्या पद्धति, दशमलव, भिन्न, लघुत्तम समापवर्त्य, महत्तम समापवर्तक, अनुपात और समानुपात, प्रतिशत, क्षेत्रमिति, समय और कार्य, समय और दूरी, साधारण और चक्रवृद्धि ब्याज, लाभ और हानि, प्रारंभिक बीजगणित, ज्यामिति और त्रिकोणमिति, प्रारंभिक सांख्यिकी
सामान्य बुद्धिमत्ता और तर्क: सादृश्यता, संख्या एवं वर्णमाला श्रृंखला, कोडिंग और डिकोडिंग, गणितीय संक्रियाएं, वेन आरेख, पहेली, कथन-निष्कर्ष, निर्णय लेना, मानचित्र, ग्राफ
सामान्य जागरूकता: इतिहास, भूगोल, राजनीति, विज्ञान, अर्थव्यवस्था, खेल, कला एवं संस्कृति, समसामयिक घटनाएं, कंप्यूटर

STRICT RULES:
1. Output ONLY pipe-separated lines — no headers, no markdown, no commentary
2. One question per line
3. Correct Answer must be ONLY 1 / 2 / 3 / 4 / UNCERTAIN — never write option text
4. If question has a figure/diagram → write {Image} in the Question field where the image appears
5. Do not invent or guess options

START OUTPUT WITH LINE 1 DIRECTLY."""

BATCH_INSTRUCTION = """---
BATCH INSTRUCTION (tell Claude which batch):
"Extract questions {start} to {end} from this image in the pipe format above."
---"""

def main():
    print("=" * 70)
    print("CLAUDE OCR — SYSTEM PROMPT")
    print("=" * 70)
    print(SYSTEM_PROMPT)
    print()
    print("=" * 70)
    print("BATCH USAGE EXAMPLES:")
    print("=" * 70)
    for start, end in [(1,10),(11,20),(21,30),(31,40),(41,50),
                       (51,60),(61,70),(71,80),(81,90),(91,100)]:
        print(f'  "Extract questions {start} to {end} from this image in the pipe format above."')

    print()
    print("=" * 70)
    print("PASTE THIS INTO CLAUDE:")
    print("=" * 70)

    combined = SYSTEM_PROMPT + "\n\n" + \
        "Extract questions 1 to 10 from the uploaded image in the pipe format above."

    # Try to copy to clipboard (Windows)
    try:
        subprocess.run("clip", input=combined.encode("utf-8"),
                       check=True, capture_output=True)
        print("✅ Prompt copied to clipboard (Windows clip)")
    except Exception:
        try:
            subprocess.run(["xclip", "-selection", "clipboard"],
                           input=combined.encode("utf-8"),
                           check=True, capture_output=True)
            print("✅ Prompt copied to clipboard (xclip)")
        except Exception:
            print("⚠️  Could not copy to clipboard — copy manually above.")

if __name__ == "__main__":
    main()