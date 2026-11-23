#!/usr/bin/env python3
"""Cut stray neighbour characters off the edges of inline math pictures (bank/m/*.webp).

When the text pipeline cropped an inline expression out of the page screenshot, the crop sometimes caught a sliver
of the character next to it: the comma or full stop after the expression, half of the next letter ("EG a",
"f AB i"). Such a piece is a SEPARATE little cluster of ink that touches the left or right border of the picture.
A genuine character at the edge is joined to the rest of the expression or is as big as it, so it is left alone.

Only pictures up to 140 px tall are looked at (taller ones are inline figures). An edge cluster is removed only if
ALL of these hold:
  * it touches the first or last pixel column (or, if it is only a speck - narrower than 0.2 x the height and under 8%
    of the ink - lies within 3 pixels of it),
  * a blank gap of at least 2 pixel columns separates it from the rest,
  * it is narrower than 0.45 x the picture height,
  * it holds less than 60% as much ink as everything else in the picture,
  * it is shorter than 70% of the typical character height of the rest (it comes from the smaller text font),
  * unless it is a speck (comma, full stop): it sits on the baseline of the other characters (not an exponent or
    subscript) and the picture has at most 6 characters.
The picture is cropped to the remaining columns (height and baseline are unchanged, so the tokens in bank/meta.js stay
valid: the page sizes inline pictures by height).

    python3 tools/trim_inline_fragments.py [--apply] [--sheet before_after.png]
"""
import argparse, io, json, os, re
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
BANK = os.path.join(HERE, '..', 'bank')
TK = re.compile(r'⟦i:([0-9a-f]+):')
THR = 140


def clusters(ink):
    cols = ink.any(0); out = []; i = 0
    while i < len(cols):
        if cols[i]:
            j = i
            while j + 1 < len(cols) and cols[j + 1]: j += 1
            out.append([i, j + 1]); i = j + 1
        else: i += 1
    return out


def plan(g):
    """-> (x0, x1) columns to keep, or None when nothing has to go."""
    ink = g < THR; h = g.shape[0]
    if h > 140: return None                      # an inline figure or diagram, not a formula
    cl = clusters(ink)
    if len(cl) < 2: return None
    area = [int(ink[:, a:b].sum()) for a, b in cl]
    keep = list(range(len(cl)))
    for side in ('l', 'r'):
        if len(keep) < 2: break
        k = keep[0] if side == 'l' else keep[-1]; nxt = keep[1] if side == 'l' else keep[-2]
        a, b = cl[k]; touches = a == 0 if side == 'l' else b == g.shape[1]
        gap = (cl[nxt][0] - b) if side == 'l' else (a - cl[nxt][1])
        rest = sum(area[i] for i in keep if i != k)
        near = a <= 3 if side == 'l' else b >= g.shape[1] - 3       # a tiny speck a pixel or two inside the border
        # a neighbour character comes from the smaller text font: it is visibly shorter than the maths beside it
        # (a bracket or a letter that belongs to the expression is as tall as the rest)
        def ext(x0, x1):
            r = np.where(ink[:, x0:x1].any(1))[0]; return (r[-1] - r[0] + 1) if len(r) else 0
        typical = float(np.median([ext(*cl[i]) for i in keep if i != k]))   # typical height of the other characters
        if ext(a, b) >= 0.7 * typical: continue
        # it must sit on the text baseline like a neighbouring word (exponents float above it, subscripts hang below it)
        rows = lambda x0, x1: np.where(ink[:, x0:x1].any(1))[0]
        base = float(np.median([rows(*cl[i])[-1] for i in keep if i != k])); fb = rows(a, b)[-1]
        speck = (b - a) < 0.2 * h and area[k] < 0.08 * rest
        if speck and fb < base - 0.08 * h: continue                 # a speck floating above the baseline is an exponent
        if not speck and not (base - 0.15 * h <= fb <= base + 0.08 * h): continue
        if not speck and len(cl) > 6: continue   # long expressions: only ever cut specks
        if gap >= 2 and ((touches and (b - a) < 0.45 * h and area[k] < 0.6 * rest) or
                         (near and (b - a) < 0.2 * h and area[k] < 0.08 * rest)): keep.remove(k)
    if len(keep) == len(cl): return None
    return max(0, cl[keep[0]][0] - 2), min(g.shape[1], cl[keep[-1]][1] + 2)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--apply', action='store_true'); ap.add_argument('--sheet')
    args = ap.parse_args()
    s = open(os.path.join(BANK, 'meta.js'), encoding='utf-8').read(); B = json.loads(s[s.index('['):s.rindex(']') + 1])
    used = set()
    for q in B:
        for t in q['P'] + ([q['PR']] if q.get('PR') else []) + [o for o in (q.get('o') or []) if isinstance(o, str)]:
            used.update(TK.findall(t))
    changed = []
    for h in sorted(used):
        path = os.path.join(BANK, 'm', h + '.webp'); im = Image.open(path); im.load()
        rgba = im.convert('RGBA'); bg = Image.new('RGBA', rgba.size, 'white'); bg.alpha_composite(rgba)
        g = np.array(bg.convert('L')); r = plan(g)
        if r is None: continue
        x0, x1 = r; new = im.crop((x0, 0, x1, im.height)); changed.append((h, im, new, (x0, im.width - x1)))
        if args.apply:
            buf = io.BytesIO(); new.save(buf, 'WEBP', lossless=True, method=6); open(path, 'wb').write(buf.getvalue())
    print('inline pictures in use: %d, trimmed: %d%s' % (len(used), len(changed), '' if args.apply else ' (report only; use --apply)'))
    if args.sheet and changed:
        import random; random.seed(1); pick = random.sample(changed, min(60, len(changed)))
        rows = []
        for h, old, new, cut in pick:
            def fl(i):
                r = i.convert('RGBA'); b = Image.new('RGBA', r.size, 'white'); b.alpha_composite(r); return b.convert('RGB')
            a, b = fl(old), fl(new); c = Image.new('RGB', (a.width + b.width + 30, a.height), (200, 200, 255)); c.paste(a, (0, 0)); c.paste(b, (a.width + 30, 0)); rows.append(c)
        cols = 3; W = max(r.width for r in rows) + 10; colH = [0] * cols; pos = []
        for c in rows:
            k = colH.index(min(colH)); pos.append((k, colH[k])); colH[k] += c.height + 6
        sh = Image.new('RGB', (cols * W, max(colH)), 'white')
        for c, (k, y) in zip(rows, pos): sh.paste(c, (k * W, y))
        sh.save(args.sheet)


if __name__ == '__main__':
    main()
