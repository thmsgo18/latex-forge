# Getting Started — @@NAME@@

## Workflow

**1. Fill in your metadata**

Open `frontmatter/metadata.tex` and set the title, author(s), course, and university.

**2. Write your content**

Add or edit files in `sections/`. To add a new section:
1. Create `sections/my-section.tex`
2. Add `\input{sections/my-section.tex}` to `@@NAME@@.tex`

**3. Save to compile**

Save `@@NAME@@.tex` in VS Code → LaTeX Workshop compiles automatically → PDF in `build/@@NAME@@.pdf`.

---

## Folder structure

| Folder | Purpose |
|---|---|
| `frontmatter/` | Title page data (`metadata.tex`) and table of contents |
| `sections/` | Main content — one `.tex` file per section |
| `backmatter/` | AI statement and end matter |
| `images/` | All images: photos, screenshots, PNG/JPG files |
| `figures/` | TikZ/pgfplots diagrams (LaTeX source figures, not image files) |
| `assets/logos/` | University and project logos |
@@EXTRA_FOLDERS@@| `styles/packages/` | Embedded LaTeX styles — do not edit |
| `build/` | Compiled PDF — auto-generated, do not commit |

---

## Common operations

### Add an image

Put your image file in `images/`, then in your `.tex` file:

```latex
\begin{figure}[h]
  \centering
  \includegraphics[width=0.8\linewidth]{my-image.png}
  \caption{Caption here.}
  \label{fig:my-label}
\end{figure}
```
@@BIBLIOGRAPHY_SECTION@@
### Rename this project

```bash
latex-forge rename new-name
```

This renames the folder, the main `.tex` file, and any build artifacts.

---

## If compilation fails

1. **LaTeX not installed** → run `latex-forge setup --install-tex`
2. **LaTeX Workshop not installed** → install it from the VS Code extensions panel
3. **Missing package** → `tlmgr install package-name` (TeX Live) or let MiKTeX auto-install
4. **Compilation stuck** → delete the `build/` folder and try again

This project uses **@@ENGINE_DISPLAY@@**. Verify it is available:

```bash
@@ENGINE@@ --version
```

---

## Resources

### Official documentation

| Resource | Link |
|---|---|
| LaTeX Project | <https://www.latex-project.org/help/documentation/> |
| CTAN — package index | <https://www.ctan.org> |
| TeXdoc — search package docs | <https://texdoc.org> |
| TikZ & PGF manual | <https://tikz.dev> |

### Learn LaTeX

| Resource | Link |
|---|---|
| Overleaf — Learn LaTeX in 30 minutes | <https://www.overleaf.com/learn/latex/Learn_LaTeX_in_30_minutes> |
| Overleaf knowledge base | <https://www.overleaf.com/learn> |
| LaTeX Wikibook | <https://en.wikibooks.org/wiki/LaTeX> |
| LaTeX FAQ | <https://texfaq.org> |

### LuaLaTeX specific

| Resource | Link |
|---|---|
| LuaLaTeX wiki | <https://www.luatex.org/documentation.html> |
| fontspec (font loading) | <https://texdoc.org/serve/fontspec/0> |
