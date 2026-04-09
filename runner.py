"""
runner.py  —  Resume-aware batch runner with state checkpointing.

Features:
- Saves state after each batch → safe to kill and resume
- Per-batch retry (up to 3 attempts)
- Detailed progress bar in terminal
- --resume flag to continue from last checkpoint
- --batch N to rerun a specific batch
- --step 1|2 to rerun only reasoning or only validation for a batch

Usage:
  python runner.py                  # fresh run
  python runner.py --resume         # continue from checkpoint
  python runner.py --batch 3        # rerun batch 3 (both steps)
  python runner.py --batch 3 --step 2   # rerun only validation for batch 3
  python runner.py --report         # print status of all batches, no run
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from datetime import datetime

# ── project imports ────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from scripts.step1_reasoning  import run_reasoning_batch
from scripts.step2_validation import run_validation_batch
from scripts.step3_docx       import generate_docx
from scripts.step4_xlsx       import generate_xlsx
from scripts.utils            import (load_pipe_text, split_into_batches,
                                      save_pipe_text, renumber)

# ── CONFIG (edit here) ─────────────────────────────────────────────────────
BATCH_SIZE       = 10
OLLAMA_BASE_URL  = "http://localhost:11434"
REASONING_MODEL  = "qwen3:14b"
VALIDATION_MODEL = "gemma3:12b"
INPUT_FILE       = "input/questions_raw.txt"
OUTPUT_DIR       = Path("output")
LOG_DIR          = Path("logs")
STATE_FILE       = OUTPUT_DIR / ".pipeline_state.json"
MAX_RETRIES      = 3
RETRY_DELAY_SEC  = 5
# ──────────────────────────────────────────────────────────────────────────

def setup_logging():
    LOG_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"runner_{ts}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ]
    )
    return log_file

log = logging.getLogger(__name__)

# ── STATE MANAGEMENT ───────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"batches": {}}

def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")

def mark_batch(state: dict, batch_num: int, step: int, status: str,
               lines: list[str] | None = None):
    key = str(batch_num)
    if key not in state["batches"]:
        state["batches"][key] = {}
    state["batches"][key][f"step{step}"] = {
        "status": status,
        "timestamp": datetime.now().isoformat(),
    }
    if lines is not None:
        path = OUTPUT_DIR / f"step{step}_batch{batch_num:02d}.txt"
        save_pipe_text(path, lines)
        state["batches"][key][f"step{step}"]["file"] = str(path)
    save_state(state)

def is_done(state: dict, batch_num: int, step: int) -> bool:
    key = str(batch_num)
    return (state["batches"].get(key, {})
                            .get(f"step{step}", {})
                            .get("status") == "done")

def load_batch_output(batch_num: int, step: int) -> list[str] | None:
    path = OUTPUT_DIR / f"step{step}_batch{batch_num:02d}.txt"
    if path.exists():
        try:
            return load_pipe_text(str(path))
        except Exception:
            return None
    return None

# ── PROGRESS BAR ───────────────────────────────────────────────────────────

def progress(current: int, total: int, label: str = "", width: int = 40):
    filled = int(width * current / total) if total else 0
    bar    = "█" * filled + "░" * (width - filled)
    pct    = int(100 * current / total) if total else 0
    sys.stdout.write(f"\r  [{bar}] {pct:3d}%  {label:<35}")
    sys.stdout.flush()
    if current >= total:
        print()

# ── BATCH EXECUTION ────────────────────────────────────────────────────────

def run_step(step: int, batch_num: int, lines: list[str],
             state: dict, force: bool = False) -> list[str]:
    if not force and is_done(state, batch_num, step):
        cached = load_batch_output(batch_num, step)
        if cached:
            log.info(f"  [Batch {batch_num}] Step {step} — using cached output")
            return cached

    fn = run_reasoning_batch if step == 1 else run_validation_batch
    model = REASONING_MODEL if step == 1 else VALIDATION_MODEL
    label = "Reasoning" if step == 1 else "Validation"

    for attempt in range(1, MAX_RETRIES + 1):
        log.info(f"  [Batch {batch_num}] Step {step} ({label}) — attempt {attempt}/{MAX_RETRIES}")
        try:
            result = fn(lines, model, OLLAMA_BASE_URL, batch_num=batch_num)
            if result:
                mark_batch(state, batch_num, step, "done", result)
                return result
        except Exception as e:
            log.error(f"  [Batch {batch_num}] Step {step} error: {e}")
        if attempt < MAX_RETRIES:
            log.warning(f"  Retrying in {RETRY_DELAY_SEC}s...")
            time.sleep(RETRY_DELAY_SEC)

    log.error(f"  [Batch {batch_num}] Step {step} FAILED after {MAX_RETRIES} attempts — using input as-is")
    mark_batch(state, batch_num, step, "failed", lines)
    return lines

# ── ASSEMBLE FINAL OUTPUT ─────────────────────────────────────────────────

def assemble_final(num_batches: int) -> list[str]:
    all_lines = []
    for i in range(1, num_batches + 1):
        lines = load_batch_output(i, 2) or load_batch_output(i, 1) or []
        all_lines.extend(lines)
    return renumber(all_lines, start=1)

# ── REPORT ─────────────────────────────────────────────────────────────────

def print_report(state: dict, num_batches: int):
    print("\n" + "─" * 60)
    print(f"{'Batch':>7}  {'Step1':>10}  {'Step2':>10}  {'Status':>12}")
    print("─" * 60)
    for i in range(1, num_batches + 1):
        key  = str(i)
        b    = state["batches"].get(key, {})
        s1   = b.get("step1", {}).get("status", "pending")
        s2   = b.get("step2", {}).get("status", "pending")
        done = s1 == "done" and s2 == "done"
        flag = "✅" if done else ("⚠️ " if "failed" in (s1, s2) else "🔄")
        print(f"  {i:>5}  {s1:>10}  {s2:>10}  {flag}")
    print("─" * 60 + "\n")

# ── MAIN ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="RRB NTPC Pipeline Runner")
    parser.add_argument("--resume",  action="store_true", help="Resume from checkpoint")
    parser.add_argument("--batch",   type=int, default=None, help="Rerun specific batch number")
    parser.add_argument("--step",    type=int, choices=[1, 2], default=None,
                        help="Only run this step (use with --batch)")
    parser.add_argument("--report",  action="store_true", help="Print status report only")
    parser.add_argument("--input",   type=str, default=INPUT_FILE, help="Override input file")
    args = parser.parse_args()

    log_file = setup_logging()
    state    = load_state()

    # Load input
    try:
        raw_lines = load_pipe_text(args.input)
    except FileNotFoundError as e:
        log.error(str(e))
        sys.exit(1)

    batches     = split_into_batches(raw_lines, BATCH_SIZE)
    num_batches = len(batches)

    log.info("=" * 60)
    log.info("RRB NTPC Runner")
    log.info(f"  Questions : {len(raw_lines)}")
    log.info(f"  Batches   : {num_batches} × {BATCH_SIZE}")
    log.info(f"  Reasoning : {REASONING_MODEL}")
    log.info(f"  Validation: {VALIDATION_MODEL}")
    log.info(f"  Resume    : {args.resume}")
    log.info("=" * 60)

    # Report-only mode
    if args.report:
        print_report(state, num_batches)
        return

    # Single-batch mode
    if args.batch is not None:
        b_idx = args.batch
        if b_idx < 1 or b_idx > num_batches:
            log.error(f"--batch must be 1–{num_batches}")
            sys.exit(1)
        batch = batches[b_idx - 1]
        steps = [args.step] if args.step else [1, 2]
        input_lines = batch
        for step in steps:
            if step == 2:
                input_lines = load_batch_output(b_idx, 1) or input_lines
            result = run_step(step, b_idx, input_lines, state, force=True)
            input_lines = result
        log.info(f"Batch {b_idx} rerun complete.")
        print_report(state, num_batches)
        return

    # Full run / resume
    for i, batch in enumerate(batches, 1):
        qs_start = (i - 1) * BATCH_SIZE + 1
        qs_end   = min(i * BATCH_SIZE, len(raw_lines))
        log.info(f"\n{'─'*50}")
        log.info(f"Batch {i}/{num_batches}  (Q{qs_start}–Q{qs_end})")
        progress(i - 1, num_batches, f"Batch {i}/{num_batches}")

        skip_s1 = args.resume and is_done(state, i, 1)
        skip_s2 = args.resume and is_done(state, i, 2)

        if skip_s1 and skip_s2:
            log.info(f"  [Batch {i}] Both steps cached — skipping")
            progress(i, num_batches, f"Batch {i}/{num_batches} (cached)")
            continue

        # Step 1
        step1_out = run_step(1, i, batch, state, force=not skip_s1)

        # Step 2
        run_step(2, i, step1_out, state, force=not skip_s2)

        progress(i, num_batches, f"Batch {i}/{num_batches} done")
        time.sleep(1)

    # Assemble + write outputs
    log.info("\n[Assembling final output...]")
    final_lines = assemble_final(num_batches)
    save_pipe_text(OUTPUT_DIR / "final_pipe.txt", final_lines)

    log.info("[Step 3] Generating DOCX...")
    generate_docx(final_lines, str(OUTPUT_DIR / "RRB_NTPC_Questions.docx"))

    log.info("[Step 4] Generating XLSX...")
    generate_xlsx(final_lines, str(OUTPUT_DIR / "RRB_NTPC_Questions.xlsx"))

    print_report(state, num_batches)
    log.info("=" * 60)
    log.info("Pipeline complete.")
    log.info(f"  DOCX : {OUTPUT_DIR / 'RRB_NTPC_Questions.docx'}")
    log.info(f"  XLSX : {OUTPUT_DIR / 'RRB_NTPC_Questions.xlsx'}")
    log.info(f"  Log  : {log_file}")
    log.info("=" * 60)

if __name__ == "__main__":
    main()