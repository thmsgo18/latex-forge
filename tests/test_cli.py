from __future__ import annotations

from unittest.mock import patch

from latex_forge.cli import main


def test_version(capsys):
    try:
        main(["--version"])
    except SystemExit as exc:
        assert exc.code == 0
    out = capsys.readouterr().out
    assert "latex-forge" in out


def test_list_templates(capsys):
    result = main(["list-templates"])
    assert result == 0
    out = capsys.readouterr().out
    assert "project-report-en" in out
    assert "research" in out


def test_create_invalid_name(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("latex_forge.cli.is_first_run", return_value=False):
        result = main(["create", "--name", "bad name", "--template", "project-report-en"])
    assert result == 1
    assert "Invalid project name" in capsys.readouterr().err


def test_create_unknown_template(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("latex_forge.cli.is_first_run", return_value=False):
        result = main(["create", "--name", "my-project", "--template", "does-not-exist"])
    assert result == 1
    assert "Unknown template" in capsys.readouterr().err


def test_create_success(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("latex_forge.cli.is_first_run", return_value=False):
        result = main(["create", "--name", "my-project", "--template", "project-report-en"])
    assert result == 0
    assert (tmp_path / "my-project" / "my-project.tex").exists()


def test_export_success(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("latex_forge.cli.is_first_run", return_value=False):
        main(["create", "--name", "my-project", "--template", "project-report-en"])
    capsys.readouterr()

    result = main(["export", "my-project"])
    assert result == 0
    out = capsys.readouterr().out
    assert "Exported:" in out
    assert "no compiled PDF" in out
    assert (tmp_path / "my-project-export.zip").exists()


def test_export_missing_directory(tmp_path, capsys):
    result = main(["export", str(tmp_path / "does-not-exist")])
    assert result == 1
    assert "not found" in capsys.readouterr().err


def test_create_with_git(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Test")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "test@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Test")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "test@example.com")
    with patch("latex_forge.cli.is_first_run", return_value=False):
        result = main(["create", "--name", "my-project", "--template", "project-report-en", "--git"])
    assert result == 0
    assert (tmp_path / "my-project" / ".git").is_dir()
    assert "Initialized a git repository" in capsys.readouterr().out


def test_create_sharing_pdf_only(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("latex_forge.cli.is_first_run", return_value=False):
        result = main(
            ["create", "--name", "my-project", "--template", "project-report-en", "--sharing", "pdf-only"]
        )
    assert result == 0
    gitignore = (tmp_path / "my-project" / ".gitignore").read_text(encoding="utf-8")
    assert "!/build/*.pdf" in gitignore
    assert "Sharing: pdf-only" in capsys.readouterr().out


def test_create_sharing_none_with_git_reports_success(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Test")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "test@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Test")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "test@example.com")
    with patch("latex_forge.cli.is_first_run", return_value=False):
        result = main(
            [
                "create", "--name", "my-project", "--template", "project-report-en",
                "--git", "--sharing", "none",
            ]
        )
    assert result == 0
    out = capsys.readouterr().out
    assert "Initialized a git repository" in out
    assert "Warning: could not initialize git" not in out


def test_create_invalid_sharing_choice_rejected(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("latex_forge.cli.is_first_run", return_value=False):
        try:
            main(
                ["create", "--name", "my-project", "--template", "project-report-en", "--sharing", "everything"]
            )
            assert False, "expected SystemExit"
        except SystemExit as exc:
            assert exc.code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_create_default_sharing_from_config(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("latex_forge.cli.get_default_sharing", lambda: "pdf-only")
    with patch("latex_forge.cli.is_first_run", return_value=False):
        result = main(["create", "--name", "my-project", "--template", "project-report-en"])
    assert result == 0
    assert "Sharing: pdf-only" in capsys.readouterr().out
