# AGENTS.md — @@NAME@@

> Briefing for any AI assistant working on this project.
> Read this file before making any changes.

## Project overview

| Field | Value |
|---|---|
| Template | `@@TEMPLATE@@` — @@DESCRIPTION@@ |
| Language | @@LANG_NOTE@@ |
| LaTeX engine | @@ENGINE_DISPLAY@@ |
| Bibliography | @@BIBLIOGRAPHY@@ |
| Output | `build/@@NAME@@.pdf` |

---

## Compilation

### Automatic (VS Code saves trigger this)

LaTeX Workshop is configured to run on save via `.vscode/settings.json`.
Recipe: `@@ENGINE@@mk` → output in `build/`.

### Manual

```bash
# Recommended — handles bibliography passes automatically
latexmk @@LATEXMK_FLAG@@ -interaction=nonstopmode -outdir=build @@NAME@@.tex
```

If `latexmk` is unavailable, run the full sequence manually:

@@COMPILE_MANUAL@@

### Verify the build

A PDF being produced does **not** mean the compilation succeeded —
`-interaction=nonstopmode` keeps going past fatal errors and produces a PDF with
missing or corrupted sections. After every compile, check `build/@@NAME@@.log` for:

- `! ` (any LaTeX/TeX error), `Extra \end{...}`, `Undefined control sequence`
- `Not allowed in LR mode` (almost always a `\\` inside a TikZ node label)
- `Empty bibliography`, `Citation '...' undefined`, `Reference '...' undefined`

Also check that every `\begin{...}`/`\end{...}` you added or edited is
balanced — an orphaned `\end{lstlisting}` or `\end{itemize}` left over from a
half-applied edit will corrupt everything that follows it in the PDF.

---

## File structure

| Path | Purpose |
|---|---|
@@STRUCTURE_ROWS@@

---

## Custom LaTeX commands

@@CUSTOM_COMMANDS@@

---

## How to add content

@@ADD_CONTENT@@

---

@@WRITING_GUIDE@@
## Content guidelines

### Language

This report's language is **@@LANG_NOTE@@** (see `frontmatter/metadata.tex`). Write
all section content — including captions, labels, and table/figure text — in
this language, regardless of the language used in this AGENTS.md file.

### Page layout and margins

Nothing may spill into the margin. After compiling, check `build/@@NAME@@.log` for
`Overfull \hbox` warnings and fix each one — the usual culprits are long unbreakable
strings (URLs, file paths, code identifiers, wide inline math), oversized images, or
wide tables. Fixes: wrap URLs/paths in `\url{}` or `\path{}`, allow the line to
break, scale the offending image or table down to `\linewidth`. Then confirm on the
rendered PDF that no text, figure, or table crosses the text block.

### Tables

Size each table to its content — neither wider than the text block nor awkwardly
large — and check the rendered PDF, not just the source:
- Prefer `tabularx` with `X` columns, or explicit `p{width}` columns sized to the
  actual text, over plain `l`/`c`/`r` columns for long content. `p{}`/`X` columns let
  cell text wrap cleanly instead of overflowing.
- Every cell's content must stay inside its own row and column — no text bleeding
  into the neighbouring column or past the table border. Long cells need a wrapping
  column type.
- For tables wider than the text width, wrap them in `\resizebox{\textwidth}{!}{...}`
  or reduce the font with `\small`/`\footnotesize`. For very tall tables, split them
  or use `longtable`.
- Avoid tables that look too narrow or too cramped for their content — a common
  rendering bug; fix it before finishing.

### Figures and diagrams (TikZ)

- **Verify every diagram on the rendered PDF.** No nodes may overlap, no arrow may
  cross a label, no text may overflow its box — overlapping or colliding elements are
  the most common diagram bug. Set explicit `node distance`, sizes and positions, and
  re-render until the layout is clean.
- Never use `\\` inside a TikZ node label, e.g. `{Capture\\(Pygame)}` — this raises
  `! LaTeX Error: Not allowed in LR mode.` and silently drops the second line. Use
  `align=center, text width=<value>` on the node, or `\shortstack{...}`.
- **Use colour to aid comprehension** (e.g. `fill=blue!10`, colored edges to group or
  distinguish elements) — a tasteful, consistent palette makes a diagram clearer.
- Keep diagrams within the page width — wrap large `tikzpicture`s in
  `\resizebox{\textwidth}{!}{...}` if needed.

### Table of contents

If the document has a table of contents, it must fit on a single page. If it spills
onto a second, tighten it rather than let it run long: reduce its depth
(`\setcounter{tocdepth}{2}` or `1`), shorten over-long section titles, or slightly
reduce the surrounding spacing/font (e.g. in `frontmatter/toc.tex`). Re-check on the
rendered PDF.

### Reported data and metrics

- Never invent quantitative results (accuracy, latency, coverage percentages,
  user-study scores, test pass counts, confusion matrices, etc.) that aren't
  backed by an actual file, log, or report in the project.
- If real data isn't available, write a clearly marked placeholder
  (`% TODO: replace with actual results from <where to find them>`) instead of
  plausible-looking fake numbers.

### Code excerpts

- Quote code from the actual source files faithfully (verbatim, or a clearly
  labeled summary) — don't rewrite or simplify an algorithm and present it as
  the real implementation.

---

## Common errors and fixes

| Error | Fix |
|---|---|
| LaTeX not installed | `latex-forge setup --install-tex` |
| `Package X not found` | `tlmgr install X` |
| Font not found | `tlmgr update --all` or install the missing font package |
| `! LaTeX Error: Not allowed in LR mode.` (inside a `tikzpicture`) | A TikZ node label contains `\\` — use `align=center, text width=<value>` instead |
| `Extra \end{...}` / `! Package ... Error: Extra \end...` | An environment was closed without a matching `\begin` — check for a duplicated paragraph or leftover line from a previous edit |
| References/citations show as `??` or stay undefined | Compile with `latexmk` (not a single engine call) — it runs the extra passes needed to resolve them |
@@BIB_ERRORS@@| Compilation stuck / blank pages | Delete `build/` then recompile |
| `Undefined control sequence \X` | Check `styles/packages/` files are present |
| PDF viewer shows duplicate page | VS Code PDF viewer in "Two Page" mode — switch to "Single Page" |

---

## Do not modify

- `styles/packages/*.sty` — managed by latex-forge; edits will be overwritten on reinstall
- `assets/logos/` — logo assets
- The `\input` / `\include` order in `@@NAME@@.tex` (section order matters for cross-references)

---

## Rename this project

```bash
latex-forge rename new-name
```

Renames the folder, the main `.tex` file, and build artifacts consistently.
