import os
import sys
import argparse
from scripts.step1_reasoning import process_with_qwen
from scripts.step2_validation import process_with_gemma
from scripts.step3_docx import generate_word_document
from scripts.step4_xlsx import generate_excel

# Configuration
INPUT_FILE = "input/questions_raw.txt"
BATCH_SIZE = 10
REASONING_MODEL = "qwen3:14b"
VALIDATION_MODEL = "gemma3:12b"
OLLAMA_API_URL = "http://localhost:11434/api/generate"

# Directories
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Output Paths
STEP1_OUTPUT = os.path.join(OUTPUT_DIR, "step1_batch_{:02d}.txt")
STEP2_OUTPUT = os.path.join(OUTPUT_DIR, "step2_batch_{:02d}.txt")
FINAL_PIPE_OUTPUT = os.path.join(OUTPUT_DIR, "final_pipe.txt")
DOCX_OUTPUT = os.path.join(OUTPUT_DIR, "RRB_NTPC_Questions.docx")
XLSX_OUTPUT = os.path.join(OUTPUT_DIR, "RRB_NTPC_Questions.xlsx")

def read_input_file(filepath):
    """Reads raw pipe-separated text, skipping empty lines."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        return lines
    except FileNotFoundError:
        print(f"Error: {filepath} not found.")
        sys.exit(1)

def batch_lines(lines, batch_size):
    """Yields successive batches from the list of lines."""
    for i in range(0, len(lines), batch_size):
        yield lines[i:i + batch_size]

def main():
    print("🚀 Starting RRB NTPC Question Pipeline...")
    
    # 1. Read Input
    lines = read_input_file(INPUT_FILE)
    total_questions = len(lines)
    print(f"📋 Found {total_questions} questions in {INPUT_FILE}")
    
    if total_questions == 0:
        print("Error: Input file is empty.")
        sys.exit(1)
        
    batches = list(batch_lines(lines, BATCH_SIZE))
    total_batches = len(batches)
    print(f"📦 Split into {total_batches} batches of up to {BATCH_SIZE} questions.")
    
    final_validated_lines = []
    
    # 2. Process Batches
    for i, batch in enumerate(batches):
        batch_num = i + 1
        
        # --- Streamlit Progress Hook ---
        print(f"PROGRESS:{batch_num}/{total_batches}", flush=True)
        # -------------------------------
        
        # Step 1: Reasoning (Qwen3)
        print(f"\n[{batch_num}/{total_batches}] Running Step 1: Reasoning ({REASONING_MODEL})...")
        batch_text = "\n".join(batch)
        
        qwen_output = process_with_qwen(batch_text, REASONING_MODEL, OLLAMA_API_URL)
        if not qwen_output:
            print(f"⚠️ Warning: Step 1 failed for batch {batch_num}. Skipping.")
            continue
            
        step1_file = STEP1_OUTPUT.format(batch_num)
        with open(step1_file, "w", encoding="utf-8") as f:
            f.write(qwen_output)
            
        # Step 2: Validation (Gemma3)
        print(f"[{batch_num}/{total_batches}] Running Step 2: Validation ({VALIDATION_MODEL})...")
        gemma_output = process_with_gemma(qwen_output, VALIDATION_MODEL, OLLAMA_API_URL)
        
        if not gemma_output:
            print(f"⚠️ Warning: Step 2 failed for batch {batch_num}. Using Step 1 output instead.")
            gemma_output = qwen_output # Fallback
            
        step2_file = STEP2_OUTPUT.format(batch_num)
        with open(step2_file, "w", encoding="utf-8") as f:
            f.write(gemma_output)
            
        # Accumulate the final validated text
        final_validated_lines.append(gemma_output)
        
    # --- Streamlit Progress Hook: Completion ---
    print("PROGRESS:COMPLETE", flush=True)
    # -------------------------------------------
    
    # 3. Combine Final Output
    print("\n🔗 Combining final pipe data...")
    final_text = "\n".join(final_validated_lines)
    
    with open(FINAL_PIPE_OUTPUT, "w", encoding="utf-8") as f:
        f.write(final_text)
        
    # 4. Generate Artifacts (Word & Excel)
    print("📝 Generating Word document...")
    generate_word_document(FINAL_PIPE_OUTPUT, DOCX_OUTPUT)
    
    print("📊 Generating Excel file...")
    generate_excel(FINAL_PIPE_OUTPUT, XLSX_OUTPUT)
    
    print("\n✅ Pipeline complete!")
    print(f"📄 Excel: {XLSX_OUTPUT}")
    print(f"📄 Word: {DOCX_OUTPUT}")

if __name__ == "__main__":
    main()