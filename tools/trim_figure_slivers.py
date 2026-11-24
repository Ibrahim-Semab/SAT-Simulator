#!/usr/bin/env python3
"""Cut stray slivers off the top/bottom of figure pictures (bank/f/*.webp).

A figure crop sometimes catches the top edge of the next block on the page (e.g. the border of the next answer
table), which shows as a few specks floating far below the figure. A sliver is removed only if it is at most 4 px tall,
holds under 0.5% of the ink and is separated from the figure by a blank gap of at least 30 px. The image is cropped
(6 px margin kept) and the height in the tokens of bank/meta.js is scaled to match.

    python3 tools/trim_figure_slivers.py [--apply]
"""
import io, json, os, re, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); BANK = os.path.join(HERE, '..', 'bank')
TK = re.compile(r'⟦f:([0-9a-f]+):(-?[\d.]+):(-?[\d.]+)⟧')
APPLY = '--apply' in sys.argv; done = {}

def plan(h):
    if h in done: return done[h]
    im = Image.open(os.path.join(BANK, 'f', h + '.webp')); im.load()
    r = im.convert('RGBA'); b = Image.new('RGBA', r.size, 'white'); b.alpha_composite(r)
    ink = np.array(b.convert('L')) < 150; rows = ink.any(1); grp = []; i = 0
    while i < len(rows):
        if rows[i]:
            j = i
            while j + 1 < len(rows) and rows[j + 1]: j += 1
            grp.append((i, j + 1)); i = j + 1
        else: i += 1
    res = None; tot = ink.sum(); n0 = len(grp)
    small = lambda g: g[1] - g[0] <= 4 and ink[g[0]:g[1]].sum() < 0.005 * tot
    while len(grp) >= 2 and small(grp[-1]) and grp[-1][0] - grp[-2][1] >= 30: grp.pop()
    while len(grp) >= 2 and small(grp[0]) and grp[1][0] - grp[0][1] >= 30: grp.pop(0)
    if len(grp) < n0:
        y0, y1 = max(0, grp[0][0] - 6), min(im.height, grp[-1][1] + 6); res = (y0, y1, im.height)
        if APPLY:
            buf = io.BytesIO(); im.crop((0, y0, im.width, y1)).save(buf, 'WEBP', lossless=True, method=6)
            open(os.path.join(BANK, 'f', h + '.webp'), 'wb').write(buf.getvalue())
    done[h] = res; return res

def fix(t):
    def f(m):
        h, w, hh = m.groups(); r = plan(h)
        return m.group(0) if not r else '⟦f:%s:%s:%s⟧' % (h, w, round(float(hh) * (r[1] - r[0]) / r[2], 3))
    return TK.sub(f, t)

s = open(os.path.join(BANK, 'meta.js'), encoding='utf-8').read()
head, body, tail = s[:s.index('[')], s[s.index('['):s.rindex(']') + 1], s[s.rindex(']') + 1:]
B = json.loads(body)
for q in B:
    q['P'] = [fix(x) for x in q['P']]
    if q.get('PR'): q['PR'] = fix(q['PR'])
    if q.get('o'): q['o'] = [fix(x) if isinstance(x, str) else x for x in q['o']]
print('figures trimmed:', {h: r for h, r in done.items() if r})
if APPLY: open(os.path.join(BANK, 'meta.js'), 'w', encoding='utf-8').write(head + json.dumps(B, ensure_ascii=False, separators=(',', ':')) + tail)
else: print('(report only; use --apply)')
