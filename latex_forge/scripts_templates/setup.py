#!/usr/bin/env python3
"""Set this LaTeX project up on the current machine.

Installs LaTeX if it's missing (TinyTeX by default: no admin rights needed),
the LaTeX packages this project uses, and the recommended VS Code extensions.
latex-forge itself is not required — everything lives in toolchain.py next to
this file. Run it through setup.sh (macOS/Linux) or setup.bat (Windows), or
directly: python3 scripts/setup.py --help
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import toolchain  # noqa: E402  (shipped next to this script)


def main(argv: list[str] | None = None) -> int:
    return toolchain.run_project_setup(SCRIPT_DIR.parent, argv)


if __name__ == "__main__":
    raise SystemExit(main())
