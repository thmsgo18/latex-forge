# Templates

## Built-in templates

Built-in templates ship with the `latex-forge` package and are available immediately after installation.

| Name | Engine | Description |
|---|---|---|
| `blank` | pdfLaTeX | Minimal starter: article class, title page, one empty section |
| `cv-en` | pdfLaTeX | English CV with sections for education, experience, projects, involvement, skills |
| `cv-fr` | pdfLaTeX | French CV with sections for formation, experience, projets, engagement, competences |
| `project-report-en` | LuaLaTeX | ISO/IEEE project report: requirements, architecture, implementation, testing, bibliography |
| `project-report-fr` | LuaLaTeX | AFNOR/ISO rapport de projet: cahier des charges, architecture, implementation, tests, bibliographie |
| `research` | LuaLaTeX | Two-column research article: related work, methodology, experiments, bibliography |

List them at any time with:

```bash
latex-forge list-templates
```

## Gallery templates

The [latex-forge-gallery](https://github.com/thmsgo18/latex-forge-gallery) hosts 80+ community templates across categories including thesis, book, presentation, poster, cheatsheet, and more.

### Install from the gallery

Copy the URL of the template directory on GitHub and pass it to `template install`:

```bash
latex-forge template install \
  https://github.com/thmsgo18/latex-forge-gallery/tree/main/templates/thesis/clean-thesis
```

Gallery templates are installed from a flat ZIP archive served on the `dist` branch of the gallery repository, so only the template files are downloaded.

After installation, the template appears in `latex-forge list-templates` and can be used with `latex-forge create --template clean-thesis`.

### Update gallery templates

```bash
# Update all gallery-installed templates
latex-forge template update

# Update one specific template
latex-forge template update clean-thesis
```

Updates are version-gated: a template is only reinstalled when the version in `gallery.json` is newer than the locally recorded version.

## Installing from other sources

```bash
# Any GitHub repository (downloads the whole repository as a ZIP)
latex-forge template install https://github.com/owner/my-latex-template

# Public ZIP URL
latex-forge template install https://example.com/my-template.zip

# Local directory
latex-forge template install ./my-template-folder

# Local ZIP file, with a custom install name
latex-forge template install ./template.zip --name my-template
```

### Engine override

If a third-party template does not declare a LaTeX engine, specify it at install time:

```bash
latex-forge template install https://github.com/owner/template --engine xelatex
```

This writes `latexforge.toml` inside the installed template so `build` uses the right compiler.

## Template file structure

A valid latex-forge template must follow this layout:

```
<template-name>/
  main.tex                      # Required: entry point, must compile standalone
  latexforge.toml               # Required if the engine is not lualatex (the default)
  frontmatter/
    metadata.tex                # Standard placeholders for profile injection
  sections/                     # Body content files
  backmatter/                   # Appendices, bibliography calls
  bibliography/
    references.bib              # Required if the template uses bibliography commands
  images/
    .gitkeep
```

### Engine declaration

`latexforge.toml` declares the LaTeX engine the template requires:

```toml
engine = "pdflatex"   # or "xelatex"
```

Omit the file entirely if the template works with LuaLaTeX (the default). The engine is written into the project's `.vscode/settings.json` at creation time so VS Code and `latex-forge build` always use the same compiler.

### Standard placeholders

`frontmatter/metadata.tex` uses `\newcommand` placeholders that the profile injection system recognises:

```latex
\newcommand{\authorname}{FirstName LASTNAME}
\newcommand{\authoremail}{firstname.lastname@example.edu}
\newcommand{\universityname}{Example University}
```

See [Profile](profile.md) for the full list of recognised command names.

## Where templates are stored

| Type | Location |
|---|---|
| Built-in | `latex_forge/templates/` inside the installed Python package |
| User-installed | `~/.latex-forge/templates/` |

The user library takes precedence: if you install a template with the same name as a built-in, the user version is used. The reverse is protected: you cannot overwrite a built-in template with `template install`.
