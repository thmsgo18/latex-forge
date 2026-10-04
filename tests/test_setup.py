"""Tests for latex_forge.setup (the `latex-forge setup` command)."""
from __future__ import annotations

import pytest

from latex_forge import setup as setup_mod
from latex_forge.cli import main


@pytest.fixture()
def env(monkeypatch):
    """Stub out everything that would touch the machine; record what's called."""
    calls: dict = {"install": [], "extensions": 0, "verify": 0, "gh": 0, "remove": 0}
    state = {"ready": False}

    monkeypatch.setattr(setup_mod.toolchain, "print_tool_status",
                        lambda out=print: (state["ready"], state["ready"]))

    def fake_install(kind, out=print, modify_path=True, extra_packages=None, reinstall=False):
        calls["install"].append({"kind": kind, "modify_path": modify_path,
                                 "extra": extra_packages, "reinstall": reinstall})
        state["ready"] = True
        return True

    def fake_verify(engine="lualatex", out=print):
        calls["verify"] += 1
        return True

    monkeypatch.setattr(setup_mod.toolchain, "install_tex", fake_install)
    monkeypatch.setattr(setup_mod.toolchain, "verify_toolchain", fake_verify)
    monkeypatch.setattr(setup_mod, "install_vscode_extensions",
                        lambda: calls.__setitem__("extensions", calls["extensions"] + 1) or True)
    monkeypatch.setattr(setup_mod.toolchain, "install_gh_cli",
                        lambda out=print: calls.__setitem__("gh", calls["gh"] + 1) or True)
    monkeypatch.setattr(setup_mod.toolchain, "uninstall_tinytex",
                        lambda out=print: calls.__setitem__("remove", calls["remove"] + 1) or True)
    monkeypatch.setattr(setup_mod.toolchain, "ask_tex_choice", lambda: None)
    monkeypatch.setattr(setup_mod.toolchain, "detect_distribution", lambda: {"kind": "none"})
    monkeypatch.setattr(setup_mod, "command_exists", lambda name: False)
    return calls, state


def test_check_only_installs_nothing(env):
    calls, _ = env
    assert setup_mod.run_setup(check_only=True) == 1
    assert calls["install"] == [] and calls["extensions"] == 0


def test_check_only_conflicts_with_install_flags(env):
    assert setup_mod.run_setup(check_only=True, tex="light") == 2
    assert setup_mod.run_setup(check_only=True, install_tex_requested=True) == 2
    assert setup_mod.run_setup(check_only=True, install_gh=True) == 2


def test_install_tex_defaults_to_light_with_baseline_packages(env):
    calls, _ = env
    assert setup_mod.run_setup(install_tex_requested=True, skip_extensions=True) == 0
    assert len(calls["install"]) == 1
    install = calls["install"][0]
    assert install["kind"] == "light"
    # Everything the built-in templates need is installed up front.
    assert {"latexmk", "biber", "fontspec", "biblatex"} <= set(install["extra"])
    assert calls["verify"] == 1  # a test compile always follows an install


def test_yes_installs_light_without_asking(env, monkeypatch):
    calls, _ = env
    monkeypatch.setattr(setup_mod.toolchain, "ask_tex_choice", lambda: pytest.fail("must not prompt"))
    assert setup_mod.run_setup(assume_yes=True, skip_extensions=True) == 0
    assert calls["install"][0]["kind"] == "light"


def test_explicit_distribution_choice(env):
    calls, _ = env
    assert setup_mod.run_setup(tex="system", skip_extensions=True) == 0
    assert calls["install"][0]["kind"] == "system"


def test_no_modify_path_is_forwarded(env):
    calls, _ = env
    setup_mod.run_setup(tex="light", skip_extensions=True, modify_path=False)
    assert calls["install"][0]["modify_path"] is False


def test_interactive_choice_is_used(env, monkeypatch):
    calls, _ = env
    monkeypatch.setattr(setup_mod.toolchain, "ask_tex_choice", lambda: "full")
    assert setup_mod.run_setup(skip_extensions=True) == 0
    assert calls["install"][0]["kind"] == "full"


def test_declining_leaves_tex_missing(env, capsys):
    calls, _ = env
    assert setup_mod.run_setup(skip_extensions=True) == 1
    assert calls["install"] == []
    assert "latex-forge setup --install-tex" in capsys.readouterr().out


def test_existing_distribution_is_left_alone(env):
    calls, state = env
    state["ready"] = True
    assert setup_mod.run_setup(install_tex_requested=True, skip_extensions=True) == 0
    assert calls["install"] == []


def test_full_upgrades_a_light_tinytex(env, monkeypatch):
    calls, state = env
    state["ready"] = True
    monkeypatch.setattr(setup_mod.toolchain, "detect_distribution", lambda: {"kind": "tinytex"})
    assert setup_mod.run_setup(tex="full", skip_extensions=True) == 0
    assert calls["install"][0]["kind"] == "full"


def test_reinstall(env):
    calls, state = env
    state["ready"] = True
    assert setup_mod.run_setup(reinstall_tex=True, skip_extensions=True) == 0
    assert calls["install"][0]["reinstall"] is True


def test_remove(env):
    calls, _ = env
    assert setup_mod.run_setup(remove_tex=True) == 0
    assert calls["remove"] == 1


def test_verify_without_install(env):
    calls, state = env
    state["ready"] = True
    assert setup_mod.run_setup(verify=True, skip_extensions=True) == 0
    assert calls["verify"] == 1


def test_extensions_installed_by_default(env):
    calls, _ = env
    setup_mod.run_setup(tex="light")
    assert calls["extensions"] == 1


def test_install_gh(env):
    calls, state = env
    state["ready"] = True
    setup_mod.run_setup(install_gh=True, skip_extensions=True)
    assert calls["gh"] == 1


def test_cli_wires_every_setup_flag(monkeypatch):
    seen = {}

    def fake_run_setup(**kwargs):
        seen.update(kwargs)
        return 0

    monkeypatch.setattr("latex_forge.cli.run_setup", fake_run_setup)
    assert main(["setup", "--tex", "full", "--yes", "--verify", "--no-modify-path", "--skip-extensions"]) == 0
    assert seen == {
        "check_only": False, "skip_extensions": True, "install_tex_requested": False,
        "install_gh": False, "tex": "full", "assume_yes": True, "modify_path": False,
        "verify": True, "reinstall_tex": False, "remove_tex": False,
    }


def test_cli_rejects_unknown_distribution():
    with pytest.raises(SystemExit):
        main(["setup", "--tex", "huge"])


def test_baseline_covers_every_builtin_template():
    from latex_forge.project import templates_dir

    per_template = setup_mod.builtin_template_packages()
    builtins = {p.name for p in templates_dir().iterdir() if p.is_dir()}
    assert builtins == set(per_template), "regenerate tex_packages.json for new built-in templates"
    baseline = set(setup_mod.baseline_packages())
    for packages in per_template.values():
        assert set(packages) <= baseline


# ── Helpers around the setup command ──────────────────────────────────────


def test_first_run_marker(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert setup_mod.is_first_run() is True
    setup_mod.mark_initialized()
    assert setup_mod.is_first_run() is False


def test_prompt_yes_no(monkeypatch):
    class Terminal:
        def isatty(self):
            return True

    monkeypatch.setattr(setup_mod.sys, "stdin", Terminal())
    monkeypatch.setattr("builtins.input", lambda prompt="": "Yes")
    assert setup_mod._prompt_yes_no("Go?") is True
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    assert setup_mod._prompt_yes_no("Go?") is False

    def eof(prompt=""):
        raise EOFError

    monkeypatch.setattr("builtins.input", eof)
    assert setup_mod._prompt_yes_no("Go?") is False


def test_prompt_yes_no_without_terminal(monkeypatch):
    class Pipe:
        def isatty(self):
            return False

    monkeypatch.setattr(setup_mod.sys, "stdin", Pipe())
    assert setup_mod._prompt_yes_no("Go?") is False


def test_vscode_extension_recommendations():
    assert "James-Yu.latex-workshop" in setup_mod.vscode_extension_recommendations()


def test_builtin_template_packages_tolerates_a_broken_file(monkeypatch, tmp_path):
    monkeypatch.setattr(setup_mod, "package_dir", lambda: tmp_path)
    assert setup_mod.builtin_template_packages() == {}
    assert setup_mod.baseline_packages() == []


def test_install_tex_only_verifies_after_success(monkeypatch):
    verified = []
    monkeypatch.setattr(setup_mod.toolchain, "verify_toolchain", lambda: verified.append(True) or True)
    monkeypatch.setattr(setup_mod.toolchain, "install_tex", lambda *a, **k: False)
    assert setup_mod.install_tex("light") is False
    assert verified == []
    monkeypatch.setattr(setup_mod.toolchain, "install_tex", lambda *a, **k: True)
    assert setup_mod.install_tex("light") is True
    assert verified == [True]


def test_install_vscode_extensions_uses_recommendations(monkeypatch):
    seen = []
    monkeypatch.setattr(setup_mod.toolchain, "install_vscode_extensions", lambda ids: seen.extend(ids) or True)
    assert setup_mod.install_vscode_extensions() is True
    assert "James-Yu.latex-workshop" in seen


def test_offer_open_vscode(monkeypatch, tmp_path):
    class Terminal:
        def isatty(self):
            return True

    opened = []
    monkeypatch.setattr(setup_mod.toolchain, "vscode_cli", lambda: "/usr/local/bin/code")
    monkeypatch.setattr(setup_mod.sys, "stdin", Terminal())
    monkeypatch.setattr(setup_mod.subprocess, "run", lambda cmd, check=False: opened.append(cmd))
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")
    setup_mod.offer_open_vscode(tmp_path)
    assert opened == [["/usr/local/bin/code", str(tmp_path)]]

    monkeypatch.setattr(setup_mod.toolchain, "vscode_cli", lambda: None)
    setup_mod.offer_open_vscode(tmp_path)
    assert len(opened) == 1


def test_warn_if_latex_missing(monkeypatch, capsys):
    monkeypatch.setattr(setup_mod, "command_exists", lambda name: True)
    setup_mod.warn_if_latex_missing()
    assert capsys.readouterr().out == ""
    monkeypatch.setattr(setup_mod, "command_exists", lambda name: False)
    setup_mod.warn_if_latex_missing()
    assert "--install-tex" in capsys.readouterr().out


@pytest.mark.parametrize("ready,choice,expected", [
    (True, None, "[ok] Your environment is ready."),
    (False, "light", None),
    (False, None, "latex-forge setup --install-tex"),
])
def test_first_launch_check(monkeypatch, capsys, ready, choice, expected):
    monkeypatch.setattr(setup_mod.toolchain, "print_tool_status", lambda out=print: (ready, ready))
    monkeypatch.setattr(setup_mod.toolchain, "ask_tex_choice", lambda: choice)
    installed = []
    monkeypatch.setattr(setup_mod, "install_tex", lambda kind: installed.append(kind))
    setup_mod.run_first_launch_check()
    out = capsys.readouterr().out
    if expected:
        assert expected in out
    assert installed == ([choice] if choice else [])


def test_run_setup_rejects_unknown_distribution(capsys):
    assert setup_mod.run_setup(tex="huge") == 2


def test_run_setup_reports_failed_install(env, monkeypatch, capsys):
    calls, state = env
    monkeypatch.setattr(setup_mod.toolchain, "install_tex", lambda *a, **k: False)
    monkeypatch.setattr(setup_mod.toolchain, "print_tool_status", lambda out=print: (False, False))
    monkeypatch.setattr(setup_mod.toolchain, "print_os_specific_help", lambda out=print: None)
    monkeypatch.setattr(setup_mod, "install_vscode_extensions", lambda: False)
    assert setup_mod.run_setup(tex="light") == 1
    out = capsys.readouterr().out
    assert "not yet complete" in out and "VS Code extensions" in out


def test_run_setup_warns_about_missing_bibliography_tools(env, monkeypatch, capsys):
    monkeypatch.setattr(setup_mod.toolchain, "print_tool_status", lambda out=print: (True, False))
    monkeypatch.setattr(setup_mod, "install_vscode_extensions", lambda: False)
    assert setup_mod.run_setup() == 0
    out = capsys.readouterr().out
    assert "bibliography tools" in out and "VS Code extensions" in out
