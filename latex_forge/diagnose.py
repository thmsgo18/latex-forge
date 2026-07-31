"""Environment diagnostics for latex-forge.

Checks that the local machine has everything ``latex-forge`` needs (TeX
distribution, latexmk, etc.) and reports the user's configuration state,
so problems can be spotted with a single ``latex-forge diagnose`` command
instead of trial-and-error compilation failures.
"""
from __future__ import annotations

import shutil
import subprocess


# ── Individual checks ─────────────────────────────────────────────────────
#
# Each check below returns a small dict with at least an "ok" key. They never
# raise: any unexpected error is swallowed and reported as a failed/unknown
# check, so one broken probe can't crash the whole `diagnose` command.


def _check_latex_forge() -> dict:
    """Report the installed latex-forge version (from package metadata)."""
    try:
        from importlib.metadata import version
        ver = version("latex-forge")
        return {"ok": True, "version": ver}
    except Exception:
        return {"ok": False, "version": None}


def _check_pipx() -> dict:
    """Check whether pipx is available (used to install latex-forge itself)."""
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


def _check_texlive() -> dict:
    """Check for a usable TeX engine and try to identify the TeX Live release year."""
    engines = ["pdflatex", "lualatex", "xelatex"]
    found = [e for e in engines if shutil.which(e)]

    if not found:
        return {"ok": False, "version": None, "engines": []}

    # Try to extract TeX Live year from pdflatex --version
    year: str | None = None
    try:
        out = subprocess.run(
            ["pdflatex", "--version"],
            capture_output=True, text=True, timeout=5,
        )
        for line in out.stdout.splitlines():
            if "TeX Live" in line:
                import re
                m = re.search(r"TeX Live (\d{4})", line)
                if m:
                    year = m.group(1)
                    break
    except Exception:
        pass

    return {"ok": True, "version": year, "engines": found}


def _check_latexmk() -> dict:
    """Check for latexmk, the multi-pass build driver latex-forge relies on."""
    if not shutil.which("latexmk"):
        return {"ok": False, "fix": "sudo tlmgr install latexmk"}
    try:
        out = subprocess.run(
            ["latexmk", "--version"],
            capture_output=True, text=True, timeout=5,
        )
        ver = out.stdout.strip().splitlines()[0] if out.stdout.strip() else None
        return {"ok": True, "version": ver}
    except Exception:
        # latexmk is on PATH but --version failed; still treat as present.
        return {"ok": True, "version": None}


def _check_biber() -> dict:
    """Check for biber, the backend used by templates with a biblatex bibliography."""
    if not shutil.which("biber"):
        return {"ok": False, "fix": "tlmgr install biber"}
    try:
        out = subprocess.run(
            ["biber", "--version"],
            capture_output=True, text=True, timeout=5,
        )
        ver = out.stdout.strip().splitlines()[0] if out.stdout.strip() else None
        return {"ok": True, "version": ver}
    except Exception:
        # biber is on PATH but --version failed; still treat as present.
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
        "pipx":              _check_pipx(),
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

    # pipx
    px = data["pipx"]
    lines.append(_row(px["ok"], "pipx", px.get("version") or ("not found" if not px["ok"] else "")))

    # TeX Live
    tl = data["texlive"]
    if tl["ok"]:
        engines_str = ", ".join(tl["engines"])
        year = tl.get("version") or "version unknown"
        lines.append(_row(True, "TeX Live", f"{year}  ({engines_str})"))
    else:
        lines.append(_row(False, "TeX Live", "not found  →  run: latex-forge setup --install-tex"))

    # latexmk
    lmk = data["latexmk"]
    if lmk["ok"]:
        lines.append(_row(True, "latexmk", lmk.get("version") or ""))
    else:
        lines.append(_row(False, "latexmk", f"not found  →  run: {lmk.get('fix', 'sudo tlmgr install latexmk')}"))

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
