# Text question pipeline

Builds `bank/meta.js` (question text, options, crop rectangles) from the three PDF text
extractions in `source/` plus the page screenshots in `bank/q/`.

Needs: python3, numpy, pillow, pytesseract + the `tesseract` binary. Run from this folder, in order:

    python3 parse_txt.py        # -> parsed.json  (text, options, answers per question id)
    python3 geom.py             # -> geom.json    (stem/option rectangles in each screenshot)
    python3 ocr_all.py          # -> ocr.json     (OCR used only to cross-check the text layer)
    python3 -c "import run_hybrid" # see note

`hybrid.py` aligns OCR word boxes with the exact text: matched words stay text, and anything the
text layer lost (typeset math) becomes a small inline picture crop. Questions that fail a check
fall back to a full crop, so nothing is ever shown wrong. `assemble.py` writes `meta_new.js`.
`old_meta.js` carries the original per-question fields (domain, skill, difficulty, size).
