#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


BASE_TOOLS = ["latexmk", "lualatex"]
EXTRA_TOOLS = ["bibtex", "biber"]


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def detect_os() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    if system == "linux":
        return "linux"
    return system


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def privilege_prefix() -> list[str]:
    geteuid = getattr(os, "geteuid", None)
    if geteuid is not None and geteuid() == 0:
        return []
    if command_exists("sudo"):
        return ["sudo"]
    return []


def recommended_extensions() -> list[str]:
    extensions_file = project_root() / ".vscode" / "extensions.json"
    if not extensions_file.exists():
        return []

    data = json.loads(extensions_file.read_text(encoding="utf-8"))
    return list(data.get("recommendations", []))


def install_vscode_extensions() -> bool:
    if not command_exists("code"):
        print("VS Code CLI not found: `code` is not in PATH.")
        print("On macOS, open VS Code then run:")
        print("Shell Command: Install 'code' command in PATH")
        return False

    all_ok = True
    for extension in recommended_extensions():
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


def print_tool_status() -> tuple[bool, bool]:
    base_ready = True
    extra_ready = True

    print("Checking LaTeX tools:")
    for tool in BASE_TOOLS:
        exists = command_exists(tool)
        print(f"- {tool}: {'ok' if exists else 'missing'}")
        base_ready = base_ready and exists

    print("Tools useful for some templates:")
    for tool in EXTRA_TOOLS:
        exists = command_exists(tool)
        print(f"- {tool}: {'ok' if exists else 'missing'}")
        extra_ready = extra_ready and exists

    return base_ready, extra_ready


def print_os_specific_help() -> None:
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


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    check_only = "--check-only" in args
    skip_extensions = "--skip-extensions" in args
    install_tex = "--install-tex" in args

    if check_only and install_tex:
        print("`--check-only` and `--install-tex` cannot be used together.")
        return 2

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
        print("[ok] The minimal environment for compiling this project is ready.")
        if not extra_ready:
            print("[warn] Some bibliography tools are still missing for certain templates.")
        return 0

    print("[warn] The LaTeX environment is not yet complete.")
    if not extensions_ok:
        print("[warn] Some VS Code extensions could not be installed automatically.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
