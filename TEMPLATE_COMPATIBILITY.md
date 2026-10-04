# Making a template compatible with latex-forge

`latex-forge template install <source>` accepts **any** Git repository, ZIP
file, or local folder that contains a `main.tex`. This guide explains how to
get the most out of `latex-forge create` with a template that wasn't built
for latex-forge from the start: your own templates, a colleague's, or one
found online.

None of this is required to install a template. It only affects two things:
which LaTeX engine is used, and whether `latex-forge create` can pre-fill
your name, email, university, etc. from your [profile](README.md#your-profile).

## 1. Folder layout

`latex-forge create` expects:

```
my-template/
├── main.tex              # required, renamed to <project-name>.tex on create
├── frontmatter/
│   └── metadata.tex       # optional, see "Profile placeholders" below
├── latexforge.toml         # optional, declares the LaTeX engine
└── ...                     # any other files (sections, assets, styles, .bib...)
```

Everything except `main.tex` is copied as-is. If your template doesn't use
this exact layout, it still installs and works: `latex-forge create` will
just rename your root `.tex` file and skip the steps below.

## 2. Declaring the LaTeX engine

`latexforge.toml` at the root of the template:

```toml
engine = "xelatex"
```

Valid values: `lualatex` (default if omitted), `xelatex`, `pdflatex`. This
controls the `latexmk` flag used by `latex-forge build`/`watch` and the
LaTeX Workshop settings written to the generated project's `.vscode/`.

If you don't want to edit the template's source, you can declare the engine
at install time instead:

```bash
latex-forge template install <source> --engine xelatex
```

This writes `latexforge.toml` for you in the installed copy (any other keys
already in the file are kept).

### Optional: the LaTeX packages the template needs

`latexforge.toml` can also list the TeX Live packages the template uses:

```toml
tex_packages = ["fontspec", "pgf", "tcolorbox", "xetex"]
```

With a lightweight TinyTeX (the default `latex-forge setup`), `latex-forge
create` then installs the missing ones in one go, so the first compile works
right away. Without the list, latex-forge finds them from the template's
`\usepackage` lines and a test compile — slower, and it can miss packages a
class loads only if they exist. Generate the list from a real compile on a
full TeX Live with the gallery's
[`compute_tex_packages.py`](https://github.com/thmsgo18/latex-forge-gallery/blob/main/scripts/compute_tex_packages.py)
(`--path <template-dir> --write`) rather than writing it by hand.

## 3. Profile placeholders

If `frontmatter/metadata.tex` exists, `latex-forge create` rewrites any of
the following standard commands using your profile
(`latex-forge profile set ...`). Commands you don't define are left alone;
add only the ones relevant to your template.

| Profile field | Recognized commands |
|---|---|
| Full name | `\newcommand{\authorname}{...}`, `\newcommand{\cvname}{...}` (also works as `\renewcommand`) |
| First / last name | `\newcommand{\cvfirstname}{...}`, `\newcommand{\cvlastname}{...}` |
| Email | `\newcommand{\authoremail}{...}`, `\newcommand{\cvemail}{...}` or `\newcommand{\cvmail}{...}` |
| Phone | `\newcommand{\authorphone}{...}`, `\newcommand{\cvphone}{...}` |
| GitHub username | `\newcommand{\cvgithub}{...}` |
| LinkedIn handle | `\newcommand{\cvlinkedin}{...}` |
| University | `\newcommand{\universityname}{...}` or `\newcommand{\cvuniversity}{...}` |
| Program / position | `\newcommand{\facultyname}{...}` or `\newcommand{\cvposition}{...}` |
| Supervisor | `\newcommand{\supervisorname}{...}` |

Example `frontmatter/metadata.tex`:

```latex
\newcommand{\authorname}{Your Name}
\newcommand{\authoremail}{you@example.com}
\newcommand{\universityname}{Your University}
```

After `latex-forge create --template my-template`, these are automatically
replaced with the values from your profile, no manual editing needed.

## 4. Checklist

- [ ] `main.tex` at the root of the template
- [ ] `latexforge.toml` with the right `engine` (or pass `--engine` at install time)
- [ ] `frontmatter/metadata.tex` uses the standard commands above, if you want profile auto-fill
- [ ] Compiles with `latexmk -<engine> main.tex` from a clean checkout

That's it: `latex-forge create --template <name>` will then produce a
project with the same structure (`.vscode/`, `.gitignore`, `AGENTS.md`,
`GETTING_STARTED.md`, `build`/`watch` support) as the built-in templates.
