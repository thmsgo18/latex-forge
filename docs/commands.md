# CLI reference

## latex-forge create

Creates a new LaTeX project from a template.

```bash
latex-forge create [--name NAME] [--template TEMPLATE] [--output DIR] [--git]
```

| Flag | Description |
|---|---|
| `--name NAME` | Project name. Prompted interactively if omitted. Only letters, digits, hyphens and underscores are allowed. |
| `--template TEMPLATE` | Template to use. Prompted interactively if omitted. Tab-completion is available. |
| `--output DIR` | Directory where the project folder is created. Defaults to the configured `default_output_dir` or the current directory. |
| `--git` | Initialises a git repository with an initial commit inside the new project folder. |

**Examples**

```bash
# Interactive (prompts for name and template)
latex-forge create

# Non-interactive
latex-forge create --name thesis --template research

# Create in a specific folder and initialise git
latex-forge create --name paper --template research --output ~/Documents --git
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

If compilation fails and missing `.sty` or `.cls` files are detected in the log, LaTeX Forge tries to install them via `tlmgr` and retries once.

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

- `latex-forge` version
- `pipx` presence and version
- TeX Live presence, year, and available engines
- `latexmk` presence and version
- `biber` presence and version (needed for `biblatex` bibliographies)
- Profile configuration status
- Default template configuration status

Pass `--json` to get a structured JSON object instead of the human-readable table (used by the VS Code extension).

Exit code `1` if TeX Live or `latexmk` is missing.

---

## latex-forge setup

Installs VS Code extensions and checks LaTeX prerequisites.

```bash
latex-forge setup [--check-only] [--skip-extensions] [--install-tex]
```

| Flag | Description |
|---|---|
| `--check-only` | Checks the environment without installing anything. |
| `--skip-extensions` | Skips VS Code extension installation. |
| `--install-tex` | Attempts to install a TeX distribution with a system package manager. |

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
