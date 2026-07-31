# Getting Started — @@NAME@@

## Workflow

**1. Set document metadata**

Open `frontmatter/metadata.tex` and update the title, author, and date.

**2. Write your content**

Edit `sections/content.tex`. To add more sections:
1. Create a new file, e.g. `sections/my-section.tex`
2. Add `\input{sections/my-section.tex}` to `@@NAME@@.tex`

**3. Save to compile**

Save `@@NAME@@.tex` in VS Code → LaTeX Workshop compiles automatically → PDF in `build/@@NAME@@.pdf`.

---

## Folder structure

| Path | Purpose |
|---|---|
| `frontmatter/metadata.tex` | Document title, author, date |
| `sections/content.tex` | Main content |
| `build/` | @@BUILD_ROW@@ |

---
@@SHARING_NOTE@@

## Common operations

### Add an image

Put your image file in the project folder, then in your `.tex` file:

```latex
\begin{figure}[h]
  \centering
  \includegraphics[width=0.8\linewidth]{my-image.png}
  \caption{Caption here.}
  \label{fig:my-label}
\end{figure}
```

### Add a bibliography

1. Add a `references.bib` file
2. In `@@NAME@@.tex`, before `\end{document}`:

```latex
\bibliographystyle{plain}
\bibliography{references}
```

3. Cite with `\cite{key}` in your text.

### Rename this project

```bash
latex-forge rename new-name
```

---

## If compilation fails

1. **LaTeX not installed** → run `latex-forge setup --install-tex`
2. **LaTeX Workshop not installed** → install it from the VS Code extensions panel
3. **Missing package** → `tlmgr install package-name`
4. **Compilation stuck** → delete the `build/` folder and try again

This project uses **@@ENGINE_DISPLAY@@**. Verify it is available:

```bash
@@ENGINE@@ --version
```

---

## Resources

| Resource | Link |
|---|---|
| LaTeX Project | <https://www.latex-project.org/help/documentation/> |
| CTAN — package index | <https://www.ctan.org> |
| Overleaf — Learn LaTeX in 30 minutes | <https://www.overleaf.com/learn/latex/Learn_LaTeX_in_30_minutes> |
| LaTeX Wikibook | <https://en.wikibooks.org/wiki/LaTeX> |
| LaTeX FAQ | <https://texfaq.org> |
