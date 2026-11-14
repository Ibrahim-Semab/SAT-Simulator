Rebuilds explanations (bank/rat.js + bank/m/*.webp equation images) from the
original College Board PDFs (kept on branch addition/original-pdfs, never deployed).
For each PDF:  python3 extract.py <pdf> <pages_dir>/<src>
Then:          python3 build_rationales.py --pages <pages_dir> --pdfs <pdf_dir> --src rw|em|hard --json out_<src>.json --out bank
Merge:         python3 build_rationales.py --pages ... --pdfs ... --merge out_rw.json out_em.json out_hard.json
