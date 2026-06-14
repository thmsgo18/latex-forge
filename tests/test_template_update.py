"""Tests for update_templates() and list_all_templates_detailed()."""
from __future__ import annotations

import pytest

import latex_forge.installed_templates as meta
import latex_forge.template_manager as tm
from latex_forge.template_manager import (
    list_all_templates_detailed,
    update_templates,
)


# ── Fixtures ──────────────────────────────────────────────────────────────

GALLERY_DATA = {
    "version": "2.0",
    "templates": [
        {
            "name": "my-tpl",
            "description": "Test template",
            "version": "2.0.0",
            "category": "article",
            "engine": "pdflatex",
            "install_url": "https://github.com/thmsgo18/latex-forge-gallery/tree/main/templates/article/my-tpl",
            "source_url": "https://github.com/thmsgo18/latex-forge-gallery",
            "tags": [],
            "preview_png": "",
            "preview_pdf": "",
        }
    ],
}


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    fake_user = tmp_path / "user_templates"
    fake_meta = tmp_path / "installed_templates.json"

    monkeypatch.setattr(tm, "_user_templates_dir", lambda: fake_user)
    monkeypatch.setattr(meta, "metadata_path", lambda: fake_meta)

    import latex_forge.project as proj
    monkeypatch.setattr(proj, "user_templates_dir", lambda: fake_user)

    yield fake_user, fake_meta


@pytest.fixture()
def installed_tpl(tmp_path, isolated_env):
    """A user-installed template with gallery metadata (version 1.0.0)."""
    fake_user, fake_meta = isolated_env
    tpl_dir = fake_user / "my-tpl"
    tpl_dir.mkdir(parents=True)
    (tpl_dir / "main.tex").write_text("\\documentclass{article}\\begin{document}end{document}")
    install_url = "https://github.com/thmsgo18/latex-forge-gallery/tree/main/templates/article/my-tpl"
    meta.record("my-tpl", install_url=install_url, version="1.0.0")
    return tpl_dir


# ── list_all_templates_detailed ───────────────────────────────────────────


def test_list_all_includes_builtins():
    entries = list_all_templates_detailed()
    names = [e["name"] for e in entries]
    assert "blank" in names
    builtin_entries = [e for e in entries if e["type"] == "builtin"]
    assert len(builtin_entries) >= 1


def test_list_all_includes_user_templates(installed_tpl):
    entries = list_all_templates_detailed()
    user_entries = [e for e in entries if e["type"] == "user"]
    names = [e["name"] for e in user_entries]
    assert "my-tpl" in names


def test_list_all_user_entry_has_version(installed_tpl):
    entries = list_all_templates_detailed()
    entry = next(e for e in entries if e["name"] == "my-tpl")
    assert entry["installed_version"] == "1.0.0"
    assert "thmsgo18" in entry["install_url"]


def test_list_all_builtin_has_no_version():
    entries = list_all_templates_detailed()
    entry = next(e for e in entries if e["type"] == "builtin")
    assert entry["installed_version"] is None
    assert entry["install_url"] is None


# ── update_templates — up_to_date ─────────────────────────────────────────


def test_update_up_to_date(installed_tpl, monkeypatch):
    """If installed version == gallery version, status is up_to_date."""
    meta.record(
        "my-tpl",
        install_url="https://github.com/thmsgo18/latex-forge-gallery/tree/main/templates/article/my-tpl",
        version="2.0.0",
    )
    results = update_templates(_gallery_data=GALLERY_DATA)
    assert len(results) == 1
    assert results[0]["status"] == "up_to_date"
    assert results[0]["from"] == "2.0.0"
    assert results[0]["to"] == "2.0.0"


# ── update_templates — updated ────────────────────────────────────────────


def test_update_installs_newer_version(installed_tpl, monkeypatch, tmp_path):
    """If gallery version > installed, the template is reinstalled."""
    # Mock install_template so we don't need a real network call
    updated = []

    def fake_install(source, name=None, force=False):
        updated.append(name or "my-tpl")
        return (name or "my-tpl", tmp_path / (name or "my-tpl"))

    monkeypatch.setattr(tm, "install_template", fake_install)

    results = update_templates(_gallery_data=GALLERY_DATA)
    assert len(results) == 1
    r = results[0]
    assert r["status"] == "updated"
    assert r["from"] == "1.0.0"
    assert r["to"] == "2.0.0"
    assert "my-tpl" in updated


# ── update_templates — no gallery URL ────────────────────────────────────


def test_update_skips_non_gallery_template(tmp_path, isolated_env):
    fake_user, _ = isolated_env
    tpl_dir = fake_user / "custom-tpl"
    tpl_dir.mkdir(parents=True)
    (tpl_dir / "main.tex").write_text("x")
    # Record with a non-gallery URL
    meta.record("custom-tpl", install_url="https://example.com/custom.zip", version="1.0.0")

    results = update_templates(_gallery_data=GALLERY_DATA)
    r = next((x for x in results if x["name"] == "custom-tpl"), None)
    assert r is not None
    assert r["status"] == "skipped"


# ── update_templates — builtin ────────────────────────────────────────────


def test_update_builtin_returns_skipped():
    results = update_templates(name="blank", _gallery_data=GALLERY_DATA)
    assert len(results) == 1
    assert results[0]["status"] == "skipped"
    assert results[0]["reason"] == "builtin template"


# ── update_templates — not found ─────────────────────────────────────────


def test_update_unknown_template_returns_error():
    results = update_templates(name="does-not-exist", _gallery_data=GALLERY_DATA)
    assert len(results) == 1
    assert results[0]["status"] == "error"
    assert "not found" in results[0]["reason"]


# ── update_templates — empty list ────────────────────────────────────────


def test_update_returns_empty_when_no_user_templates():
    results = update_templates(_gallery_data=GALLERY_DATA)
    assert results == []


# ── update_templates — gallery fetch error ───────────────────────────────


def test_update_propagates_gallery_error(installed_tpl, monkeypatch):
    def bad_fetch(*a, **kw):
        raise ValueError("network error")

    monkeypatch.setattr(tm, "fetch_gallery_json", bad_fetch)
    results = update_templates()  # no _gallery_data → calls fetch_gallery_json
    assert all(r["status"] == "error" for r in results)
