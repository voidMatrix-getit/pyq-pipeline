"""utils.py — shared helpers for RRB pipeline"""

import re
from pathlib import Path

COLUMNS = [
    "No", "Section", "Sub-Section", "Question",
    "Option1", "Option2", "Option3", "Option4",
    "Correct Answer", "Explanation", "Difficulty"
]
HEADER = "|".join(COLUMNS)

# ── FILE I/O ──────────────────────────────────────────────────────────────────

def load_pipe_text(filepath: str) -> list[str]:
    """Return non-empty, non-header lines from a pipe-separated file."""
    p = Path(filepath)
    if not p.exists():
        raise FileNotFoundError(f"Input file not found: {filepath}")
    lines = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        # skip header row
        if line.lower().startswith("no|") or line.lower().startswith("no |"):
            continue
        lines.append(line)
    return lines

def save_pipe_text(filepath, lines: list[str]):
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    content = HEADER + "\n" + "\n".join(lines)
    Path(filepath).write_text(content, encoding="utf-8")

def merge_pipe_lines(batches: list[list[str]]) -> list[str]:
    merged = []
    for b in batches:
        merged.extend(b)
    return merged

# ── BATCH SPLIT ───────────────────────────────────────────────────────────────

def split_into_batches(lines: list[str], size: int) -> list[list[str]]:
    return [lines[i:i+size] for i in range(0, len(lines), size)]

# ── PIPE PARSING ─────────────────────────────────────────────────────────────

def parse_pipe_line(line: str) -> dict | None:
    """Parse a pipe-separated line into dict. Returns None if malformed."""
    parts = [p.strip() for p in line.split("|")]
    if len(parts) != 11:
        return None
    return dict(zip(COLUMNS, parts))

def serialize_row(row: dict) -> str:
    return "|".join(row.get(c, "") for c in COLUMNS)

# ── EXTRACT PIPE LINES FROM LLM RESPONSE ─────────────────────────────────────

def extract_pipe_lines(text: str) -> list[str]:
    """
    Pull out valid 11-column pipe lines from raw LLM output.
    Strips markdown fences, stray prose, partial lines.
    """
    lines = text.splitlines()
    valid = []
    for line in lines:
        line = line.strip()
        # skip headers / fences / empty
        if not line or line.startswith("```") or line.startswith("#"):
            continue
        if line.lower().startswith("no|") or line.lower().startswith("no |"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) == 11:
            # basic sanity: col 0 should be a number
            if parts[0].isdigit() or re.match(r"^\d+$", parts[0]):
                valid.append("|".join(parts))
    return valid

# ── RENUMBER LINES ────────────────────────────────────────────────────────────

def renumber(lines: list[str], start: int = 1) -> list[str]:
    result = []
    for i, line in enumerate(lines, start):
        parts = line.split("|")
        if len(parts) == 11:
            parts[0] = str(i)
            result.append("|".join(parts))
        else:
            result.append(line)
    return result