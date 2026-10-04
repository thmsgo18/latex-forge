# CLI reference

## latex-forge create

Creates a new LaTeX project from a template.

```bash
latex-forge create [--name NAME] [--template TEMPLATE] [--output DIR]
                   [--repo {create,existing,none}] [--repo-name NAME] [--visibility {private,public}]
                   [--sharing {full,pdf-only}] [--build-before-commit] [--skip-packages]
```

| Flag | Description |
|---|---|
| `--name NAME` | Project name. Prompted interactively if omitted. Only letters, digits, hyphens and underscores are allowed. |
| `--template TEMPLATE` | Template to use. Prompted interactively if omitted. Tab-completion is available. |
| `--output DIR` | Directory where the project folder is created. Defaults to the configured `default_output_dir` or the current directory. |
| `--repo MODE` | `create` a new GitHub repository (git init + commit + `gh repo create`), `existing` (the folder already lives in a versioned folder: git is left alone), or `none` (default). |
| `--repo-name`, `--visibility` | Name (default: the project name) and visibility (default: private) of the repository created with `--repo create`. |
| `--sharing MODE` | What the `.gitignore` tracks with `--repo create/existing`: `full` (sources + PDF) or `pdf-only`. |
| `--build-before-commit` | With `--repo create`, build once so the PDF is in the initial commit. |
| `--skip-packages` | Don't install the LaTeX packages the template needs. Only relevant with a lightweight TinyTeX, where they are otherwise installed right away (useful offline). |

**Examples**

```bash
# Interactive (prompts for name, template and versioning)
latex-forge create

# Non-interactive
latex-forge create --name thesis --template research

# Create in a specific folder, with its own private GitHub repository
latex-forge create --name paper --template research --output ~/Documents --repo create
```

---

## latex-forge build

Compiles the project to PDF using `latexmk`.

```bash
latex-forge build [PROJECT] [--clean] [--verbose]
```

| Argument | Description |
|---|---|
| `PROJECT` | Path to the project directory. Defaults to the current directory. |
| `--clean` | Deletes `build/` before compiling. Use this to recover from corrupted auxiliary files. |
| `--verbose` | Shows the full `latexmk` output instead of filtering to errors only. |

The engine (`lualatex`, `xelatex` or `pdflatex`) is read from `.vscode/settings.json` inside the project. The compiled PDF is written to `build/<project-name>.pdf`.

If compilation fails because something is missing — a `.sty`/`.cls` file, an OpenType font, a biblatex style, a babel language, `biber` — LaTeX Forge installs the TeX Live package that provides it with `tlmgr` and recompiles, as many times as needed (LaTeX stops at the first missing file). This works with the TinyTeX installed by `latex-forge setup` or any TeX Live you own; with a system-wide TeX Live, the `sudo tlmgr install …` command to run is printed instead. MiKTeX installs missing packages on its own.

The TeX tools are found even when they aren't on your PATH (a freshly installed TinyTeX, MacTeX in an editor started from the Dock…).

---

## latex-forge watch

Recompiles automatically whenever a source file changes.

```bash
latex-forge watch [PROJECT] [--verbose]
```

This runs `latexmk -pvc` and keeps the terminal attached. Press `Ctrl+C` to stop. The same engine detection as `build` applies.

---

## latex-forge export

Bundles the project into a ZIP archive for submission.

```bash
latex-forge export [PROJECT] [--output PATH]
```

| Argument | Description |
|---|---|
| `PROJECT` | Path to the project directory. Defaults to the current directory. |
| `--output PATH` | Where to write the ZIP. Defaults to `<project>-export.zip` next to the project folder. |

The archive contains the full source tree. Excluded items: `build/`, `.git/`, `.vscode/`, `.DS_Store`, and other editor files. The compiled PDF is included if present inside `build/`.

---

## latex-forge rename

Renames the project folder and its main `.tex` file in sync.

```bash
# From inside the project folder
latex-forge rename new-name

# From the parent folder
latex-forge rename old-name new-name
```

This keeps the `<folder>/<folder>.tex` naming convention intact, which `build` and `export` rely on.

---

## latex-forge template

Manages user-installed templates.

### install

```bash
latex-forge template install SOURCE [--name NAME] [--force] [--engine ENGINE]
```

| Argument | Description |
|---|---|
| `SOURCE` | GitHub URL, ZIP URL, local directory, or local `.zip` file. |
| `--name NAME` | Name to give the installed template. Defaults to the repository or folder name. |
| `--force` | Overwrites an existing user-installed template with the same name. |
| `--engine ENGINE` | LaTeX engine (`lualatex`, `xelatex`, `pdflatex`). Written to `latexforge.toml` if the template does not already declare one. |

**Supported sources**

```bash
# Gallery template (fast: downloads a flat ZIP from the dist branch)
latex-forge template install https://github.com/thmsgo18/latex-forge-gallery/tree/main/templates/thesis/clean-thesis

# Any GitHub repository
latex-forge template install https://github.com/owner/my-template

# ZIP URL
latex-forge template install https://example.com/my-template.zip

# Local directory
latex-forge template install ./my-template

# Local ZIP file
latex-forge template install ./my-template.zip --name custom-name
```

### list

```bash
latex-forge template list [--json]
```

Lists built-in and user-installed templates. Pass `--json` for machine-readable output with version and install URL metadata.

### update

```bash
latex-forge template update [NAME] [--json]
```

Checks for newer versions of gallery-installed templates by comparing the locally recorded version against `gallery.json`. If `NAME` is omitted, all user-installed gallery templates are checked.

Exit codes: `0` (at least one template updated), `1` (error), `2` (all up to date).

### remove

```bash
latex-forge template remove NAME
```

Removes a user-installed template. Built-in templates cannot be removed.

---

## latex-forge profile

Manages the user profile stored in `~/.latex-forge/profile.toml`.

### set

```bash
latex-forge profile set
```

Interactive prompt that walks through all profile fields. Press Enter to keep the current value. Leave blank to clear a field.

### show

```bash
latex-forge profile show
```

Prints all profile fields and their current values.

### clear

```bash
latex-forge profile clear
```

Deletes the profile file entirely.

---

## latex-forge diagnose

Checks the environment and reports the status of every required component.

```bash
latex-forge diagnose [--json]
```

Checks:

- `latex-forge` version, and how it was installed (`uv`, `pipx`, ...)
- the LaTeX distribution (TinyTeX, TeX Live, MacTeX, MiKTeX…), its location, and whether missing packages can be installed automatically
- TeX Live presence, year, and available engines
- `latexmk` presence and version
- `biber` presence and version (needed for `biblatex` bibliographies)
- Profile configuration status
- Default template configuration status

Pass `--json` to get a structured JSON object instead of the human-readable table (used by the VS Code extension).

Exit code `1` if TeX Live or `latexmk` is missing.

---

## latex-forge setup

Installs LaTeX (no administrator rights needed by default), checks that it works, and installs the recommended VS Code extensions.

```bash
latex-forge setup [--check-only] [--skip-extensions] [--install-tex] [--tex {light,full,system}]
                  [--yes] [--verify] [--no-modify-path] [--install-gh]
                  [--reinstall-tex] [--remove-tex]
```

| Flag | Description |
|---|---|
| `--check-only` | Checks the environment without installing anything. |
| `--skip-extensions` | Skips VS Code extension installation. |
| `--install-tex` | Installs a LaTeX distribution if none is found — `light` unless `--tex` says otherwise. An existing distribution is never touched. |
| `--tex KIND` | `light` (TinyTeX, ~500 MB, packages added on demand), `full` (all of TeX Live, ~2 GB, also upgrades a light install) or `system` (MacTeX/MiKTeX/TeX Live via the package manager — needs an admin password, so it refuses to run without a terminal). |
| `--yes` | Never prompts: installs the light distribution if LaTeX is missing. |
| `--verify` | Compiles a test document (done automatically after an install). |
| `--no-modify-path` | Doesn't add `~/.local/bin` to your shell startup files. |
| `--install-gh` | Installs the GitHub CLI (needed for `create --repo create`). |
| `--reinstall-tex` | Reinstalls the managed TinyTeX, keeping its packages — needed after a new TeX Live year. |
| `--remove-tex` | Uninstalls the managed TinyTeX. |

Without flags, `setup` asks which distribution to install when LaTeX is missing. Exit code `0` when the environment can compile, `1` otherwise.

---

## latex-forge list-templates

Prints a table of all available templates (built-in and user-installed) with short descriptions.

```bash
latex-forge list-templates
```

---

## latex-forge completion

Prints shell completion setup code.

```bash
latex-forge completion [--shell SHELL]
```

`SHELL` is auto-detected from `$SHELL` if omitted. Supported values: `bash`, `zsh`, `fish`.
