Digital SAT Practice
====================
Open index.html in Chrome, Edge or Safari (double-click, no server needed).
Keep the "bank" folder next to it.

* Each new test is generated from the bank. Questions you have not seen come first;
  once everything has been seen, the least-repeated ones come back.
  History, in-progress tests and results are stored in the browser (localStorage).
* Reading and Writing follows the official blueprint: 27 questions per module, ordered by domain then skill
  (Craft and Structure, Information and Ideas, Standard English Conventions, Expression of Ideas), with
  ~28/26/26/20% across the two modules. Skill counts per module are set in QUOTA at the top of index.html.
* Module 2 is chosen from your Module 1 result (22+ of 27 in Reading and Writing, about 80%,
  16+ of 22 in Math, about 70% -> harder module). The easier module 2 caps the section score at 550.
* Scoring is 3-parameter logistic item response theory: each question has its own difficulty, discrimination and
  guessing floor (0.25 multiple choice, 0 student-produced response); ability is the maximum-likelihood estimate over
  your whole answer pattern, mapped from theta (about -3 to +3) onto 200-800 and rounded to 10.
* Each Math module holds about one third student-produced response and two thirds multiple choice.
* To add questions: build a bigger bank folder with tools/build_bank.py
  (python3 tools/build_bank.py <source files> --out bank) and replace bank/.
* Colours are CSS variables at the top of index.html (:root).
Full question bank
------------------
The included bank contains 1,933 unique SAT questions extracted from the three supplied PDFs:
* Math Easy + Medium: 655 questions
* Math Hard: 340 questions
* Reading and Writing: 938 questions

Original PDFs (where they are)
------------------------------
The three source PDFs are NOT on main. They are about 44 MB, so they are kept out of the deployed site on their own
git branch of this repository:   add-original-pdfs
  https://github.com/Ibrahim-Semab/SAT-Simulator/tree/add-original-pdfs
* Math Easy+Medium_compressed.pdf        (655 questions, 687 pages)
* Math Hard_compressed.pdf               (340 questions)
* Reading & Writing_compressed.pdf       (938 questions, 1005 pages)  <- the COMPLETE Reading and Writing bank
* Reading & Writing All Q&A_compressed.pdf   (753 questions) - the older, incomplete download. It is kept on the branch
  but nothing uses it any more. Every Reading and Writing question's "p"/"ep" now counts pages of the complete PDF.
(The 185 Reading and Writing questions that the older PDF lacked were added from the complete PDF with
tools/pdf_pipeline/add_missing.py; see "Adding questions from a newer PDF" below.)
Get them without leaving main:
    git fetch origin add-original-pdfs
    git show "origin/add-original-pdfs:Math Hard_compressed.pdf" > "Math Hard_compressed.pdf"     (same for the others)
  or: git checkout origin/add-original-pdfs -- "Math Hard_compressed.pdf"      (puts the file in your working folder)
Every question in bank/meta.js records where it came from: "src" is the PDF (Math Easy+Medium, Math Hard or
Reading & Writing) and "p" to "ep" are its first and last page, counted from 1. Example: question 0ea7ef01 is on
page 88 of Math Easy+Medium. The pages are vector drawings, so figures can be cropped from them at any resolution.
The PDFs are used by tools/pdf_pipeline (explanations and equation images) and tools/restore_figures.py (figures).

Question images exclude the answer key and explanation. The matching explanation image includes the correct answer and rationale. Content that continues onto another PDF page is joined in reading order. Figures, graphs, tables, and equations are preserved in the images.

See bank/index.csv for the question inventory and bank/extraction_notes.txt for extraction details.


QUESTION FORMAT (text edition)
- Passages, prompts and answer choices are real text; equations, graphs and tables are small picture crops from bank/q.
- Difficulty is shown only on the post-test review screen, never during the exam.
- tools/text_pipeline rebuilds bank/meta.js from the PDF text extractions.

Question quality check
* python3 tools/audit_bank.py [--list] checks every picture crop in bank/meta.js against its screenshot in
  bank/q (tiny, out of bounds, blank, answer start cut off, answer end cut off) and exits 1 if anything is wrong.
  Run it after regenerating the bank.
* bank/excluded.json holds questions kept out of tests because their source screenshot is itself incomplete.
* python3 tools/fix_bank.py [--apply] repairs figure questions that the text pipeline split into pieces: pictures that are
  only a copy or fragment of another picture in the same question are dropped, and questions that cannot be repaired
  from the screenshots alone (detached labels or axis titles, two different crops of one figure, "Math output error")
  are moved to bank/excluded.json with the reason. tools/audit_bank.py runs the same checks, so run it after
  regenerating the bank.
* python3 tools/restore_figures.py --pdf-dir <folder with the PDFs> [--apply] brings those questions back: it crops the
  figure from the original PDF page (see "Original PDFs" above) as one clean picture, replaces the loose pieces with it
  and moves the question back into bank/meta.js. It did this for all 20 questions that had been parked: 19 split
  figures, and 75a32330, whose answer choice D (a graph) was cut off in its screenshot and which now has both equations
  and all four graphs taken from the PDF. In the two questions where the source PDF prints "Math output error" instead
  of a line name (58687a66, 858809e7), the text now says "line ℓ", the name the figure gives that line.
  bank/excluded.json is now empty.
  Rebuilding the whole bank from the PDFs brings the broken figures back; run fix_bank.py and restore_figures.py again.
* python3 tools/trim_inline_fragments.py [--apply] cuts stray neighbour characters (the comma or full stop after a formula,
  half of the next letter) off the edges of small inline formula pictures in bank/m. It only removes a separate cluster of ink
  at the edge that is smaller than the formula and sits on its baseline, and leaves exponents, subscripts, brackets and
  inline diagrams alone. 157 pictures (about 126 questions) were trimmed; a few one-letter slivers (such as an "i" after an
  overlined name) are still there because they cannot be told apart from real characters without the source page.

Hard mode (start screen)
------------------------
The start screen has a "Test mode" choice: Official (official time), Hard (5% less time per module) and Extreme (10% less
time per module; Reading and Writing 28:48 instead of 32:00, Math 31:30 instead of 35:00). Only the time changes: the
questions, the module 2 routing, the 550 cap and the scoring are the official ones. The choice is remembered; a test in
progress keeps the mode it started with; the history list shows the mode in the title, e.g. "Practice Test 9 (Hard)"
(nothing is added for Official). To change the amounts, edit MODES near the top of the script in index.html.

Figure slivers (tools/trim_figure_slivers.py)
---------------------------------------------
Some figure/table crops caught specks of the neighbouring text line (the edge of the next answer table, the cut-off
bottom of a caption). The tool crops such slivers (height <= 4 px, < 0.5% of the ink, 30+ px away from the figure) and
rescales the height in the tokens of bank/meta.js. Run `python3 tools/trim_figure_slivers.py` (report) or `--apply`.

Blurry figures (tools/upscale_figures.py)
-----------------------------------------
Many scatterplots/graphs are only small bitmaps inside the original PDFs (e.g. 140 x 154 px), so they cannot be truly
sharp. The tool takes the PDF's embedded bitmap (pdfimages), enlarges it 3x, removes JPEG noise, sharpens and stretches
the contrast, and swaps it in only when it is verifiably the same drawing as the bank picture (dark-ink overlap >= 0.8
and clearly better than any other bitmap on the page). Run with --pdf-dir (PDFs from the add-original-pdfs branch).

Adding questions from a newer PDF (tools/pdf_pipeline/add_missing.py)
---------------------------------------------------------------------
The first Reading and Writing PDF had only 753 of the 938 questions of the College Board bank. After the complete PDF
was uploaded, the 185 missing ones were added like this:
    python3 tools/pdf_pipeline/extract.py "Reading & Writing_compressed.pdf" /tmp/pages/rw2
    python3 tools/pdf_pipeline/add_missing.py --pages /tmp/pages/rw2 --pdf "Reading & Writing_compressed.pdf" --apply
It reads every "Question ID" of the PDF, skips the ones already in bank/meta.js, and for each new one takes domain, skill,
difficulty, stem, prompt, choices, correct answer and explanation from the PDF (figures and equations are cut from the
PDF pages into bank/f and bank/m). The same run re-points p/ep of all Reading and Writing questions to the complete PDF.
`--check N` rebuilds N existing questions the same way and reports how often header and prompt match the bank (80 of 80
headers and 78 of 80 prompts matched). Chart titles and legends that sit around a figure are now absorbed into the figure
picture by build_questions.py (find_figures) instead of staying behind as loose text.

Reading typography
------------------
Question text, answer choices and explanations use a clean serif (--serif in index.html: Source Serif 4, then Iowan Old
Style, Charter, Noto Serif, Georgia ... whichever the device has; no font files are bundled). In explanations every
"Choice X ..." sentence starts its own paragraph with a bold label, the correct choice in green (see ratParas()).
