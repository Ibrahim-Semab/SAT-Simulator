"""Layout helpers: turn the draw-ordered page JSON from extract.py into lines and paragraphs.

Chrome emits a page in reading order, so a maximal run of drawn shapes between two text runs is one
inline equation (split where it wraps onto the next line). Positions are used only to decide which
line a piece sits on and where paragraphs break."""
import json, os, re

BODY_PT = 9.6          # body font size of the PDF text in points (measured from glyph ascenders)
QID = re.compile(r'Question ID:\s*([0-9a-f]{8})')

def load_pages(d):
    return {int(n[:4]): json.load(open(os.path.join(d, n))) for n in sorted(os.listdir(d))}

def page_text(p):
    return ''.join(e[1] for e in p['seq'] if e[0] == 't')

def split_run(run):
    """One run of shapes -> pieces, starting a new piece where the equation wraps to the next line."""
    pieces = []; cur = None
    for _, x0, y0, x1, y1, kind in run:
        if cur and (x1 < cur['x0'] - 25 or y0 > cur['y1'] + 6): pieces.append(cur); cur = None
        if cur is None: cur = {'k': 'm', 'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1, 'n': 1}
        else:
            cur['x0'] = min(cur['x0'], x0); cur['y0'] = min(cur['y0'], y0)
            cur['x1'] = max(cur['x1'], x1); cur['y1'] = max(cur['y1'], y1); cur['n'] += 1
    if cur: pieces.append(cur)
    return pieces

def tokens(seq, y_min=-1):
    """Draw-ordered text runs and equation pieces below y_min."""
    out = []; run = []
    def flush():
        nonlocal run
        for pc in split_run(run):
            if (pc['y0'] + pc['y1']) / 2 > y_min: out.append(pc)
        run = []
    for e in seq:
        if e[0] == 'm': run.append(e)
        else:
            flush()
            if e[3] > y_min: out.append({'k': 't', 't': e[1], 'x0': e[2], 'x1': e[4], 'y': e[3]})
    flush()
    return out

def lines_of(tks):
    """Group tokens into lines. -> [{'items','base','top','bot','x1','text'}]"""
    lines = []; cur = None
    def new(tk):
        nonlocal cur
        cur = {'items': [], 'base': None, 'top': 1e9, 'bot': -1e9, 'x1': -1e9, 'text': False}; lines.append(cur)
    for tk in tks:
        if tk['k'] == 't':
            ok = cur and tk['x0'] >= cur['x1'] - 3 and (
                (cur['base'] is not None and abs(tk['y'] - cur['base']) <= 4.6) or
                (cur['base'] is None and -8 <= tk['y'] - (cur['top'] + cur['bot']) / 2 <= 14))
            if not ok: new(tk)
            if cur['base'] is None: cur['base'] = tk['y']
            cur['text'] = cur['text'] or bool(tk['t'].strip())
            cur['top'] = min(cur['top'], tk['y'] - 7.4); cur['bot'] = max(cur['bot'], tk['y'] + 2.6)
            cur['x1'] = max(cur['x1'], tk['x1'])
        else:
            cy = (tk['y0'] + tk['y1']) / 2
            ok = cur and tk['x0'] >= cur['x1'] - 3 and (
                (cur['base'] is not None and -8 <= cur['base'] - cy <= 14) or
                (cur['base'] is None and abs(cy - (cur['top'] + cur['bot']) / 2) <= 12))
            if not ok: new(tk)
            cur['top'] = min(cur['top'], tk['y0']); cur['bot'] = max(cur['bot'], tk['y1'])
            cur['x1'] = max(cur['x1'], tk['x1'])
        cur['items'].append(tk)
    for l in lines:
        if l['base'] is None: l['base'] = max(i['y1'] for i in l['items']) - 3
    return lines

def paragraphs(lines, gap=8.0):
    """Group lines into paragraphs; a line that has no text (a displayed equation) is a paragraph of its own."""
    paras = []
    for l in lines:
        if paras and l['text'] and paras[-1][-1]['text'] and l['top'] - paras[-1][-1]['bot'] < gap: paras[-1].append(l)
        else: paras.append([l])
    return paras
