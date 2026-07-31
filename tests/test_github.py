from __future__ import annotations

import subprocess
from unittest.mock import patch

from latex_forge.github import create_github_repo, gh_authenticated, gh_cli_available


def test_gh_cli_available_true(monkeypatch):
    monkeypatch.setattr("latex_forge.github.shutil.which", lambda name: "/usr/bin/gh")
    assert gh_cli_available() is True


def test_gh_cli_available_false(monkeypatch):
    monkeypatch.setattr("latex_forge.github.shutil.which", lambda name: None)
    assert gh_cli_available() is False


def test_gh_authenticated_true(monkeypatch):
    with patch("latex_forge.github.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        assert gh_authenticated() is True


def test_gh_authenticated_false(monkeypatch):
    with patch("latex_forge.github.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        assert gh_authenticated() is False


def test_gh_authenticated_handles_missing_binary(monkeypatch):
    with patch("latex_forge.github.subprocess.run", side_effect=OSError("not found")):
        assert gh_authenticated() is False


def test_create_github_repo_success(tmp_path):
    with patch("latex_forge.github.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        assert create_github_repo(tmp_path, "my-repo", "private") is True
    args = mock_run.call_args
    assert args.kwargs["cwd"] == tmp_path
    command = args.args[0]
    assert command == ["gh", "repo", "create", "my-repo", "--private", "--source=.", "--remote=origin", "--push"]


def test_create_github_repo_public_visibility(tmp_path):
    with patch("latex_forge.github.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        create_github_repo(tmp_path, "my-repo", "public")
    command = mock_run.call_args.args[0]
    assert "--public" in command
    assert "--private" not in command


def test_create_github_repo_failure_returns_false(tmp_path):
    with patch(
        "latex_forge.github.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, "gh"),
    ):
        assert create_github_repo(tmp_path, "my-repo", "private") is False
