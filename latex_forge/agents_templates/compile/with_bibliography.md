```bash
@@ENGINE@@ -interaction=nonstopmode -output-directory=build @@NAME@@.tex
biber build/@@NAME@@
@@ENGINE@@ -interaction=nonstopmode -output-directory=build @@NAME@@.tex
@@ENGINE@@ -interaction=nonstopmode -output-directory=build @@NAME@@.tex
```