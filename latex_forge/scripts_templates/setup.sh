#!/usr/bin/env bash
# Set this LaTeX project up on the current machine (see setup.py --help).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 &&
     "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 8))' >/dev/null 2>&1; then
    exec "$candidate" "$SCRIPT_DIR/setup.py" "$@"
  fi
done

# No usable Python: uv can run the script with a Python it downloads itself.
for uv in uv "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv"; do
  if command -v "$uv" >/dev/null 2>&1; then
    exec "$uv" run --no-project --python 3.12 "$SCRIPT_DIR/setup.py" "$@"
  fi
done

echo "Python 3.8+ is required to run this setup script."
echo "Install it, or install uv (which brings its own Python) and run this script again:"
echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
exit 1
