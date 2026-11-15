#!/usr/bin/env python3
"""Step 3 - rebuild every question (stem, answer choices, figures) from the original PDFs.

  python3 build_questions.py --pages PAGES_DIR --pdfs PDF_DIR --out ../../bank --src rw|em|hard --json out.json
  python3 build_questions.py --merge a.json b.json c.json --out ../../bank      # writes the new fields into bank/meta.js

What the PDF gives us (see extract.py): real text runs, drawn shapes / pictures in reading order, and the page
itself.  For each question this script
  * cuts the page into stem (between the 'Question' and 'Answer' headings) and answer choices (A-D),
  * turns every table / graph / picture into one crisp figure image rendered straight from the PDF page,
  * turns every inline equation into a small transparent picture (same as the explanations),
  * keeps all words as text, with underlines, bullets, 'Text 1' / 'Text 2' headings recovered.
Output per question:  P (paragraph strings), PR (prompt string or null), U (underline ranges), o (choice strings).
Picture tokens inside strings:   ⟦i:HASH:HEIGHT_EM:VALIGN_EM⟧  inline equation   ⟦f:HASH:WIDTH_EM:HEIGHT_EM⟧  figure
"""
import argparse, gc, html, json, os, re, sys
import numpy as np
from PIL import Image
import pypdfium2 as pdfium
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flow, render
from render import PageRaster
from build_rationales import DOCS, question_pages

BODY = flow.BODY_PT
FIG_SCALE = 3.0           # figures are cut from the 4x page render and stored at 3x (about 216 dpi)
THIN = 1.3
SUP = str.maketrans('0123456789+-−', '⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁻')
SUB = str.maketrans('0123456789+-−', '₀₁₂₃₄₅₆₇₈₉₊₋₋')

def fnum(x): return ('%.3f' % x).rstrip('0').rstrip('.')

def ycen(e): return e[3] if e[0] == 't' else (e[2] + e[4]) / 2

# ───────────── regions ─────────────
def split_regions(pages, nums):
    """-> (stem, opts, correct): stem / opts are lists of (page_no, entries)."""
    stem, opts, correct = [], [], None; state = 'pre'
    for k, n in enumerate(nums):
        seq = pages[n]['seq']; qy = ay = cy = None
        for e in seq:
            if e[0] != 't' or e[2] > 26: continue
            t = e[1].strip()
            if t == 'Question' and k == 0 and qy is None: qy = e[3]
            elif t == 'Answer' and ay is None and cy is None: ay = e[3]
            elif (t.startswith('Correct Answer') or t == 'Rationale') and cy is None:
                cy = e[3]; m = re.search(r'Correct Answer:\s*(.*)', t)
                correct = (m.group(1).strip() if m else None) or correct
        if k == 0:
            if qy is None: return None
            state = 'stem'; lo = qy + 3
        else: lo = 20
        if state == 'stem':
            end = ay if ay is not None else cy
            hi = end - 8 if end is not None else 1e9
            stem.append((n, [e for e in seq if lo < ycen(e) < hi]))
            if ay is not None: state = 'opts'; lo2 = ay + 3
            elif cy is not None: state = 'done'
        if state == 'opts':
            hi = cy - 8 if cy is not None else 1e9
            lo2 = lo2 if ay is not None else lo
            opts.append((n, [e for e in seq if lo2 < ycen(e) < hi]))
            if cy is not None: state = 'done'
        if state == 'done': break
    return stem, opts, correct

# ───────────── figures ─────────────
def clusters(ms, grow=2.0):
    """Union-find over drawn shapes that touch (bbox grown by `grow`)."""
    n = len(ms); par = list(range(n))
    def f(i):
        while par[i] != i: par[i] = par[par[i]]; i = par[i]
        return i
    order = sorted(range(n), key=lambda i: ms[i][1])
    for a in range(n):
        i = order[a]
        for b in range(a + 1, n):
            j = order[b]
            if ms[j][1] > ms[i][3] + grow + 400: break
            if ms[j][1] - grow <= ms[i][3] + 0 and ms[i][1] - grow <= ms[j][3] and ms[j][2] - grow <= ms[i][4] and ms[i][2] - grow <= ms[j][4]:
                par[f(i)] = f(j)
    out = {}
    for i in range(n): out.setdefault(f(i), []).append(ms[i])
    return list(out.values())

def is_thin(m): return min(m[3] - m[1], m[4] - m[2]) <= THIN and max(m[3] - m[1], m[4] - m[2]) >= 12

def find_figures(entries):
    """-> figures [{'box':(x0,y0,x1,y1)}], plus the entries that are not part of any figure."""
    ms = [e for e in entries if e[0] == 'm' and not (e[3] - e[1] <= 4.5 and e[4] - e[2] <= 4.5)]
    figs = []
    # a big picture is a figure on its own (never merged with the equation pictures that touch it)
    for m in ms:
        if m[5] == 'i' and (m[3] - m[1]) >= 55 and (m[4] - m[2]) >= 50: figs.append([m[1], m[2], m[3], m[4]])
    # drawn vector shapes: a ruled grid is a table, a big tangle of paths is a graph
    for comp in clusters([m for m in ms if m[5] == 'p']):
        x0 = min(m[1] for m in comp); y0 = min(m[2] for m in comp); x1 = max(m[3] for m in comp); y1 = max(m[4] for m in comp)
        w, h = x1 - x0, y1 - y0
        hor = sum(1 for m in comp if is_thin(m) and m[3] - m[1] >= m[4] - m[2]); ver = sum(1 for m in comp if is_thin(m) and m[4] - m[2] > m[3] - m[1])
        if (hor >= 2 and ver >= 2 and w >= 40 and h >= 20) or (w >= 90 and h >= 70 and len(comp) >= 6): figs.append([x0, y0, x1, y1])
    # figures drawn side by side on the same rows are one figure
    merged = True
    while merged:
        merged = False
        for i in range(len(figs)):
            for j in range(i + 1, len(figs)):
                a, b = figs[i], figs[j]
                ov = min(a[3], b[3]) - max(a[1], b[1])
                if ov > 0.5 * min(a[3] - a[1], b[3] - b[1]) and (a[2] - 40 < b[2]) and (b[0] - 40 < a[2]) \
                        or (min(a[2], b[2]) - max(a[0], b[0]) > 0 and max(a[1], b[1]) - min(a[3], b[3]) < 6):
                    figs[i] = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]; del figs[j]; merged = True; break
            if merged: break
    # absorb the labels that belong to a figure: a title hugging it, short indented lines around it (axis labels, legends)
    texts = [e for e in entries if e[0] == 't' and e[1].strip()]
    def line_of(e): return [t for t in texts if abs(t[3] - e[3]) <= 3]
    out = []
    def gap(e, f):
        dx = max(f[0] - e[4], e[2] - f[2], 0); dy = max(f[1] - e[3], e[3] - 9 - f[3], 0); return dx + dy
    for fb in figs:
        x0, y0, x1, y1 = fb; labels = []
        def inside(e): return x0 - 3 <= e[2] and e[4] <= x1 + 3 and y0 - 2 <= e[3] - 6 and e[3] <= y1 + 2
        for e in texts:
            if inside(e): continue
            ln = line_of(e); lx0 = min(t[2] for t in ln); lx1 = max(t[4] for t in ln)
            near_above = y0 - 22 <= e[3] <= y0 + 1 and lx0 >= 40
            label = lx0 >= 40 and lx1 - lx0 <= 150 and x0 - 90 <= e[2] and e[4] <= x1 + 70 and y0 - 30 <= e[3] <= y1 + 150
            if any(in_box(e, f2) for f2 in figs if f2 is not fb): continue
            if (near_above or label) and all(gap(e, fb) <= gap(e, f2) for f2 in figs if f2 is not fb): labels.append(e)
        for e in labels:
            x0 = min(x0, e[2]); x1 = max(x1, e[4]); y0 = min(y0, e[3] - 9); y1 = max(y1, e[3] + 3)
        # loose drawn pieces next to the labels (legend swatches, arrows) belong to the figure too, unless they sit on a text line
        extras = []
        body = [t for t in texts if t not in labels and not any(in_box(t, f2) for f2 in figs)]
        for m in entries:
            if m[0] != 'm' or in_box(m, fb) or any(in_box(m, f2) for f2 in figs if f2 is not fb): continue
            if not (x0 - 6 <= m[3] and m[1] <= x1 + 6 and y0 - 6 <= m[4] and m[2] <= y1 + 6): continue
            cy = (m[2] + m[4]) / 2
            if any(abs(t[3] - 3 - cy) <= 7 for t in body): continue
            extras.append(m)
        for m in extras: x0 = min(x0, m[1]); x1 = max(x1, m[3]); y0 = min(y0, m[2]); y1 = max(y1, m[4])
        out.append({'core': fb, 'box': [x0, y0, x1, y1], 'labels': labels + extras})
    return out

def in_box(e, fb, pad=2.0):
    x0, y0, x1, y1 = fb
    if e[0] == 't': return x0 - pad <= e[2] and e[4] <= x1 + pad and y0 - pad <= e[3] - 6 and e[3] <= y1 + pad
    return x0 - pad <= e[1] and e[3] <= x1 + pad and y0 - pad <= e[2] and e[4] <= y1 + pad

def render_figure(pr, fig, page_entries, out_dir, others=()):
    """Render the figure from the page at 4x, white out everything that is not part of it, trim to its ink, store at 3x."""
    x0, y0, x1, y1 = fig['box']; S = render.SCALE
    wx0, wy0, wx1, wy1 = max(0, x0 - 90), max(0, y0 - 30), min(pr.W, x1 + 70), min(pr.H, y1 + 150)
    own = {id(e) for e in fig['labels']}
    img = pr.rgb().crop((int(wx0 * S), int(wy0 * S), int(wx1 * S), int(wy1 * S))).copy()
    px = img.load(); W_, H_ = img.size
    def white(rx0, ry0, rx1, ry1):
        a = max(0, int((rx0 - wx0) * S)); b = max(0, int((ry0 - wy0) * S)); c = min(W_, int((rx1 - wx0) * S) + 1); d = min(H_, int((ry1 - wy0) * S) + 1)
        if c > a and d > b: img.paste((255, 255, 255), (a, b, c, d))
    # the page text lines that are not part of the figure, and the other drawn pieces outside it
    for e in page_entries:
        if id(e) in own or in_box(e, fig['core'], 2.0): continue
        if e[0] == 't': white(e[2] - 0.6, e[3] - 8.2, e[4] + 0.6, e[3] + 2.6)
        else: white(e[1] - 0.4, e[2] - 0.4, e[3] + 0.4, e[4] + 0.4)
    for ob in others:                                   # neighbouring figures are masked as a whole
        white(ob[0] + 0.5, ob[1] - 5, ob[2] - 0.5, ob[3] - 0.5)
    arr = np.asarray(img).min(axis=2)
    ys, xs = np.where(arr < 243)
    if len(xs) == 0: ys, xs = np.array([0, H_ - 1]), np.array([0, W_ - 1])
    P = int(2.0 * S)
    cx0, cx1 = max(0, xs.min() - P), min(W_, xs.max() + P + 1); cy0, cy1 = max(0, ys.min() - P), min(H_, ys.max() + P + 1)
    im = img.crop((cx0, cy0, cx1, cy1))
    w, h = im.size
    im = im.resize((max(1, int(round(w * FIG_SCALE / S))), max(1, int(round(h * FIG_SCALE / S)))), Image.LANCZOS)
    import hashlib
    key = hashlib.sha1(im.tobytes() + repr(im.size).encode()).hexdigest()[:12]
    path = os.path.join(out_dir, key + '.webp')
    if not os.path.exists(path): im.save(path, quality=88, method=6)
    return key, w / S, h / S, wy0 + cy0 / S

# ───────────── text assembly ─────────────
def clean(t): return t.replace('\x02', '-').replace('\xa0', ' ').replace('‑', '-')

def build_blocks(entries, page, mdir, fdir, page_entries=None, want_figs=True):
    """One region of one page -> list of blocks in reading order:
       {'k':'p','text':str,'ul':[(s,e)],'bullet':bool,'top':y} | {'k':'f','tok':str,'top':y}"""
    page_entries = page_entries if page_entries is not None else entries
    figs = find_figures(entries) if want_figs else []
    gone = {id(e) for fg in figs for e in fg['labels']}
    rest = [e for e in entries if id(e) not in gone and not any(in_box(e, fg['core']) for fg in figs)]
    # bullets (small dots) and underlines (thin horizontal rules under text)
    bullets, rules, keep = [], [], []
    for e in rest:
        if e[0] == 'm' and e[5] == 'p':
            w, h = e[3] - e[1], e[4] - e[2]
            if w <= 4.5 and h <= 4.5: bullets.append(e); continue
            if h <= 1.6 and w >= 6: rules.append(e); continue
        keep.append(e)
    rules.sort(key=lambda r: (round(r[2]), r[1])); mr = []
    for r in rules:
        if mr and abs(mr[-1][2] - r[2]) < 0.8 and r[1] - mr[-1][3] <= 2.5: mr[-1] = [mr[-1][0], mr[-1][1], mr[-1][2], max(mr[-1][3], r[3]), mr[-1][4], 'p']
        else: mr.append(list(r))
    rules = mr
    tks = flow.tokens(keep, -1)
    lines = flow.lines_of(tks)
    blocks = []
    for para in flow.paragraphs(lines):
        # split a paragraph at bullet lines
        groups = []
        for l in para:
            first = next((i for i in l['items'] if i['k'] == 't' and i['t'].strip()), None)
            isb = bool(first) and any(abs((b[2] + b[4]) / 2 - l['base'] + 3.5) <= 6 and b[3] <= first['x0'] + 1 and first['x0'] - b[3] < 20 for b in bullets)
            if isb or not groups or (groups[-1]['bullet'] and not isb and first and first['x0'] < 40): groups.append({'bullet': isb, 'lines': [l]})
            else: groups[-1]['lines'].append(l)
        for g in groups: blocks.append(para_block(g['lines'], g['bullet'], rules, page, mdir))
    for fg in figs:
        key, wpt, hpt, top = render_figure(page, fg, page_entries, fdir, [o['box'] for o in figs if o is not fg])
        blocks.append({'k': 'f', 'tok': '⟦f:%s:%s:%s⟧' % (key, fnum(wpt / BODY), fnum(hpt / BODY)), 'top': fg['box'][1]})
    blocks.sort(key=lambda b: b['top'])
    return blocks

def underlined(it, rules):
    for r in rules:
        if 0.2 <= r[2] - it['y'] <= 4.8 and r[1] <= it['x0'] + 1.5 and r[3] >= it['x1'] - 1.5: return True
    return False

def para_block(lines, bullet, rules, page, mdir):
    s = ''; ul = []
    def add(txt, u=False):
        nonlocal s
        if not txt: return
        if u: ul.append([len(s), len(s) + len(txt)])
        s += txt
    for li, l in enumerate(lines):
        if li and s and not s.endswith((' ', '-', '—', '–')): s += ' '
        prev = None
        for it in l['items']:
            if it['k'] == 't':
                raw = clean(it['t']); dy = it['y'] - l['base']
                sub = 1.2 < abs(dy) <= 4.6 and raw.strip().isalnum()
                piece = raw
                if sub:
                    tab = SUB if dy > 0 else SUP; core = raw.strip()
                    piece = core.translate(tab) if all(ord(c) in tab for c in core) else '<%s>%s</%s>' % ('sub' if dy > 0 else 'sup', core, 'sub' if dy > 0 else 'sup')
                    if raw[-1:].isspace(): piece += ' '
                if prev is not None and prev['k'] == 'm' and not raw[:1].isspace() and not raw[:1] in ',.;:)]}?!’\'' and not s.endswith(' '): s += ' '
                add(piece, underlined(it, rules) and bool(raw.strip()))
            else:
                key, wpt, hpt, (t, b) = render.render_piece(page, (it['x0'], it['y0'], it['x1'], it['y1']), mdir)
                if prev is not None and not s.endswith((' ', '(', '[', '{', '$', '“', '‘', '-', '−', '/')) and s: s += ' '
                add('⟦i:%s:%s:%s⟧' % (key, fnum(hpt / BODY), fnum(-(b - l['base']) / BODY)))
            prev = it
    # tidy spaces but keep underline offsets valid: collapse only outside underlined ranges
    top = lines[0]['top']
    t = s.strip()
    lead = len(s) - len(s.lstrip())
    ul = [[max(0, a - lead), max(0, b - lead)] for a, b in ul]
    return {'k': 'p', 'text': t, 'ul': ul, 'bullet': bullet, 'top': top}

def collapse(s, ul):
    """Collapse double spaces, adjusting underline ranges."""
    out = []; mp = []
    for i, ch in enumerate(s):
        if ch == ' ' and out and out[-1] == ' ': mp.append(len(out) - 1); continue
        mp.append(len(out)); out.append(ch)
    mp.append(len(out))
    return ''.join(out), [[mp[min(a, len(s))], mp[min(b, len(s))]] for a, b in ul]

# ───────────── options ─────────────
LABEL = re.compile(r'^\s*([A-D])\.\s*$')

def split_options(opt_regions):
    """-> {letter: [(page_no, entries)]}"""
    res = {}; cur = None
    for n, ents in opt_regions:
        pend = {}
        order = [(e, i) for i, e in enumerate(ents)]
        labels = [(i, LABEL.match(e[1]).group(1)) for e, i in order if e[0] == 't' and e[2] < 26 and LABEL.match(e[1])]
        bounds = [i for i, _ in labels] + [len(ents)]
        if cur and (not labels or labels[0][0] > 0):
            res.setdefault(cur, []).append((n, ents[:labels[0][0] if labels else len(ents)]))
        for k, (i, L) in enumerate(labels):
            cur = L
            res.setdefault(L, []).append((n, ents[i + 1:bounds[k + 1]]))
    return res

def option_string(parts, pages_raster, mdir, fdir, pages):
    texts = []
    for n, ents in parts:
        if not ents: continue
        blocks = build_blocks(ents, pages_raster[n], mdir, fdir, pages[n]['seq'])
        for b in blocks: texts.append(b['tok'] if b['k'] == 'f' else b['text'])
    return ' '.join(t for t in texts if t).strip()

# ───────────── question ─────────────
def build_question(qid, q_old, pages, nums, pdf, mdir, fdir):
    r = split_regions(pages, nums)
    if not r: return None, 'no Question heading'
    stem, opts, correct = r
    rasters = {}
    def raster(n):
        if n not in rasters: rasters[n] = PageRaster(pdf[n - 1])
        return rasters[n]
    class Lazy(dict):
        def __missing__(self, n): return raster(n)
    L = Lazy()
    blocks = []
    for n, ents in stem: blocks += build_blocks(ents, L[n], mdir, fdir, pages[n]['seq'])
    paras = []; ul = []
    for b in blocks:
        if b['k'] == 'f': paras.append(b['tok']); continue
        txt, u = collapse(b['text'], b['ul'])
        if not txt: continue
        if re.fullmatch(r'Text [12]', txt): txt = '# ' + txt; u = []
        elif b['bullet']: txt = '• ' + txt; u = [[a + 2, c + 2] for a, c in u]
        mu = []
        for a, c in sorted(u):
            if mu and a - mu[-1][1] <= 1: mu[-1][1] = max(mu[-1][1], c)
            else: mu.append([a, c])
        for a, c in mu: ul.append([len(paras), a, c])
        paras.append(txt)
    o = None
    if opts:
        parts = split_options(opts)
        o = [collapse(option_string(parts.get(c, []), L, mdir, fdir, pages), [])[0] for c in 'ABCD']
    for p in rasters.values(): p.page.close(); p.a = None; p._rgb = None
    return {'P': paras, 'U': ul, 'o': o, 'correct': correct}, None

SRC = None
def build(ids, pages_root, pdf_root, out, progress=True):
    mdir = os.path.join(out, 'm'); fdir = os.path.join(out, 'f'); os.makedirs(mdir, exist_ok=True); os.makedirs(fdir, exist_ok=True)
    meta = open(os.path.join(out, 'meta.js'), encoding='utf-8').read()
    meta = {q['id']: q for q in json.loads(meta[meta.index('['):meta.rindex(']') + 1])}
    ids = ids or list(meta)
    if SRC: ids = [i for i in ids if DOCS[meta[i]['src']][0] == SRC]
    res = {}; problems = []; by_src = {}
    for i in ids: by_src.setdefault(meta[i]['src'], []).append(i)
    for src, group in by_src.items():
        sub, pdfname = DOCS[src]
        pages = flow.load_pages(os.path.join(pages_root, sub)); qp = question_pages(pages)
        pdf = pdfium.PdfDocument(os.path.join(pdf_root, pdfname))
        for k, qid in enumerate(group):
            if qid not in qp: problems.append((qid, 'not found in pdf')); continue
            try: r, err = build_question(qid, meta[qid], pages, qp[qid], pdf, mdir, fdir)
            except Exception as ex: r, err = None, 'error %r' % (ex,)
            if err: problems.append((qid, err)); continue
            res[qid] = r; gc.collect()
            if progress and k % 100 == 0: print(src, k, '/', len(group), flush=True)
    return res, problems

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--pages'); ap.add_argument('--pdfs')
    ap.add_argument('--out', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'bank'))
    ap.add_argument('--ids'); ap.add_argument('--json'); ap.add_argument('--src')
    a = ap.parse_args(); SRC = a.src
    res, problems = build(a.ids.split(',') if a.ids else None, a.pages, a.pdfs, a.out)
    if a.json: json.dump(res, open(a.json, 'w'), ensure_ascii=False, indent=1)
    print(len(res), 'questions;', len(problems), 'problems', problems[:10])
