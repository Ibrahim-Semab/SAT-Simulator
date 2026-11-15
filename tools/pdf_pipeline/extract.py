#!/usr/bin/env python3
"""Step 1 - read every page of a question-bank PDF into plain JSON (fast, via pdfium).

The PDFs are College Board printouts. Body text is real text, typeset maths is drawn as vector shapes
(Math Hard) or small raster pictures (Math Easy+Medium); Reading & Writing has no pictures at all.
Chrome writes a page in reading order, so the drawing order tells us which equation sits between which
words. For each page this stores that drawing order:
  ['t', text, x_left, baseline_y, x_right]      one text run   (y measured from the top of the page, in pt)
  ['m', x0, y0, x1, y1, 'p'|'i']               one drawn shape / picture (a piece of an equation)

usage: extract.py PDF OUT_DIR [first_page last_page]     (pages are 1-based)
"""
import sys, os, json, ctypes
import pypdfium2 as pdfium
import pypdfium2.raw as raw

def page_data(pdf, i):
    pg = pdf[i]; W, H = pg.get_size(); tp = pg.get_textpage(); seq = []
    for o in pg.get_objects(filter=[raw.FPDF_PAGEOBJ_TEXT, raw.FPDF_PAGEOBJ_PATH, raw.FPDF_PAGEOBJ_IMAGE]):
        l, b, r, t = o.get_bounds()
        if o.type == raw.FPDF_PAGEOBJ_TEXT:
            n = raw.FPDFTextObj_GetText(o.raw, tp.raw, None, 0)
            buf = (ctypes.c_ushort * n)(); raw.FPDFTextObj_GetText(o.raw, tp.raw, buf, n)
            txt = ''.join(chr(c) for c in buf if c)
            if not txt: continue
            seq.append(['t', txt, round(l, 2), round(H - o.get_matrix().f, 2), round(r, 2)])
        else:
            if r - l > 560 and t - b > 700: continue                      # page background
            seq.append(['m', round(l, 2), round(H - t, 2), round(r, 2), round(H - b, 2), 'i' if o.type == raw.FPDF_PAGEOBJ_IMAGE else 'p'])
    pg.close()
    return {'w': W, 'h': H, 'seq': seq}

if __name__ == '__main__':
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    pdf = pdfium.PdfDocument(src); n = len(pdf)
    a = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    b = int(sys.argv[4]) if len(sys.argv) > 4 else n
    for i in range(a - 1, b):
        json.dump(page_data(pdf, i), open(os.path.join(out, '%04d.json' % (i + 1)), 'w'), separators=(',', ':'))
        if (i + 1) % 100 == 0: print(i + 1, '/', n, flush=True)
