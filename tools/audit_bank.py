#!/usr/bin/env python3
"""Extraction quality check for bank/meta.js (run from anywhere: python3 tools/audit_bank.py).

Every picture crop the app shows is a rectangle [y0,y1,x0,x1] cut from bank/q/<id>.webp.
This flags crops that would render incomplete or clipped, so they are fixed before they
reach a student:
  tiny   - narrower than 6px or shorter than 8px (nothing readable in it)
  oob    - extends past the screenshot
  blank  - almost no ink
  left   - an answer-choice crop with answer ink to its left (the first glyphs were cut off)
  right  - an answer-choice crop with ink just past its right edge (the end of the answer was cut off)
Exit status is 1 when anything is flagged, so it can gate a build.   --list prints every hit.
"""
import json, re, sys, collections, os
import numpy as np
from PIL import Image

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
MK = re.compile(r'\[\[(\d+),(\d+),(\d+),(\d+)\]\]')
LABEL_X = 42            # the 'A.'-'D.' label ends by x=36; answer text starts at x=39..41 in the 853px screenshots

def load_bank(path=None):
    s = open(path or os.path.join(ROOT, 'bank', 'meta.js'), encoding='utf-8').read()
    return json.loads(s[s.index('['):s.rindex(']') + 1])

def crops(q, W):
    """Yield (kind, label, [y0,y1,x0,x1]) for every picture crop in a question."""
    for i, o in enumerate(q.get('o') or []):
        if isinstance(o, list): yield 'opt', 'ABCD'[i], o
        elif isinstance(o, str):
            for m in MK.finditer(o): yield 'optinline', 'ABCD'[i], [int(x) for x in m.groups()]
    for p in (q.get('P') or []) + [q.get('PR') or '']:
        for m in MK.finditer(p): yield 'stem', '', [int(x) for x in m.groups()]
    for k in ('si', 'fg'):
        if q.get(k): yield k, '', [q[k][0], q[k][1], 18, W - 14]

def audit(bank, bank_dir=None):
    bank_dir = bank_dir or os.path.join(ROOT, 'bank', 'q')
    hits = collections.defaultdict(list)
    for q in bank:
        g = np.array(Image.open(os.path.join(bank_dir, q['id'] + '.webp')).convert('L'))
        H, W = g.shape
        for kind, lab, r in crops(q, W):
            y0, y1, x0, x1 = r
            tag = (q['id'], kind + lab, r)
            if x1 - x0 < 6 or y1 - y0 < 8: hits['tiny'].append(tag); continue
            if y1 > H or x1 > W or y0 < 0 or x0 < 0: hits['oob'].append(tag); continue
            reg = g[y0:y1, x0:x1]
            if (reg < 180).mean() < 0.004: hits['blank'].append(tag); continue
            if kind == 'opt' and x0 > LABEL_X and (g[y0:y1, LABEL_X - 5:x0 - 1] < 180).any():
                hits['left'].append(tag)      # answer ink exists to the left of the crop: first glyphs cut off
            if kind == 'opt' and (g[y0:y1, x1:x1 + 3] < 150).any() and x1 < W - 3:
                hits['right'].append(tag)     # answer ink continues past the crop: its end was cut off
    return hits

if __name__ == '__main__':
    bank = load_bank()
    hits = audit(bank)
    ids = {t[0] for v in hits.values() for t in v}
    print('%d questions, %d with problems · %s' % (len(bank), len(ids),
          ', '.join('%s %d' % (k, len(v)) for k, v in sorted(hits.items())) or 'clean'))
    if '--list' in sys.argv:
        for k, v in sorted(hits.items()):
            for t in v: print(k, *t)
    sys.exit(1 if hits else 0)
