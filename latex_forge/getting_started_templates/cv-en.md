# Getting Started — @@NAME@@

## Workflow

**1. Edit your personal information**

Open `sections/heading.tex` and fill in your name, phone, email and GitHub/LinkedIn links.

**2. Fill in each section**

Edit the files in `sections/` — one file per section.

**3. Save to compile**

Save `@@NAME@@.tex` in VS Code → LaTeX Workshop compiles automatically → PDF in `build/@@NAME@@.pdf`.

---

## Section structure

| File | Content |
|---|---|
| `sections/heading.tex` | Name, contacts, summary |
| `sections/education.tex` | Degrees and education |
| `sections/experience.tex` | Work experience |
| `sections/projects.tex` | Personal and academic projects |
| `sections/involvement.tex` | Volunteering and associations |
| `sections/skills.tex` | Technical skills and languages |

---

## Common operations

### Add a work experience

In `sections/experience.tex`, add a `\resumeSubheading` block:

```latex
\resumeSubheading
  {Job Title}{Month 20XX -- Month 20XX}
  {Company Name}{City, Country}
  \begin{itemize}[leftmargin=0.12in, label={}, itemsep=0pt]
    \item \small Description of your responsibilities.
  \end{itemize}
```

### Add a project

In `sections/projects.tex`, add a `\resumeProjectHeading` block:

```latex
\resumeProjectHeading
  {\textbf{\href{https://github.com/username/project}{Name -- Technologies}}}{Context}
  \begin{itemize}[leftmargin=0.12in, label={}, itemsep=0pt]
    \item \small Project description.
  \end{itemize}
```

---

## If compilation fails

1. **LaTeX not installed** → `latex-forge setup --install-tex`
2. **LaTeX Workshop not installed** → install from the VS Code Extensions panel
3. **Font not found** → make sure TeX Live is up to date: `tlmgr update --all`
4. **Compilation stuck** → delete the `build/` folder and try again

This CV uses **LuaLaTeX** (for fontspec). Verify:

```bash
lualatex --version
```

---

## Resources

| Resource | Link |
|---|---|
| Overleaf — CV templates | <https://www.overleaf.com/gallery/tagged/cv> |
| LaTeX Wikibook | <https://en.wikibooks.org/wiki/LaTeX> |
| fontawesome5 icons | <https://mirrors.ctan.org/fonts/fontawesome5/doc/fontawesome5.pdf> |
