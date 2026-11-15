#!/usr/bin/env python3
"""Step 4 - fold the PDF-built questions (build_questions.py output) into bank/meta.js.

  python3 assemble_questions.py --out ../../bank q_rw.json q_em.json q_hard.json [--keep-old]

For every question the rebuilt stem / choices replace the old text-plus-screenshot-crops version when they pass
the checks below; a question that fails keeps its old data (and its bank/q screenshot) so nothing is ever worse.
Reading & Writing prompts (PR): the rebuilt paragraph list is split where the old PR text starts.
Writes bank/meta.js and bank/keep_q.json (ids that still need their bank/q/<id>.webp screenshot).
"""
import argparse, collections, json, os, re, sys

TOK = re.compile(r'⟦[^⟧]*⟧|\[\[\d+,\d+,\d+,\d+\]\]|</?su[bp]>')
def words(t): return collections.Counter(re.findall(r"[a-z0-9]+", TOK.sub(' ', t).lower()))
START = re.compile(r'(?:Which (?:choice|finding|quotation|statement|detail|sentence|of the following|option)|Based on the (?:text|texts|data|graph|table|information|passage|notes|poem)|According to (?:the|both) |As used in the text|What (?:does|is|would|will|can)|How (?:does|would|do|did)|Why (?:does|would|is|did)|In (?:the|this) (?:text|context|poem))')

def plain(t): return TOK.sub(' ', t)

def split_prompt(P, U, old_pr):
    """-> (P, PR, U) with the prompt split off the passage."""
    if not old_pr: return P, None, U
    ws = re.findall(r'\w+', old_pr)[:6]
    if not ws: return P, None, U
    rx = re.compile(r'\b' + r'\W+'.join(re.escape(w) for w in ws), re.I)
    for i in range(len(P) - 1, -1, -1):
        if P[i].startswith('# ') or P[i].startswith('⟦f:'): continue
        m = rx.search(P[i])
        if not m: continue
        k = m.start()
        head = P[i][:k].rstrip(); rest = ' '.join([P[i][k:]] + P[i + 1:])
        newP = P[:i] + ([head] if head else [])
        newU = []
        for pi, a, b in U:
            if pi > i or (pi == i and a >= k): continue            # underline inside the prompt: drop (never happens in the bank)
            newU.append([pi, a, min(b, len(head))] if pi == i else [pi, a, b])
        return newP, rest, newU
    return P, None, U

def check(q, new):
    """-> reason string if the rebuilt question must not be used, else None."""
    P, o = new['P'], new['o']
    if not P: return 'empty stem'
    for t in P + (o or []):
        if t.count('⟦') != t.count('⟧'): return 'broken picture token'
    if q['m'] == 'MCQ':
        if not o or len(o) != 4 or any(not x.strip() for x in o): return 'choices'
        if new.get('correct') and new['correct'] != q['a']: return 'answer mismatch'
    elif o: return 'spr with choices'
    old = ' '.join((q.get('P') or []) + [q.get('PR') or ''] + [x for x in (q.get('o') or []) if isinstance(x, str)])
    a = words(old); tot = sum(a.values())
    if tot and not q.get('si'):
        b = words(' '.join(P + (o or [])))
        if sum((a - b).values()) / tot > 0.12: return 'lost words'
    return None

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); ap.add_argument('files', nargs='+')
    a = ap.parse_args()
    mp = os.path.join(a.out, 'meta.js')
    s = open(mp, encoding='utf-8').read(); pre = s[:s.index('[')]; post = s[s.rindex(']') + 1:]
    bank = json.loads(s[s.index('['):s.rindex(']') + 1])
    new = {}
    for f in a.files: new.update(json.load(open(f)))
    keep = []; why = collections.Counter(); out = []
    for q in bank:
        n = new.get(q['id'])
        r = check(q, n) if n else 'not rebuilt'
        if r:
            why[r] += 1; keep.append(q['id']); out.append(q); continue
        P, PR, U = split_prompt(n['P'], n['U'], q.get('PR'))
        if q.get('PR') and PR is None:
            why['prompt not found'] += 1; keep.append(q['id']); out.append(q); continue
        q2 = {k: v for k, v in q.items() if k not in ('P', 'PR', 'U', 'o', 'fg', 'si', 'w', 'h')}
        q2['P'] = P
        if PR: q2['PR'] = PR
        if U: q2['U'] = U
        if n['o']: q2['o'] = n['o']
        out.append(q2)
    open(mp, 'w', encoding='utf-8').write(pre + json.dumps(out, ensure_ascii=False, separators=(',', ':')) + post)
    json.dump(sorted(keep), open(os.path.join(a.out, 'keep_q.json'), 'w'))
    print('rebuilt', len(bank) - len(keep), '| kept old', len(keep), dict(why))
    for i in keep[:20]: print(' keep', i)

if __name__ == '__main__': main()
