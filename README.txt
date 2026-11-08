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
