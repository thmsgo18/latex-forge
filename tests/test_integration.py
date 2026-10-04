"""End-to-end tests against a real TeX distribution.

Skipped unless LATEX_FORGE_INTEGRATION=1. CI's "integration" job sets it on
Linux, macOS and Windows right after installing latex-forge and the light
TinyTeX with install.sh / install.ps1, so these tests prove that a fresh
machine can compile every built-in template and install a missing package
on demand. Locally, they run against whatever distribution you have.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from latex_forge import toolchain
from latex_forge.cli import main
from latex_forge.project import templates_dir

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("LATEX_FORGE_INTEGRATION") != "1",
                       reason="set LATEX_FORGE_INTEGRATION=1 to run against a real TeX distribution"),
]

BUILTIN_TEMPLATES = sorted(p.name for p in templates_dir().iterdir() if p.is_dir())


@pytest.fixture(autouse=True)
def quiet_create(monkeypatch):
    monkeypatch.setattr("latex_forge.cli.is_first_run", lambda: False)
    monkeypatch.setattr("latex_forge.cli.offer_open_vscode", lambda target: None)


def test_toolchain_is_ready():
    assert toolchain.tex_ready(), "latexmk and lualatex must be reachable"
    assert toolchain.verify_toolchain(out=lambda m: None)


@pytest.mark.parametrize("template", BUILTIN_TEMPLATES)
def test_builtin_template_compiles(template, tmp_path):
    name = f"it-{template}"
    assert main(["create", "--name", name, "--template", template,
                 "--output", str(tmp_path), "--repo", "none"]) == 0
    project = tmp_path / name
    assert main(["build", str(project)]) == 0
    pdf = project / "build" / f"{name}.pdf"
    assert pdf.exists() and pdf.stat().st_size > 1000


def test_missing_package_is_installed_on_demand(tmp_path):
    dist = toolchain.detect_distribution()
    if not dist["can_install_packages"] or dist["kind"] not in ("tinytex", "texlive"):
        pytest.skip(f"{dist['label']} can't install packages without admin rights")
    assert main(["create", "--name", "ondemand", "--template", "blank",
                 "--output", str(tmp_path), "--repo", "none"]) == 0
    project = tmp_path / "ondemand"
    main_tex = project / "ondemand.tex"
    source = main_tex.read_text(encoding="utf-8")
    main_tex.write_text(
        source.replace("\\begin{document}", "\\usepackage{tikz-cd}\n\\begin{document}", 1)
              .replace("\\end{document}", "\\begin{tikzcd} A \\arrow[r] & B \\end{tikzcd}\n\\end{document}", 1),
        encoding="utf-8",
    )
    assert main(["build", str(project)]) == 0
    assert "tikz-cd" in (toolchain.installed_packages() or set())


def test_diagnose_reports_a_working_setup(capsys):
    assert main(["diagnose", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["texlive"]["ok"] and data["latexmk"]["ok"]
    expected = os.environ.get("LATEX_FORGE_EXPECT_DISTRIBUTION")
    if expected:
        assert data["tex_distribution"]["kind"] == expected


def test_project_setup_script_works_standalone(tmp_path):
    assert main(["create", "--name", "standalone", "--template", "cv-en",
                 "--output", str(tmp_path), "--repo", "none", "--skip-packages"]) == 0
    script = tmp_path / "standalone" / "scripts" / "setup.py"
    result = subprocess.run([sys.executable, "-I", str(script), "--skip-extensions"],
                            capture_output=True, text=True, timeout=1800)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ready" in result.stdout
