"""GitHub repository creation via the `gh` CLI.

Used by ``latex-forge create --repo create`` to create a new GitHub
repository for a project and push its initial commit, without the user
having to create the repository by hand. Never drives `gh auth login`
itself — that's an interactive OAuth flow only the user can complete.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def gh_cli_available() -> bool:
    """Return True if the `gh` (GitHub CLI) binary is on PATH."""
    return shutil.which("gh") is not None


def gh_authenticated() -> bool:
    """Return True if `gh` is authenticated against github.com."""
    try:
        result = subprocess.run(["gh", "auth", "status"], capture_output=True, check=False)
    except OSError:
        return False
    return result.returncode == 0


def create_github_repo(target_dir: Path, repo_name: str, visibility: str) -> bool:
    """Create a GitHub repo for *target_dir* (already a git repo) and push to it.

    Best-effort: returns False on any failure (network error, name already
    taken, gh not authenticated, ...) instead of raising, so a failed remote
    creation never rolls back the project — the local git repo made by
    `init_git_repo` is still valid on its own.
    """
    visibility_flag = "--public" if visibility == "public" else "--private"
    try:
        subprocess.run(
            ["gh", "repo", "create", repo_name, visibility_flag, "--source=.", "--remote=origin", "--push"],
            cwd=target_dir,
            capture_output=True,
            check=True,
        )
    except (subprocess.CalledProcessError, OSError):
        return False
    return True
