"""
validate_input.py  —  Validates questions_raw.txt before running the pipeline.
Checks: column count, empty fields, duplicate numbers, KaTeX, Correct Answer match.
Run: python validate_input.py
     python validate_input.py --fix    (auto-fix minor issues and save)
"""

import re
import sys
import argparse
from pathlib import Path

INPUT_FILE = Path("input/questions_raw.txt")
COLUMNS    = ["No","Section","Sub-Section","Question",
              "Answer 1","Answer 2","Answer 3","Answer 4",
              "Correct Answer","Explanation","Difficulty"]
VALID_SECTIONS = {
    "गणित",
    "सामान्य बुद्धिमत्ता और तर्क",
    "सामान्य जागरूकता"
}
VALID_DIFFICULTY = {"Easy", "Medium", "Hard"}
VALID_CORRECT    = {"1", "2", "3", "4", "UNCERTAIN"}

RED  = "\033[91m"
GRN  = "\033[92m"
YLW  = "\033[93m"
RST  = "\033[0m"
BLD  = "\033[1m"

errors   = []
warnings = []

def err(line_no, msg):
    errors.append((line_no, msg))

def warn(line_no, msg):
    warnings.append((line_no, msg))


def check_katex_numbers(text: str) -> list[str]:
    """Find bare numbers/% outside $...$"""
    # Remove existing KaTeX spans
    clean = re.sub(r'\$[^$]+\$', '', text)
    issues = []
    # Bare percentage
    if re.search(r'\d+\s*%', clean):
        issues.append("bare % (should be $...\\%$)")
    # Bare fractions written as a/b
    if re.search(r'\b\d+/\d+\b', clean):
        issues.append("bare fraction (should use $\\frac{}{}$)")
    # Bare Rs. amounts
    if re.search(r'Rs\.\s*\d+', clean):
        issues.append("bare Rs. amount (should be $Rs.\\,\\d+$)")
    return issues


def validate(lines: list[str], fix: bool = False) -> list[str]:
    fixed_lines = []
    seen_numbers = {}

    for i, line in enumerate(lines, 1):
        line = line.rstrip()
        if not line:
            warn(i, "Empty line skipped")
            continue

        parts = [p.strip() for p in line.split("|")]

        # ── Column count ──────────────────────────────────────────────────
        if len(parts) != 11:
            err(i, f"Column count = {len(parts)} (expected 11). Line: {line[:80]}")
            fixed_lines.append(line)
            continue

        row = dict(zip(COLUMNS, parts))

        # ── Serial number ─────────────────────────────────────────────────
        no = row["No"].strip()
        if not no.isdigit():
            err(i, f"'No' column is not a number: '{no}'")
        else:
            n = int(no)
            if n in seen_numbers:
                err(i, f"Duplicate question number {n} (first seen on input line {seen_numbers[n]})")
            seen_numbers[n] = i

        # ── Empty fields ──────────────────────────────────────────────────
        for col in COLUMNS:
            if not row.get(col, "").strip():
                err(i, f"Empty field: '{col}'")

        # ── Section ───────────────────────────────────────────────────────
        sec = row.get("Section", "").strip()
        if sec and sec not in VALID_SECTIONS:
            warn(i, f"Unusual section: '{sec}'. Expected one of: {', '.join(sorted(VALID_SECTIONS))}")

        # ── Difficulty ────────────────────────────────────────────────────
        diff = row.get("Difficulty", "").strip()
        if diff and diff not in VALID_DIFFICULTY:
            warn(i, f"Invalid Difficulty: '{diff}'. Must be Easy/Medium/Hard")
            if fix:
                row["Difficulty"] = "Medium"

        # ── Correct Answer must be 1/2/3/4/UNCERTAIN ─────────────────────
        ca = row.get("Correct Answer", "").strip()
        if ca and ca.upper() not in VALID_CORRECT:
            warn(i, f"Correct Answer must be 1/2/3/4/UNCERTAIN — got: '{ca}'")

        # ── KaTeX check ───────────────────────────────────────────────────
        for col in ["Question", "Option1", "Option2", "Option3", "Option4",
                    "Explanation"]:
            issues = check_katex_numbers(row.get(col, ""))
            for issue in issues:
                warn(i, f"KaTeX issue in '{col}': {issue}")

        # Rebuild fixed line
        fixed_lines.append("|".join(row[c] for c in COLUMNS))

    return fixed_lines


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fix",   action="store_true", help="Auto-fix minor issues")
    parser.add_argument("--input", default=str(INPUT_FILE), help="Input file path")
    args = parser.parse_args()

    fpath = Path(args.input)
    if not fpath.exists():
        print(f"{RED}File not found: {fpath}{RST}")
        sys.exit(1)

    # Use the shared loader which correctly strips headers
    sys.path.insert(0, str(Path(__file__).parent))
    from scripts.utils import load_pipe_text
    try:
        data_lines = load_pipe_text(str(fpath))
    except Exception as e:
        print(f"{RED}{e}{RST}")
        sys.exit(1)

    print(f"\n{BLD}RRB Input Validator{RST}")
    print(f"  File   : {fpath}")
    print(f"  Lines  : {len(data_lines)}")
    print()

    fixed = validate(data_lines, fix=args.fix)

    # Summary
    if errors:
        print(f"{RED}ERRORS ({len(errors)}):{RST}")
        for line_no, msg in errors:
            print(f"  {RED}✗{RST}  Line {line_no:>4}: {msg}")
    else:
        print(f"{GRN}✓ No errors found{RST}")

    if warnings:
        print(f"\n{YLW}WARNINGS ({len(warnings)}):{RST}")
        for line_no, msg in warnings:
            print(f"  {YLW}⚠{RST}  Line {line_no:>4}: {msg}")
    else:
        print(f"{GRN}✓ No warnings{RST}")

    # Stats
    uncertain_count = sum(1 for l in data_lines
                          if "UNCERTAIN" in l.upper().split("|")[8] if "|" in l)
    print(f"\n  UNCERTAIN answers : {uncertain_count}")
    print(f"  Total questions   : {len(data_lines)}")

    if args.fix and not errors:
        header = "|".join(COLUMNS)
        out    = header + "\n" + "\n".join(fixed)
        fpath.write_text(out, encoding="utf-8")
        print(f"\n{GRN}✓ Fixed file saved → {fpath}{RST}")

    if errors:
        print(f"\n{RED}Fix errors above before running the pipeline.{RST}")
        sys.exit(1)
    else:
        print(f"\n{GRN}Input is ready for pipeline.{RST}")

if __name__ == "__main__":
    main()