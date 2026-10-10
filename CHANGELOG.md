# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

## [0.8.1] - 2026-10-10

### Fixed
- LaTeX packages stopped installing (during `setup`, `create` and the on-demand installs of `build`) once the package repository shipped a newer `tlmgr` than the installed TinyTeX: `tlmgr install` refused to do anything until `tlmgr update --self` was run, and on Windows it even reported success. latex-forge now updates `tlmgr` when it asks for it and retries the install.

## [0.8.0] - 2026-10-04

### Added
- **LaTeX without administrator rights**: `latex-forge setup --install-tex` now installs [TinyTeX](https://yihui.org/tinytex/) in your home folder (~500 MB, a few minutes) instead of a 5 GB system distribution, plus every package the built-in templates use, and compiles a test document to prove it works. `--tex {light,full,system}` picks the distribution: `full` is all of TeX Live (still no admin rights, also upgrades a light install), `system` is the previous MacTeX/MiKTeX/TeX Live install through the package manager. Without flags, `setup` asks. An existing distribution is never touched.
- **One-line installers** for people who don't use VS Code: `install.sh` (macOS/Linux, `curl … | sh`) and `install.ps1` (Windows) install uv, the CLI on a uv-managed Python, and LaTeX — no Python, pipx or admin rights needed.
- **Missing packages are installed on demand**: `build` now recognises missing files, OpenType fonts, biblatex styles, babel languages, hyphenation patterns and helper programs (biber, bibtex, makeindex), installs the TeX Live package for each, and recompiles until the document builds. Lookups use the repository's package database (downloaded once, cached a week) instead of one slow `tlmgr search` per file.
- **`create` installs what the template needs** on a lightweight TinyTeX, so the first compile in VS Code just works: from the template's `tex_packages` list when it has one (built-in templates, and gallery templates once the gallery publishes them), otherwise from its sources and a throwaway test compile. `--skip-packages` turns it off (e.g. offline).
- `setup --yes`, `--verify` (test compile), `--no-modify-path`, `--reinstall-tex` (after a new TeX Live year, keeping your packages) and `--remove-tex`.
- `watch` installs the packages the sources load before starting `latexmk -pvc`.
- `diagnose` reports the distribution in use (TinyTeX, TeX Live, MacTeX, MiKTeX…), where it is, whether missing packages can be installed automatically, and how latex-forge itself was installed (`uv`, `pipx`, …) — the VS Code extension uses it to upgrade the CLI the right way. `--json` adds `tex_distribution` and `cli_install`; existing keys are unchanged.
- A project's `scripts/setup.py`/`.sh`/`.bat` now install LaTeX the same way (light by default) and the project's own packages, with a standalone copy of the installer (`scripts/toolchain.py`), so a cloned project can be set up without latex-forge. The shell wrappers fall back to `uv run` when no Python 3.8+ is available.

### Changed
- `latex-forge setup --install-tex` installs the light TinyTeX by default; use `--tex system` for the previous behaviour.
- TeX tools are now found even when they aren't on PATH: the managed TinyTeX and the usual install locations (MacTeX's `/Library/TeX/texbin`, `/usr/local/texlive/<year>`, `C:\texlive\<year>`, MiKTeX) are searched too, so no more "restart VS Code / open a new terminal" after installing LaTeX.
- Python 3.13 and 3.14 are supported and tested (3.14 is what uv installs for new users).
- `diagnose` shows "LaTeX" instead of "TeX Live" (it can be MiKTeX) and suggests the right install command for your distribution (`tlmgr install`, `sudo tlmgr install`, `mpm --install`, or `latex-forge setup --install-tex`).

### Fixed
- `build` retried with plain `latexmk` after installing a package, which latexmk answered with "Nothing to do" because the sources hadn't changed: the retry now forces a rebuild (`-g`), and keeps going while each round installs something new.
- The system install could never succeed from VS Code: MacTeX's installer (and `sudo apt`) need an administrator password but ran without a terminal. It now refuses up front with the command to run in a terminal (the extension runs it in one).
- With MiKTeX, latexmk failed with "could not find the script engine 'perl'": the system install now also installs Strawberry Perl, and `diagnose` reports latexmk as broken (with the fix) in that situation.
- `pacman` installs no longer wait forever for a confirmation nobody can give (`--noconfirm`).
- On Windows, `tlmgr` (a `.bat`) and `code` (a `.cmd`) are run by full path; running them by bare name failed.
- `setup` finds VS Code's `code` command in its default install location when it isn't on PATH.
- `template install --engine` no longer erases the other keys of an existing `latexforge.toml`.
- On Windows consoles using a legacy code page (cp1252), `diagnose` and `template update` crashed with a `UnicodeEncodeError` on the ✓/✗/→ symbols; they now fall back to `OK`, `X` and `->`.
- `~/.latex-forge.toml` is located when it's read, not when latex-forge starts.

## [0.7.0] - 2026-07-31

### Added
- **`latex-forge create --repo {create,existing,none}`**: an open-ended versioning choice. `create` creates a brand-new GitHub repository for the project via the GitHub CLI (`gh`) — initializes git, commits, and pushes — so you never have to create it by hand; `existing` assumes the project folder already lives inside a versioned (e.g. GitHub) folder and leaves git untouched; `none` keeps the project fully local. Defaults to `default_repo_mode` in `~/.latex-forge.toml`, or `none`.
- **`--repo-name`/`--visibility {private,public}`**: name and visibility (default `private`) for the GitHub repository created with `--repo create`.
- **`latex-forge setup --install-gh`**: installs the GitHub CLI via the host's package manager (Homebrew/winget/apt/dnf/pacman), the same way `--install-tex` installs a TeX distribution. `latex-forge diagnose` now also reports whether `gh` is installed and authenticated.
- The interactive `create` prompt now asks how to version the project (and, for `create`/`existing`, what to share) when run without flags, with a confirmation recap before actually creating a GitHub repository.
- `GETTING_STARTED.md` and the post-create summary now report the chosen versioning mode and, for `create`, the created repository's URL.

### Changed
- **Breaking**: `--git` is replaced by `--repo create` (local git init + commit, plus creating a new GitHub repository) or `--repo existing` (nothing git-related is touched at all — for a project nested inside an already-versioned folder). `--sharing` no longer accepts `none` — use `--repo none` instead, which implies it.

## [0.6.0] - 2026-07-31

### Added
- **`latex-forge create --sharing {full,pdf-only,none}`**: controls what the generated `.gitignore` tracks — `full` shares the LaTeX sources and the compiled PDF, `pdf-only` shares only the compiled PDF, and `none` keeps the whole project local. Defaults to `full`, or to `default_sharing` in `~/.latex-forge.toml` if set.
- **`latex-forge create --build-before-commit`**: with `--git` and a PDF-sharing mode, builds the project once before the initial commit so the compiled PDF is included right away instead of only appearing after your first manual build.
- `GETTING_STARTED.md` now documents the chosen sharing mode, with a reminder to build and commit the PDF yourself when it isn't in the initial commit yet.
- Generated `AGENTS.md` now includes a **writing-quality guide** for academic documents (reports, research articles, theses and any gallery template in the `report`/`research` families). It states the quality bar — start from the real source material (read the project/code/data the report documents, never invent), clear thesis, evidence over assertion, signposting, depth, right length (no padding), varied layout (lists, tables, figures, formulas — not walls of text), critical stance, register, coherence — plus a pre-finish self-review checklist, so a single "write the report" prompt yields a substantive draft rather than a skeleton. CV and blank projects are unaffected.
- The shared `AGENTS.md` **Content guidelines** were hardened for rendering quality across all templates: nothing overflowing the margins (`Overfull \hbox`), correctly sized tables with no cell content bleeding past its row/column, diagrams verified overlap-free on the PDF (and colour encouraged for clarity), and a table of contents kept to a single page.

### Fixed
- `latex-forge create --git` no longer silently reports "could not initialize git" when nothing is staged for the initial commit (e.g. with `--sharing none`) — the initial commit now uses `--allow-empty`.

## [0.5.0] - 2026-06-10

### Added
- **`latex-forge create --git`**: initializes a git repository in the new project and creates an initial commit.
- **`latex-forge export [project] [--output file.zip]`**: bundles the project's sources and compiled PDF into a clean ZIP for submission (arXiv, journal, teacher), excluding build artifacts and VCS metadata.
- **`latex-forge build`/`watch`** now auto-install missing LaTeX packages: on a "File `X.sty' not found" error, the package providing it is looked up via `tlmgr search` and installed automatically before retrying the build.
- **`latex-forge template install --engine {pdflatex,xelatex,lualatex}`**: declares the LaTeX engine for a template that doesn't already specify one, writing `latexforge.toml`. See [TEMPLATE_COMPATIBILITY.md](TEMPLATE_COMPATIBILITY.md) for making third-party templates fully compatible (engine + profile placeholders).
- Gallery template installs (`template install <gallery-url>`) now download a small per-template archive instead of the entire gallery repository, making installs much faster.

## [0.4.0] - 2026-06-10

### Added
- **`latex-forge build [project]`**: compiles the project to PDF with latexmk, no editor required. Reads the engine from the project's `.vscode/settings.json` (same invocation LaTeX Workshop would use, LuaLaTeX fallback), outputs to `build/`, and prints actionable hints on failure. `--clean` deletes `build/` first.
- **`latex-forge watch [project]`**: continuous compilation on every save (`latexmk -pvc`), stop with Ctrl+C.

### Fixed
- Template names are validated on install/remove: names containing path separators or `..` can no longer escape the user template library.
- `profile.toml` values containing quotes or backslashes are escaped correctly, and a corrupted profile file no longer blocks project creation.
- `latex-forge rename` with an invalid name prints a clean error instead of a traceback, and files with multi-part extensions (e.g. `.synctex.gz`) are renamed correctly.

## [0.3.0] - 2026-06-09

### Added
- **Install tracking**: after every `template install`, metadata (version, install URL, timestamp) is persisted to `~/.latex-forge/installed_templates.json`.  The VS Code extension can read this file directly without spawning the CLI.
- **`latex-forge template list --json`**: outputs all templates (built-in + user-installed) as a JSON array with `name`, `type`, `description`, `installed_version`, and `install_url` fields.
- **`latex-forge template update [name]`**: checks the gallery for newer versions of user-installed templates and reinstalls them.  Accepts an optional template name to update only one; otherwise updates all.  Supports `--json`. Exit codes: `0` = at least one update applied, `1` = error, `2` = nothing to update / already up to date.
- **`latex-forge diagnose`**: environment health check that reports the installed latex-forge version, pipx, TeX Live (year + available engines), latexmk, profile status, and default template. Supports `--json`. Exit code `1` if TeX Live or latexmk is missing.
- **Template versioning in gallery**: `gallery.json` schema bumped to `v2.0`; every template entry now carries a `"version": "1.0.0"` semver field used by `template update` to detect outdated installs.

## [0.2.5] - 2026-06-09

### Added
- User profile stored at `~/.latex-forge/profile.toml`: name, email, phone, website, GitHub, LinkedIn, university, faculty, program, supervisor, company, department, job title.
- `latex-forge profile set`: interactive prompts to create or update the profile.
- `latex-forge profile show`: display the current profile.
- `latex-forge profile clear`: delete the profile.
- Profile is applied automatically at `latex-forge create`: substitutes values into `frontmatter/metadata.tex` (reports, blank) and `sections/heading.tex` / `sections/en-tete.tex` (CVs). Silent no-op for external/gallery templates and unset fields.
- Profile file is plain TOML, readable and writable directly by the future VS Code extension without spawning the CLI.

## [0.2.4] - 2026-06-08

### Added
- New built-in template `blank`: minimal pdfLaTeX `article` starter with title, author, and one section, the simplest possible starting point.
- `latex-forge template install` now raises an error if the template name is already installed, preventing silent overwrites. Add `--force` to overwrite explicitly.
- Attempting to install a template with the same name as a built-in template now raises a clear error.

### Fixed
- `AGENTS.md` and `GETTING_STARTED.md` now reflect the actual LaTeX engine of the template instead of always showing LuaLaTeX.
- Added `.claude/` to `.gitignore` so Claude Code session files are never accidentally committed.

## [0.2.3] - 2026-06-08

### Changed
- Renamed the built-in templates `rapport-projet-en`/`rapport-projet-fr` to `project-report-en`/`project-report-fr`, so the template name is in English regardless of the document's language, consistent with `cv-en`/`cv-fr`. Update `--template`, `default_template`, and any scripts that reference the old names.

## [0.2.2] - 2026-06-07

### Added
- Project creation now reads the LaTeX engine (`lualatex`/`xelatex`/`pdflatex`) from each template's `latexforge.toml` and generates the matching `latexmk` recipe in `.vscode/settings.json`
- `apply_profile_to_metadata` (now removed, see below) gained `\author{PLACEHOLDER}` recognition before the feature was dropped entirely

### Changed
- Both READMEs rewritten to lead with the live PDF preview experience rather than LaTeX itself, with a real screenshot and an "AI-friendly by design" section

### Removed
- The `latex-forge profile` command and the whole user-profile feature (`get_profile`/`save_profile`, `apply_profile_to_metadata`, `apply_profile_to_cv_heading`, the first-launch profile prompt, and related tests/docs). Generated projects now keep their template placeholders for the user to fill in directly.

## [0.2.0] - 2026-06-02

### Added
- Interactive mode: `create` prompts for name, template, and output directory when arguments are omitted
- `--output` flag to specify where the project is created
- `--version` flag
- Guided LaTeX installation: first run checks the environment and offers to install LaTeX automatically
- `latex-forge setup` now prompts interactively to install LaTeX when it is missing, without requiring `--install-tex`
- Offer to open the generated project in VS Code after creation
- Installation duration warning for long-running commands (MacTeX takes ~20-30 min)
- Name validation: rejects spaces, special characters, and dot-prefixed names
- 29 automated tests covering all critical paths
- PyPI metadata: authors, readme, keywords, classifiers, project URLs
- MIT license
- GitHub Actions workflow for automated PyPI publishing on version tags
- CI workflow running tests on Python 3.10, 3.11, and 3.12

### Changed
- All CLI messages translated to English
- `create_project` is now atomic: the project folder is removed automatically if an error occurs mid-creation
- `patch_local_style` now uses a regex instead of fragile exact-string matching
- `rename_project` and `rename_current_project` refactored into a shared `_rename` helper
- Templates, styles, and assets moved inside the Python package for correct pip distribution
- Cleaner output after `create`: removed internal technical details

### Fixed
- `sys.stdin.isatty()` inconsistency in interactive checks replaced with `_is_interactive()` helper
- `KeyboardInterrupt` during template selection now exits cleanly instead of looping
- `OSError` handling added to all prompt functions for robustness on Windows and in CI environments

### Removed
- Legacy `scripts/new-project.py` and `scripts/new-project.sh` compatibility wrappers

## [0.1.0] - 2026-06-01

### Added
- Initial release
- `create` command to generate standalone LaTeX projects from templates
- `rename` command to rename a project folder and its main `.tex` file
- `setup` command to check and install the LaTeX environment
- `list-templates` command
- Four templates: `rapport-projet-en`, `rapport-projet-fr`, `rapport-ter`, `research`
- Automatic style dependency resolution
- VS Code settings and extension recommendations generated per project
- Standalone setup scripts embedded in each generated project
- Cross-platform support: macOS, Linux, Windows
- Published to PyPI
