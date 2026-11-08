Digital SAT Practice
====================
Open index.html in Chrome, Edge or Safari (double-click, no server needed).
Keep the "bank" folder next to it.

* Each new test is generated from the bank. Questions you have not seen come first;
  once everything has been seen, the least-repeated ones come back.
  History, in-progress tests and results are stored in the browser (localStorage).
* Module 2 is chosen from your Module 1 result (16+ of 27 in Reading and Writing,
  13+ of 22 in Math -> harder module).
* To add questions: build a bigger bank folder with tools/build_bank.py
  (python3 tools/build_bank.py <source files> --out bank) and replace bank/.
* Colours are CSS variables at the top of index.html (:root).

Importing the supplied Question Bank PDFs
------------------------------------------
The accessible-bank importer extracts question text, choices, correct answers,
SAT domain/skill/difficulty metadata, and explanations. It also renders original
PDF pages as high-resolution visuals where Math equations or diagrams need to
remain exact.

Install the PDF reader dependency:
  python3 -m pip install pymupdf

Then run from the repository root (adjust the PDF paths as needed):
  python3 tools/import_question_pdfs.py "Math Hard_compressed.pdf" "Math Easy+Medium_compressed.pdf" "Reading & Writing All Q&A_compressed.pdf" --out bank/imported

The importer creates bank/imported/questions.js, bank/imported/visuals/, and
bank/imported/report.json. The simulator loads the generated bank automatically.
Do not use --no-visuals for a production import: that option is only for checking
text extraction and would omit the original math/diagram artwork.
