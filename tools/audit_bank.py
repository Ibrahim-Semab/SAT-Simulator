#!/usr/bin/env python3
"""Audit bank/meta.js: every MCQ has four non-empty choices, every picture token points at an existing file,
no old screenshot crops are left. Exit code 1 if anything is wrong."""
import json, os, re, sys
bank = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'bank')
s = open(os.path.join(bank, 'meta.js'), encoding='utf-8').read()
B = json.loads(s[s.index('['):s.rindex(']') + 1]); bad = []
for q in B:
    texts = q['P'] + [q.get('PR') or ''] + (q.get('o') or [])
    if q['m'] == 'MCQ' and (len(q.get('o') or []) != 4 or not all((o or '').strip() for o in q['o'])): bad.append((q['id'], 'choices'))
    if not q['P']: bad.append((q['id'], 'empty stem'))
    if q.get('si') or q.get('fg') or any('[[' in t for t in texts): bad.append((q['id'], 'old crop'))
    for t in texts:
        for m in re.finditer(r'⟦([if]):([0-9a-f]+):', t):
            if not os.path.exists(os.path.join(bank, 'm' if m.group(1) == 'i' else 'f', m.group(2) + '.webp')): bad.append((q['id'], 'missing picture ' + m.group(2)))
print(len(B), 'questions;', len(bad), 'problems', bad[:10]); sys.exit(1 if bad else 0)
