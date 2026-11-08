#!/usr/bin/env python3
"""Import SAT Question Bank PDFs into the simulator's accessible text bank.

The PDFs contain selectable text, but many Math expressions and some charts are
vector artwork. This importer keeps extracted text and renders the original
question page as a high-resolution visual wherever equations/graphics need it.

Usage:
  python3 tools/import_question_pdfs.py math-hard.pdf math-easy-medium.pdf rw.pdf --out bank/imported

Requires: PyMuPDF (pip install pymupdf). Output:
  bank/imported/questions.js
  bank/imported/visuals/<question-id>.png
  bank/imported/report.json
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
import fitz

ID_RE = re.compile(r"Question ID:\s*([a-f0-9]{8})", re.I)
CHOICE_RE = re.compile(r"(?m)^([A-D])\.\s*(.*?)(?=^[A-D]\.\s*|\Z)", re.S)
ANSWER_RE = re.compile(r"Correct Answer:\s*(.+?)(?:\n|$)")


def norm(s):
    s = s.replace('\xa0', ' ').replace('\u00ad', '')
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    return s.strip()


def split_sections(text):
    lines = text.splitlines()
    qpos = next((i for i, x in enumerate(lines) if x.strip() == 'Question'), None)
    if qpos is None:
        return {}, '', [], '', ''
    meta_lines = [x.strip() for x in lines[1:qpos] if x.strip()]
    meta = {}
    try:
        sat_i = meta_lines.index('SAT')
        meta['subject'] = meta_lines[sat_i + 1]
        meta['domain'] = meta_lines[sat_i + 2]
        meta['skill'] = ' '.join(meta_lines[sat_i + 3:-1]).strip()
        meta['difficulty'] = meta_lines[-1]
    except (ValueError, IndexError):
        pass
    tail = '\n'.join(lines[qpos + 1:])
    parts = re.split(r"(?m)^Rationale\s*$", tail, maxsplit=1)
    before_rat = parts[0]
    rationale = norm(parts[1]) if len(parts) > 1 else ''
    answer_match = ANSWER_RE.search(before_rat)
    answer = norm(answer_match.group(1)) if answer_match else ''
    if answer_match:
        before_rat = before_rat[:answer_match.start()]
    choice_match = re.search(r"(?m)^Answer\s*$", before_rat)
    if choice_match:
        stem = norm(before_rat[:choice_match.start()])
        choice_text = before_rat[choice_match.end():]
    else:
        stem, choice_text = norm(before_rat), ''
    choices, last_label = [], 0
    for m in CHOICE_RE.finditer(choice_text):
        n = ord(m.group(1)) - ord('A') + 1
        # Avoid false choice markers in wrapped text, e.g. "C. helleri".
        if n <= last_label:
            continue
        choices.append({'label': m.group(1), 'text': norm(m.group(2))})
        last_label = n
    return meta, stem, choices, answer, rationale


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('pdfs', nargs='+')
    ap.add_argument('--out', default='bank/imported')
    ap.add_argument('--scale', type=float, default=2.0)
    ap.add_argument('--all-visuals', action='store_true')
    ap.add_argument('--no-visuals', action='store_true', help='validate text extraction only')
    args = ap.parse_args()
    out = Path(args.out)
    visuals = out / 'visuals'
    visuals.mkdir(parents=True, exist_ok=True)
    bank, report, seen = [], [], set()

    for pdf_path in args.pdfs:
        doc = fitz.open(pdf_path)
        pages = []
        for i, page in enumerate(doc):
            page_text = page.get_text('text')
            match = ID_RE.search(page_text)
            if match:
                pages.append((i, match.group(1).lower(), page_text))

        for j, (page_i, qid, page_text) in enumerate(pages):
            if qid in seen:
                report.append({'id': qid, 'status': 'duplicate', 'source': Path(pdf_path).name, 'page': page_i + 1})
                continue
            seen.add(qid)
            next_page = pages[j + 1][0] if j + 1 < len(pages) else len(doc)
            continuation = [norm(doc[k].get_text('text')) for k in range(page_i + 1, next_page)]
            group_text = page_text + '\n' + '\n'.join(x for x in continuation if x)
            meta, stem, choices, answer, rationale = split_sections(group_text)
            subject = meta.get('subject', '')
            is_math = subject.lower() == 'math' or 'math' in Path(pdf_path).name.lower()
            page = doc[page_i]
            has_images = False if args.no_visuals else bool(page.get_images(full=True))
            likely_graphic = bool(re.search(r"\b(graph|chart|table|figure|diagram|shown in|xy-plane|x-y plane)\b", group_text, re.I))
            # Math pages always need the vector-art fallback, so avoid the
            # expensive drawing scan there. Scan RW pages only when likely.
            drawings = [] if (args.no_visuals or is_math or (not likely_graphic and not has_images)) else page.get_drawings()
            has_graphics = any(
                (d['rect'].width > 35 and d['rect'].height > 25) or
                (d['rect'].width > 100 and d['rect'].height < 3) or
                (d['rect'].height > 100 and d['rect'].width < 3)
                for d in drawings
            )
            needs_visual = (not args.no_visuals) and (args.all_visuals or is_math or has_graphics or has_images)
            visual_path = ''
            if needs_visual:
                pix = page.get_pixmap(matrix=fitz.Matrix(args.scale, args.scale), alpha=False)
                pix.save(visuals / f'{qid}.png')
                visual_path = f'visuals/{qid}.png'

            is_mcq = answer.strip().upper() in {'A', 'B', 'C', 'D'}
            choice_map = {c['label']: c['text'] for c in choices}
            # Formula glyphs in Math PDFs are vector drawings and may not appear
            # in the text layer. Keep four interactive answer targets when the
            # official key identifies an A-D answer; the full-page visual carries
            # the exact original expressions and diagrams.
            choices_text = [choice_map.get(label, '') for label in 'ABCD'] if is_mcq else []
            record = {
                'id': qid,
                's': 'rw' if ('reading' in subject.lower() or 'writing' in subject.lower() or 'reading' in Path(pdf_path).name.lower()) else 'math',
                'd': meta.get('domain', ''),
                'k': meta.get('skill', ''),
                'l': {'Easy': 'E', 'Medium': 'M', 'Hard': 'H'}.get(meta.get('difficulty', '').strip(), 'M'),
                'm': 'MCQ' if is_mcq else 'SPR',
                'a': answer,
                'text': stem,
                'choicesText': choices_text,
                'rationaleText': rationale,
                'visual': visual_path,
                'source': Path(pdf_path).name,
                'sourcePage': page_i + 1,
            }
            bank.append(record)
            report.append({'id': qid, 'status': 'ok' if stem else 'needs-review', 'subject': record['s'],
                           'difficulty': record['l'], 'choices': len(choices), 'visual': bool(visual_path),
                           'source': Path(pdf_path).name, 'page': page_i + 1})

    (out / 'questions.js').write_text('window.IMPORTED_BANK=' + json.dumps(bank, ensure_ascii=False, separators=(',', ':')) + ';\n', encoding='utf-8')
    summary = {
        'questionCount': len(bank),
        'bySubject': {s: sum(q['s'] == s for q in bank) for s in ('rw', 'math')},
        'byDifficulty': {d: sum(q['l'] == d for q in bank) for d in ('E', 'M', 'H')},
        'withVisual': sum(bool(q['visual']) for q in bank),
        'withoutStem': sum(not q['text'] for q in bank),
        'choiceCounts': {str(n): sum(len(q['choicesText']) == n for q in bank) for n in range(5)},
        'records': report,
    }
    (out / 'report.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k != 'records'}, indent=2))


if __name__ == '__main__':
    main()
