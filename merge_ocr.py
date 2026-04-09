"""
merge_ocr.py  —  Merges multiple Claude OCR batch files into questions_raw.txt
Usage:
  python merge_ocr.py ocr_batch1.txt ocr_batch2.txt ocr_batch3.txt ...
  python merge_ocr.py ocr_batches/batch*.txt         (glob)
  python merge_ocr.py --dir ocr_batches/             (all .txt in folder)

Handles: duplicate headers, renumbering, empty lines.
"""

import sys
import argparse
from pathlib import Path
from scripts.utils import COLUMNS, renumber

OUTPUT_FILE = Path("input/questions_raw.txt")
HEADER      = "|".join(COLUMNS)


def load_lines(filepath: Path) -> list[str]:
    raw = filepath.read_text(encoding="utf-8").splitlines()
    lines = []
    for line in raw:
        line = line.strip()
        if not line:
            continue
        if line.lower().startswith("no|") or line.lower().startswith("no |"):
            continue  # skip headers
        if line.count("|") >= 10:  # at least 11 columns
            lines.append(line)
    return lines


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="*", help="OCR batch .txt files")
    parser.add_argument("--dir",    type=str, default=None,
                        help="Folder containing OCR batch .txt files")
    parser.add_argument("--output", type=str, default=str(OUTPUT_FILE))
    args = parser.parse_args()

    files = []
    if args.dir:
        folder = Path(args.dir)
        files  = sorted(folder.glob("*.txt"))
    else:
        files = [Path(f) for f in args.files]

    if not files:
        print("No files provided. Usage: python merge_ocr.py batch1.txt batch2.txt ...")
        sys.exit(1)

    all_lines = []
    for f in files:
        if not f.exists():
            print(f"  ⚠  File not found: {f}")
            continue
        lines = load_lines(f)
        print(f"  ✓  {f.name:40s}  →  {len(lines)} questions")
        all_lines.extend(lines)

    if not all_lines:
        print("No valid lines found.")
        sys.exit(1)

    # Renumber sequentially
    renumbered = renumber(all_lines, start=1)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(HEADER + "\n" + "\n".join(renumbered), encoding="utf-8")

    print(f"\n✅  Merged {len(renumbered)} questions → {out_path}")
    print("   Next: python validate_input.py")

if __name__ == "__main__":
    main()