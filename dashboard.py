import streamlit as st
import os
import subprocess
import requests
import pandas as pd
from pdf2image import convert_from_bytes
from paddleocr import PaddleOCR

# Initialize PaddleOCR
@st.cache_resource
def load_ocr():
    return PaddleOCR(use_angle_cls=True, lang='en')

ocr = load_ocr()

st.set_page_config(page_title="PYQ Pipeline", page_icon="📄", layout="wide")

# Define paths
INPUT_DIR = "input"
OUTPUT_DIR = "output"
RAW_FILE = os.path.join(INPUT_DIR, "questions_raw.txt")
EXCEL_FILE = os.path.join(OUTPUT_DIR, "RRB_NTPC_Questions.xlsx")
WORD_FILE = os.path.join(OUTPUT_DIR, "RRB_NTPC_Questions.docx")

os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

def structure_with_llm(raw_text):
    """Sends raw text to Ollama to format into pipe-separated structure."""
    prompt = f"""
    You are an expert data extraction assistant. Format this raw OCR text EXACTLY into this pipe-separated structure:
    No|Section|Sub-Section|Question|Option1|Option2|Option3|Option4|Correct Answer|Explanation|Difficulty
    
    Rules:
    1. Output ONLY the pipe-separated rows. No header, no markdown, no introductions.
    2. Maintain the exact 11 columns. Leave missing fields blank (e.g., ||).
    
    Raw OCR Text:
    {raw_text}
    """
    try:
        response = requests.post('http://localhost:11434/api/generate', json={
            "model": "qwen3:14b", 
            "prompt": prompt,
            "stream": False
        })
        if response.status_code == 200:
            return response.json()['response'].strip()
        return f"Error: Status {response.status_code}"
    except Exception as e:
        return f"Error: {str(e)}"

def run_pipeline_with_progress():
    """Runs pipeline.py and reads stdout to update a Streamlit progress bar."""
    progress_text = "Running LLM Reasoning & Validation..."
    my_bar = st.progress(0, text=progress_text)
    
    # Run pipeline and stream the output line by line
    process = subprocess.Popen(
        ["python", "pipeline.py"], 
        stdout=subprocess.PIPE, 
        stderr=subprocess.STDOUT, 
        text=True,
        bufsize=1
    )
    
    for line in process.stdout:
        line = line.strip()
        # Look for the progress marker we added to pipeline.py
        if line.startswith("PROGRESS:"):
            data = line.split(":")[1]
            if data == "COMPLETE":
                my_bar.progress(100, text="Pipeline Complete!")
            else:
                try:
                    current, total = map(int, data.split("/"))
                    percent_complete = int((current / total) * 100)
                    my_bar.progress(percent_complete, text=f"Processing batch {current} of {total}...")
                except Exception:
                    pass
                    
    process.wait()
    if process.returncode != 0:
        st.error("Pipeline encountered an error. Check terminal logs.")

# --- UI Layout ---

st.title("📄 PYQ Automated Extraction")
st.markdown("Transform raw exam PDFs or text into structured DataFrames and Word documents using local LLMs.")

with st.sidebar:
    st.header("⚙️ Configuration")
    mode = st.radio("Pipeline Mode", ["Auto (PDF Upload)", "Manual (Text Input)"])
    st.markdown("---")
    st.info("Ensure Ollama (`qwen3:14b` & `gemma3:12b`) is running locally on port 11434.")

# Main Processing Area
if mode == "Auto (PDF Upload)":
    uploaded_file = st.file_uploader("Upload Question Paper (PDF)", type=["pdf"])
    
    if uploaded_file and st.button("🚀 Start Full Automation", type="primary"):
        
        # 1. OCR Stage
        with st.spinner("📸 Extracting text from PDF via PaddleOCR..."):
            images = convert_from_bytes(uploaded_file.read())
            raw_extracted_text = ""
            for i, img in enumerate(images):
                img_path = f"temp_page_{i}.jpg"
                img.save(img_path, "JPEG")
                result = ocr.ocr(img_path, cls=True)
                for res in result:
                    if res:
                        for line in res:
                            raw_extracted_text += line[1][0] + "\n"
                os.remove(img_path)
        st.success(f"Successfully scanned {len(images)} pages.")

        # 2. Structuring Stage
        with st.spinner("🧠 Structuring data with Qwen3:14b..."):
            structured_text = structure_with_llm(raw_extracted_text)
            
        if "Error" in structured_text:
            st.error(structured_text)
        else:
            with open(RAW_FILE, "w", encoding="utf-8") as f:
                f.write(structured_text)
            st.success("Data formatted successfully!")
            
            with st.expander("Preview Extracted Pipe Data"):
                st.text(structured_text[:500] + "\n...[truncated]")

            # 3. Pipeline Execution Stage with LIVE PROGRESS
            run_pipeline_with_progress()
            st.toast("Processing finished!", icon="✅")

elif mode == "Manual (Text Input)":
    manual_text = st.text_area("Paste Pipe-Separated Text Here", height=250, 
                               placeholder="1|Math|Algebra|What is x...|A|B|C|D|A|Explanation|Medium")
    
    if st.button("🚀 Run Pipeline", type="primary"):
        if manual_text.strip():
            with open(RAW_FILE, "w", encoding="utf-8") as f:
                f.write(manual_text)
                
            # LIVE PROGRESS
            run_pipeline_with_progress()
            st.toast("Processing finished!", icon="✅")
        else:
            st.warning("Please paste some text first.")

# --- Results UI Layer ---
st.markdown("---")
st.header("📊 Extraction Results")

if os.path.exists(EXCEL_FILE) and os.path.exists(WORD_FILE):
    try:
        df = pd.read_excel(EXCEL_FILE)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Questions", len(df))
        if 'Difficulty' in df.columns:
            hard_count = len(df[df['Difficulty'].astype(str).str.contains('Hard', case=False, na=False)])
            col2.metric("Hard Questions", hard_count)
        if 'Correct Answer' in df.columns:
            uncertain = len(df[df['Correct Answer'].astype(str).str.contains('UNCERTAIN', case=False, na=False)])
            col3.metric("Flags (Uncertain)", uncertain, delta_color="inverse")
            
        st.subheader("Data Preview")
        st.dataframe(df, use_container_width=True, height=300)
        
        st.subheader("Download Artifacts")
        btn_col1, btn_col2 = st.columns(2)
        
        with open(EXCEL_FILE, "rb") as file:
            btn_col1.download_button("📥 Download Excel (.xlsx)", data=file, file_name="RRB_NTPC_Questions.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            
        with open(WORD_FILE, "rb") as file:
            btn_col2.download_button("📥 Download Word (.docx)", data=file, file_name="RRB_NTPC_Questions.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
            
    except Exception as e:
        st.info("Output files generated, but could not load the preview. (Is the Excel file corrupted?)")
else:
    st.info("Results will appear here once the pipeline finishes processing.")