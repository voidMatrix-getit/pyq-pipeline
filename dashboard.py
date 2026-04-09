"""
dashboard.py  —  Live terminal status dashboard for the pipeline.
Shows batch progress, UNCERTAIN counts, model status, output file sizes.
Run: python dashboard.py          (auto-refreshes every 5s)
     python dashboard.py --once   (print once and exit)
"""

import json
import os
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

STATE_FILE  = Path("output/.pipeline_state.json")
OUTPUT_DIR  = Path("output")
INPUT_FILE  = Path("input/questions_raw.txt")
BATCH_SIZE  = 10

# ANSI colors
R   = "\033[91m"   # red
G   = "\033[92m"   # green
Y   = "\033[93m"   # yellow
B   = "\033[94m"   # blue
C   = "\033[96m"   # cyan
W   = "\033[97m"   # white bold
DIM = "\033[2m"
RST = "\033[0m"
CLS = "\033[2J\033[H"


def file_size(path: Path) -> str:
    if path.exists():
        sz = path.stat().st_size
        if sz > 1_000_000:
            return f"{sz/1_000_000:.1f} MB"
        return f"{sz/1_000:.0f} KB"
    return "—"


def count_uncertain(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines()
                   if "UNCERTAIN" in line.upper())
    except Exception:
        return 0


def ollama_status() -> tuple[bool, list[str]]:
    """Check if Ollama is running and which models are available."""
    try:
        import requests
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            return True, models
    except Exception:
        pass
    return False, []


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"batches": {}}


def total_questions() -> int:
    try:
        lines = [l for l in INPUT_FILE.read_text(encoding="utf-8").splitlines()
                 if l.strip() and not l.lower().startswith("no|")]
        return len(lines)
    except Exception:
        return 0


def render(once: bool = False):
    state       = load_state()
    total_q     = total_questions()
    num_batches = (total_q + BATCH_SIZE - 1) // BATCH_SIZE if total_q else 10
    batches     = state.get("batches", {})

    done_s1 = sum(1 for b in batches.values()
                  if b.get("step1", {}).get("status") == "done")
    done_s2 = sum(1 for b in batches.values()
                  if b.get("step2", {}).get("status") == "done")
    fail_s1 = sum(1 for b in batches.values()
                  if b.get("step1", {}).get("status") == "failed")
    fail_s2 = sum(1 for b in batches.values()
                  if b.get("step2", {}).get("status") == "failed")

    final_pipe = OUTPUT_DIR / "final_pipe.txt"
    docx_path  = OUTPUT_DIR / "RRB_NTPC_Questions.docx"
    xlsx_path  = OUTPUT_DIR / "RRB_NTPC_Questions.xlsx"
    uncertain  = count_uncertain(final_pipe)

    ollama_up, models = ollama_status()

    bar_width = 30

    def bar(done, total, color=G):
        filled = int(bar_width * done / total) if total else 0
        b = color + "█" * filled + DIM + "░" * (bar_width - filled) + RST
        return b

    def status_dot(s):
        if s == "done":   return G + "●" + RST
        if s == "failed": return R + "●" + RST
        return Y + "○" + RST

    now = datetime.now().strftime("%H:%M:%S")

    out = []
    out.append(f"{W}{'─'*62}{RST}")
    out.append(f"  {C}RRB NTPC Pipeline Dashboard{RST}  {DIM}{now}{RST}")
    out.append(f"{W}{'─'*62}{RST}")

    # Ollama status
    ollama_str = (G + "● Running" + RST) if ollama_up else (R + "● Offline" + RST)
    model_str  = "  " + ", ".join(models[:4]) if models else "  no models loaded"
    out.append(f"  Ollama : {ollama_str}")
    out.append(f"  Models :{DIM}{model_str}{RST}")

    out.append(f"  Questions in input : {W}{total_q}{RST}")
    out.append("")

    # Step 1
    pct1 = int(100 * done_s1 / num_batches) if num_batches else 0
    out.append(f"  Step 1  Reasoning   {bar(done_s1, num_batches)}  "
               f"{W}{done_s1:2d}/{num_batches}{RST} batches  {pct1}%"
               + (f"  {R}{fail_s1} failed{RST}" if fail_s1 else ""))

    # Step 2
    pct2 = int(100 * done_s2 / num_batches) if num_batches else 0
    out.append(f"  Step 2  Validation  {bar(done_s2, num_batches)}  "
               f"{W}{done_s2:2d}/{num_batches}{RST} batches  {pct2}%"
               + (f"  {R}{fail_s2} failed{RST}" if fail_s2 else ""))

    out.append("")
    out.append(f"  {'Batch':>6}  {'Step1':>10}  {'Step2':>10}  {'Timestamp':>20}")
    out.append(f"  {'─'*6}  {'─'*10}  {'─'*10}  {'─'*20}")

    for i in range(1, num_batches + 1):
        b   = batches.get(str(i), {})
        s1  = b.get("step1", {})
        s2  = b.get("step2", {})
        ts  = s2.get("timestamp", s1.get("timestamp", ""))[:19] or "—"
        row = (f"  {i:>6}  "
               f"{status_dot(s1.get('status','pending'))} {s1.get('status','pending'):>8}  "
               f"{status_dot(s2.get('status','pending'))} {s2.get('status','pending'):>8}  "
               f"{DIM}{ts}{RST}")
        out.append(row)

    out.append("")
    out.append(f"  {'─'*58}")
    out.append(f"  Output Files")
    out.append(f"  {'─'*58}")

    def fline(label, path):
        exists = path.exists()
        color  = G if exists else DIM
        sz     = file_size(path)
        unc    = ""
        if exists and path.suffix == ".txt":
            unc_c = count_uncertain(path)
            unc   = f"  {R}⚠ {unc_c} UNCERTAIN{RST}" if unc_c else f"  {G}✓ clean{RST}"
        return f"  {color}{label:<28}{RST}  {sz:<10}{unc}"

    out.append(fline("final_pipe.txt",            final_pipe))
    out.append(fline("RRB_NTPC_Questions.docx",   docx_path))
    out.append(fline("RRB_NTPC_Questions.xlsx",   xlsx_path))

    if uncertain:
        out.append("")
        out.append(f"  {R}⚠  {uncertain} UNCERTAIN answer(s) in final output{RST}")
        out.append(f"  {DIM}→ Check UNCERTAIN_Review sheet in Excel{RST}")

    # Overall done
    if done_s2 == num_batches and docx_path.exists() and xlsx_path.exists():
        out.append("")
        out.append(f"  {G}✅  Pipeline complete!{RST}")

    out.append(f"{W}{'─'*62}{RST}")
    if not once:
        out.append(f"  {DIM}Auto-refreshing every 5s  •  Ctrl+C to exit{RST}")

    print(CLS + "\n".join(out))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    if args.once:
        render(once=True)
        return

    try:
        while True:
            render()
            time.sleep(5)
    except KeyboardInterrupt:
        print("\nDashboard closed.")

if __name__ == "__main__":
    main()