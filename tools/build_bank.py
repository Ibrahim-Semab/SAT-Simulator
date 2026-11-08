#!/usr/bin/env python3
"""
Build the question bank used by index.html.

Input  : the original single-file simulator (.html with `const DB={...}`) or a JSON file
         with the same shape: {"modules": {"<name>": [ {id, subject, answer, domain, skill,
         difficulty, mode, question_img(base64 jpeg), rationale_img(base64 jpeg)} ... ]}}
         Several inputs can be given; questions are de-duplicated by id.
Output : bank/meta.js        (window.BANK = [...])
         bank/q/<id>.webp    (cleaned question image)
         bank/r/<id>.webp    (rationale image)

Each question image is a screenshot with a "Question" heading, the stem, an "Answer" heading
and the A-D choices. The script finds those parts so the app can lay them out like Bluebook
(passage left, prompt + choices right). Anything it cannot split cleanly is flagged split=false
and the app falls back to showing the whole image.

Usage: python3 tools/build_bank.py INPUT [INPUT ...] [--out bank]
"""
import argparse, base64, io, json, os, re, sys
import numpy as np
from PIL import Image

def decode(b64):
    return Image.open(io.BytesIO(base64.b64decode(b64))).convert('RGB')

def line_bands(gray, thr=200, merge_gap=4):
    ink = gray < thr
    rows = ink.any(axis=1)
    bands, s = [], None
    for y, v in enumerate(rows):
        if v and s is None: s = y
        if not v and s is not None: bands.append([s, y]); s = None
    if s is not None: bands.append([s, len(rows)])
    merged = []
    for b in bands:
        if merged and b[0] - merged[-1][1] < merge_gap: merged[-1][1] = b[1]
        else: merged.append(b)
    out = []
    for s, e in merged:
        cols = np.where(ink[s:e].any(axis=0))[0]
        out.append((s, e, int(cols[0]), int(cols[-1])))
    return out

def blocks_of(lines, gap=15):
    B = [[lines[0]]]
    for l in lines[1:]:
        if l[0] - B[-1][-1][1] < gap: B[-1].append(l)
        else: B.append([l])
    return B

def clean(im):
    a = np.array(im)
    a[a >= 236] = 255          # flatten JPEG haze around text
    return Image.fromarray(a)

def load_inputs(paths):
    qs = {}
    for p in paths:
        raw = open(p, encoding='utf8').read()
        if p.lower().endswith('.json'):
            db = json.loads(raw)
        else:
            m = re.search(r'^const DB=(\{.*\});?\s*$', raw, re.M)
            if not m: sys.exit('no `const DB=` line in ' + p)
            db = json.loads(m.group(1))
        for mod in db['modules'].values():
            for q in mod: qs.setdefault(q['id'], q)
    return list(qs.values())

def make_template(qs):
    """Use the first MCQ image: its 'Answer' heading is the narrow line preceding the choices."""
    for q in qs:
        if q['mode'] != 'MCQ': continue
        g = np.array(decode(q['question_img']).convert('L'))
        L = line_bands(g)
        B = blocks_of(L)
        if len(B) >= 5 and len(B[-4]) >= 2:
            s, e, x0, x1 = B[-4][0]
            if x1 - x0 < 80:
                return g[s:e, x0:x1 + 1].astype(int)
    sys.exit('could not derive the "Answer" heading template')

def is_answer_heading(g, line, tpl):
    """Same size as the template and the ink masks overlap (tolerating a 1px shift)."""
    s, e, x0, x1 = line
    th, tw = tpl.shape
    if abs((e - s) - th) > 1 or abs((x1 - x0 + 1) - tw) > 1 or x0 > 12: return False
    tm = tpl < 160
    best = 0
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            ys, xs = s + dy, x0 + dx
            if ys < 0 or xs < 0: continue
            crop = g[ys:ys + th, xs:xs + tw]
            if crop.shape != tpl.shape: continue
            cm = crop < 160
            union = (cm | tm).sum()
            if union: best = max(best, (cm & tm).sum() / union)
    return best > 0.55

def analyse(q, tpl):
    im = decode(q['question_img'])
    g = np.array(im.convert('L'))
    H, W = g.shape
    L = line_bands(g)
    res = {'w': W, 'h': H, 'split': False}
    if len(L) < 2: return im, res
    body = L[1:]                                  # drop the "Question" heading line
    if q['mode'] == 'SPR':
        res.update(split=True, stem=[max(0, body[0][0] - 3), min(H, body[-1][1] + 3)])
        return im, res
    ai = next((i for i, l in enumerate(body) if is_answer_heading(g, l, tpl)), None)
    if ai is None or ai == 0: return im, res
    stem, ch = body[:ai], body[ai + 1:]
    starts = [l for l in ch if l[2] <= 12]
    if len(starts) != 4: return im, res
    tops = [l[0] for l in starts]
    rects = []
    for i, t in enumerate(tops):
        nxt = tops[i + 1] if i < 3 else 10 ** 9
        mine = [l for l in ch if t <= l[0] < nxt]
        rects.append([max(0, t - 4), min(H, mine[-1][1] + 4), 21, min(W, max(l[3] for l in mine) + 8)])
    res['choices'] = rects
    if q['subject'].startswith('Read'):
        B = blocks_of(stem)
        if len(B) >= 2:
            pa, pr = B[:-1], B[-1]
            res['stem'] = [max(0, pa[0][0][0] - 3), pa[-1][-1][1] + 3]
            res['prompt'] = [pr[0][0] - 3, pr[-1][1] + 3]
        else:
            res['stem'] = [max(0, stem[0][0] - 3), stem[-1][1] + 3]
    else:
        res['stem'] = [max(0, stem[0][0] - 3), stem[-1][1] + 3]
    res['split'] = True
    return im, res

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('inputs', nargs='+')
    ap.add_argument('--out', default='bank')
    a = ap.parse_args()
    qs = load_inputs(a.inputs)
    tpl = make_template(qs)
    os.makedirs(os.path.join(a.out, 'q'), exist_ok=True)
    os.makedirs(os.path.join(a.out, 'r'), exist_ok=True)
    meta, unsplit = [], []
    for q in qs:
        im, r = analyse(q, tpl)
        clean(im).save(os.path.join(a.out, 'q', q['id'] + '.webp'), 'WEBP', lossless=True, quality=60, method=1)
        clean(decode(q['rationale_img'])).save(os.path.join(a.out, 'r', q['id'] + '.webp'), 'WEBP', lossless=True, quality=60, method=1)
        r.update(id=q['id'], s='rw' if q['subject'].startswith('Read') else 'math',
                 a=q['answer'], d=q['domain'], k=q['skill'], l=q['difficulty'][0], m=q['mode'])
        if not r['split']: unsplit.append(q['id'])
        meta.append(r)
    with open(os.path.join(a.out, 'meta.js'), 'w', encoding='utf8') as f:
        f.write('window.BANK=' + json.dumps(meta, separators=(',', ':')) + ';\n')
    print(f'{len(meta)} questions written; {len(unsplit)} not split: {unsplit}')

if __name__ == '__main__':
    main()
