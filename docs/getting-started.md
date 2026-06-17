# First project

This walkthrough creates a project report, compiles it to PDF, and covers the key conventions every project follows.

## 1. Set up your profile (recommended)

Run this once to save your personal information:

```bash
latex-forge profile set
```

You will be prompted for your name, email, university, and other details. These values are injected automatically into every new project so you never retype them.

## 2. Create a project

```bash
latex-forge create --name my-report --template project-report-en
```

If you omit `--name` or `--template`, the command prompts you interactively with a numbered list.

The project is created in the current directory by default. Use `--output /path/to/dir` to choose a different location, or configure a default in `~/.latex-forge.toml` (see [Profile](profile.md)).

### What gets created

```
my-report/
  my-report.tex              # Main entry point
  frontmatter/
    metadata.tex             # Title, authors, university (pre-filled from profile)
    abstract.tex
    toc.tex
  sections/
    introduction.tex
    requirements.tex
    architecture.tex
    implementation.tex
    results.tex
    testing.tex
    conclusion.tex
  backmatter/
    acknowledgements.tex
    appendices.tex
    ai-statement.tex
  bibliography/
    references.bib
  styles/packages/           # Local .sty files required by the template
  .vscode/
    settings.json            # LaTeX Workshop recipe (auto-detected engine)
  .gitignore
  scripts/
    setup.sh / setup.bat / setup.py
  GETTING_STARTED.md         # Quick reference inside the project
  AGENTS.md                  # Briefing for AI code assistants
```

!!! note "Naming convention"
    The main `.tex` file is always named after the project folder (`my-report.tex` inside `my-report/`). The `latex-forge build` and `latex-forge rename` commands rely on this convention.

## 3. Fill in the metadata

Open `frontmatter/metadata.tex`. If you ran `profile set`, your name and institution are already filled in. Complete the remaining fields:

```latex
\newcommand{\docTitle}{My Project Report}
\newcommand{\docSubtitle}{Subtitle (optional)}
```

## 4. Compile

```bash
cd my-report
latex-forge build
```

The PDF is written to `build/my-report.pdf`.

On first compile, `latexmk` may detect missing TeX Live packages and install them automatically via `tlmgr`. If auto-install fails (offline or restricted environment), the error message tells you which package to install manually.

## 5. Watch mode

Keep the PDF in sync while writing:

```bash
latex-forge watch
```

Press `Ctrl+C` to stop. This runs `latexmk -pvc` under the hood, which recompiles whenever any source file changes.

## 6. Export for submission

Package the sources and compiled PDF into a clean ZIP:

```bash
latex-forge export
```

This creates `my-report-export.zip` next to the project folder, excluding build artifacts, `.git`, `.vscode`, and editor files.

## Common next steps

- Install a template from the gallery: see [Templates](templates.md)
- Understand how the profile is applied: see [Profile](profile.md)
- Rename the project: `latex-forge rename my-report final-report`
