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
* Module 2 is chosen from your Module 1 result (16+ of 27 in Reading and Writing,
  13+ of 22 in Math -> harder module).
* To add questions: build a bigger bank folder with tools/build_bank.py
  (python3 tools/build_bank.py <source files> --out bank) and replace bank/.
* Colours are CSS variables at the top of index.html (:root).
Full question bank
------------------
The included bank contains 1,748 unique SAT questions extracted from the three supplied PDFs:
* Math Easy + Medium: 655 questions
* Math Hard: 340 questions
* Reading and Writing: 753 questions

Question images exclude the answer key and explanation. The matching explanation image includes the correct answer and rationale. Content that continues onto another PDF page is joined in reading order. Figures, graphs, tables, and equations are preserved in the images.

See bank/index.csv for the question inventory and bank/extraction_notes.txt for extraction details.


QUESTION FORMAT (text edition)
- Passages, prompts and answer choices are real text; equations, graphs and tables are small picture crops from bank/q.
- Difficulty is shown only on the post-test review screen, never during the exam.
- tools/text_pipeline rebuilds bank/meta.js from the PDF text extractions.
