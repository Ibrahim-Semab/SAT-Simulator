#!/usr/bin/env python3
"""Add the Reading & Writing questions that are in the original PDF but not yet in bank/meta.js.

The complete College Board printout is  Reading & Writing_compressed.pdf  (938 questions, 1005 pages) on the git branch
add-original-pdfs; the older "Reading & Writing All Q&A_compressed.pdf" has only 753 of them.

    python3 extract.py "Reading & Writing_compressed.pdf" /tmp/pages/rw2          # step 1: page JSON
    python3 add_missing.py --pages /tmp/pages/rw2 --pdf "Reading & Writing_compressed.pdf" [--apply] [--check N]

For each question id found in the PDF but not in the bank this reads the header (domain, skill, difficulty), the stem and
choices (build_questions.build_question), the correct answer and the explanation (build_rationales), appends the
question to bank/meta.js and its explanation to bank/rat.js. It also re-points "p"/"ep" of ALL Reading & Writing
questions to page numbers of this complete PDF, and sets src to "Reading & Writing".
--check N rebuilds N existing questions the same way and reports how often the result equals what is in the bank
(tests the prompt split and the header parsing).
"""
import argparse, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flow, pypdfium2 as pdfium
import build_questions as bq
from build_rationales import question_pages, rationale_pages, para_html
from render import PageRaster

BANK = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'bank')
START = re.compile(r'(?:Which (?:choice|finding|quotation|statement|detail|sentence|of the following|option)|Based on the (?:text|texts|data|graph|table|information|passage|notes|poem)|According to (?:the|both) |As used in the text|What (?:does|is|would|will|can)|How (?:does|would|do|did)|Why (?:does|would|is|did)|In (?:the|this) (?:text|context|poem))')
LEVEL = {'Easy': 'E', 'Medium': 'M', 'Hard': 'H'}

def header(pages, n):
    seq = [e for e in pages[n]['seq'] if e[0] == 't' and 80 < e[3] < 135]
    def col(x0, x1):
        parts = sorted([e for e in seq if x0 <= e[2] < x1], key=lambda e: (round(e[3]), e[2]))
        return re.sub(r'\s+', ' ', ' '.join(e[1].strip() for e in parts)).strip()
    return col(245, 362), col(362, 477), col(477, 600)

def split_prompt(P, U):
    """-> (P, PR, U). The prompt is the last paragraph when it opens like a question; otherwise it is cut off the end of
    the last paragraph at its last question-like opening."""
    if not P: return P, None, U
    last = len(P) - 1
    if len(P) >= 2 and not P[last].startswith(('#', '⟦f:')) and (START.match(P[last]) or P[last].rstrip().endswith('?')):
        return P[:last], P[last], [u for u in U if u[0] != last]
    ms = list(START.finditer(P[last]))
    if ms:
        k = ms[-1].start(); head = P[last][:k].rstrip()
        if head:
            return P[:last] + [head], P[last][k:], [[pi, a, min(b, len(head))] for pi, a, b in U if not (pi == last and a >= k)]
    return P, None, U

def build_one(qid, pages, nums, pdf, mdir, fdir):
    r, err = bq.build_question(qid, None, pages, nums, pdf, mdir, fdir)
    if err: return None, err
    P, PR, U = split_prompt(r['P'], r['U'])
    d, k, lv = header(pages, nums[0])
    rec = {'id': qid, 's': 'rw', 'a': (r['correct'] or '').strip(), 'd': d, 'k': k, 'l': LEVEL.get(lv, '?'), 'm': 'MCQ',
           'src': 'Reading & Writing', 'p': nums[0], 'ep': nums[-1], 'P': P}
    if PR: rec['PR'] = PR
    if U: rec['U'] = U
    rec['o'] = r['o']
    return rec, None

def rationale(qid, pages, nums, pdf, mdir):
    regs = rationale_pages(pages, nums); paras = []
    for n, tks in regs:
        page = pdf[n - 1]; pr = PageRaster(page)
        for para in flow.paragraphs(flow.lines_of(tks)): paras.append(para_html(para, pr, mdir))
        page.close()
    return [p for p in paras if p]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--pages', required=True); ap.add_argument('--pdf', required=True)
    ap.add_argument('--apply', action='store_true'); ap.add_argument('--check', type=int, default=0); a = ap.parse_args()
    pages = flow.load_pages(a.pages); qp = question_pages(pages); pdf = pdfium.PdfDocument(a.pdf)
    mdir = os.path.join(BANK, 'm'); fdir = os.path.join(BANK, 'f')
    s = open(os.path.join(BANK, 'meta.js'), encoding='utf-8').read(); pre, post = s[:s.index('[')], s[s.rindex(']') + 1:]
    B = json.loads(s[s.index('['):s.rindex(']') + 1]); have = {q['id']: q for q in B}
    if a.check:
        import random; random.seed(3); ids = random.sample([q['id'] for q in B if q['src'] == 'Reading & Writing'], a.check)
        bad = {'a': 0, 'd': 0, 'k': 0, 'l': 0, 'PR': 0, 'nP': 0, 'o': 0}; tot = 0
        for i in ids:
            rec, err = build_one(i, pages, qp[i], pdf, os.path.join('/tmp', 'chk_m'), os.path.join('/tmp', 'chk_f'))
            if not rec: print(i, err); continue
            q = have[i]; tot += 1
            for f in ('a', 'd', 'k', 'l'):
                if rec[f] != q[f]: bad[f] += 1; print(' ', i, f, repr(rec[f]), repr(q[f]))
            if (rec.get('PR') or '') != (q.get('PR') or ''): bad['PR'] += 1; print('  PR', i, repr((rec.get('PR') or '')[:70]), '|', repr((q.get('PR') or '')[:70]))
            if len(rec['P']) != len(q['P']): bad['nP'] += 1
        print('checked', tot, bad); return
    missing = [i for i in qp if i not in have]
    new = []; rats = {}; problems = []
    for k, qid in enumerate(missing):
        try: rec, err = build_one(qid, pages, qp[qid], pdf, mdir, fdir)
        except Exception as ex: rec, err = None, repr(ex)
        if err or not rec['a'] in list('ABCD') or rec['l'] == '?' or not rec['o'] or len(rec['o']) != 4 or any(not x for x in rec['o']): problems.append((qid, err or 'incomplete')); continue
        rp = rationale(qid, pages, qp[qid], pdf, mdir)
        if not rp: problems.append((qid, 'no rationale')); continue
        new.append(rec); rats[qid] = rp
    print('missing %d, built %d, problems %d' % (len(missing), len(new), len(problems)), problems[:10])
    if not a.apply: return
    for q in B:
        if q['src'] == 'Reading & Writing' and q['id'] in qp: q['p'], q['ep'] = qp[q['id']][0], qp[q['id']][-1]
    B += new
    open(os.path.join(BANK, 'meta.js'), 'w', encoding='utf-8').write(pre + json.dumps(B, ensure_ascii=False, separators=(',', ':')) + post)
    rs = open(os.path.join(BANK, 'rat.js'), encoding='utf-8').read(); R = json.loads(rs[rs.index('{'):rs.rindex('}') + 1]); R.update(rats)
    open(os.path.join(BANK, 'rat.js'), 'w', encoding='utf-8').write('window.RAT=' + json.dumps(R, ensure_ascii=False, separators=(',', ':')) + ';')
    print('wrote bank/meta.js (%d questions) and bank/rat.js (%d explanations)' % (len(B), len(R)))
if __name__ == '__main__': main()
