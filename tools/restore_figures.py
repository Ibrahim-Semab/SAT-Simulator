#!/usr/bin/env python3
"""Rebuild the figure of questions that tools/fix_bank.py had to park in bank/excluded.json.

The original PDFs are NOT on main: they live on the git branch  add-original-pdfs  (see README.txt, "Original PDFs").
Fetch them first, e.g.
    git fetch origin add-original-pdfs
    mkdir -p /tmp/pdfs && for f in "Math Easy+Medium_compressed.pdf" "Math Hard_compressed.pdf" \
        "Reading & Writing All Q&A_compressed.pdf"; do git show "origin/add-original-pdfs:$f" > "/tmp/pdfs/$f"; done
then run
    python3 tools/restore_figures.py --pdf-dir /tmp/pdfs [--apply]

For each parked question it opens the question's PDF page (bank/meta.js keeps "src" and "p"), finds the figure by
looking for white-space gaps between the stem text and the figure, crops it (with its "Note: Figure not drawn to
scale." caption) as ONE clean picture at twice the bank's usual resolution into bank/f/, replaces the loose pieces
of the old crop in the question text with that picture, and moves the question back into bank/meta.js.
Needs numpy, pillow and poppler (pdftoppm, pdftotext).
"""
import argparse, hashlib, io, json, os, re, subprocess, sys, tempfile
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
BANK = os.path.join(HERE, '..', 'bank')
SRC = {'Math Easy+Medium': 'Math Easy+Medium_compressed.pdf', 'Math Hard': 'Math Hard_compressed.pdf',
       'Reading & Writing': 'Reading & Writing All Q&A_compressed.pdf'}
DPI = 200.8            # twice the 100.4 dpi at which the bank's pictures were made (28.8 px per em there)
EM = 28.8 * 2          # pixels per em at DPI
PAD = 14
TOK_ELL = '⟦i:ELL:0:0⟧'  # placeholder, replaced with the bank's existing "ℓ" picture (see ELL_FROM)
ELL_FROM = ('9d078710', 2)   # paragraph 2 of this question starts "In the figure shown, line ℓ intersects ..."

# id -> (paragraph numbers that are loose pieces of the old figure crop, number of figures to put in their place)
PIECES = {
    '0ea7ef01': ([1, 2, 3], 1), '79340403': ([0, 1, 2], 1), '9d078710': ([0, 1], 1), '4a141e77': ([0, 1], 1),
    '58687a66': ([0, 1], 1), '3b4b5b1e': ([0, 1], 1), 'cab8f907': ([0, 1, 2], 1), 'de9148c4': ([0, 1, 2], 1),
    '36661021': ([0, 1, 2], 1), 'd21270da': ([0, 1], 1), '25fc031a': ([0, 1, 2, 3, 4, 5, 6], 2),
    'ecc98c87': ([0, 1, 2], 1), '659cb706': ([0, 1, 2, 3, 4], 1), 'de550be0': ([0, 1, 2], 1),
    'e9c5bfb2': ([0, 1, 2, 3, 4], 1), '0013adbd': ([0, 1], 1), 'd3b9c8d8': ([0, 1, 2, 3], 1),
    '7b52985c': ([1, 2, 3], 1), '858809e7': ([0, 1, 2], 1),
}
# The source PDFs themselves print "Math output error" where the name of a line should be. In both questions the
# line is labelled ℓ in the figure, so the text is repaired to "line ℓ".
FIX_TEXT = {'58687a66': (2, '▣ Math output error'), '858809e7': (3, '▣ Math output error')}

TK = re.compile(r'⟦([if]):([0-9a-f]+):(-?[\d.]+):(-?[\d.]+)⟧')


def words(pdf, p):
    h = subprocess.run(['pdftotext', '-f', str(p), '-l', str(p), '-bbox', pdf, '-'], capture_output=True, text=True).stdout
    return [(float(a), float(b), float(c), float(d), t) for a, b, c, d, t in
            re.findall(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>', h)]


def render(pdf, p):
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(['pdftoppm', '-f', str(p), '-l', str(p), '-r', str(DPI), '-gray', '-png', pdf, d + '/pg'], check=True)
        f = [x for x in os.listdir(d)][0]
        return np.array(Image.open(os.path.join(d, f)).convert('L'))


def figures(pdf, p):
    """-> list of (y0, y1, x0, x1) pixel boxes, one per figure on the page (caption included)."""
    W = words(pdf, p); a = render(pdf, p); k = DPI / 72
    yq = [w for w in W if w[4] == 'Question' and not any(v[4] == 'ID:' and abs(v[1] - w[1]) < 2 for v in W)]
    ya = sorted([w for w in W if w[4] in ('Answer', 'Correct') and w[0] < 60], key=lambda w: w[1])
    y0, y1 = int(yq[0][3] * k) + 6, int(ya[0][1] * k) - 6
    ink = a < 200
    gap = int(0.21 * DPI)
    rows = ink[y0:y1].any(1); bl = []; i = 0
    while i < len(rows):
        if rows[i]:
            j = last = i
            while j < len(rows) and j - last <= gap:
                if rows[j]: last = j
                j += 1
            bl.append([y0 + i, y0 + last + 1]); i = last + 1
        else: i += 1
    bl = [b for b in bl if b[1] - b[0] > 8]
    def xr(b):
        c = np.where(ink[b[0]:b[1]].any(0))[0]; return int(c[0]), int(c[-1]) + 1
    # the figure may touch the stem text (gap too small): cut at the first row that has ink in the text margin
    margin = min([xr(b)[0] for b in bl if b[1] - b[0] < 90] or [60])
    out = []
    for b in bl:
        x0, x1 = xr(b)
        if b[1] - b[0] > 160 and x1 - x0 > 1400:
            left = ink[b[0]:b[1], :margin + 25].any(1)
            hit = np.where(left)[0]
            if len(hit) and hit[0] > 100:
                # figure and stem line touch: the figure is as wide as its top half, the text line is wider
                h = b[1] - b[0]; top = ink[b[0]:b[0] + h // 2].any(0); cols = np.where(top)[0]; sx0, sx1 = cols[0] - 40, cols[-1] + 40
                outside = np.where(ink[b[0] + h // 2:b[1], :max(sx0, 0)].any(1) | ink[b[0] + h // 2:b[1], sx1:].any(1))[0]
                cut = h // 2 + int(outside[0]) if len(outside) else h
                any_ink = ink[b[0]:b[1]].any(1); k = cut
                while k > 0 and cut - k < 8 and any_ink[k - 1]: k -= 1      # tops of tall characters of the text line
                if k > 0 and not any_ink[k - 1] and cut - k < 8: cut = k
                b = [b[0], b[0] + cut]; x0, x1 = xr(b)
            elif len(hit):          # starts in the text margin: a paragraph (e.g. stem plus I./II./III. lines), not a figure
                b = [b[0], b[0] + 1]
        out.append((b[0], b[1], x0, x1))
    figs = []
    for n, (ya_, yb, xa, xb) in enumerate(out):
        if yb - ya_ >= 150: figs.append([ya_, yb, xa, xb, n])
    for f in figs:   # centred caption right below ("Note: Figure not drawn to scale.")
        n = f[4] + 1
        if n < len(out):
            ya_, yb, xa, xb = out[n]
            if yb - ya_ < 60 and xb - xa < 700 and abs((xa + xb) / 2 - (f[2] + f[3]) / 2) < 60 and not (f[4] + 1 < len(figs) and False):
                f[1] = max(f[1], yb); f[2] = min(f[2], xa); f[3] = max(f[3], xb)
    return a, [tuple(f[:4]) for f in figs]


def save(a, box, outdir):
    y0, y1, x0, x1 = box
    rows = (a < 200).any(1)
    up = max([r for r in range(0, y0) if rows[r]] or [-99]); dn = min([r for r in range(y1, len(rows)) if rows[r]] or [10 ** 9])
    pt, pb = max(0, min(PAD, y0 - up - 2)), max(0, min(PAD, dn - y1 - 2))     # never pull in the neighbouring text line
    crop = a[y0 - pt:y1 + pb, max(0, x0 - PAD):x1 + PAD]
    im = Image.fromarray(crop).convert('L')
    buf = io.BytesIO(); im.save(buf, 'WEBP', lossless=True, method=6); data = buf.getvalue()
    h = hashlib.sha1(data).hexdigest()[:12]
    open(os.path.join(outdir, h + '.webp'), 'wb').write(data)
    return '⟦f:%s:%.3f:%.3f⟧' % (h, im.width / EM, im.height / EM)


def _blocks(a, y0, y1, gap=None):
    """White-space separated blocks of ink between rows y0 and y1: -> [(top, bottom, left, right)]."""
    ink = a < 200; gap = gap or int(0.21 * DPI)
    rows = ink[y0:y1].any(1); out = []; i = 0
    while i < len(rows):
        if rows[i]:
            j = last = i
            while j < len(rows) and j - last <= gap:
                if rows[j]: last = j
                j += 1
            c = np.where(ink[y0 + i:y0 + last + 1].any(0))[0]
            out.append((y0 + i, y0 + last + 1, int(c[0]), int(c[-1]) + 1)); i = last + 1
        else: i += 1
    return [b for b in out if b[1] - b[0] > 8]


def restore_graph_choices(q, pdf, outm, outf):
    """75a32330: two display equations, then four graphs as the answer choices (A-D), spread over three PDF pages.
    The old screenshot cut choice D off, which is why the question was parked. Each graph stands above its letter."""
    EMI = 38.4 * 2 / 2          # inline pictures: 38.4 px per em at 200.8 dpi (the bank's pictures are 2x the screenshots)
    graphs, eqs = [], []
    for pg in range(q['p'], q['ep'] + 1):
        W = words(pdf, pg); a = render(pdf, pg); k = DPI / 72
        stop = sorted([w for w in W if w[4] == 'Correct' and w[0] < 60], key=lambda w: w[1])
        yend = int(stop[0][1] * k) - 6 if stop else a.shape[0] - 6
        if pg == q['p']:
            yq = [w for w in W if w[4] == 'Question' and not any(v[4] == 'ID:' and abs(v[1] - w[1]) < 2 for v in W)]
            ya = sorted([w for w in W if w[4] == 'Answer' and w[0] < 60], key=lambda w: w[1])
            top = _blocks(a, int(yq[0][3] * k) + 6, int(ya[0][1] * k) - 6, gap=int(0.1 * DPI))
            eqs = [(a, b) for b in top[:2]]                      # the two equations; the third block is the stem text
            y0 = int(ya[0][3] * k) + 6
        else: y0 = 6
        graphs += [(a, b) for b in _blocks(a, y0, yend, gap=int(0.1 * DPI)) if b[1] - b[0] > 400]
    if len(graphs) != 4 or len(eqs) != 2: sys.exit('75a32330: found %d graphs and %d equations, expected 4 and 2' % (len(graphs), len(eqs)))
    P = []
    for a, (y0, y1, x0, x1) in eqs:
        ink = a < 200; pad = 6
        crop = a[y0 - pad:y1 + pad, x0 - pad:x1 + pad]
        cols = np.where((crop < 200).any(0))[0]; last = cols[-1]
        c = last
        while c > 0 and (crop[:, c - 6:c + 1] < 200).any(): c -= 1                 # leftmost column of the last character
        rr = np.where((crop[:, c:last + 1] < 200).any(1))[0]; base = int(rr[-1]) + 1  # its bottom is the baseline
        im = Image.fromarray(crop).convert('L'); buf = io.BytesIO(); im.save(buf, 'WEBP', lossless=True, method=6); data = buf.getvalue()
        h = hashlib.sha1(data).hexdigest()[:12]; open(os.path.join(outm, h + '.webp'), 'wb').write(data)
        P.append('⟦i:%s:%.3f:%.3f⟧' % (h, im.height / EMI, -(im.height - base) / EMI))
    return P, [save(a, b, outf) for a, b in graphs]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--pdf-dir', required=True); ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    ex_path = os.path.join(BANK, 'excluded.json'); ex = json.load(open(ex_path, encoding='utf-8'))
    s = open(os.path.join(BANK, 'meta.js'), encoding='utf-8').read()
    head, tail = s[:s.index('[')], s[s.rindex(']') + 1:]; B = json.loads(s[s.index('['):s.rindex(']') + 1])
    by = {q['id']: q for q in B}; by.update({e['id']: e['entry'] for e in ex})
    restored, left = [], []
    for e in ex:
        qid = e['id']
        if qid not in PIECES: left.append(e); continue
        q = dict(e['entry']); idx, nfig = PIECES[qid]
        pdf = os.path.join(args.pdf_dir, SRC[q['src']])
        a, boxes = figures(pdf, q['p'])
        if len(boxes) != nfig: sys.exit('%s: found %d figures on page %s, expected %d' % (qid, len(boxes), q['p'], nfig))
        toks = [save(a, b, BANK + '/f') if args.apply else '⟦f:%s:0:0⟧' % ('0' * 12) for b in boxes]
        P = [p for i, p in enumerate(q['P']) if i not in idx]
        P[idx[0]:idx[0]] = toks if idx[0] <= len(P) else toks
        if qid in FIX_TEXT:
            ell = '⟦%s:%s:%s:%s⟧' % TK.findall(by[ELL_FROM[0]]['P'][ELL_FROM[1]])[0]   # the bank's own picture of "ℓ"
            pi, old = FIX_TEXT[qid]; pi = pi - len([i for i in idx if i < pi]) + len(toks)
            ptxt = P[pi]; m = re.search(r'⟦i:[0-9a-f]+:[\d.]+:-?[\d.]+⟧ Math output error', ptxt)
            if not m: sys.exit('%s: no error text found' % qid)
            P[pi] = ptxt[:m.start()] + ell + ptxt[m.end():]
        q['P'] = P; restored.append(q)
        print(qid, 'restored,', len(boxes), 'figure(s)')
    for e in [e for e in left if e['id'] == '75a32330']:
        q = {k: v for k, v in e['entry'].items() if k not in ('w', 'h', 'P', 'o')}
        if not args.apply: print('75a32330 would be rebuilt (two equations, four graph choices)'); continue
        P, O = restore_graph_choices(q, os.path.join(args.pdf_dir, SRC[q['src']]), BANK + '/m', BANK + '/f')
        q['P'] = P + ['Which graph represents the given system of equations?']; q['o'] = O
        restored.append(q); left.remove(e); print('75a32330 restored, 2 equations + 4 graph choices')
    if not args.apply: print('(report only; use --apply to write)'); return
    keep = B + restored
    with open(os.path.join(BANK, 'meta.js'), 'w', encoding='utf-8') as f:
        f.write(head + json.dumps(keep, ensure_ascii=False, separators=(',', ':')) + tail)
    json.dump(left, open(ex_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('meta.js now has', len(keep), 'questions;', len(left), 'still excluded')


if __name__ == '__main__':
    main()
