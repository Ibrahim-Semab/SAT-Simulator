#!/usr/bin/env python3
"""Find and repair broken figure questions in bank/meta.js.

Why questions break: the text pipeline turns words that sit inside a figure (axis numbers, side lengths, "x°", the
"Note: Figure not drawn to scale." caption) into separate little picture crops, so the same figure shows up as one big
crop plus loose copies/fragments of itself, or a label ends up detached from the drawing.

What this does, per question (all checks are pixel based, so it needs no source PDFs):
  1. A picture that sits on a line of its own and whose ink is already contained in another picture of the same
     question is a duplicate/fragment of it  -> dropped (safe: nothing is lost).
  2. A blank picture on its own line -> dropped.
  3. What cannot be repaired without the source PDF is moved out of meta.js into bank/excluded.json with a reason:
       - text such as "Math output error" (the source site failed to render the maths)
       - a blank or tiny picture inside the text
       - a figure question that still has loose pictures that are not a "Note: ... not drawn to scale." caption
         (axis titles, side lengths, labels or a second crop of the figure that has information the first lacks)
       - a question that cannot be shown without its picture (missing stem, missing options, bad key)
Usage:
  python3 tools/fix_bank.py            # report only
  python3 tools/fix_bank.py --apply    # rewrite bank/meta.js and bank/excluded.json
Needs numpy, opencv-python, pillow, pytesseract (+ tesseract) for the caption check.
"""
import json, os, re, sys
import numpy as np, cv2
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
BANK = os.path.join(HERE, '..', 'bank')
TK = re.compile(r'⟦([if]):([0-9a-f]+):(-?[\d.]+):(-?[\d.]+)⟧')
ALONE = re.compile(r'\s*(⟦[if]:[^⟧]+⟧\s*)+')
COVER = 0.97          # share of a picture's ink that must lie on another picture's ink to call it a duplicate
FIG_EM = 4.0          # inline pictures at least this tall count as a figure
ERR = re.compile(r'math output error|output error', re.I)
CAPTION = re.compile(r'note\W*figures?\s+(is\s+|are\s+)?not\s+drawn\s+to\s+scale', re.I)
# questions whose extra pictures were looked at by hand and are fine as they are (id -> why)
REVIEWED_OK = {}
# broken in ways the pixel checks cannot tell (found by looking at every flagged question) -> reason
FORCE_EXCLUDE = {
    '79340403': 'bar chart y-axis numbers cut off; their digits sit in a separate crop',
    'd3b9c8d8': 'box plot: group labels and a second axis are loose crops, so boxes cannot be matched to groups',
    '25fc031a': 'second histogram is clipped; its axis labels sit in loose crops',
    'e9c5bfb2': 'side labels of the rectangles are cut off and sit in a loose crop',
}

_cache = {}
def load(kind, h):
    key = (kind, h)
    if key not in _cache:
        im = Image.open(os.path.join(BANK, 'm' if kind == 'i' else 'f', h + '.webp')).convert('RGBA')
        bg = Image.new('RGBA', im.size, 'white'); bg.alpha_composite(im)
        _cache[key] = np.array(bg.convert('L'))
    return _cache[key]

def px_per_em(t, g):
    return g.shape[0] / float(t['a']) if t['k'] == 'i' else g.shape[1] / float(t['a'])

def ink(g): return int((g < 170).sum())

def _match(gs, gl):
    """Best position of picture gs inside gl (padded): -> (score, share of gs's ink lying on gl's ink)."""
    if gs.std() < 8: return None
    pad = 40
    gl = cv2.copyMakeBorder(gl, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=255)
    if gs.shape[0] > gl.shape[0] or gs.shape[1] > gl.shape[1]: return None
    r = cv2.matchTemplate(gl, gs, cv2.TM_CCOEFF_NORMED)
    _, mx, _, (x, y) = cv2.minMaxLoc(r)
    ink_s = gs < 170
    ink_l = cv2.dilate((gl < 170).astype(np.uint8), np.ones((3, 3), np.uint8), iterations=2).astype(bool)
    win = ink_l[y:y + gs.shape[0], x:x + gs.shape[1]]
    return mx, float((ink_s & win).sum()) / max(1, int(ink_s.sum()))

def covered(S, L, multiscale=False):
    """How much of picture S is already on picture L: -> (match score, share of S's ink on L's ink) or None.
    S is first scaled to L's resolution from the em sizes in the tokens; with multiscale the scale is also searched,
    because a second crop of a figure is often rendered at a different size."""
    gs0, gl = load(S['k'], S['h']), load(L['k'], L['h'])
    base = px_per_em(L, gl) / px_per_em(S, gs0)
    best = None
    for f in ([1.0] if not multiscale else list(np.geomspace(0.5, 2.0, 31)) + [1.0]):
        sc = base * f
        gs = gs0 if abs(sc - 1) <= 0.02 else cv2.resize(gs0, (max(1, round(gs0.shape[1] * sc)), max(1, round(gs0.shape[0] * sc))), interpolation=cv2.INTER_AREA)
        m = _match(gs, gl)
        if m and (best is None or m[0] > best[0]): best = m
    return best

def tokens(q):
    out = []
    for pi, p in enumerate(q['P']):
        alone = bool(ALONE.fullmatch(p))
        for m in TK.finditer(p):
            k, h, a, b = m.groups()
            out.append(dict(pi=pi, k=k, h=h, a=a, b=b, alone=alone, tok=m.group(0)))
    return out

def is_fig(t): return t['k'] == 'f' or (t['k'] == 'i' and float(t['a']) >= FIG_EM)

def caption_text(t):
    try:
        import pytesseract
        g = load(t['k'], t['h'])
        im = Image.fromarray(g).convert('L'); im = im.resize((im.width * 2, im.height * 2))
        return pytesseract.image_to_string(im, config='--psm 7')
    except Exception:
        return ''

def analyse(q):
    """-> (new paragraph list, list of reasons the question must be excluded)"""
    P = list(q['P']); reasons = []
    texts = P + [q.get('PR') or ''] + [o for o in (q.get('o') or []) if isinstance(o, str)]
    if any(ERR.search(TK.sub('', t)) for t in texts): reasons.append('source text contains "Math output error"')
    toks = tokens(q)
    drop = set()
    # blank pictures
    for t in toks:
        g = load(t['k'], t['h'])
        if ink(g) < 0.002 * g.size:
            if t['alone']: drop.add(t['pi'])
            else: reasons.append('blank picture inside the text (%s)' % t['h'])
        elif min(g.shape) < 6 and not t['alone']: reasons.append('tiny picture inside the text (%s)' % t['h'])
    # duplicates / fragments: loose pictures whose ink is already on another picture of the question
    alone = [t for t in toks if t['alone'] and t['pi'] not in drop]
    alone.sort(key=lambda t: ink(load(t['k'], t['h'])))
    for S in alone:
        if S['pi'] in drop: continue
        for L in toks:
            if L is S or L['pi'] in drop or L['h'] == S['h'] and L['pi'] == S['pi']: continue
            if L['h'] == S['h']: drop.add(S['pi']); break
            c = covered(S, L)
            if c is None or c[0] < 0.6: c = covered(S, L, multiscale=True) if min(load(S['k'], S['h']).shape) >= 100 else None
            if c is not None and c[0] >= 0.6 and c[1] >= COVER: drop.add(S['pi']); break
    P2 = [p for i, p in enumerate(P) if i not in drop]
    q2 = dict(q, P=P2)
    toks2 = tokens(q2)
    # figure questions: what is still loose next to the figure must be a caption, a legend, a table or another graph
    if any(is_fig(t) for t in toks2) and q['id'] not in REVIEWED_OK:
        loose = [t for t in toks2 if t['alone']]
        main = max((t for t in toks2 if is_fig(t)), key=lambda t: load(t['k'], t['h']).size)
        mg = load(main['k'], main['h'])
        for t in loose:
            if t is main or t['h'] == main['h']: continue
            g = load(t['k'], t['h']); h, w = g.shape
            tag = '%s (%dx%d px)' % (t['h'], w, h)
            if h * w < 4500: reasons.append('label detached from the figure: ' + tag); continue
            if h >= 1.8 * w: reasons.append('rotated axis title detached from the figure: ' + tag); continue
            # a figure-sized picture of the other kind (inline vs figure crop) is a second crop of the same drawing:
            # pixel matching cannot align them (different scale and line weight) and each lacks labels the other has
            if t['k'] != main['k'] and 0.4 <= g.size / mg.size <= 2.5 and (is_fig(t) or min(g.shape) >= 300):
                reasons.append('second crop of the figure with labels the first lacks: ' + tag); continue
            if CAPTION.search(caption_text(t)): continue
    if q['id'] in FORCE_EXCLUDE: reasons.append(FORCE_EXCLUDE[q['id']])
    # structural
    if q['m'] == 'MCQ':
        o = q.get('o') or []
        if len(o) != 4 or not all((x or '').strip() for x in o): reasons.append('MCQ without four non-empty choices')
        if str(q['a']).strip().upper() not in 'ABCD' or not str(q['a']).strip(): reasons.append('bad answer key')
    elif not str(q['a']).strip(): reasons.append('no answer key')
    if not any(p.strip() for p in P2): reasons.append('empty stem')
    return P2, len(drop), reasons

def main():
    apply = '--apply' in sys.argv
    s = open(os.path.join(BANK, 'meta.js'), encoding='utf-8').read()
    head, body = s[:s.index('[')], s[s.index('['):s.rindex(']') + 1]
    tail = s[s.rindex(']') + 1:]
    B = json.loads(body)
    keep, excl, dropped = [], [], 0
    for q in B:
        P2, nd, reasons = analyse(q)
        dropped += nd
        if reasons: excl.append(dict(id=q['id'], reason='; '.join(sorted(set(reasons))), entry=q))
        else:
            if nd: q = dict(q, P=P2)
            keep.append(q)
    print('questions %d  fragments dropped %d  excluded %d  kept %d' % (len(B), dropped, len(excl), len(keep)))
    for e in excl: print(' ', e['id'], '-', e['reason'])
    if not apply: print('(report only; use --apply to write)'); return
    exp = os.path.join(BANK, 'excluded.json')
    old = json.load(open(exp, encoding='utf-8')) if os.path.exists(exp) else []
    have = {e['id'] for e in old}
    old += [e for e in excl if e['id'] not in have]
    json.dump(old, open(exp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    with open(os.path.join(BANK, 'meta.js'), 'w', encoding='utf-8') as f:
        f.write(head + json.dumps(keep, ensure_ascii=False, separators=(',', ':')) + tail)
    print('wrote bank/meta.js and bank/excluded.json')

if __name__ == '__main__':
    main()
