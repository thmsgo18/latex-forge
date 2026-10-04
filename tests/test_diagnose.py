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
