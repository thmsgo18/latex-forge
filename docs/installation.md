# Installation

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10+ | |
| pipx | any | Recommended installer for CLI tools |
| TeX Live | 2022+ | Or MiKTeX on Windows |
| latexmk | any | Included in TeX Live full |

### Install TeX Live

=== "macOS"

    ```bash
    brew install --cask mactex
    ```

=== "Debian / Ubuntu"

    ```bash
    sudo apt-get install texlive-full latexmk
    ```

=== "Windows"

    Download the installer from [tug.org/texlive](https://tug.org/texlive/) and run it. MiKTeX is also supported.

=== "All platforms"

    Use the official TeX Live installer from [tug.org/texlive](https://tug.org/texlive/). This gives you the most up-to-date packages.

### Install pipx

```bash
pip install --user pipx
pipx ensurepath
```

## Install latex-forge

```bash
pipx install latex-forge
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
LaTeX Forge - Environment Diagnostics
══════════════════════════════════════
✓ latex-forge         0.5.0
✓ pipx                1.5.0
✓ TeX Live            2024  (pdflatex, lualatex, xelatex)
✓ latexmk             4.88
✓ biber               2.20
✗ Profile             not set  →  run: latex-forge profile set
✗ Default template    not configured
```

The two optional items (Profile and Default template) can be set later and are not required to compile documents.
