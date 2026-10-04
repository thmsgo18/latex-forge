"""Tests for latex_forge.build (latex-forge build / watch)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from latex_forge.build import (
    _detect_latexmk_flag,
    _find_main_tex,
    _find_missing_files,
    _install_missing_packages,
    _tlmgr_package_for_file,
    build_command,
    run_build,
)


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture()
def project(tmp_path) -> Path:
    """A minimal generated project: <name>.tex + .vscode/settings.json."""
    proj = tmp_path / "my-report"
    proj.mkdir()
    (proj / "my-report.tex").write_text("\\documentclass{article}", encoding="utf-8")
    vscode = proj / ".vscode"
    vscode.mkdir()
    (vscode / "settings.json").write_text(
        json.dumps({
            "latex-workshop.latex.tools": [
                {
                    "name": "pdflatexmk",
                    "command": "latexmk",
                    "args": [
                        "-synctex=1",
                        "-interaction=nonstopmode",
                        "-file-line-error",
                        "-pdf",
                        "-outdir=%OUTDIR%",
                        "%DOC%",
                    ],
                }
            ]
        }),
        encoding="utf-8",
    )
    return proj


# ── Engine detection ──────────────────────────────────────────────────────


def test_detect_flag_from_settings(project):
    assert _detect_latexmk_flag(project) == "-pdf"


def test_detect_flag_defaults_to_lualatex(tmp_path):
    assert _detect_latexmk_flag(tmp_path) == "-lualatex"


def test_detect_flag_tolerates_broken_settings(tmp_path):
    vscode = tmp_path / ".vscode"
    vscode.mkdir()
    (vscode / "settings.json").write_text("{not json", encoding="utf-8")
    assert _detect_latexmk_flag(tmp_path) == "-lualatex"


# ── Main file resolution ──────────────────────────────────────────────────


def test_find_main_tex_by_folder_name(project):
    assert _find_main_tex(project).name == "my-report.tex"


def test_find_main_tex_single_file(tmp_path):
    (tmp_path / "whatever.tex").touch()
    assert _find_main_tex(tmp_path).name == "whatever.tex"


def test_find_main_tex_none_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        _find_main_tex(tmp_path)


def test_find_main_tex_ambiguous_raises(tmp_path):
    (tmp_path / "a.tex").touch()
    (tmp_path / "b.tex").touch()
    with pytest.raises(ValueError):
        _find_main_tex(tmp_path)


# ── Command construction ──────────────────────────────────────────────────


def test_build_command(project):
    cmd = build_command(project)
    assert cmd[0] == "latexmk"
    assert "-pdf" in cmd
    assert "-outdir=build" in cmd
    assert "-quiet" in cmd
    assert cmd[-1] == "my-report.tex"
    assert "-pvc" not in cmd


def test_build_command_watch_adds_pvc(project):
    assert "-pvc" in build_command(project, watch=True)


def test_build_command_verbose_drops_quiet(project):
    assert "-quiet" not in build_command(project, verbose=True)


# ── run_build behaviour ───────────────────────────────────────────────────


_TINYTEX = {"kind": "tinytex", "label": "TinyTeX", "bin_dir": "/x", "root": "/x",
            "tlmgr": "/x/tlmgr", "managed": True, "can_install_packages": True}
_SYSTEM_TEXLIVE = dict(_TINYTEX, kind="texlive", managed=False, can_install_packages=False)


def _result(code):
    class R:
        returncode = code
        stdout = ""
        stderr = ""

    return R()


@pytest.fixture()
def tex(monkeypatch):
    """Pretend a TinyTeX is installed: every tool resolves, tlmgr can install."""
    monkeypatch.setattr("latex_forge.build.toolchain.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr("latex_forge.build.toolchain.detect_distribution", lambda: dict(_TINYTEX))
    return monkeypatch


def test_run_build_missing_latexmk(project, monkeypatch, capsys):
    monkeypatch.setattr("latex_forge.build.toolchain.which", lambda _: None)
    assert run_build(project) == 1
    assert "latex-forge setup" in capsys.readouterr().out


def test_run_build_invokes_latexmk(project, tex):
    calls: dict = {}

    def fake_run(command, cwd, check, env):
        calls["command"] = command
        calls["cwd"] = cwd
        calls["env"] = env
        return _result(0)

    tex.setattr("latex_forge.build.subprocess.run", fake_run)
    assert run_build(project) == 0
    assert calls["command"][0] == "/usr/bin/latexmk"  # resolved, not just "latexmk"
    assert calls["command"][-1] == "my-report.tex"
    assert calls["cwd"] == project.resolve()
    assert "PATH" in calls["env"]


def test_run_build_clean_removes_build_dir(project, tex):
    build_dir = project / "build"
    build_dir.mkdir()
    (build_dir / "stale.aux").touch()

    tex.setattr("latex_forge.build.subprocess.run", lambda command, cwd, check, env: _result(0))
    run_build(project, clean=True)
    assert not build_dir.exists()


def test_run_build_missing_directory():
    with pytest.raises(FileNotFoundError):
        run_build(Path("/nonexistent/nowhere"))


def test_run_build_propagates_exit_code(project, tex):
    tex.setattr("latex_forge.build.subprocess.run", lambda command, cwd, check, env: _result(12))
    tex.setattr("latex_forge.build.toolchain.missing_helpers", lambda _: [])
    assert run_build(project) == 12


# ── Missing package detection & auto-install ──────────────────────────────


def test_find_missing_files_parses_log(tmp_path):
    log = tmp_path / "my-report.log"
    log.write_text(
        "! LaTeX Error: File `tikz.sty' not found.\n"
        "Some other line\n"
        "! LaTeX Error: File `tikz.sty' not found.\n",
        encoding="utf-8",
    )
    assert _find_missing_files(log) == ["tikz.sty"]


def test_find_missing_files_no_log(tmp_path):
    assert _find_missing_files(tmp_path / "nope.log") == []


def test_tlmgr_package_for_file_uses_toolchain(monkeypatch):
    seen = []

    def fake_package_for(requirement):
        seen.append(requirement)
        return "pgf"

    monkeypatch.setattr("latex_forge.build.toolchain.package_for", fake_package_for)
    assert _tlmgr_package_for_file("tikz.sty") == "pgf"
    assert seen == [("file", "tikz.sty")]


def test_install_missing_packages_no_tlmgr(monkeypatch):
    monkeypatch.setattr("latex_forge.build.toolchain.which", lambda _: None)
    assert _install_missing_packages(["tikz.sty"]) == []


def test_install_missing_packages_installs(monkeypatch):
    monkeypatch.setattr("latex_forge.build.toolchain.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr("latex_forge.build.toolchain.package_for", lambda r: "pgf")
    monkeypatch.setattr("latex_forge.build.toolchain.install_packages", lambda pkgs: list(pkgs))
    assert _install_missing_packages(["tikz.sty"]) == ["pgf"]


def _write_log(project: Path, text: str) -> None:
    log_path = project / "build" / "my-report.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(text, encoding="utf-8")


def test_run_build_retries_after_installing_missing_package(project, tex, capsys):
    _write_log(project, "! LaTeX Error: File `tikz.sty' not found.\n")
    calls = {"latexmk": 0, "installed": []}

    def fake_run(command, cwd, check, env):
        calls["latexmk"] += 1
        return _result(1)

    def fake_install(packages):
        calls["installed"].append(list(packages))
        return list(packages)

    tex.setattr("latex_forge.build.subprocess.run", fake_run)
    tex.setattr("latex_forge.build.toolchain.package_for", lambda r: "pgf" if r == ("file", "tikz.sty") else None)
    tex.setattr("latex_forge.build.toolchain.install_packages", fake_install)
    result = run_build(project)

    assert result == 1
    # One retry after installing pgf; the log still says tikz.sty is missing,
    # but pgf was already tried, so the loop stops instead of spinning.
    assert calls["latexmk"] == 2
    assert calls["installed"] == [["pgf"]]
    out = capsys.readouterr().out
    assert "Missing package files: tikz.sty" in out
    assert "Installed: pgf" in out


def test_run_build_keeps_installing_until_it_compiles(project, tex, capsys):
    """LaTeX stops at the first missing file, so several rounds may be needed."""
    logs = iter([
        "! LaTeX Error: File `tikz.sty' not found.\n",
        "! LaTeX Error: File `siunitx.sty' not found.\n",
    ])
    _write_log(project, next(logs))
    codes = iter([1, 1, 0])

    def fake_run(command, cwd, check, env):
        code = next(codes)
        if code == 1 and calls["latexmk"] == 1:
            _write_log(project, next(logs))
        calls["latexmk"] += 1
        calls["commands"].append(command)
        return _result(code)

    calls = {"latexmk": 0, "commands": []}
    mapping = {("file", "tikz.sty"): "pgf", ("file", "siunitx.sty"): "siunitx"}
    tex.setattr("latex_forge.build.subprocess.run", fake_run)
    tex.setattr("latex_forge.build.toolchain.package_for", lambda r: mapping.get(r))
    tex.setattr("latex_forge.build.toolchain.install_packages", lambda pkgs: list(pkgs))
    assert run_build(project) == 0
    assert calls["latexmk"] == 3
    # Retries force latexmk to rerun: otherwise it says "Nothing to do".
    assert "-g" not in calls["commands"][0]
    assert all("-g" in c for c in calls["commands"][1:])
    out = capsys.readouterr().out
    assert "Installed: pgf" in out and "Installed: siunitx" in out
    assert "PDF ready" in out


def test_run_build_installs_missing_font(project, tex, capsys):
    _write_log(project, '! Package fontspec Error: The font "Fira Mono" cannot be found.\n')
    codes = iter([1, 0])
    tex.setattr("latex_forge.build.subprocess.run", lambda command, cwd, check, env: _result(next(codes)))
    tex.setattr("latex_forge.build.toolchain.package_for",
                lambda r: "fira" if r == ("font", "Fira Mono") else None)
    tex.setattr("latex_forge.build.toolchain.install_packages", lambda pkgs: list(pkgs))
    assert run_build(project) == 0
    assert 'font "Fira Mono"' in capsys.readouterr().out


def test_run_build_system_texlive_prints_sudo_hint(project, tex, capsys):
    """A root-owned TeX Live can't be changed by us: show the exact command."""
    _write_log(project, "! LaTeX Error: File `tikz.sty' not found.\n")
    tex.setattr("latex_forge.build.toolchain.detect_distribution", lambda: dict(_SYSTEM_TEXLIVE))
    tex.setattr("latex_forge.build.subprocess.run", lambda command, cwd, check, env: _result(1))
    tex.setattr("latex_forge.build.toolchain.package_for", lambda r: "pgf")

    def no_install(_):
        raise AssertionError("must not try to install without rights")

    tex.setattr("latex_forge.build.toolchain.install_packages", no_install)
    assert run_build(project) == 1
    assert "sudo tlmgr install pgf" in capsys.readouterr().out


def test_run_build_miktex_does_not_retry(project, tex):
    """MiKTeX installs missing packages on its own during the compile."""
    calls = {"latexmk": 0}

    def fake_run(command, cwd, check, env):
        calls["latexmk"] += 1
        return _result(1)

    _write_log(project, "! LaTeX Error: File `tikz.sty' not found.\n")
    tex.setattr("latex_forge.build.toolchain.detect_distribution",
                lambda: dict(_TINYTEX, kind="miktex"))
    tex.setattr("latex_forge.build.subprocess.run", fake_run)
    assert run_build(project) == 1
    assert calls["latexmk"] == 1


def test_run_build_no_retry_without_missing_packages(project, tex):
    calls = {"latexmk": 0}

    def fake_run(command, cwd, check, env):
        calls["latexmk"] += 1
        return _result(1)

    tex.setattr("latex_forge.build.subprocess.run", fake_run)
    tex.setattr("latex_forge.build.toolchain.missing_helpers", lambda _: [])
    result = run_build(project)

    assert result == 1
    assert calls["latexmk"] == 1


def test_watch_preinstalls_packages_from_sources(project, tex):
    (project / "my-report.tex").write_text(
        "\\documentclass{article}\n\\usepackage{tikz}\n", encoding="utf-8")
    installed = []
    tex.setattr("latex_forge.build.toolchain.unresolved_files", lambda names: [n for n in names if n == "tikz.sty"])
    tex.setattr("latex_forge.build.toolchain.package_for", lambda r: "pgf" if r == ("file", "tikz.sty") else None)
    tex.setattr("latex_forge.build.toolchain.install_packages", lambda pkgs: installed.extend(pkgs) or list(pkgs))
    tex.setattr("latex_forge.build.subprocess.run", lambda command, cwd, check, env: _result(0))
    run_build(project, watch=True)
    assert installed == ["pgf"]
