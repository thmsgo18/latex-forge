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


def test_create_repo_none_by_default(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("latex_forge.cli.is_first_run", return_value=False):
        result = main(["create", "--name", "my-project", "--template", "project-report-en"])
    assert result == 0
    assert not (tmp_path / "my-project" / ".git").exists()
    assert "Versioning: none" in capsys.readouterr().out


def test_create_repo_create(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Test")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "test@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Test")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "test@example.com")
    with patch("latex_forge.cli.is_first_run", return_value=False), \
         patch("latex_forge.cli.gh_cli_available", return_value=True), \
         patch("latex_forge.cli.gh_authenticated", return_value=True), \
         patch("latex_forge.github.create_github_repo", return_value=True) as mock_gh:
        result = main(
            [
                "create", "--name", "my-project", "--template", "project-report-en",
                "--repo", "create", "--repo-name", "custom-name", "--visibility", "public",
            ]
        )
    assert result == 0
    assert (tmp_path / "my-project" / ".git").is_dir()
    assert "Initialized a git repository" in capsys.readouterr().out
    mock_gh.assert_called_once_with(tmp_path / "my-project", "custom-name", "public")


def test_create_repo_create_gh_not_installed(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("latex_forge.cli.is_first_run", return_value=False), \
         patch("latex_forge.cli.gh_cli_available", return_value=False):
        result = main(
            ["create", "--name", "my-project", "--template", "project-report-en", "--repo", "create"]
        )
    assert result == 1
    assert not (tmp_path / "my-project").exists()
    assert "GitHub CLI (gh) not found" in capsys.readouterr().err


def test_create_repo_create_gh_not_authenticated(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("latex_forge.cli.is_first_run", return_value=False), \
         patch("latex_forge.cli.gh_cli_available", return_value=True), \
         patch("latex_forge.cli.gh_authenticated", return_value=False):
        result = main(
            ["create", "--name", "my-project", "--template", "project-report-en", "--repo", "create"]
        )
    assert result == 1
    assert not (tmp_path / "my-project").exists()
    assert "Not authenticated" in capsys.readouterr().err


def test_create_repo_existing_never_touches_git(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("latex_forge.cli.is_first_run", return_value=False):
        result = main(
            [
                "create", "--name", "my-project", "--template", "project-report-en",
                "--repo", "existing", "--sharing", "pdf-only",
            ]
        )
    assert result == 0
    assert not (tmp_path / "my-project" / ".git").exists()
    gitignore = (tmp_path / "my-project" / ".gitignore").read_text(encoding="utf-8")
    assert "!/build/*.pdf" in gitignore
    assert "Versioning: existing  |  Sharing: pdf-only" in capsys.readouterr().out


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


def test_create_invalid_repo_choice_rejected(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("latex_forge.cli.is_first_run", return_value=False):
        try:
            main(
                ["create", "--name", "my-project", "--template", "project-report-en", "--repo", "everything"]
            )
            assert False, "expected SystemExit"
        except SystemExit as exc:
            assert exc.code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_create_default_sharing_from_config(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("latex_forge.cli.get_default_sharing", lambda: "pdf-only")
    with patch("latex_forge.cli.is_first_run", return_value=False):
        result = main(
            ["create", "--name", "my-project", "--template", "project-report-en", "--repo", "existing"]
        )
    assert result == 0
    assert "Sharing: pdf-only" in capsys.readouterr().out


def test_create_default_repo_mode_from_config(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("latex_forge.cli.get_default_repo_mode", lambda: "existing")
    with patch("latex_forge.cli.is_first_run", return_value=False):
        result = main(["create", "--name", "my-project", "--template", "project-report-en"])
    assert result == 0
    assert not (tmp_path / "my-project" / ".git").exists()
    assert "Versioning: existing" in capsys.readouterr().out
