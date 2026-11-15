Rebuilds explanations (bank/rat.js + bank/m/*.webp equation images) from the
original College Board PDFs (kept on branch addition/original-pdfs, never deployed).
For each PDF:  python3 extract.py <pdf> <pages_dir>/<src>
Then:          python3 build_rationales.py --pages <pages_dir> --pdfs <pdf_dir> --src rw|em|hard --json out_<src>.json --out bank
Merge:         python3 build_rationales.py --pages ... --pdfs ... --merge out_rw.json out_em.json out_hard.json

Questions (stems, choices, tables, graphs):
  python3 build_questions.py --pages <pages_dir> --pdfs <pdf_dir> --src rw|em|hard --json q_<src>.json   (writes bank/m and bank/f)
  python3 assemble_questions.py --out ../../bank q_rw.json q_em.json q_hard.json                          (rewrites bank/meta.js)
Picture tokens inside question text:  ⟦i:HASH:H_EM:VALIGN_EM⟧ inline equation (bank/m)   ⟦f:HASH:W_EM:H_EM⟧ figure/table (bank/f)
assemble_questions.py needs the PRE-rebuild meta.js (it reads the old PR/answer fields): git show <commit before>:bank/meta.js
