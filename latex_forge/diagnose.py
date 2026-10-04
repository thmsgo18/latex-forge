"""Environment diagnostics for latex-forge.

Checks that the local machine has everything ``latex-forge`` needs (TeX
distribution, latexmk, etc.) and reports the user's configuration state,
so problems can be spotted with a single ``latex-forge diagnose`` command
instead of trial-and-error compilation failures.

TeX tools are looked up the way ``latex-forge build`` finds them (PATH plus
the managed TinyTeX and well-known install locations), so a distribution
that works for latex-forge is never reported missing.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys

from . import toolchain


# ── Individual checks ─────────────────────────────────────────────────────
#
# Each check below returns a small dict with at least an "ok" key. They never
# raise: any unexpected error is swallowed and reported as a failed/unknown
# check, so one broken probe can't crash the whole `diagnose` command.


def _first_line(*args: str) -> tuple[int, str | None]:
    """Run a tool (resolved like latex-forge does) → (exit code, first output line)."""
    out = subprocess.run(
        [toolchain.which(args[0]) or args[0], *args[1:]],
        capture_output=True, text=True, timeout=10, env=toolchain.tex_env(), errors="replace",
    )
    text = (out.stdout or out.stderr).strip()
    return out.returncode, (text.splitlines()[0] if text else None)


def _check_latex_forge() -> dict:
    """Report the installed latex-forge version (from package metadata)."""
    try:
        from importlib.metadata import version
        ver = version("latex-forge")
        return {"ok": True, "version": ver}
    except Exception:
        return {"ok": False, "version": None}


def _install_method() -> str:
    """How this copy of latex-forge was installed: uv, pipx, editable, venv or pip."""
    prefix = sys.prefix.replace("\\", "/").lower()
    if "/uv/tools/" in prefix:
        return "uv"
    if "/pipx/" in prefix and "/venvs/" in prefix:
        return "pipx"
    try:
        from importlib.metadata import distribution
        direct_url = json.loads(distribution("latex-forge").read_text("direct_url.json") or "{}")
        if direct_url.get("dir_info", {}).get("editable"):
            return "editable"
    except Exception:
        pass
    if sys.prefix != getattr(sys, "base_prefix", sys.prefix):
        return "venv"
    return "pip"


def _check_cli_install() -> dict:
    """Report how latex-forge is installed (drives how it gets upgraded)."""
    return {
        "ok": True,
        "method": _install_method(),
        "python": ".".join(str(v) for v in sys.version_info[:3]),
        "prefix": sys.prefix,
    }


def _check_pipx() -> dict:
    """Check whether pipx is available (one of the ways to install latex-forge)."""
    if not shutil.which("pipx"):
        return {"ok": False, "version": None}
    try:
        out = subprocess.run(
            ["pipx", "--version"],
            capture_output=True, text=True, timeout=5,
        )
        ver = out.stdout.strip().splitlines()[0] if out.stdout.strip() else None
        return {"ok": True, "version": ver}
    except Exception:
        # pipx is on PATH but --version failed; still treat as present.
        return {"ok": True, "version": None}


def _check_tex_distribution() -> dict:
    """Describe the TeX distribution in use (TinyTeX, TeX Live, MiKTeX...)."""
    try:
        dist = toolchain.detect_distribution()
    except Exception:
        return {"ok": False, "kind": "unknown", "label": "unknown"}
    return {"ok": dist["kind"] != "none", **dist}


def _install_fix(package: str) -> str:
    """The command that installs a TeX Live *package* on this machine."""
    try:
        dist = toolchain.detect_distribution()
    except Exception:
        dist = {"kind": "none", "can_install_packages": False}
    if dist["kind"] == "none":
        return "latex-forge setup --install-tex"
    if dist["kind"] == "miktex":
        return f"mpm --install={package}"
    if dist["kind"] == "distro":
        return f"install {package} with your system package manager (e.g. sudo apt install {package})"
    if dist.get("can_install_packages"):
        return f"tlmgr install {package}"
    return f"sudo tlmgr install {package}"


def _check_texlive() -> dict:
    """Check for a usable TeX engine and try to identify the TeX Live release year."""
    engines = ["pdflatex", "lualatex", "xelatex"]
    found = [e for e in engines if toolchain.which(e)]

    if not found:
        return {"ok": False, "version": None, "engines": [], "fix": "latex-forge setup --install-tex"}

    # Try to extract TeX Live year from the engine's --version banner.
    year: str | None = None
    try:
        out = subprocess.run(
            [toolchain.which(found[0]) or found[0], "--version"],
            capture_output=True, text=True, timeout=5, env=toolchain.tex_env(), errors="replace",
        )
        m = re.search(r"TeX Live (\d{4})", out.stdout)
        if m:
            year = m.group(1)
    except Exception:
        pass

    return {"ok": True, "version": year, "engines": found}


def _check_latexmk() -> dict:
    """Check for latexmk, the multi-pass build driver latex-forge relies on.

    latexmk is a Perl script: on MiKTeX it's found but can't run without a
    Perl interpreter, which is reported as a failure with the right fix.
    """
    if not toolchain.which("latexmk"):
        return {"ok": False, "fix": _install_fix("latexmk")}
    try:
        code, ver = _first_line("latexmk", "--version")
        if code != 0 and ver and "perl" in ver.lower():
            return {
                "ok": False,
                "version": None,
                "fix": "latexmk needs Perl: winget install StrawberryPerl.StrawberryPerl",
            }
        return {"ok": True, "version": ver}
    except Exception:
        # latexmk is found but --version failed; still treat as present.
        return {"ok": True, "version": None}


def _check_biber() -> dict:
    """Check for biber, the backend used by templates with a biblatex bibliography."""
    if not toolchain.which("biber"):
        return {"ok": False, "fix": _install_fix("biber")}
    try:
        _, ver = _first_line("biber", "--version")
        return {"ok": True, "version": ver}
    except Exception:
        # biber is found but --version failed; still treat as present.
        return {"ok": True, "version": None}


def _check_gh_cli() -> dict:
    """Check for the GitHub CLI (gh), used by `latex-forge create --repo create`."""
    if not shutil.which("gh"):
        return {"ok": False, "authenticated": False, "version": None}
    try:
        out = subprocess.run(
            ["gh", "--version"],
            capture_output=True, text=True, timeout=5,
        )
        ver = out.stdout.strip().splitlines()[0] if out.stdout.strip() else None
    except Exception:
        ver = None
    try:
        auth = subprocess.run(["gh", "auth", "status"], capture_output=True, timeout=5)
        authenticated = auth.returncode == 0
    except Exception:
        authenticated = False
    return {"ok": True, "authenticated": authenticated, "version": ver}


def _check_profile() -> dict:
    """Check whether the user has saved a profile (name/affiliation, etc.)."""
    from .profile import profile_path
    p = profile_path()
    if p.exists():
        return {"ok": True, "path": str(p)}
    return {"ok": False, "path": str(p)}


def _check_default_template() -> dict:
    """Check whether the user has configured a default project template."""
    try:
        from .config import get_default_template
        val = get_default_template()
        if val:
            return {"ok": True, "value": val}
        return {"ok": False, "value": None}
    except Exception:
        return {"ok": False, "value": None}


# ── Public API ────────────────────────────────────────────────────────────


def run_diagnose() -> dict:
    """Run all checks and return a structured result dict."""
    return {
        "latex_forge":       _check_latex_forge(),
        "cli_install":       _check_cli_install(),
        "pipx":              _check_pipx(),
        "tex_distribution":  _check_tex_distribution(),
        "texlive":           _check_texlive(),
        "latexmk":           _check_latexmk(),
        "biber":             _check_biber(),
        "gh_cli":            _check_gh_cli(),
        "profile":           _check_profile(),
        "default_template":  _check_default_template(),
    }


def format_diagnose_text(data: dict) -> str:
    """Render *data* (from :func:`run_diagnose`) as a human-readable string."""
    lines = [
        "LaTeX Forge — Environment Diagnostics",
        "══════════════════════════════════════",
    ]

    def _row(ok: bool, label: str, detail: str = "") -> str:
        icon = "✓" if ok else "✗"
        return f"{icon} {label:<20} {detail}".rstrip()

    # latex-forge
    lf = data["latex_forge"]
    lines.append(_row(lf["ok"], "latex-forge", lf.get("version") or "not found"))

    # How latex-forge itself is installed (uv, pipx, ...)
    ci = data.get("cli_install")
    if ci:
        lines.append(_row(True, "Installed with", f"{ci['method']}  (Python {ci['python']})"))
    else:
        px = data["pipx"]
        lines.append(_row(px["ok"], "pipx", px.get("version") or ("not found" if not px["ok"] else "")))

    # TeX distribution
    tl = data["texlive"]
    dist = data.get("tex_distribution") or {}
    if tl["ok"]:
        engines_str = ", ".join(tl["engines"])
        label = dist.get("label") or "TeX Live"
        year = tl.get("version")
        detail = label if not year or year in label else f"{label} {year}"
        lines.append(_row(True, "LaTeX", f"{detail}  ({engines_str})"))
    else:
        lines.append(_row(False, "LaTeX", "not found  →  run: latex-forge setup --install-tex"))

    # latexmk
    lmk = data["latexmk"]
    if lmk["ok"]:
        lines.append(_row(True, "latexmk", lmk.get("version") or ""))
    else:
        lines.append(_row(False, "latexmk", f"not working  →  run: {lmk.get('fix', 'latex-forge setup --install-tex')}"))

    # biber (only needed by templates with a biblatex bibliography)
    bib = data["biber"]
    if bib["ok"]:
        lines.append(_row(True, "biber", bib.get("version") or ""))
    else:
        lines.append(_row(False, "biber", f"not found (needed for bibliographies)  →  run: {bib.get('fix', 'tlmgr install biber')}"))

    # GitHub CLI (only needed for `create --repo create`)
    gh = data["gh_cli"]
    if not gh["ok"]:
        lines.append(_row(False, "GitHub CLI", "not found (needed for --repo create)  →  run: latex-forge setup --install-gh"))
    elif not gh["authenticated"]:
        lines.append(_row(False, "GitHub CLI", f"{gh.get('version') or ''} — not authenticated  →  run: gh auth login"))
    else:
        lines.append(_row(True, "GitHub CLI", gh.get("version") or ""))

    # Profile
    prof = data["profile"]
    if prof["ok"]:
        lines.append(_row(True, "Profile", f"configured ({prof['path']})"))
    else:
        lines.append(_row(False, "Profile", "not set  →  run: latex-forge profile set"))

    # Default template
    dt = data["default_template"]
    if dt["ok"]:
        lines.append(_row(True, "Default template", dt.get("value") or ""))
    else:
        lines.append(_row(False, "Default template", "not configured"))

    return "\n".join(lines)
