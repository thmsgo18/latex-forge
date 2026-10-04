"""Tests for the CLI dispatch of every subcommand (latex_forge.cli.main)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from latex_forge import cli
from latex_forge.cli import main


@pytest.fixture()
def answers(monkeypatch):
    """Simulate an interactive terminal answering prompts in order."""
    class Terminal:
        def isatty(self):
            return True

    def set_answers(*replies):
        it = iter(replies)
        monkeypatch.setattr(cli, "_is_interactive", lambda: True)
        monkeypatch.setattr("sys.stdin", Terminal())  # for _prompt_yes_no
        monkeypatch.setattr("builtins.input", lambda prompt="": next(it))
    return set_answers


@pytest.fixture(autouse=True)
def no_first_run(monkeypatch):
    monkeypatch.setattr(cli, "is_first_run", lambda: False)
    monkeypatch.setattr(cli, "offer_open_vscode", lambda target: None)


# ── profile ───────────────────────────────────────────────────────────────


def test_profile_show_empty(capsys):
    assert main(["profile", "show"]) == 0
    assert "No profile set" in capsys.readouterr().out


def test_profile_set_show_clear(answers, capsys):
    from latex_forge.profile import PROFILE_SCHEMA, load_profile

    replies = ["Ada Lovelace"] + [""] * (len(PROFILE_SCHEMA) - 1)
    answers(*replies)
    assert main(["profile", "set"]) == 0
    first_key = PROFILE_SCHEMA[0][0]
    assert load_profile()[first_key] == "Ada Lovelace"

    capsys.readouterr()
    assert main(["profile", "show"]) == 0
    out = capsys.readouterr().out
    assert "Ada Lovelace" in out and "(not set)" in out

    assert main(["profile", "clear"]) == 0
    assert load_profile() == {}


def test_profile_set_needs_a_terminal(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_is_interactive", lambda: False)
    assert main(["profile", "set"]) == 1
    assert "interactive terminal" in capsys.readouterr().err


def test_profile_set_ctrl_c(monkeypatch):
    monkeypatch.setattr(cli, "_is_interactive", lambda: True)

    def interrupt(prompt=""):
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", interrupt)
    assert main(["profile", "set"]) == 1


# ── template ──────────────────────────────────────────────────────────────


def test_template_install_success_and_failure(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr("latex_forge.template_manager.install_template",
                        lambda source, name, force=False, engine=None: ("thesis", tmp_path / "thesis"))
    assert main(["template", "install", "./thesis", "--engine", "xelatex"]) == 0
    assert "Template installed: thesis" in capsys.readouterr().out

    def broken(*a, **k):
        raise ValueError("Cannot install template from: 'nope'")

    monkeypatch.setattr("latex_forge.template_manager.install_template", broken)
    assert main(["template", "install", "nope"]) == 1
    assert "Cannot install" in capsys.readouterr().err


def test_template_list_human_and_json(capsys, tmp_path, monkeypatch):
    assert main(["template", "list"]) == 0
    out = capsys.readouterr().out
    assert "Built-in templates:" in out and "No user-installed templates." in out

    user_dir = Path.home() / ".latex-forge" / "templates" / "my-template"
    user_dir.mkdir(parents=True)
    (user_dir / "main.tex").touch()
    assert main(["template", "list"]) == 0
    assert "my-template" in capsys.readouterr().out

    assert main(["template", "list", "--json"]) == 0
    entries = json.loads(capsys.readouterr().out)
    assert any(entry["name"] == "research" for entry in entries)


@pytest.mark.parametrize("results,code,needle", [
    ([], 2, "No user-installed templates to update."),
    ([{"name": "a", "status": "updated", "from": "1.0.0", "to": "1.1.0"}], 0, "1.0.0 → 1.1.0"),
    ([{"name": "a", "status": "up_to_date", "from": "1.0.0"}], 2, "already up to date"),
    ([{"name": "a", "status": "skipped", "reason": "not from the gallery"}], 2, "not from the gallery"),
    ([{"name": "a", "status": "error", "reason": "offline"}], 1, "offline"),
])
def test_template_update_human(monkeypatch, capsys, results, code, needle):
    monkeypatch.setattr("latex_forge.template_manager.update_templates", lambda name=None: results)
    assert main(["template", "update"]) == code
    captured = capsys.readouterr()
    assert needle in captured.out + captured.err


@pytest.mark.parametrize("results,code", [
    ([{"name": "a", "status": "updated"}], 0),
    ([{"name": "a", "status": "up_to_date"}], 2),
    ([{"name": "a", "status": "error"}], 1),
])
def test_template_update_json(monkeypatch, capsys, results, code):
    monkeypatch.setattr("latex_forge.template_manager.update_templates", lambda name=None: results)
    assert main(["template", "update", "a", "--json"]) == code
    assert json.loads(capsys.readouterr().out) == results


def test_template_remove(monkeypatch, capsys):
    removed = []
    monkeypatch.setattr("latex_forge.template_manager.remove_template", removed.append)
    assert main(["template", "remove", "thesis"]) == 0
    assert removed == ["thesis"]

    def missing(name):
        raise FileNotFoundError(f"Template not found: {name}")

    monkeypatch.setattr("latex_forge.template_manager.remove_template", missing)
    assert main(["template", "remove", "ghost"]) == 1
    assert "Template not found" in capsys.readouterr().err


# ── build / watch / export / rename ───────────────────────────────────────


def test_build_and_watch_dispatch(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr("latex_forge.build.run_build",
                        lambda project_dir=None, watch=False, clean=False, verbose=False:
                        calls.append((project_dir, watch, clean, verbose)) or 0)
    assert main(["build", str(tmp_path), "--clean", "--verbose"]) == 0
    assert main(["watch"]) == 0
    assert calls == [(tmp_path.resolve(), False, True, True), (None, True, False, False)]


def test_build_reports_layout_errors(monkeypatch, capsys, tmp_path):
    assert main(["build", str(tmp_path / "missing")]) == 1
    assert "not found" in capsys.readouterr().err


def test_export_reports_errors(capsys, tmp_path):
    assert main(["export", str(tmp_path)]) == 1


def test_rename_variants(monkeypatch, capsys, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert main(["create", "--name", "old", "--template", "blank", "--repo", "none", "--skip-packages"]) == 0
    assert main(["rename", "old", "new"]) == 0
    assert (tmp_path / "new" / "new.tex").exists()

    monkeypatch.chdir(tmp_path / "new")
    assert main(["rename", "newer"]) == 0
    assert (tmp_path / "newer" / "newer.tex").exists()

    monkeypatch.chdir(tmp_path)
    capsys.readouterr()
    assert main(["rename", "a", "b", "c"]) == 1
    assert "Usage" in capsys.readouterr().err
    assert main(["rename", "ghost", "x"]) == 1


# ── diagnose / completion / setup ─────────────────────────────────────────


def test_diagnose_exit_code_follows_latex_readiness(monkeypatch, capsys):
    import latex_forge.diagnose as diag

    monkeypatch.setattr(diag, "_check_texlive", lambda: {"ok": True, "version": None, "engines": ["lualatex"]})
    monkeypatch.setattr(diag, "_check_latexmk", lambda: {"ok": True, "version": "4.88"})
    assert main(["diagnose", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["latexmk"]["ok"] is True
    monkeypatch.setattr(diag, "_check_latexmk", lambda: {"ok": False, "fix": "x"})
    assert main(["diagnose"]) == 1


@pytest.mark.parametrize("shell", ["bash", "zsh", "fish"])
def test_completion(capsys, shell):
    assert main(["completion", "--shell", shell]) == 0
    assert "latex-forge" in capsys.readouterr().out


def test_completion_detects_the_shell(monkeypatch, capsys):
    monkeypatch.setenv("SHELL", "/usr/bin/zsh")
    assert main(["completion"]) == 0
    monkeypatch.setenv("SHELL", "/usr/bin/tcsh")  # unsupported: falls back to bash
    assert main(["completion"]) == 0


def test_setup_check_only_runs(monkeypatch, capsys):
    monkeypatch.setattr("latex_forge.toolchain.print_tool_status", lambda out=print: (True, True))
    assert main(["setup", "--check-only"]) == 0
    assert "[ok]" in capsys.readouterr().out


# ── create ────────────────────────────────────────────────────────────────


def test_create_requires_name_and_template_without_a_terminal(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(cli, "_is_interactive", lambda: False)
    monkeypatch.chdir(tmp_path)
    assert main(["create", "--template", "blank"]) == 1
    assert "--name is required" in capsys.readouterr().err
    monkeypatch.setattr(cli, "get_default_template", lambda: None)
    assert main(["create", "--name", "x"]) == 1
    assert "--template is required" in capsys.readouterr().err


def test_create_uses_default_template_from_config(monkeypatch, capsys, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "get_default_template", lambda: "blank")
    assert main(["create", "--name", "x", "--repo", "none", "--skip-packages"]) == 0
    assert (tmp_path / "x" / "x.tex").exists()


def test_create_warns_about_an_unknown_default_template(monkeypatch, capsys, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "_is_interactive", lambda: False)
    monkeypatch.setattr(cli, "get_default_template", lambda: "gone")
    assert main(["create", "--name", "x"]) == 1
    assert "does not match any available template" in capsys.readouterr().err


def test_create_guided(answers, monkeypatch, capsys, tmp_path):
    from latex_forge.project import available_templates

    blank_index = available_templates().index("blank") + 1
    out_dir = tmp_path / "docs"
    answers(
        "bad name",            # rejected: spaces
        "my-notes",            # project name
        "0", str(blank_index), # template (0 is out of range)
        str(out_dir),          # output directory (created)
        "",                    # versioning: default (none)
    )
    monkeypatch.setattr(cli, "get_default_template", lambda: None)
    monkeypatch.setattr(cli, "get_default_output_dir", lambda: None)
    monkeypatch.setattr(cli, "get_default_repo_mode", lambda: None)
    assert main(["create", "--skip-packages"]) == 0
    assert (out_dir / "my-notes" / "my-notes.tex").exists()
    out = capsys.readouterr().out
    assert "Invalid project name" in out and "Versioning: none" in out


def test_create_guided_github_repo(answers, monkeypatch, capsys, tmp_path):
    monkeypatch.chdir(tmp_path)
    created = {}

    def fake_create_project(**kwargs):
        created.update(kwargs)
        target = tmp_path / kwargs["name"]
        target.mkdir()
        return target, target / f"{kwargs['name']}.tex"

    monkeypatch.setattr(cli, "create_project", fake_create_project)
    monkeypatch.setattr(cli, "gh_cli_available", lambda: True)
    monkeypatch.setattr(cli, "gh_authenticated", lambda: True)
    monkeypatch.setattr(cli, "get_default_visibility", lambda: None)
    monkeypatch.setattr(cli, "get_default_sharing", lambda: None)
    answers(
        "thesis",      # name
        "",            # output dir: default (cwd)
        "1",           # versioning: create a GitHub repository
        "",            # repo name: default
        "pub",         # visibility: public
        "y",           # confirm creation
        "pdf",         # sharing: pdf-only
    )
    assert main(["create", "--template", "blank"]) == 0
    assert created["repo_mode"] == "create"
    assert created["repo_name"] == "thesis"
    assert created["visibility"] == "public"
    assert created["sharing"] == "pdf-only"
    captured = capsys.readouterr()
    assert "could not initialize git" in captured.err  # no .git in the faked project
    assert "could not create the GitHub repository" in captured.err


def test_create_guided_github_repo_declined(answers, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "gh_cli_available", lambda: True)
    monkeypatch.setattr(cli, "gh_authenticated", lambda: True)
    monkeypatch.setattr(cli, "create_project", lambda **k: pytest.fail("declined"))
    answers("thesis", "", "1", "my-repo", "", "n")
    assert main(["create", "--template", "blank"]) == 1


def test_create_runs_first_launch_check(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "is_first_run", lambda: True)
    events = []
    monkeypatch.setattr(cli, "run_first_launch_check", lambda: events.append("check"))
    monkeypatch.setattr(cli, "mark_initialized", lambda: events.append("marked"))
    assert main(["create", "--name", "x", "--template", "blank", "--repo", "none", "--skip-packages"]) == 0
    assert events == ["check", "marked"]


def test_create_warns_when_latex_is_missing(monkeypatch, capsys, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("latex_forge.setup.command_exists", lambda name: False)
    assert main(["create", "--name", "x", "--template", "blank", "--repo", "none", "--skip-packages"]) == 0
    assert "latex-forge setup --install-tex" in capsys.readouterr().out


def test_create_existing_versioning_message(monkeypatch, capsys, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert main(["create", "--name", "x", "--template", "cv-en", "--repo", "existing",
                 "--sharing", "full", "--skip-packages"]) == 0
    out = capsys.readouterr().out
    assert "sections/heading.tex" in out
    assert "make sure its parent folder is versioned" in out


def test_create_installs_template_packages_unless_skipped(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    calls = []
    monkeypatch.setattr("latex_forge.toolchain.ensure_project_packages",
                        lambda *a, **k: calls.append(k.get("declared")) or True)
    assert main(["create", "--name", "a", "--template", "research", "--repo", "none"]) == 0
    assert main(["create", "--name", "b", "--template", "research", "--repo", "none", "--skip-packages"]) == 0
    assert len(calls) == 1 and "biblatex" in calls[0]
