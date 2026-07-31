"""First-run checks and `latex-forge setup`: verify and install the LaTeX toolchain.

Detects the host OS and package manager, reports which required tools
(latexmk, lualatex, bibtex/biber) and VS Code extensions are present, and can
drive the platform-specific commands to install a full TeX distribution.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from .project import package_dir


BASE_TOOLS = ["latexmk", "lualatex"]
TEMPLATE_SPECIFIC_TOOLS = ["bibtex", "biber"]


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


def detect_os() -> str:
    """Return a short OS identifier: "macos", "windows", "linux", or the raw platform name."""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    if system == "linux":
        return "linux"
    return system


def vscode_extension_recommendations() -> list[str]:
    """Return the extension IDs recommended by the bundled .vscode/extensions.json."""
    extensions_file = package_dir() / ".vscode" / "extensions.json"
    if not extensions_file.exists():
        return []

    data = json.loads(extensions_file.read_text(encoding="utf-8"))
    return list(data.get("recommendations", []))


def command_exists(name: str) -> bool:
    """Return True if *name* resolves to an executable on PATH."""
    return shutil.which(name) is not None


def privilege_prefix() -> list[str]:
    """Return the command prefix needed for privileged installs on Linux.

    Empty if already running as root or if `sudo` is unavailable (in which
    case the install command is attempted without elevation and may fail).
    """
    geteuid = getattr(os, "geteuid", None)
    if geteuid is not None and geteuid() == 0:
        return []
    if command_exists("sudo"):
        return ["sudo"]
    return []


def install_vscode_extensions() -> bool:
    """Install every recommended extension via the `code` CLI.

    Returns False if `code` is missing, or if any extension failed to
    install (a warning is printed per failure but the rest still proceed).
    """
    if not command_exists("code"):
        print("VS Code CLI not found: `code` is not in PATH.")
        print("On macOS, open VS Code then run:")
        print("Shell Command: Install 'code' command in PATH")
        return False

    all_ok = True
    for extension in vscode_extension_recommendations():
        result = subprocess.run(
            ["code", "--install-extension", extension, "--force"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(f"[ok] Extension installed or already present: {extension}")
        else:
            all_ok = False
            stderr = result.stderr.strip() or result.stdout.strip()
            print(f"[warn] Could not install extension {extension}")
            if stderr:
                print(stderr)
    return all_ok


def _miktex_bin_dir() -> Path | None:
    """Locate MiKTeX's bin directory right after a winget install.

    A freshly installed MiKTeX isn't on PATH yet for this process (PATH is
    only refreshed in new shells), so `command_exists` can't find `mpm`/
    `initexmf` immediately after `install_tex_distribution` runs winget.
    Falls back to bare command names (resolved via PATH) if nothing is found.
    """
    candidates = []
    for env_var in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"):
        base = os.environ.get(env_var)
        if not base:
            continue
        candidates.append(Path(base) / "Programs" / "MiKTeX" / "miktex" / "bin" / "x64")
        candidates.append(Path(base) / "MiKTeX" / "miktex" / "bin" / "x64")

    for candidate in candidates:
        if (candidate / "mpm.exe").exists():
            return candidate
    return None


def _ensure_miktex_latexmk() -> None:
    """Enable MiKTeX's on-the-fly package installs and pull in latexmk/biber.

    This is the manual step a user otherwise has to do through MiKTeX
    Console's package manager after `winget install MiKTeX.MiKTeX`: the
    winget package doesn't ship `latexmk`/`biber`, and on-the-fly install of
    missing packages defaults to off outside the interactive GUI installer.
    """
    bin_dir = _miktex_bin_dir()

    def tool(name: str) -> str:
        return str(bin_dir / f"{name}.exe") if bin_dir else name

    print("")
    print("Configuring MiKTeX (auto-install missing packages, latexmk, biber)...")
    steps = [
        [tool("initexmf"), "--set-config-value=[MPM]AutoInstall=1"],
        [tool("mpm"), "--update-db"],
        [tool("mpm"), "--install=latexmk"],
        [tool("mpm"), "--install=biber"],
    ]
    for step in steps:
        try:
            result = subprocess.run(step, check=False, capture_output=True, text=True)
        except (FileNotFoundError, OSError):
            print(f"[warn] Could not run: {' '.join(step)}")
            print("       Open 'MiKTeX Console' -> Packages and install 'latexmk' and 'biber' manually.")
            return
        if result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip()
            print(f"[warn] Command failed: {' '.join(step)}")
            if stderr:
                print(stderr)


def install_tex_distribution() -> bool:
    """Install a full TeX distribution using the host's native package manager.

    Picks Homebrew (macOS), winget (Windows), or apt/dnf/pacman (Linux,
    elevated via `privilege_prefix`), running each step's command in turn and
    printing manual-install instructions if no supported manager is found or
    a command fails.
    """
    current_os = detect_os()

    commands: list[list[str]] = []
    description = ""

    if current_os == "macos":
        if not command_exists("brew"):
            print("Homebrew not found. Cannot install TeX automatically on macOS.")
            print("Install MacTeX manually: https://www.tug.org/mactex/")
            return False
        description = "Installing MacTeX (no GUI apps) via Homebrew"
        commands = [["brew", "install", "--cask", "mactex-no-gui"]]
    elif current_os == "windows":
        if not command_exists("winget"):
            print("winget not found. Cannot install TeX automatically on Windows.")
            print("Install MiKTeX or TeX Live manually.")
            print("MiKTeX: https://miktex.org/howto/install-miktex")
            print("TeX Live: https://www.tug.org/texlive/windows.html")
            return False
        description = "Installing MiKTeX via winget"
        commands = [[
            "winget",
            "install",
            "-e",
            "--id",
            "MiKTeX.MiKTeX",
            "--accept-source-agreements",
            "--accept-package-agreements",
        ]]
    elif current_os == "linux":
        sudo_prefix = privilege_prefix()
        if command_exists("apt-get"):
            description = "Installing full TeX Live via apt"
            commands = [
                [*sudo_prefix, "apt-get", "update"],
                [*sudo_prefix, "apt-get", "install", "-y", "texlive-full", "latexmk", "biber"],
            ]
        elif command_exists("dnf"):
            description = "Installing full TeX Live via dnf"
            commands = [
                [*sudo_prefix, "dnf", "install", "-y", "texlive-scheme-full", "latexmk", "biber"],
            ]
        elif command_exists("pacman"):
            description = "Installing TeX Live via pacman"
            commands = [
                [*sudo_prefix, "pacman", "-S", "--needed", "texlive-meta", "biber"],
            ]
        else:
            print("No supported package manager detected automatically on Linux.")
            print("Install TeX Live manually: https://www.tug.org/texlive/quickinstall.html")
            return False
    else:
        print(f"OS not supported for automatic installation: {current_os}")
        return False

    print(description)
    if current_os == "macos":
        print("This may take 20-30 minutes — Homebrew will show its progress below.")
    else:
        print("This may take several minutes.")
    for command in commands:
        print("")
        print("Running command:")
        print(" ".join(command))
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            print("")
            print("[warn] Automatic installation failed.")
            return False

    if current_os == "windows":
        _ensure_miktex_latexmk()

    print("")
    print("[ok] Installation commands completed.")
    if current_os == "macos":
        print("On macOS, open a new terminal or run:")
        print('eval "$(/usr/libexec/path_helper)"')
    print("Then restart VS Code before compiling.")
    return True


def install_gh_cli() -> bool:
    """Install the GitHub CLI (`gh`) using the host's native package manager.

    Needed for `latex-forge create --repo create`. Doesn't touch GitHub
    authentication — the user still has to run `gh auth login` themselves.
    """
    current_os = detect_os()

    command: list[str] = []

    if current_os == "macos":
        if not command_exists("brew"):
            print("Homebrew not found. Cannot install the GitHub CLI automatically on macOS.")
            print("Install it manually: https://cli.github.com/")
            return False
        command = ["brew", "install", "gh"]
    elif current_os == "windows":
        if not command_exists("winget"):
            print("winget not found. Cannot install the GitHub CLI automatically on Windows.")
            print("Install it manually: https://cli.github.com/")
            return False
        command = [
            "winget",
            "install",
            "-e",
            "--id",
            "GitHub.cli",
            "--accept-source-agreements",
            "--accept-package-agreements",
        ]
    elif current_os == "linux":
        sudo_prefix = privilege_prefix()
        if command_exists("apt-get"):
            command = [*sudo_prefix, "apt-get", "install", "-y", "gh"]
        elif command_exists("dnf"):
            command = [*sudo_prefix, "dnf", "install", "-y", "gh"]
        elif command_exists("pacman"):
            command = [*sudo_prefix, "pacman", "-S", "--needed", "github-cli"]
        else:
            print("No supported package manager detected automatically on Linux.")
            print("Install the GitHub CLI manually: https://cli.github.com/")
            return False
    else:
        print(f"OS not supported for automatic installation: {current_os}")
        return False

    print("Installing the GitHub CLI (gh)")
    print(" ".join(command))
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        print("")
        print("[warn] Automatic installation failed.")
        return False

    print("")
    print("[ok] GitHub CLI installed. Run `gh auth login` to authenticate.")
    return True


def print_tool_status() -> tuple[bool, bool]:
    """Print availability of required and template-specific LaTeX tools.

    Returns (base_ready, extra_ready): whether all of BASE_TOOLS and all of
    TEMPLATE_SPECIFIC_TOOLS, respectively, were found on PATH.
    """
    base_ready = True
    extra_ready = True

    print("Checking LaTeX tools:")
    for tool in BASE_TOOLS:
        exists = command_exists(tool)
        status = "ok" if exists else "missing"
        print(f"- {tool}: {status}")
        base_ready = base_ready and exists

    print("Tools useful for some templates:")
    for tool in TEMPLATE_SPECIFIC_TOOLS:
        exists = command_exists(tool)
        status = "ok" if exists else "missing"
        print(f"- {tool}: {status}")
        extra_ready = extra_ready and exists

    return base_ready, extra_ready


def print_os_specific_help() -> None:
    """Print manual TeX-distribution installation instructions for the detected OS."""
    current_os = detect_os()
    print("")
    print("Recommended LaTeX distribution installation:")

    if current_os == "macos":
        print("- OS detected: macOS")
        print("- Recommended: MacTeX")
        print("- Official site: https://www.tug.org/mactex/")
        print("- After installation, restart VS Code then verify:")
        print("  latexmk --version")
        print("  lualatex --version")
    elif current_os == "windows":
        print("- OS detected: Windows")
        print("- Recommended: TeX Live for a stable setup, or MiKTeX for a lighter install.")
        print("- TeX Live: https://www.tug.org/texlive/windows.html")
        print("- MiKTeX: https://miktex.org/howto/install-miktex")
        print("- After installation, restart VS Code then verify:")
        print("  latexmk --version")
        print("  lualatex --version")
    elif current_os == "linux":
        print("- OS detected: Linux")
        print("- Recommended: TeX Live")
        print("- Official guide: https://www.tug.org/texlive/quickinstall.html")
        print("- After installation, restart VS Code then verify:")
        print("  latexmk --version")
        print("  lualatex --version")
    else:
        print(f"- OS detected: {current_os}")
        print("- Install a LaTeX distribution that provides at least `latexmk` and `lualatex`.")


def offer_open_vscode(target_dir: Path) -> None:
    """Interactively offer to open *target_dir* in VS Code, if `code` is available."""
    if not command_exists("code"):
        return
    if not sys.stdin.isatty():
        return
    try:
        answer = input("Open project in VS Code? [y/N] ").strip().lower()
        if answer in ("y", "yes"):
            subprocess.run(["code", str(target_dir)], check=False)
    except (EOFError, OSError, KeyboardInterrupt):
        print("")


def warn_if_latex_missing() -> None:
    """Print a warning (with a fix command) if lualatex is not on PATH."""
    if not command_exists("lualatex"):
        print("")
        print("[warn] LaTeX (lualatex) is not installed — you won't be able to compile yet.")
        print("       Run `latex-forge setup --install-tex` to install it automatically.")


def run_first_launch_check() -> None:
    """Run the lightweight check shown the first time `latex-forge` is used.

    Only verifies the base LaTeX tools and, if missing, offers to install
    them — unlike `run_setup`, it doesn't touch VS Code extensions.
    """
    print("Welcome to LaTeX Forge!")
    print("Checking your environment before creating your first project...")
    print("")

    base_ready, _ = print_tool_status()

    if base_ready:
        print("")
        print("[ok] Your environment is ready.")
    else:
        print("")
        if _prompt_yes_no("LaTeX is not installed. Install it now?"):
            install_tex_distribution()
        else:
            print("You can install it later with: latex-forge setup --install-tex")

    print("")


def run_setup(
    check_only: bool = False,
    skip_extensions: bool = False,
    install_tex: bool = False,
    install_gh: bool = False,
) -> int:
    """Implement `latex-forge setup`: report or fix the local LaTeX environment.

    With *check_only*, nothing is installed — only the current status is
    printed. Otherwise, recommended VS Code extensions are installed (unless
    *skip_extensions*), a missing TeX distribution is installed either
    because *install_tex* was requested or the user agrees to a prompt, and
    the GitHub CLI is installed if *install_gh* was requested (needed for
    `latex-forge create --repo create`; doesn't affect the return code, since
    it's unrelated to LaTeX compilation readiness).
    Returns 0 if the environment ends up ready for compilation, 1 otherwise,
    or 2 for an invalid combination of flags.
    """
    if check_only and (install_tex or install_gh):
        print("`--check-only` cannot be combined with `--install-tex`/`--install-gh`.")
        return 2

    if install_gh and not command_exists("gh"):
        print("")
        install_gh_cli()

    print(f"OS detected: {detect_os()}")
    print(f"Python: {sys.executable}")
    print("")

    extensions_ok = True
    if skip_extensions:
        print("VS Code extension installation skipped.")
    elif check_only:
        print("Check-only mode: no VS Code extensions will be installed.")
    else:
        print("Installing recommended VS Code extensions...")
        extensions_ok = install_vscode_extensions()

    print("")
    base_ready, extra_ready = print_tool_status()

    if not base_ready and not check_only and not install_tex:
        print("")
        if _prompt_yes_no("LaTeX is not installed. Install it now?"):
            install_tex = True

    if install_tex and not base_ready:
        print("")
        tex_install_ok = install_tex_distribution()
        print("")
        base_ready, extra_ready = print_tool_status()
        if not tex_install_ok and not base_ready:
            print_os_specific_help()
            print("")
            print("[warn] The LaTeX environment is not yet complete.")
            if not extensions_ok:
                print("[warn] Some VS Code extensions could not be installed automatically.")
            return 1

    print_os_specific_help()

    print("")
    if base_ready:
        print("[ok] The minimal environment for compiling LaTeX projects is ready.")
        if not extra_ready:
            print("[warn] Some bibliography tools are still missing for certain templates.")
        return 0

    print("[warn] The LaTeX environment is not yet complete.")
    if not extensions_ok:
        print("[warn] Some VS Code extensions could not be installed automatically.")
    return 1
