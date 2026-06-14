"""Tests for user template install / remove / list."""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from latex_forge.template_manager import (
    install_template,
    list_user_templates,
    remove_template,
)
from latex_forge.project import available_templates, templates_dir


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def isolated_user_dir(tmp_path, monkeypatch):
    """Redirect the user templates directory and metadata path to temp folders."""
    import latex_forge.template_manager as tm
    import latex_forge.project as proj
    import latex_forge.installed_templates as meta

    fake_dir = tmp_path / "user_templates"
    fake_meta = tmp_path / "installed_templates.json"

    monkeypatch.setattr(tm, "_user_templates_dir", lambda: fake_dir)
    monkeypatch.setattr(proj, "user_templates_dir", lambda: fake_dir)
    monkeypatch.setattr(meta, "metadata_path", lambda: fake_meta)
    # Prevent network calls in _record_installation by making _GALLERY_HOST never match
    monkeypatch.setattr(tm, "_GALLERY_HOST", "__no_match__")
    yield fake_dir


@pytest.fixture()
def sample_template(tmp_path) -> Path:
    """A minimal valid template directory."""
    t = tmp_path / "my-template"
    t.mkdir()
    (t / "main.tex").write_text("\\documentclass{article}\\begin{document}\\end{document}")
    (t / "sections").mkdir()
    (t / "sections" / "intro.tex").write_text("\\section{Intro}")
    return t


@pytest.fixture()
def sample_zip(tmp_path, sample_template) -> Path:
    """A ZIP file containing the sample template."""
    zip_path = tmp_path / "my-template.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for f in sample_template.rglob("*"):
            zf.write(f, f.relative_to(sample_template))
    return zip_path


# ── list_user_templates ───────────────────────────────────────────────────


def test_list_empty_when_no_user_dir():
    assert list_user_templates() == []


def test_list_after_install(sample_template):
    install_template(str(sample_template))
    assert "my-template" in list_user_templates()


# ── install from local directory ──────────────────────────────────────────


def test_install_local_dir(sample_template):
    name, path = install_template(str(sample_template))
    assert name == "my-template"
    assert path.is_dir()
    assert (path / "main.tex").exists()


def test_install_local_dir_custom_name(sample_template):
    name, path = install_template(str(sample_template), name="custom-name")
    assert name == "custom-name"
    assert path.name == "custom-name"


def test_install_with_engine_writes_latexforge_toml(sample_template):
    name, path = install_template(str(sample_template), engine="xelatex")
    assert (path / "latexforge.toml").read_text(encoding="utf-8") == 'engine = "xelatex"\n'


def test_install_without_engine_does_not_write_latexforge_toml(sample_template):
    name, path = install_template(str(sample_template))
    assert not (path / "latexforge.toml").exists()


def test_install_invalid_engine_raises(sample_template):
    with pytest.raises(ValueError, match="Invalid engine"):
        install_template(str(sample_template), engine="not-an-engine")


def test_install_raises_when_already_installed(sample_template):
    install_template(str(sample_template))
    with pytest.raises(FileExistsError, match="already installed"):
        install_template(str(sample_template))


def test_install_force_overwrites(sample_template, isolated_user_dir):
    install_template(str(sample_template))
    (sample_template / "extra.tex").write_text("extra")
    install_template(str(sample_template), force=True)
    assert (isolated_user_dir / "my-template" / "extra.tex").exists()


def test_install_raises_for_builtin_name(sample_template):
    built_ins = [p.name for p in templates_dir().iterdir() if p.is_dir()]
    if built_ins:
        with pytest.raises(ValueError, match="built-in"):
            install_template(str(sample_template), name=built_ins[0])


def test_install_missing_main_tex_raises(tmp_path):
    bad = tmp_path / "bad-template"
    bad.mkdir()
    with pytest.raises(ValueError, match="main.tex"):
        install_template(str(bad))


def test_install_unknown_source_raises():
    with pytest.raises(ValueError, match="Cannot install"):
        install_template("not-a-url-or-path")


# ── install from local ZIP ────────────────────────────────────────────────


def test_install_local_zip(sample_zip):
    name, path = install_template(str(sample_zip))
    assert name == "my-template"
    assert (path / "main.tex").exists()


def test_install_local_zip_custom_name(sample_zip):
    name, _ = install_template(str(sample_zip), name="renamed")
    assert name == "renamed"


# ── remove ────────────────────────────────────────────────────────────────


def test_remove_installed(sample_template):
    install_template(str(sample_template))
    assert "my-template" in list_user_templates()
    remove_template("my-template")
    assert "my-template" not in list_user_templates()


def test_remove_not_found_raises(sample_template):
    with pytest.raises(FileNotFoundError):
        remove_template("nonexistent-template")


def test_remove_builtin_raises():
    built_ins = [p.name for p in templates_dir().iterdir() if p.is_dir()]
    if built_ins:
        with pytest.raises(ValueError, match="built-in"):
            remove_template(built_ins[0])


# ── available_templates includes user templates ───────────────────────────


def test_available_templates_includes_user(sample_template):
    install_template(str(sample_template))
    assert "my-template" in available_templates()


def test_available_templates_without_user_dir():
    templates = available_templates()
    assert "blank" in templates
    assert "project-report-fr" in templates
    assert "cv-en" in templates
