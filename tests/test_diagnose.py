"""Tests for the diagnose module."""
from __future__ import annotations

import json

from latex_forge.diagnose import format_diagnose_text, run_diagnose


# ── run_diagnose ──────────────────────────────────────────────────────────


def test_run_diagnose_returns_all_keys():
    data = run_diagnose()
    expected_keys = {"latex_forge", "pipx", "texlive", "latexmk", "profile", "default_template"}
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
    assert "TeX Live" in text
    assert "latexmk" in text
    assert "Profile" in text


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
    assert "✗ TeX Live" in text


def test_format_diagnose_text_shows_ok_icon_when_tool_present(monkeypatch):
    import latex_forge.diagnose as diag

    monkeypatch.setattr(
        diag,
        "_check_texlive",
        lambda: {"ok": True, "version": "2024", "engines": ["pdflatex", "lualatex"]},
    )
    data = run_diagnose()
    text = format_diagnose_text(data)
    assert "✓ TeX Live" in text
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
