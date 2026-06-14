from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from latex_forge.project import (
    available_templates,
    create_project,
    init_git_repo,
    patch_local_style,
    rename_current_project,
    rename_project,
    required_style_files,
    templates_dir,
    validate_name,
)


# ---------------------------------------------------------------------------
# validate_name
# ---------------------------------------------------------------------------

def test_validate_name_valid():
    validate_name("my-project")
    validate_name("rapport-ter-2024")
    validate_name("audio_search")


def test_validate_name_empty():
    with pytest.raises(ValueError, match="empty"):
        validate_name("")


def test_validate_name_space():
    with pytest.raises(ValueError, match="Invalid project name"):
        validate_name("my project")


def test_validate_name_slash():
    with pytest.raises(ValueError, match="Invalid project name"):
        validate_name("rapport/2024")


def test_validate_name_backslash():
    with pytest.raises(ValueError, match="Invalid project name"):
        validate_name("rapport\\2024")


def test_validate_name_dot_prefix():
    with pytest.raises(ValueError, match="dot"):
        validate_name(".hidden")


# ---------------------------------------------------------------------------
# patch_local_style
# ---------------------------------------------------------------------------

def test_patch_local_style_replaces_relative_path(tmp_path):
    sty = tmp_path / "test.sty"
    sty.write_text(
        r"\graphicspath{{images/}{../../assets/images/common/}{../../assets/logos/}}",
        encoding="utf-8",
    )
    patch_local_style(sty)
    content = sty.read_text(encoding="utf-8")
    assert "../../assets/" not in content
    assert "assets/images/common/" in content
    assert "assets/logos/" in content


def test_patch_local_style_no_change_needed(tmp_path):
    sty = tmp_path / "test.sty"
    original = r"\graphicspath{{images/}{assets/logos/}}"
    sty.write_text(original, encoding="utf-8")
    patch_local_style(sty)
    assert sty.read_text(encoding="utf-8") == original


def test_patch_local_style_missing_file(tmp_path):
    patch_local_style(tmp_path / "nonexistent.sty")


# ---------------------------------------------------------------------------
# available_templates / required_style_files
# ---------------------------------------------------------------------------

def test_available_templates():
    templates = available_templates()
    assert "project-report-en" in templates
    assert "project-report-fr" in templates
    assert "research" in templates
    assert "cv-fr" in templates
    assert "cv-en" in templates
    assert "rapport-ter" not in templates


def test_required_style_files_returns_paths():
    source = templates_dir() / "project-report-en"
    styles = required_style_files(source)
    assert len(styles) > 0
    assert all(p.suffix == ".sty" for p in styles)
    assert all(p.exists() for p in styles)


# ---------------------------------------------------------------------------
# create_project
# ---------------------------------------------------------------------------

def test_create_project_success(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target_dir, main_tex = create_project("my-project", "project-report-en")

    assert target_dir == tmp_path / "my-project"
    assert main_tex == target_dir / "my-project.tex"
    assert main_tex.exists()
    assert (target_dir / "styles" / "packages").is_dir()
    assert (target_dir / "assets" / "logos").is_dir()
    assert (target_dir / ".vscode" / "settings.json").exists()
    assert (target_dir / ".gitignore").exists()


def test_create_project_all_templates(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for template in available_templates():
        target_dir, main_tex = create_project(template, template)
        assert main_tex.exists()


def test_create_project_unknown_template(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="Unknown template"):
        create_project("my-project", "does-not-exist")


def test_create_project_existing_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "my-project").mkdir()
    with pytest.raises(FileExistsError):
        create_project("my-project", "project-report-en")


def test_create_project_invalid_name(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="Invalid project name"):
        create_project("my project", "project-report-en")


def test_create_project_with_git(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Test")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "test@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Test")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "test@example.com")
    target_dir, _ = create_project("my-project", "project-report-en", init_git=True)

    assert (target_dir / ".git").is_dir()
    log = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=target_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Initial commit" in log.stdout


def test_create_project_without_git_by_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target_dir, _ = create_project("my-project", "project-report-en")

    assert not (target_dir / ".git").exists()


def test_init_git_repo_missing_git(tmp_path, monkeypatch):
    monkeypatch.setattr("latex_forge.project.shutil.which", lambda name: None)
    assert init_git_repo(tmp_path) is False


def test_create_project_atomic_cleanup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch("latex_forge.project.write_project_gitignore", side_effect=OSError("disk full")):
        with pytest.raises(OSError):
            create_project("my-project", "project-report-en")
    assert not (tmp_path / "my-project").exists()


def test_create_project_no_relative_paths_in_styles(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_project("my-project", "project-report-en")
    for sty in (tmp_path / "my-project" / "styles" / "packages").glob("*.sty"):
        content = sty.read_text(encoding="utf-8")
        assert "../../assets/" not in content, f"Unpatched path in {sty.name}"


# ---------------------------------------------------------------------------
# rename_project
# ---------------------------------------------------------------------------

def test_rename_project_success(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_project("old-name", "project-report-en")
    new_dir, new_tex = rename_project("old-name", "new-name")

    assert new_dir == tmp_path / "new-name"
    assert new_tex.exists()
    assert not (tmp_path / "old-name").exists()


def test_rename_project_not_found(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        rename_project("ghost", "new-name")


def test_rename_project_target_exists(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_project("old-name", "project-report-en")
    (tmp_path / "new-name").mkdir()
    with pytest.raises(FileExistsError):
        rename_project("old-name", "new-name")


def test_rename_project_invalid_new_name(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_project("old-name", "project-report-en")
    with pytest.raises(ValueError, match="Invalid project name"):
        rename_project("old-name", "new name")


def test_rename_current_project_success(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_project("old-name", "project-report-en")
    monkeypatch.chdir(tmp_path / "old-name")
    new_dir, new_tex = rename_current_project("new-name")

    assert new_dir == tmp_path / "new-name"
    assert new_tex.exists()


def test_rename_renames_build_artifacts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_project("old-name", "project-report-en")
    build_dir = tmp_path / "old-name" / "build"
    build_dir.mkdir()
    (build_dir / "old-name.pdf").touch()
    (build_dir / "old-name.log").touch()

    rename_project("old-name", "new-name")

    assert (tmp_path / "new-name" / "build" / "new-name.pdf").exists()
    assert (tmp_path / "new-name" / "build" / "new-name.log").exists()
