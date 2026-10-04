"""First-run checks and `latex-forge setup`: verify and install the LaTeX toolchain.

The heavy lifting (finding a TeX distribution, installing TinyTeX or a system
distribution, installing packages, the test compile) lives in
:mod:`latex_forge.toolchain`, which is shared with the standalone
``scripts/setup.py`` of generated projects. This module wires it to the CLI:
the ``setup`` command, the one-time check before the first ``create``, and a
few small helpers used by ``create``.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from . import toolchain
from .project import package_dir
from .toolchain import TEX_CHOICES, command_exists, detect_os


def _marker_file() -> Path:
    """Path to the sentinel file written after the first-run check has run once."""
    return Path.home() / ".latex_forge_initialized"


def is_first_run() -> bool:
    """Return True if `latex-forge` has never completed its first-run check before."""
    return not _marker_file().exists()


def mark_initialized() -> None:
    """Record that the first-run check has been performed, so it isn't repeated."""
    _marker_file().touch()


def _prompt_yes_no(question: str) -> bool:
    """Ask a yes/no question on stdin; defaults to No (including in non-interactive runs)."""
    if not sys.stdin.isatty():
        return False
    try:
        answer = input(f"{question} [y/N] ").strip().lower()
        return answer in ("y", "yes")
    except (EOFError, OSError, KeyboardInterrupt):
        print("")
        return False


def vscode_extension_recommendations() -> list[str]:
    """Return the extension IDs recommended by the bundled .vscode/extensions.json."""
    return toolchain.read_extension_recommendations(package_dir() / ".vscode" / "extensions.json")


def builtin_template_packages() -> dict[str, list[str]]:
    """TeX Live packages needed by each built-in template (from tex_packages.json)."""
    path = package_dir() / "tex_packages.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))["templates"]
    except (OSError, ValueError, KeyError):
        return {}


def baseline_packages() -> list[str]:
    """Everything the built-in templates need, installed with a light TinyTeX."""
    union: set[str] = set()
    for packages in builtin_template_packages().values():
        union.update(packages)
    return sorted(union)


def install_tex(kind: str, modify_path: bool = True, reinstall: bool = False) -> bool:
    """Install a TeX distribution (light/full TinyTeX, or system) and test it."""
    ok = toolchain.install_tex(
        kind,
        modify_path=modify_path,
        extra_packages=baseline_packages(),
        reinstall=reinstall,
    )
    if ok:
        ok = toolchain.verify_toolchain()
    return ok


def install_vscode_extensions() -> bool:
    """Install every recommended extension via the `code` CLI."""
    return toolchain.install_vscode_extensions(vscode_extension_recommendations())


def offer_open_vscode(target_dir: Path) -> None:
    """Interactively offer to open *target_dir* in VS Code, if `code` is available."""
    code = toolchain.vscode_cli()
    if code is None or not sys.stdin.isatty():
        return
    try:
        answer = input("Open project in VS Code? [y/N] ").strip().lower()
        if answer in ("y", "yes"):
            subprocess.run([code, str(target_dir)], check=False)
    except (EOFError, OSError, KeyboardInterrupt):
        print("")


def warn_if_latex_missing() -> None:
    """Print a warning (with a fix command) if lualatex can't be found."""
    if not command_exists("lualatex"):
        print("")
        print("[warn] LaTeX (lualatex) is not installed — you won't be able to compile yet.")
        print("       Run `latex-forge setup --install-tex` to install it (no admin rights needed).")


def run_first_launch_check() -> None:
    """Run the lightweight check shown the first time `latex-forge` is used.

    Only verifies the base LaTeX tools and, if missing, offers to install
    them — unlike `run_setup`, it doesn't touch VS Code extensions.
    """
    print("Welcome to LaTeX Forge!")
    print("Checking your environment before creating your first project...")
    print("")

    base_ready, _ = toolchain.print_tool_status()

    if base_ready:
        print("")
        print("[ok] Your environment is ready.")
    else:
        print("")
        kind = toolchain.ask_tex_choice()
        if kind:
            install_tex(kind)
        else:
            print("You can install it later with: latex-forge setup --install-tex")

    print("")


def run_setup(
    check_only: bool = False,
    skip_extensions: bool = False,
    install_tex_requested: bool = False,
    install_gh: bool = False,
    tex: str | None = None,
    assume_yes: bool = False,
    modify_path: bool = True,
    verify: bool = False,
    reinstall_tex: bool = False,
    remove_tex: bool = False,
) -> int:
    """Implement `latex-forge setup`: report or fix the local LaTeX environment.

    With *check_only*, nothing is installed — only the current status is
    printed. Otherwise, recommended VS Code extensions are installed (unless
    *skip_extensions*), and a missing TeX distribution is installed: the kind
    given by *tex* (light, full or system), else light when *assume_yes* or
    *install_tex_requested*, else whatever the user picks at the prompt. The
    GitHub CLI is installed if *install_gh* was requested (needed for
    `latex-forge create --repo create`; doesn't affect the return code, since
    it's unrelated to LaTeX compilation readiness). *verify* compiles a test
    document even when nothing was installed. *reinstall_tex* replaces the
    managed TinyTeX (e.g. after a new TeX Live year), keeping its packages;
    *remove_tex* uninstalls it.

    Returns 0 if the environment ends up ready for compilation, 1 otherwise,
    or 2 for an invalid combination of flags.
    """
    if tex is not None and tex not in TEX_CHOICES:
        print(f"Unknown distribution {tex!r} (expected one of {', '.join(TEX_CHOICES)}).")
        return 2
    wants_install = install_tex_requested or tex is not None or reinstall_tex
    if check_only and (wants_install or install_gh or remove_tex):
        print("`--check-only` cannot be combined with `--install-tex`/`--tex`/`--install-gh`.")
        return 2

    if remove_tex:
        return 0 if toolchain.uninstall_tinytex() else 1

    if install_gh and not command_exists("gh"):
        print("")
        toolchain.install_gh_cli()

    print(f"OS detected: {detect_os()}")
    print(f"Python: {sys.executable}")
    print("")

    extensions_ok = True
    if skip_extensions:
        print("VS Code extension installation skipped.")
    elif check_only:
        print("Check-only mode: no VS Code extensions will be installed.")
    else:
        toolchain.step("Installing recommended VS Code extensions")
        extensions_ok = install_vscode_extensions()

    print("")
    base_ready, extra_ready = toolchain.print_tool_status()

    installed_now = False
    if reinstall_tex:
        print("")
        installed_now = install_tex(tex or "light", modify_path=modify_path, reinstall=True)
    elif not base_ready and not check_only:
        kind = tex
        if kind is None:
            kind = "light" if (install_tex_requested or assume_yes) else toolchain.ask_tex_choice()
        if kind:
            print("")
            installed_now = install_tex(kind, modify_path=modify_path)
        else:
            print("")
            print("LaTeX not installed. Install it later with: latex-forge setup --install-tex")
    elif tex == "full" and toolchain.detect_distribution()["kind"] == "tinytex":
        # Upgrading an existing light TinyTeX to the full TeX Live.
        print("")
        installed_now = install_tex("full", modify_path=modify_path)

    if installed_now or (wants_install and not base_ready):
        print("")
        base_ready, extra_ready = toolchain.print_tool_status()
    elif verify and base_ready:
        print("")
        base_ready = toolchain.verify_toolchain()

    if not base_ready:
        toolchain.print_os_specific_help()
        print("")
        print("[warn] The LaTeX environment is not yet complete.")
        if not extensions_ok:
            print("[warn] Some VS Code extensions could not be installed automatically.")
        return 1

    print("")
    print("[ok] The minimal environment for compiling LaTeX projects is ready.")
    if not extra_ready:
        print("[warn] Some bibliography tools are still missing for certain templates.")
    if not extensions_ok:
        print("[warn] Some VS Code extensions could not be installed automatically.")
    return 0
