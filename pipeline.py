"""
RRB NTPC Question Bank Pipeline
Orchestrates: Claude OCR → Qwen3 Reasoning → Gemma Validation → DOCX → XLSX
"""

import os
import sys
import time
import json
import logging
from pathlib import Path
from datetime import datetime

from scripts.step1_reasoning import run_reasoning_batch
from scripts.step2_validation import run_validation_batch
from scripts.step3_docx import generate_docx
from scripts.step4_xlsx import generate_xlsx
from scripts.utils import load_pipe_text, split_into_batches, merge_pipe_lines, save_pipe_text

# ─── CONFIG ──────────────────────────────────────────────────────────────────
BATCH_SIZE        = 10          # questions per prompt
TOTAL_QUESTIONS   = 100
OLLAMA_BASE_URL   = "http://localhost:11434"
REASONING_MODEL   = "qwen3:14b"
VALIDATION_MODEL  = "gemma3:12b"   # good at fact-checking + fits in 16GB alongside qwen
INPUT_FILE        = "input/questions_raw.txt"
OUTPUT_DIR        = Path("output")
LOG_DIR           = Path("logs")
# ─────────────────────────────────────────────────────────────────────────────

def setup_logging():
    LOG_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"pipeline_{ts}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return log_file

def main():
    log_file = setup_logging()
    log = logging.getLogger(__name__)
    OUTPUT_DIR.mkdir(exist_ok=True)

    log.info("=" * 60)
    log.info("RRB NTPC Pipeline Started")
    log.info(f"Model (Reasoning) : {REASONING_MODEL}")
    log.info(f"Model (Validation): {VALIDATION_MODEL}")
    log.info("=" * 60)

    # ── LOAD INPUT ─────────────────────────────────────────────────────────
    raw_text = load_pipe_text(INPUT_FILE)
    batches  = split_into_batches(raw_text, BATCH_SIZE)
    log.info(f"Loaded {len(raw_text)} questions → {len(batches)} batches of {BATCH_SIZE}")

    reasoned_lines  = []
    validated_lines = []

    # ── STEP 1 + 2: BATCH LOOP ─────────────────────────────────────────────
    for i, batch in enumerate(batches, 1):
        log.info(f"\n{'─'*50}")
        log.info(f"Batch {i}/{len(batches)} | Questions {(i-1)*BATCH_SIZE+1}–{i*BATCH_SIZE}")

        # Step 1 – Reasoning / Calculation (Qwen3:14b)
        log.info(f"  [Step 1] Reasoning with {REASONING_MODEL}...")
        reasoned = run_reasoning_batch(
            batch, REASONING_MODEL, OLLAMA_BASE_URL, batch_num=i
        )
        reasoned_lines.extend(reasoned)
        save_pipe_text(OUTPUT_DIR / f"step1_batch{i:02d}.txt", reasoned)
        log.info(f"  [Step 1] Done → {len(reasoned)} lines")

        # Step 2 – Validation (Gemma3:12b)
        log.info(f"  [Step 2] Validation with {VALIDATION_MODEL}...")
        validated = run_validation_batch(
            reasoned, VALIDATION_MODEL, OLLAMA_BASE_URL, batch_num=i
        )
        validated_lines.extend(validated)
        save_pipe_text(OUTPUT_DIR / f"step2_batch{i:02d}.txt", validated)
        log.info(f"  [Step 2] Done → {len(validated)} lines")

        time.sleep(1)   # brief cooldown between batches

    # ── MERGE & SAVE FINAL PIPE ────────────────────────────────────────────
    final_pipe_path = OUTPUT_DIR / "final_pipe.txt"
    save_pipe_text(final_pipe_path, validated_lines)
    log.info(f"\nFinal pipe saved → {final_pipe_path}")

    # ── STEP 3 – DOCX ──────────────────────────────────────────────────────
    log.info("\n[Step 3] Generating Word Document...")
    docx_path = OUTPUT_DIR / "RRB_NTPC_Questions.docx"
    generate_docx(validated_lines, str(docx_path))
    log.info(f"  DOCX saved → {docx_path}")

    # ── STEP 4 – XLSX ──────────────────────────────────────────────────────
    log.info("\n[Step 4] Generating Excel File...")
    xlsx_path = OUTPUT_DIR / "RRB_NTPC_Questions.xlsx"
    generate_xlsx(validated_lines, str(xlsx_path))
    log.info(f"  XLSX saved → {xlsx_path}")

    log.info("\n" + "=" * 60)
    log.info("Pipeline Complete")
    log.info(f"  Pipe  : {final_pipe_path}")
    log.info(f"  DOCX  : {docx_path}")
    log.info(f"  XLSX  : {xlsx_path}")
    log.info(f"  Log   : {log_file}")
    log.info("=" * 60)

if __name__ == "__main__":
    main()