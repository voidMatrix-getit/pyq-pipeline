"""
test_pipeline.py
Tests DOCX + XLSX generation with sample data (no Ollama required).
Run: python test_pipeline.py
"""

import sys
sys.path.insert(0, ".")

from pathlib import Path
from scripts.utils import load_pipe_text
from scripts.step3_docx import generate_docx
from scripts.step4_xlsx import generate_xlsx

TEST_INPUT = "input/questions_raw.txt"
OUT_DOCX   = "output/test_output.docx"
OUT_XLSX   = "output/test_output.xlsx"

Path("output").mkdir(exist_ok=True)

print("Loading sample questions...")
lines = load_pipe_text(TEST_INPUT)
print(f"  Loaded {len(lines)} questions")

print("\nGenerating DOCX...")
generate_docx(lines, OUT_DOCX)
print(f"  → {OUT_DOCX}")

print("\nGenerating XLSX...")
generate_xlsx(lines, OUT_XLSX)
print(f"  → {OUT_XLSX}")

print("\nTest complete. Check output/ folder.")