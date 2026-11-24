#!/usr/bin/env python3
"""Replace blurry figure pictures (bank/f) by a cleaner enlargement of the bitmap that the original PDF embeds.

Many figures (scatterplots, graphs) are only small bitmaps inside the College Board PDFs (for example 140 x 154 px),
so they cannot be sharper than that, but the bank copy had been resampled twice and looked blotchy. This takes the
embedded bitmap itself (pdfimages), enlarges it 3x (Lanczos), removes the JPEG noise, sharpens and stretches the
contrast. Vector figures were already re-cut at 2x by tools/restore_figures.py and are not touched.

A bank picture is replaced only if a bitmap of its question's PDF page(s) is the same drawing: aspect ratio within 8%
and correlation >= 0.6 after resizing both to 200 x 200. The token keeps its width in em; the height follows the
bitmap's aspect.

The PDFs are on the git branch add-original-pdfs (see README.txt):
    python3 tools/upscale_figures.py --pdf-dir /tmp/pdfs [--apply] [--sheet before_after.png]
"""
import argparse, glob, hashlib, io, json, os, re, subprocess, sys, tempfile
import cv2, numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); BANK = os.path.join(HERE, '..', 'bank')
SRC = {'Math Easy+Medium': 'Math Easy+Medium_compressed.pdf', 'Math Hard': 'Math Hard_compressed.pdf',
       'Reading & Writing': 'Reading & Writing All Q&A_compressed.pdf'}
TK = re.compile(r'⟦f:([0-9a-f]+):(-?[\d.]+):(-?[\d.]+)⟧')
MIN = 60; FACT = 3

def bank_gray(h):
    im = Image.open(os.path.join(BANK, 'f', h + '.webp')).convert('RGBA'); b = Image.new('RGBA', im.size, 'white'); b.alpha_composite(im)
    return np.array(b.convert('L'), dtype=np.uint8)

_cache = {}
def page_bitmaps(pdf, p):
    k = (pdf, p)
    if k not in _cache:
        out = []
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(['pdfimages', '-f', str(p), '-l', str(p), '-png', pdf, d + '/im'], check=True, capture_output=True)
            for f in sorted(glob.glob(d + '/im-*.png')):
                im = Image.open(f); im.load()
                if im.width >= MIN and im.height >= MIN: out.append(im.convert('RGB'))
        _cache[k] = out
    return _cache[k]

def score(old, new):
    """How well the bitmap `new` matches the bank picture `old` (0..1). The bitmap is scaled to the picture's size
    (slightly smaller is allowed: the picture may carry a margin), placed where it correlates best, and the DARK ink
    (curves, labels; not the faint grid) of both is compared: the share of each one's dark pixels that lies within
    3 px of the other's dark pixels, the smaller of the two shares is the score."""
    base = old.shape[1] / new.shape[1]; best = (0.0, None)
    ob = cv2.GaussianBlur(old, (0, 0), 2)
    for f in np.geomspace(0.88, 1.0, 9):
        sc = base * f; g = cv2.resize(new, (max(8, round(new.shape[1] * sc)), max(8, round(new.shape[0] * sc))), interpolation=cv2.INTER_AREA)
        if g.shape[0] > old.shape[0] or g.shape[1] > old.shape[1] or g.shape[0] < 0.88 * old.shape[0]: continue
        r = cv2.matchTemplate(ob, cv2.GaussianBlur(g, (0, 0), 2), cv2.TM_CCOEFF_NORMED); _, mx, _, (x, y) = cv2.minMaxLoc(r)
        if mx > best[0]: best = (mx, (g, x, y))
    if best[1] is None: return 0.0
    g, x, y = best[1]; win = old[y:y + g.shape[0], x:x + g.shape[1]]
    d1 = win < np.percentile(win, 12) ; d2 = g < np.percentile(g, 12)
    k = np.ones((7, 7), np.uint8)
    c1 = (d1 & (cv2.dilate(d2.astype(np.uint8), k) > 0)).sum() / max(1, d1.sum())
    c2 = (d2 & (cv2.dilate(d1.astype(np.uint8), k) > 0)).sum() / max(1, d2.sum())
    return float(min(c1, c2))

def enhance(rgb):
    a = np.array(rgb); colour = (a.max(2).astype(int) - a.min(2)).mean() > 12
    ch = [a[:, :, i] for i in range(3)] if colour else [cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)]
    out = []
    for g in ch:
        u = cv2.resize(g, None, fx=FACT, fy=FACT, interpolation=cv2.INTER_LANCZOS4)
        u = cv2.fastNlMeansDenoising(u, None, h=6, templateWindowSize=5, searchWindowSize=15)
        s = cv2.addWeighted(u, 1.8, cv2.GaussianBlur(u, (0, 0), 1.6), -0.8, 0)
        out.append(s)
    s = np.stack(out, 2) if colour else out[0]
    lo, hi = np.percentile(s, 2), np.percentile(s, 97)
    s = np.clip((s.astype(float) - lo) / max(1, hi - lo), 0, 1)
    return Image.fromarray((255 * s ** 0.75).astype(np.uint8))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--pdf-dir', required=True); ap.add_argument('--apply', action='store_true'); ap.add_argument('--sheet')
    args = ap.parse_args()
    s = open(os.path.join(BANK, 'meta.js'), encoding='utf-8').read()
    head, body, tail = s[:s.index('[')], s[s.index('['):s.rindex(']') + 1], s[s.rindex(']') + 1:]
    B = json.loads(body); new = {}; seen = set(); miss = 0; pairs = []
    for q in B:
        pdf = os.path.join(args.pdf_dir, SRC[q['src']])
        for t in q['P'] + [o for o in (q.get('o') or []) if isinstance(o, str)]:
            for h, w, hh in TK.findall(t):
                if h in seen: continue
                seen.add(h); old = bank_gray(h)
                if old.shape[1] / float(w) > 45: continue                  # already re-cut from the vector page (2x)
                cand = []
                for p in range(q['p'], q['ep'] + 1):
                    for bm in page_bitmaps(pdf, p): cand.append((score(old, np.array(bm.convert('L'), dtype=np.uint8)), bm))
                cand.sort(key=lambda c: -c[0])
                hit = cand[0][1] if cand and cand[0][0] >= 0.8 and (len(cand) == 1 or cand[0][0] - cand[1][0] >= 0.1) else None
                if hit is None: miss += 1; continue
                e = enhance(hit); buf = io.BytesIO(); e.save(buf, 'WEBP', lossless=True, method=6)
                new[h] = (hashlib.sha1(buf.getvalue()).hexdigest()[:12], buf.getvalue(), e.height / e.width); pairs.append((h, e))
    print('bank figures: %d, bitmap figures enhanced: %d' % (len(seen), len(new)))
    if args.sheet and pairs:
        rows = []
        for h, e in pairs[:40]:
            o = Image.open(os.path.join(BANK, 'f', h + '.webp')).convert('RGB'); n = e.convert('RGB').resize((o.width, int(o.width * e.height / e.width)))
            c = Image.new('RGB', (o.width * 2 + 10, max(o.height, n.height)), (200, 200, 255)); c.paste(o, (0, 0)); c.paste(n, (o.width + 10, 0)); rows.append(c)
        W = max(r.width for r in rows); cols = 3; colH = [0] * cols; pos = []
        for c in rows:
            k = colH.index(min(colH)); pos.append((k, colH[k])); colH[k] += c.height + 6
        sh = Image.new('RGB', (cols * (W + 6), max(colH)), 'white')
        for c, (k, y) in zip(rows, pos): sh.paste(c, (k * (W + 6), y))
        sh.save(args.sheet)
    if args.apply:
        for h, (nh, data, r) in new.items(): open(os.path.join(BANK, 'f', nh + '.webp'), 'wb').write(data)
        def sub(t):
            def f(m):
                h, w, hh = m.groups()
                return m.group(0) if h not in new else '⟦f:%s:%s:%.3f⟧' % (new[h][0], w, float(w) * new[h][2])
            return TK.sub(f, t)
        for q in B:
            q['P'] = [sub(x) for x in q['P']]
            if q.get('o'): q['o'] = [sub(x) if isinstance(x, str) else x for x in q['o']]
        open(os.path.join(BANK, 'meta.js'), 'w', encoding='utf-8').write(head + json.dumps(B, ensure_ascii=False, separators=(',', ':')) + tail)
        print('wrote bank/meta.js')
if __name__ == '__main__': main()
