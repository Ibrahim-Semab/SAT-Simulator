#!/usr/bin/env python3
"""Step 2 - rebuild every answer explanation (rationale) as real text + crisp equation pictures.

  python3 build_rationales.py --pages PAGES_DIR --pdfs PDF_DIR --out ../../bank [--ids id1,id2]

PAGES_DIR holds the output of extract.py in sub folders  rw/  em/  hard/ ; PDF_DIR holds the three PDFs.
Writes   bank/rat.js   window.RAT = { id: [html paragraph, ...] }
         bank/m/<hash>.webp   one small transparent picture per distinct equation
"""
import argparse, html, json, os, re, sys
import pypdfium2 as pdfium
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flow, render
from render import PageRaster

DOCS = {'Reading & Writing': ('rw', 'Reading & Writing All Q&A_compressed.pdf'),
        'Math Easy+Medium': ('em', 'Math Easy+Medium_compressed.pdf'),
        'Math Hard': ('hard', 'Math Hard_compressed.pdf')}

def question_pages(pages):
    """{question id: [page numbers]} - a page that has no 'Question ID' continues the previous question."""
    qs = {}; cur = None
    for n in sorted(pages):
        m = flow.QID.search(flow.page_text(pages[n]))
        if m: cur = m.group(1); qs[cur] = []
        if cur: qs[cur].append(n)
    return qs

def heading_y(seq, name):
    for e in seq:
        if e[0] == 't' and e[1].strip() == name: return e[3]
    return None

def rationale_pages(pages, nums):
    """[(page number, tokens)] for everything after the 'Rationale' heading (it may continue on later pages)."""
    out = []; started = False
    for n in nums:
        seq = pages[n]['seq']
        if not started:
            y = heading_y(seq, 'Rationale')
            if y is None: continue
            started = True; y += 3
        else: y = 20
        out.append((n, flow.tokens(seq, y)))
    return out

def para_html(lines, page, mdir):
    """One paragraph (a list of lines) -> html: text as text, every equation piece as a small crisp picture."""
    parts = []; display = len(lines) == 1 and not lines[0]['text']
    for li, l in enumerate(lines):
        if li and parts and not parts[-1].endswith(' '): parts.append(' ')
        prev = None
        for it in l['items']:
            if it['k'] == 't':
                dy = it['y'] - l['base']; raw_t = it['t']; t = html.escape(raw_t, quote=False)
                if 1.2 < abs(dy) <= 4.6 and raw_t.strip().isalnum(): t = '<%s>%s</%s>' % ('sub' if dy > 0 else 'sup', t, 'sub' if dy > 0 else 'sup')
                piece = t; starts_punct = raw_t[:1] in ',.;:)]}?!’\''; starts_space = raw_t[:1].isspace()
            else:
                key, wpt, hpt, (t, b) = render.render_piece(page, (it['x0'], it['y0'], it['x1'], it['y1']), mdir)
                style = 'height:%.3fem' % (hpt / flow.BODY_PT)
                if not display: style += ';vertical-align:%.3fem' % (-(b - l['base']) / flow.BODY_PT)
                piece = '<img class="mi" src="bank/m/%s.webp" style="%s" alt="">' % (key, style)
                starts_punct = False; starts_space = False
            # the PDF encodes the space between an equation and a word as a gap, not as a character
            if prev is not None and parts and not starts_space and not starts_punct and not parts[-1].endswith(' ') \
                    and (it['k'] == 'm' or prev['k'] == 'm') and not (prev['k'] == 't' and prev['t'][-1:] in '([{$“‘-−/') :
                parts.append(' ')
            parts.append(piece); prev = it
    h = re.sub(r' {2,}', ' ', ''.join(parts)).strip()
    return ('<div class="md">%s</div>' % h) if display else h

SRC = None
def build(ids, pages_root, pdf_root, out):
    mdir = os.path.join(out, 'm'); os.makedirs(mdir, exist_ok=True)
    meta = open(os.path.join(out, 'meta.js'), encoding='utf-8').read()
    meta = {q['id']: q for q in json.loads(meta[meta.index('['):meta.rindex(']') + 1])}
    ids = ids or list(meta)
    if SRC: ids = [i for i in ids if DOCS[meta[i]['src']][0] == SRC]
    res = {}; problems = []
    by_src = {}
    for i in ids: by_src.setdefault(meta[i]['src'], []).append(i)
    for src, group in by_src.items():
        sub, pdfname = DOCS[src]
        pages = flow.load_pages(os.path.join(pages_root, sub)); qp = question_pages(pages)
        pdf = pdfium.PdfDocument(os.path.join(pdf_root, pdfname))
        for qid in group:
            if qid not in qp: problems.append((qid, 'not found in pdf')); continue
            regs = rationale_pages(pages, qp[qid])
            if not regs: problems.append((qid, 'no Rationale heading')); continue
            paras = []
            for n, tks in regs:
                page = pdf[n - 1]; pr = PageRaster(page)
                for para in flow.paragraphs(flow.lines_of(tks)): paras.append(para_html(para, pr, mdir))
                page.close()
            paras = [p for p in paras if p]
            if not paras: problems.append((qid, 'empty rationale')); continue
            res[qid] = paras
    return res, problems

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--pages', required=True); ap.add_argument('--pdfs', required=True)
    ap.add_argument('--out', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'bank'))
    ap.add_argument('--ids'); ap.add_argument('--json'); ap.add_argument('--src', help='only this PDF: rw, em or hard'); ap.add_argument('--merge', nargs='*', help='combine --json outputs into bank/rat.js')
    a = ap.parse_args()
    if a.merge is not None:
        allr = {}
        for f in a.merge: allr.update(json.load(open(f)))
        open(os.path.join(a.out, 'rat.js'), 'w', encoding='utf-8').write('window.RAT=' + json.dumps(allr, ensure_ascii=False, separators=(',', ':')) + ';')
        print('merged', len(allr)); sys.exit(0)
    SRC = a.src
    res, problems = build(a.ids.split(',') if a.ids else None, a.pages, a.pdfs, a.out)
    if a.json: json.dump(res, open(a.json, 'w'), ensure_ascii=False, indent=1)
    else:
        open(os.path.join(a.out, 'rat.js'), 'w', encoding='utf-8').write('window.RAT=' + json.dumps(res, ensure_ascii=False, separators=(',', ':')) + ';')
    print(len(res), 'rationales;', len(problems), 'problems', problems[:10])
