# LaTeX Forge

LaTeX Forge is a command-line tool that scaffolds structured LaTeX projects from templates, compiles them to PDF through `latexmk`, and automatically fills in personal information across every new project from a saved profile.

## Core features

- **Create** a project from a built-in or gallery template in one command, pre-filled with your name, email, and institution.
- **Build** the project to PDF with automatic detection of the right LaTeX engine and auto-installation of missing TeX Live packages.
- **Watch** mode recompiles on every save.
- **Install** any template from the [gallery](https://github.com/thmsgo18/latex-forge-gallery), a GitHub URL, or a local directory.
- **Profile** stores your personal details once and injects them into every new project automatically.

## Quick start

```bash
# Install
pipx install latex-forge

# Set up your profile (optional but recommended)
latex-forge profile set

# Create a project
latex-forge create --name my-report --template project-report-en

# Compile
cd my-report
latex-forge build
```

## Ecosystem

| Repository | Role |
|---|---|
| [latex-forge](https://github.com/thmsgo18/latex-forge) | This CLI package (Python) |
| [latex-forge-gallery](https://github.com/thmsgo18/latex-forge-gallery) | Community template registry (80+ templates) |
| [latex-forge-vscode](https://github.com/thmsgo18/latex-forge-vscode) | VS Code extension (thin CLI wrapper) |
| [latex-forge-skill](https://github.com/thmsgo18/latex-forge-skill) | Claude Code skill for AI-assisted editing |

## Built-in templates

| Name | Description |
|---|---|
| `blank` | Minimal pdfLaTeX starter (article class, title, one section) |
| `cv-en` | English CV with education, experience, projects, skills |
| `cv-fr` | French CV with formation, experience, projets, competences |
| `project-report-en` | ISO/IEEE project report with requirements, architecture, testing |
| `project-report-fr` | AFNOR/ISO rapport de projet with cahier des charges, architecture |
| `research` | Two-column research article with related work, methodology, experiments |

For the full gallery of 80+ community templates, see [latex-forge-gallery](https://github.com/thmsgo18/latex-forge-gallery).
