#!/usr/bin/env python3
"""Extract reliable question text from the supplied SAT PDFs.

Usage:
  python3 tools/extract_text_bank.py --math "Math All Q&A_compressed(1).pdf" \
      --rw "Reading & Writing All Q&A_compressed(1).pdf" --out bank/text.js

Only questions whose text and (for MCQ) all four choices extract cleanly are emitted.
Questions containing missing math glyphs or likely chart/figure content are omitted so
the simulator continues to use its original image instead of displaying damaged text.
Requires: pip install pymupdf
"""
import argparse
import json
import re
import sys
from pathlib import Path

try:
    import fitz
except ImportError:
    sys.exit("Install PyMuPDF first: python3 -m pip install pymupdf")

ID_RE = re.compile(r"Question ID:\s*([0-9a-f]{8})", re.I)
CORRECT_RE = re.compile(r"(?im)^\s*Correct Answer\s*:")
ANSWER_RE = re.compile(r"(?im)^\s*Answer\s*$")
CHOICE_RE = re.compile(r"(?m)^\s*([A-D])\.\s*")

def clean_lines(value):
    value = value.replace("\u00a0", " ").replace("\u00ad", "")
    lines = [re.sub(r"[ \t]+", " ", x).strip() for x in value.splitlines()]
    paragraphs, current = [], []
    for line in lines:
        if not line:
            if current:
                paragraphs.append(" ".join(current))
                current = []
        else:
            current.append(line)
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(paragraphs).strip()

def parse_record(raw, subject, has_figure):
    qhead = re.search(r"(?im)^\s*Question\s*$", raw)
    if not qhead:
        return None
    body = raw[qhead.end():]
    correct = CORRECT_RE.search(body)
    if correct:
        body = body[:correct.start()]
    answer = ANSWER_RE.search(body)
    stem_raw = body[:answer.start()] if answer else body
    choices_raw = body[answer.end():] if answer else ""
    stem = clean_lines(stem_raw)
    if not stem:
        return None

    choices = []
    if answer:
        matches = list(CHOICE_RE.finditer(choices_raw))
        if len(matches) != 4 or [m.group(1) for m in matches] != list("ABCD"):
            return None
        for i, match in enumerate(matches):
            end = matches[i + 1].start() if i < 3 else len(choices_raw)
            choice = clean_lines(choices_raw[match.end():end])
            if not choice:
                return None
            choices.append(choice)

    # PDF text extraction drops many math symbols. Keep those questions as the
    # original image rather than publishing incomplete equations or answer choices.
    if subject == "math":
        missing_math = re.search(
            r"(?:,\s*|\b(?:and|or|is|are|equals?)\s*)\n\s*(?:and|or|is|are|what|which|the|a\b|,|\.)"
            r"|\b(?:equation|expression|function|slope|value)\b[^\n]{0,35}\n\s*(?:,|\?|and|or)\b",
            stem_raw, re.I
        )
        if missing_math:
            return None
        if any(re.search(r"\n\s*(?:,|\.)\s*(?:\n|$)", c) for c in choices_raw.splitlines()):
            return None

    # A chart/diagram may not survive as ordinary text. Retain the screenshot
    # whenever the page contains a visual and the question refers to one.
    if has_figure and re.search(r"\b(graph|figure|diagram|table|chart|shown above|shown)\b", stem, re.I):
        return None

    prompt = ""
    if subject == "rw" and "\n\n" in stem:
        parts = stem.split("\n\n")
        last = parts[-1]
        if "?" in last and len(last) < 360:
            prompt = last
            stem = "\n\n".join(parts[:-1]).strip()
    result = {"stem": stem}
    if prompt:
        result["prompt"] = prompt
    if choices:
        result["choices"] = choices
    return result

def extract(pdf_path, subject):
    doc = fitz.open(pdf_path)
    records = {}
    current_id, current_pages, current_figure = None, [], False
    page_count = 0

    def flush():
        if not current_id:
            return
        raw = "\n".join(current_pages)
        # Inspect pages grouped with this question for likely embedded figures.
        data = parse_record(raw, subject, current_figure)
        if data:
            records[current_id] = data

    for page in doc:
        page_count += 1
        raw = page.get_text("text", sort=True)
        match = ID_RE.search(raw)
        if match:
            flush()
            current_id = match.group(1).lower()
            current_pages = [raw]
            current_figure = bool(page.get_images(full=True))
        elif current_id:
            current_pages.append(raw)
            current_figure = current_figure or bool(page.get_images(full=True))
    flush()
    print(f"{pdf_path}: {len(records)} text-safe questions from {page_count} pages", file=sys.stderr)
    return records

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--math", required=True, help="Math source PDF")
    ap.add_argument("--rw", required=True, help="Reading & Writing source PDF")
    ap.add_argument("--out", default="bank/text.js")
    args = ap.parse_args()

    bank = {}
    bank.update(extract(args.math, "math"))
    bank.update(extract(args.rw, "rw"))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("window.TEXTBANK=" + json.dumps(bank, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"Wrote {len(bank)} text-first questions to {out}")

if __name__ == "__main__":
    main()
