"""Tests for the diagnose module."""
from __future__ import annotations

import json

from latex_forge.diagnose import format_diagnose_text, run_diagnose


# ── run_diagnose ──────────────────────────────────────────────────────────


def test_run_diagnose_returns_all_keys():
    data = run_diagnose()
    expected_keys = {
        "latex_forge", "cli_install", "pipx", "tex_distribution", "texlive", "latexmk",
        "biber", "gh_cli", "profile", "default_template",
    }
    assert expected_keys == set(data.keys())


def test_run_diagnose_each_entry_has_ok():
    data = run_diagnose()
    for key, val in data.items():
        assert "ok" in val, f"Missing 'ok' in diagnose entry: {key}"
        assert isinstance(val["ok"], bool), f"'ok' must be bool in entry: {key}"


def test_run_diagnose_latex_forge_ok():
    """latex-forge itself must always be found (we're running inside it)."""
    data = run_diagnose()
    lf = data["latex_forge"]
    assert lf["ok"] is True
    assert lf["version"] is not None


def test_run_diagnose_is_json_serialisable():
    data = run_diagnose()
    # Should not raise
    serialised = json.dumps(data)
    parsed = json.loads(serialised)
    assert parsed.keys() == data.keys()


# ── format_diagnose_text ──────────────────────────────────────────────────


def test_format_diagnose_text_contains_section_labels():
    data = run_diagnose()
    text = format_diagnose_text(data)
    assert "latex-forge" in text
    assert "LaTeX" in text
    assert "Installed with" in text
    assert "latexmk" in text
    assert "biber" in text
    assert "Profile" in text


def test_format_diagnose_text_shows_biber_missing(monkeypatch):
    import latex_forge.diagnose as diag

    monkeypatch.setattr(diag, "_check_biber", lambda: {"ok": False, "fix": "tlmgr install biber"})
    data = run_diagnose()
    text = format_diagnose_text(data)
    assert "biber" in text
    assert "tlmgr install biber" in text


def test_format_diagnose_text_shows_ok_icon_for_latex_forge():
    data = run_diagnose()
    text = format_diagnose_text(data)
    # latex-forge is always installed in the test environment
    assert "✓ latex-forge" in text


def test_format_diagnose_text_shows_fail_icon_for_missing_tool(monkeypatch):
    """Mock texlive as missing and verify ✗ appears."""
    import latex_forge.diagnose as diag

    monkeypatch.setattr(diag, "_check_texlive", lambda: {"ok": False, "version": None, "engines": []})
    data = run_diagnose()
    text = format_diagnose_text(data)
    assert "✗ LaTeX" in text
    assert "latex-forge setup --install-tex" in text


def test_format_diagnose_text_shows_ok_icon_when_tool_present(monkeypatch):
    import latex_forge.diagnose as diag

    monkeypatch.setattr(
        diag,
        "_check_texlive",
        lambda: {"ok": True, "version": "2024", "engines": ["pdflatex", "lualatex"]},
    )
    data = run_diagnose()
    text = format_diagnose_text(data)
    assert "✓ LaTeX" in text
    assert "2024" in text


def test_format_diagnose_text_shows_profile_not_set(tmp_path, monkeypatch):
    import latex_forge.diagnose as diag

    monkeypatch.setattr(
        diag,
        "_check_profile",
        lambda: {"ok": False, "path": str(tmp_path / "profile.toml")},
    )
    data = run_diagnose()
    text = format_diagnose_text(data)
    assert "✗ Profile" in text
    assert "profile set" in text


# ── CLI integration ───────────────────────────────────────────────────────


def test_cli_diagnose_text(monkeypatch):
    """latex-forge diagnose exits with 0 or 1 (never crashes)."""
    from latex_forge.cli import main

    # Should not raise, only return 0 or 1
    rc = main(["diagnose"])
    assert rc in (0, 1)


def test_cli_diagnose_json(monkeypatch):
    """latex-forge diagnose --json outputs valid JSON to stdout."""
    import io
    from latex_forge.cli import main

    captured = io.StringIO()
    monkeypatch.setattr("sys.stdout", captured)
    rc = main(["diagnose", "--json"])
    assert rc in (0, 1)
    output = captured.getvalue()
    parsed = json.loads(output)
    assert "latex_forge" in parsed


def test_cli_diagnose_json_exits_1_when_texlive_missing(monkeypatch):
    import io
    import latex_forge.diagnose as diag

    monkeypatch.setattr(diag, "_check_texlive", lambda: {"ok": False, "version": None, "engines": []})
    monkeypatch.setattr(diag, "_check_latexmk", lambda: {"ok": True, "version": "4.80"})

    captured = io.StringIO()
    monkeypatch.setattr("sys.stdout", captured)
    from latex_forge.cli import main
    rc = main(["diagnose", "--json"])
    assert rc == 1


# ── Install method & distribution ─────────────────────────────────────────


def test_install_method_detects_uv(monkeypatch):
    import latex_forge.diagnose as diag

    monkeypatch.setattr(diag.sys, "prefix", "/Users/me/.local/share/uv/tools/latex-forge")
    assert diag._install_method() == "uv"


def test_install_method_detects_pipx(monkeypatch):
    import latex_forge.diagnose as diag

    monkeypatch.setattr(diag.sys, "prefix", "/Users/me/.local/pipx/venvs/latex-forge")
    assert diag._install_method() == "pipx"


def test_install_method_detects_pipx_windows(monkeypatch):
    import latex_forge.diagnose as diag

    monkeypatch.setattr(diag.sys, "prefix", r"C:\\Users\\me\\pipx\\venvs\\latex-forge")
    assert diag._install_method() == "pipx"


def test_cli_install_reports_python_version():
    import latex_forge.diagnose as diag

    info = diag._check_cli_install()
    assert info["ok"] is True
    assert info["python"].count(".") == 2


def test_install_fix_depends_on_distribution(monkeypatch):
    import latex_forge.diagnose as diag

    def dist(**kw):
        base = {"kind": "texlive", "can_install_packages": False}
        base.update(kw)
        return lambda: base

    monkeypatch.setattr(diag.toolchain, "detect_distribution", dist(kind="none"))
    assert diag._install_fix("latexmk") == "latex-forge setup --install-tex"
    monkeypatch.setattr(diag.toolchain, "detect_distribution", dist(kind="tinytex", can_install_packages=True))
    assert diag._install_fix("biber") == "tlmgr install biber"
    monkeypatch.setattr(diag.toolchain, "detect_distribution", dist())
    assert diag._install_fix("biber") == "sudo tlmgr install biber"
    monkeypatch.setattr(diag.toolchain, "detect_distribution", dist(kind="miktex"))
    assert diag._install_fix("latexmk") == "mpm --install=latexmk"


def test_latexmk_without_perl_is_reported(monkeypatch):
    """MiKTeX's latexmk exists but can't run without Perl."""
    import latex_forge.diagnose as diag

    monkeypatch.setattr(diag.toolchain, "which", lambda name: f"C:/MiKTeX/{name}.exe")
    monkeypatch.setattr(diag, "_first_line",
                        lambda *a: (1, "MiKTeX could not find the script engine 'perl.exe'"))
    result = diag._check_latexmk()
    assert result["ok"] is False
    assert "Perl" in result["fix"]


def test_tex_distribution_in_json_output():
    data = run_diagnose()
    dist = data["tex_distribution"]
    assert {"kind", "label", "bin_dir", "managed", "can_install_packages"} <= set(dist)


# ── Individual checks with fake tools ─────────────────────────────────────


def _completed(code=0, stdout="", stderr=""):
    import subprocess
    return subprocess.CompletedProcess(args=[], returncode=code, stdout=stdout, stderr=stderr)


def test_check_latex_forge_without_metadata(monkeypatch):
    import importlib.metadata as md

    import latex_forge.diagnose as diag

    def missing(name):
        raise md.PackageNotFoundError(name)

    monkeypatch.setattr(md, "version", missing)
    assert diag._check_latex_forge() == {"ok": False, "version": None}


def test_install_method_editable_and_venv(monkeypatch):
    import latex_forge.diagnose as diag

    class Dist:
        def __init__(self, text):
            self.text = text

        def read_text(self, name):
            return self.text

    monkeypatch.setattr(diag.sys, "prefix", "/home/me/project/.venv")
    monkeypatch.setattr(diag.sys, "base_prefix", "/usr")
    monkeypatch.setattr("importlib.metadata.distribution",
                        lambda name: Dist('{"url": "file:///src", "dir_info": {"editable": true}}'))
    assert diag._install_method() == "editable"
    monkeypatch.setattr("importlib.metadata.distribution", lambda name: Dist(None))
    assert diag._install_method() == "venv"
    monkeypatch.setattr(diag.sys, "base_prefix", "/home/me/project/.venv")
    assert diag._install_method() == "pip"


def test_check_pipx_variants(monkeypatch):
    import latex_forge.diagnose as diag

    monkeypatch.setattr(diag.shutil, "which", lambda name: None)
    assert diag._check_pipx() == {"ok": False, "version": None}
    monkeypatch.setattr(diag.shutil, "which", lambda name: "/usr/bin/pipx")
    monkeypatch.setattr(diag.subprocess, "run", lambda *a, **k: _completed(stdout="1.7.1\n"))
    assert diag._check_pipx() == {"ok": True, "version": "1.7.1"}

    def broken(*a, **k):
        raise OSError("boom")

    monkeypatch.setattr(diag.subprocess, "run", broken)
    assert diag._check_pipx() == {"ok": True, "version": None}


def test_check_tex_distribution_handles_errors(monkeypatch):
    import latex_forge.diagnose as diag

    def broken():
        raise RuntimeError("boom")

    monkeypatch.setattr(diag.toolchain, "detect_distribution", broken)
    assert diag._check_tex_distribution()["ok"] is False
    monkeypatch.setattr(diag.toolchain, "detect_distribution", lambda: {"kind": "tinytex", "label": "TinyTeX"})
    assert diag._check_tex_distribution() == {"ok": True, "kind": "tinytex", "label": "TinyTeX"}


def test_install_fix_for_system_packages(monkeypatch):
    import latex_forge.diagnose as diag

    monkeypatch.setattr(diag.toolchain, "detect_distribution",
                        lambda: {"kind": "distro", "can_install_packages": False})
    assert "system package manager" in diag._install_fix("biber")

    def broken():
        raise RuntimeError("boom")

    monkeypatch.setattr(diag.toolchain, "detect_distribution", broken)
    assert diag._install_fix("biber") == "latex-forge setup --install-tex"


def test_check_texlive_reads_the_year(monkeypatch):
    import latex_forge.diagnose as diag

    monkeypatch.setattr(diag.toolchain, "which", lambda name: f"/tex/{name}" if name == "lualatex" else None)
    monkeypatch.setattr(diag.subprocess, "run",
                        lambda *a, **k: _completed(stdout="This is LuaHBTeX, Version 1.22 (TeX Live 2026)\n"))
    assert diag._check_texlive() == {"ok": True, "version": "2026", "engines": ["lualatex"]}

    def broken(*a, **k):
        raise OSError("boom")

    monkeypatch.setattr(diag.subprocess, "run", broken)
    assert diag._check_texlive()["version"] is None


def test_check_latexmk_and_biber(monkeypatch):
    import latex_forge.diagnose as diag

    monkeypatch.setattr(diag.toolchain, "which", lambda name: None)
    monkeypatch.setattr(diag, "_install_fix", lambda pkg: f"tlmgr install {pkg}")
    assert diag._check_latexmk() == {"ok": False, "fix": "tlmgr install latexmk"}
    assert diag._check_biber() == {"ok": False, "fix": "tlmgr install biber"}

    monkeypatch.setattr(diag.toolchain, "which", lambda name: f"/tex/{name}")
    monkeypatch.setattr(diag, "_first_line", lambda *a: (0, "Latexmk, John Collins. Version 4.88"))
    assert diag._check_latexmk() == {"ok": True, "version": "Latexmk, John Collins. Version 4.88"}
    monkeypatch.setattr(diag, "_first_line", lambda *a: (0, "biber version: 2.21"))
    assert diag._check_biber() == {"ok": True, "version": "biber version: 2.21"}

    def broken(*a):
        raise OSError("boom")

    monkeypatch.setattr(diag, "_first_line", broken)
    assert diag._check_latexmk() == {"ok": True, "version": None}
    assert diag._check_biber() == {"ok": True, "version": None}


def test_first_line(monkeypatch):
    import latex_forge.diagnose as diag

    monkeypatch.setattr(diag.toolchain, "which", lambda name: None)
    monkeypatch.setattr(diag.subprocess, "run", lambda *a, **k: _completed(2, stdout="", stderr="oops\nmore"))
    assert diag._first_line("tool", "--version") == (2, "oops")
    monkeypatch.setattr(diag.subprocess, "run", lambda *a, **k: _completed(0))
    assert diag._first_line("tool") == (0, None)


def test_check_gh_cli(monkeypatch):
    import latex_forge.diagnose as diag

    monkeypatch.setattr(diag.shutil, "which", lambda name: None)
    assert diag._check_gh_cli()["ok"] is False
    monkeypatch.setattr(diag.shutil, "which", lambda name: "/usr/bin/gh")
    responses = iter([_completed(stdout="gh version 2.96.0\n"), _completed(1)])
    monkeypatch.setattr(diag.subprocess, "run", lambda *a, **k: next(responses))
    assert diag._check_gh_cli() == {"ok": True, "authenticated": False, "version": "gh version 2.96.0"}

    def broken(*a, **k):
        raise OSError("boom")

    monkeypatch.setattr(diag.subprocess, "run", broken)
    assert diag._check_gh_cli() == {"ok": True, "authenticated": False, "version": None}


def test_default_template_check(monkeypatch):
    import latex_forge.diagnose as diag

    monkeypatch.setattr("latex_forge.config.get_default_template", lambda: "research")
    assert diag._check_default_template() == {"ok": True, "value": "research"}

    def broken():
        raise RuntimeError("boom")

    monkeypatch.setattr("latex_forge.config.get_default_template", broken)
    assert diag._check_default_template() == {"ok": False, "value": None}


def test_format_text_for_every_state(monkeypatch):
    data = {
        "latex_forge": {"ok": True, "version": "0.8.0"},
        "pipx": {"ok": False, "version": None},
        "texlive": {"ok": True, "version": "2026", "engines": ["lualatex"]},
        "tex_distribution": {"label": "TinyTeX"},
        "latexmk": {"ok": False, "fix": "tlmgr install latexmk"},
        "biber": {"ok": True, "version": "2.21"},
        "gh_cli": {"ok": True, "authenticated": True, "version": "gh 2.96"},
        "profile": {"ok": True, "path": "/p"},
        "default_template": {"ok": True, "value": "research"},
    }
    text = format_diagnose_text(data)
    assert "✗ pipx" in text  # older data without cli_install still renders
    assert "TinyTeX 2026" in text
    assert "tlmgr install latexmk" in text
    assert "✓ GitHub CLI" in text and "configured (/p)" in text and "research" in text
    data["gh_cli"] = {"ok": True, "authenticated": False, "version": "gh 2.96"}
    assert "gh auth login" in format_diagnose_text(data)
