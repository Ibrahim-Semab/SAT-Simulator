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
The included bank contains 1,748 unique SAT questions extracted from the three supplied PDFs:
* Math Easy + Medium: 655 questions
* Math Hard: 340 questions
* Reading and Writing: 753 questions

Original PDFs (where they are)
------------------------------
The three source PDFs are NOT on main. They are about 44 MB, so they are kept out of the deployed site on their own
git branch of this repository:   add-original-pdfs
  https://github.com/Ibrahim-Semab/SAT-Simulator/tree/add-original-pdfs
* Math Easy+Medium_compressed.pdf        (655 questions, 687 pages)
* Math Hard_compressed.pdf               (340 questions)
* Reading & Writing All Q&A_compressed.pdf   (753 questions)
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
A switch on the start screen makes the next test harder by giving less time. Difficulty runs from level 1 (official
timing) to level 5; the switch uses level 2, which is 85% of the official time per module (Reading and Writing 27 minutes
instead of 32, Math 30 instead of 35). Only the time changes: the questions, the module 2 routing, the 550 cap and the
scoring are the official ones. The switch is remembered; a test in progress keeps the level it started with; results
and the history list show "Hard". To change how hard the switch is, edit HARD_LEVEL or the LEVELS table (levels 3 to 5 are
already defined: 75%, 65%, 55% of the official time) near the top of the script in index.html.
