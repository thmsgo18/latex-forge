#!/bin/sh
# Install LaTeX Forge and LaTeX on macOS or Linux — no Python, pipx or admin
# rights needed:
#
#   curl -LsSf https://raw.githubusercontent.com/thmsgo18/latex-forge/main/install.sh | sh
#
# 1. installs uv (https://docs.astral.sh/uv/) if it's missing,
# 2. installs the latex-forge CLI with it, on a Python that uv manages,
# 3. runs `latex-forge setup` to install LaTeX: you pick the distribution
#    (light TinyTeX by default), then a test document is compiled.
#
# Environment variables:
#   LATEX_FORGE_TEX   light | full | system | none — skip the question
#                     (none: don't install LaTeX)
#   LATEX_FORGE_SPEC  what to install (default: latex-forge from PyPI; a
#                     local checkout or a git URL also work)
set -eu

TEX="${LATEX_FORGE_TEX:-}"
SPEC="${LATEX_FORGE_SPEC:-latex-forge}"
BIN_DIR="$HOME/.local/bin"

say() { printf '==> %s\n' "$*"; }
fail() { printf 'error: %s\n' "$*" >&2; exit 1; }

case "$TEX" in
  ""|light|full|system|none) ;;
  *) fail "LATEX_FORGE_TEX must be light, full, system or none (got '$TEX')" ;;
esac

# 1. uv
if command -v uv >/dev/null 2>&1; then
  UV="$(command -v uv)"
elif [ -x "$BIN_DIR/uv" ]; then
  UV="$BIN_DIR/uv"
else
  say "Installing uv (it installs latex-forge and the Python it runs on)"
  if command -v curl >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
  elif command -v wget >/dev/null 2>&1; then
    wget -qO- https://astral.sh/uv/install.sh | sh
  else
    fail "curl or wget is required"
  fi
  UV="$BIN_DIR/uv"
  [ -x "$UV" ] || fail "uv was not installed in $BIN_DIR"
fi

# 2. latex-forge (installed or upgraded)
say "Installing the latex-forge CLI"
"$UV" tool install --managed-python --force --upgrade "$SPEC"
"$UV" tool update-shell >/dev/null 2>&1 || true
LF="$BIN_DIR/latex-forge"
[ -x "$LF" ] || LF="$(command -v latex-forge || true)"
[ -n "$LF" ] || fail "latex-forge was installed but can't be found in $BIN_DIR"
"$LF" --version

# 3. LaTeX
if [ "$TEX" = "none" ]; then
  say "Skipping LaTeX (LATEX_FORGE_TEX=none). Install it later with: latex-forge setup --install-tex"
elif [ -n "$TEX" ]; then
  "$LF" setup --install-tex --tex "$TEX" --yes --skip-extensions
elif (exec </dev/tty) 2>/dev/null; then
  # Piped into sh, stdin is this script: ask the questions on the terminal.
  "$LF" setup --skip-extensions </dev/tty
else
  "$LF" setup --install-tex --tex light --yes --skip-extensions
fi

echo
say "Done. Open a new terminal (or run: export PATH=\"$BIN_DIR:\$PATH\"), then:"
echo "    latex-forge create"
