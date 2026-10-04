# Installation

LaTeX Forge needs two things: the `latex-forge` command and a LaTeX distribution. Neither requires administrator rights, and you don't need Python installed beforehand.

## One-line install (recommended)

=== "macOS / Linux"

    ```bash
    curl -LsSf https://raw.githubusercontent.com/thmsgo18/latex-forge/main/install.sh | sh
    ```

=== "Windows (PowerShell)"

    ```powershell
    powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/thmsgo18/latex-forge/main/install.ps1 | iex"
    ```

=== "VS Code"

    Install the [LaTeX Forge extension](https://marketplace.visualstudio.com/items?itemName=thmsgo18.latex-forge-vscode) and click **Set Up Now** (or run **LaTeX Forge: Install Everything**).

The installer:

1. installs [uv](https://docs.astral.sh/uv/) if it's missing — a single binary that installs Python tools and downloads a private Python for them;
2. installs `latex-forge` with `uv tool install`, on that uv-managed Python (so an OS or Homebrew Python upgrade can never break it);
3. runs `latex-forge setup`, which installs LaTeX — you choose the distribution — and compiles a test document to prove it works.

Set `LATEX_FORGE_TEX=light|full|system|none` to skip the distribution question.

## Choosing a LaTeX distribution

| `--tex` | What you get | Size | Admin rights |
|---|---|---|---|
| `light` (default) | [TinyTeX](https://yihui.org/tinytex/) in your home folder, plus everything the built-in templates use. Any other package a document needs is installed automatically the first time it's compiled | ~500 MB, a few minutes | No |
| `full` | TinyTeX with all of TeX Live (scheme-full), everything available offline | ~2 GB download | No |
| `system` | MacTeX (Homebrew), MiKTeX + Strawberry Perl (winget) or TeX Live (apt/dnf/pacman) | 5+ GB, 20–30 min | Yes |

```bash
latex-forge setup --install-tex            # light
latex-forge setup --tex full               # all of TeX Live (also upgrades a light install)
latex-forge setup --tex system             # through your package manager (asks for your password)
```

TinyTeX goes where its own installer would put it: `~/Library/TinyTeX` (macOS), `~/.TinyTeX` (Linux), `%APPDATA%\TinyTeX` (Windows); set `TINYTEX_DIR` to choose its parent folder. Its programs are linked into `~/.local/bin` (added to your shell's PATH unless you pass `--no-modify-path`), and latex-forge finds them even before you open a new terminal.

A distribution that's already installed (MacTeX, TeX Live, MiKTeX, a TinyTeX from R/Quarto…) is detected — even when it isn't on your PATH yet — and never modified.

Maintenance:

```bash
latex-forge setup --verify          # compile a test document
latex-forge setup --reinstall-tex   # after a new TeX Live year: reinstall, keeping your packages
latex-forge setup --remove-tex      # uninstall the TinyTeX managed by latex-forge
```

## Install by hand

If you already use uv or pipx:

```bash
uv tool install latex-forge      # or: pipx install latex-forge  (Python 3.10+)
latex-forge setup
```

Verify:

```bash
latex-forge --version
```

## Shell completion

LaTeX Forge uses `argcomplete` for tab completion. Enable it for your shell:

=== "Bash"

    ```bash
    eval "$(latex-forge completion --shell bash)"
    # Or add to ~/.bashrc for persistence:
    echo 'eval "$(latex-forge completion --shell bash)"' >> ~/.bashrc
    ```

=== "Zsh"

    ```bash
    eval "$(latex-forge completion --shell zsh)"
    # Or add to ~/.zshrc for persistence:
    echo 'eval "$(latex-forge completion --shell zsh)"' >> ~/.zshrc
    ```

=== "Fish"

    ```bash
    latex-forge completion --shell fish | source
    # Or add to ~/.config/fish/config.fish for persistence:
    latex-forge completion --shell fish >> ~/.config/fish/config.fish
    ```

## Development installation

Use this if you want to contribute or run the tests:

```bash
git clone https://github.com/thmsgo18/latex-forge.git
cd latex-forge
pipx install --editable ".[dev]"
```

The version is derived from the latest git tag via `setuptools-scm`. Running from an untagged commit will produce a version like `0.5.0.dev4+gab12cd3`.

## Verify the environment

After installation, run the diagnostics command to confirm everything is in order:

```bash
latex-forge diagnose
```

Expected output:

```
LaTeX Forge — Environment Diagnostics
══════════════════════════════════════
✓ latex-forge          0.8.0
✓ Installed with       uv  (Python 3.14.8)
✓ LaTeX                TinyTeX  (pdflatex, lualatex, xelatex)
✓ latexmk              Latexmk, John Collins, 9 March 2026. Version 4.88
✓ biber                biber version: 2.21
✓ GitHub CLI           gh version 2.96.0 (2026-07-02)
✗ Profile              not set  →  run: latex-forge profile set
✗ Default template     not configured
```

The two optional items (Profile and Default template) can be set later and are not required to compile documents.
