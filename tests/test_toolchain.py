"""Tests for latex_forge.toolchain (finding, installing and driving TeX)."""
from __future__ import annotations

import os
import stat
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from latex_forge import toolchain


unix_only = pytest.mark.skipif(sys.platform == "win32", reason="uses POSIX shell scripts as fake tools")


def _executable(path: Path, body: str = "#!/bin/sh\nexit 0\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return path


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """No test may download the TeX Live package database."""
    monkeypatch.setattr(toolchain, "package_index", lambda out=print: None)


@pytest.fixture()
def home(tmp_path, monkeypatch):
    """An empty HOME, no TINYTEX_DIR, no well-known TeX dirs, minimal PATH."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.delenv("TINYTEX_DIR", raising=False)
    monkeypatch.setenv("LATEX_FORGE_TEX_DIRS", "")
    monkeypatch.setenv("PATH", os.pathsep.join(["/usr/bin", "/bin"]))
    return tmp_path


# ── Locations ─────────────────────────────────────────────────────────────


def test_tinytex_root_per_os(home, monkeypatch):
    monkeypatch.setattr(toolchain, "detect_os", lambda: "macos")
    assert toolchain.tinytex_root() == home / "Library" / "TinyTeX"
    monkeypatch.setattr(toolchain, "detect_os", lambda: "linux")
    assert toolchain.tinytex_root() == home / ".TinyTeX"


def test_tinytex_root_windows_appdata(monkeypatch):
    monkeypatch.delenv("TINYTEX_DIR", raising=False)
    monkeypatch.setattr(toolchain, "detect_os", lambda: "windows")
    monkeypatch.setenv("APPDATA", r"C:\Users\me\AppData\Roaming")
    assert toolchain.tinytex_root() == Path(r"C:\Users\me\AppData\Roaming") / "TinyTeX"


def test_tinytex_root_windows_falls_back_for_non_ascii_appdata(monkeypatch):
    """TeX Live breaks under paths with spaces/accents: TinyTeX uses ProgramData then."""
    monkeypatch.delenv("TINYTEX_DIR", raising=False)
    monkeypatch.setattr(toolchain, "detect_os", lambda: "windows")
    monkeypatch.setenv("APPDATA", r"C:\Users\Zoé Martin\AppData\Roaming")
    monkeypatch.setenv("ProgramData", r"C:\ProgramData")
    assert toolchain.tinytex_root() == Path(r"C:\ProgramData") / "TinyTeX"


def test_tinytex_dir_override(tmp_path, monkeypatch):
    monkeypatch.setenv("TINYTEX_DIR", str(tmp_path))
    monkeypatch.setattr(toolchain, "detect_os", lambda: "macos")
    assert toolchain.tinytex_root() == tmp_path / "TinyTeX"


def test_tinytex_bin_dir(tmp_path):
    root = tmp_path / "TinyTeX"
    assert toolchain.tinytex_bin_dir(root) is None
    _executable(root / "bin" / "universal-darwin" / "tlmgr")
    assert toolchain.tinytex_bin_dir(root) == root / "bin" / "universal-darwin"


def test_extra_dirs_include_managed_tinytex(home, monkeypatch):
    monkeypatch.setattr(toolchain, "detect_os", lambda: "linux")
    bin_dir = home / ".TinyTeX" / "bin" / "x86_64-linux"
    _executable(bin_dir / "tlmgr")
    assert toolchain.extra_tex_dirs() == [bin_dir]


def test_extra_dirs_override(home, tmp_path, monkeypatch):
    custom = tmp_path / "custom-tex"
    custom.mkdir()
    monkeypatch.setenv("LATEX_FORGE_TEX_DIRS", os.pathsep.join([str(custom), str(tmp_path / "missing")]))
    assert toolchain.extra_tex_dirs() == [custom]


def test_search_path_appends_without_duplicates(home, tmp_path, monkeypatch):
    custom = tmp_path / "custom-tex"
    custom.mkdir()
    monkeypatch.setenv("LATEX_FORGE_TEX_DIRS", str(custom))
    monkeypatch.setenv("PATH", os.pathsep.join(["/usr/bin", str(custom)]))
    assert toolchain.search_path().split(os.pathsep) == ["/usr/bin", str(custom)]
    monkeypatch.setenv("PATH", "/usr/bin")
    assert toolchain.search_path().split(os.pathsep) == ["/usr/bin", str(custom)]


@unix_only
def test_which_finds_tools_outside_path(home, monkeypatch):
    """A freshly installed TinyTeX isn't on PATH yet — it must still be found."""
    monkeypatch.setattr(toolchain, "detect_os", lambda: "linux")
    bin_dir = home / ".TinyTeX" / "bin" / "x86_64-linux"
    _executable(bin_dir / "tlmgr")
    latexmk = _executable(bin_dir / "latexmk")
    assert toolchain.which("latexmk") == str(latexmk)
    assert toolchain.tex_env()["PATH"].endswith(str(bin_dir))


# ── Distribution detection ────────────────────────────────────────────────


def test_detect_distribution_none(home):
    assert toolchain.detect_distribution()["kind"] == "none"
    assert toolchain.tex_ready() is False


@unix_only
def test_detect_distribution_tinytex(home, monkeypatch):
    monkeypatch.setattr(toolchain, "detect_os", lambda: "linux")
    root = home / ".TinyTeX"
    bin_dir = root / "bin" / "x86_64-linux"
    (root / "tlpkg").mkdir(parents=True)
    _executable(bin_dir / "tlmgr")
    _executable(bin_dir / "luahbtex")
    os.symlink("luahbtex", bin_dir / "lualatex")
    dist = toolchain.detect_distribution()
    assert dist["kind"] == "tinytex"
    assert dist["managed"] is True
    assert dist["can_install_packages"] is True
    assert dist["bin_dir"] == str(Path(os.path.realpath(bin_dir)))


@unix_only
def test_detect_distribution_through_user_bin_symlinks(home, monkeypatch):
    """`tlmgr path add` symlinks tools into ~/.local/bin; we must see through them."""
    monkeypatch.setattr(toolchain, "detect_os", lambda: "linux")
    root = home / ".TinyTeX"
    bin_dir = root / "bin" / "x86_64-linux"
    (root / "tlpkg").mkdir(parents=True)
    _executable(bin_dir / "tlmgr")
    _executable(bin_dir / "lualatex")
    user_bin = home / ".local" / "bin"
    user_bin.mkdir(parents=True)
    os.symlink(bin_dir / "lualatex", user_bin / "lualatex")
    monkeypatch.setenv("PATH", str(user_bin))
    assert toolchain.detect_distribution()["kind"] == "tinytex"


@unix_only
def test_detect_distribution_read_only_texlive(home, tmp_path, monkeypatch):
    root = tmp_path / "texlive" / "2026"
    bin_dir = root / "bin" / "x86_64-linux"
    (root / "tlpkg").mkdir(parents=True)
    _executable(bin_dir / "lualatex")
    _executable(bin_dir / "tlmgr")
    monkeypatch.setenv("LATEX_FORGE_TEX_DIRS", str(bin_dir))
    (root / "tlpkg").chmod(0o555)  # like a root-owned /usr/local/texlive
    try:
        dist = toolchain.detect_distribution()
    finally:
        (root / "tlpkg").chmod(0o755)
    assert dist["kind"] == "texlive"
    assert dist["label"] == "TeX Live 2026"
    assert dist["can_install_packages"] is False


# ── Package database ──────────────────────────────────────────────────────

_TLPDB = """name pgf
category Package
runfiles size=2
 texmf-dist/tex/latex/pgf/frontendlayer/tikz.sty
 texmf-dist/tex/generic/pgf/pgf.revision.tex

name fira
category Package
runfiles size=2
 texmf-dist/fonts/opentype/public/fira/FiraMono-Regular.otf
 texmf-dist/fonts/opentype/public/fira/FiraSans-Regular.otf

name hyphen-french
category Package
runfiles size=1
 texmf-dist/tex/generic/hyph-utf8/loadhyph/loadhyph-fr.tex

name babel-french
category Package
runfiles size=1
 texmf-dist/tex/generic/babel-french/french.ldf

name luatex.x86_64-linux
category Package
binfiles arch=x86_64-linux size=1
 bin/x86_64-linux/luatex
"""


def test_parse_tlpdb():
    files, packages = toolchain.parse_tlpdb(_TLPDB)
    assert files["tikz.sty"] == ["pgf"]
    assert files["FiraMono-Regular.otf"] == ["fira"]
    assert "luatex.x86_64-linux" not in packages
    assert {"pgf", "fira", "hyphen-french", "babel-french"} <= packages


@pytest.fixture()
def index(monkeypatch, offline):
    parsed = toolchain.parse_tlpdb(_TLPDB)
    monkeypatch.setattr(toolchain, "package_index", lambda out=print: parsed)
    return parsed


def test_package_for_file(index):
    assert toolchain.package_for(("file", "tikz.sty")) == "pgf"
    assert toolchain.package_for(("file", "french.ldf")) == "babel-french"


def test_package_for_font(index):
    assert toolchain.package_for(("font", "Fira Mono")) == "fira"
    assert toolchain.package_for(("font", "FiraSans-Regular")) == "fira"
    assert toolchain.package_for(("font", "Comic Sans")) is None


def test_package_for_hyphenation(index):
    assert toolchain.package_for(("hyphen", "French")) == "hyphen-french"
    assert toolchain.package_for(("hyphen", "Klingon")) is None


def test_package_for_unknown_file_does_not_call_tlmgr(index, monkeypatch):
    monkeypatch.setattr(toolchain, "_tlmgr_search_file", lambda name: pytest.fail("slow fallback used"))
    assert toolchain.package_for(("file", "chapter3.tex")) is None


def test_missing_from_log_ignores_user_images():
    log = "! LaTeX Error: File `figures/plot.png' not found.\n! LaTeX Error: File `refs.bib' not found.\n"
    assert toolchain.missing_from_log(log) == []


def test_required_files_works_under_a_folder_named_build(tmp_path):
    project = tmp_path / "build" / "thesis"
    project.mkdir(parents=True)
    (project / "thesis.tex").write_text("\\usepackage{tikz}\n", encoding="utf-8")
    (project / "build").mkdir()
    (project / "build" / "old.tex").write_text("\\usepackage{ignored}\n", encoding="utf-8")
    assert toolchain.required_files(project) == ["tikz.sty"]


def test_package_for_falls_back_to_tlmgr_search(monkeypatch):
    monkeypatch.setattr(toolchain, "package_index", lambda out=print: None)
    monkeypatch.setattr(toolchain, "_tlmgr_search_file", lambda name: "pgf" if name == "tikz.sty" else None)
    assert toolchain.package_for(("file", "tikz.sty")) == "pgf"


def test_tlmgr_search_output_parsing(monkeypatch):
    class R:
        returncode = 0
        stdout = "tikz.sty:\n\tpgf:\n\t\ttexmf-dist/tex/generic/pgf/frontendlayer/tikz/tikz.sty\n"

    monkeypatch.setattr(toolchain, "_run", lambda args, **kw: R())
    assert toolchain._tlmgr_search_file("tikz.sty") == "pgf"


# ── Reading logs ──────────────────────────────────────────────────────────


def test_missing_from_log_patterns():
    log = "\n".join([
        "! LaTeX Error: File `tikz.sty' not found.",
        "! Package fontspec Error: The font \"Fira Mono\" cannot be found.",
        "! Package babel Error: Unknown option `ngerman'. Either you misspelled it",
        "! Font \\T1/cmr/m/n/10=ecrm1000 at 10.0pt not loadable: Metric (TFM) file not found.",
        "Package babel Warning: No hyphenation patterns were preloaded for",
        "(babel)                the language 'French' into the format.",
    ])
    found = toolchain.missing_from_log(log)
    assert ("file", "tikz.sty") in found
    assert ("font", "Fira Mono") in found
    assert ("file", "ngerman.ldf") in found
    assert ("file", "ecrm1000.tfm") in found
    assert ("hyphen", "French") in found


def test_missing_from_log_biblatex_style_and_color_profile():
    log = ("./biblatex.sty:16474: Package biblatex Error: Style 'ieee' not found.\n"
           "./pdfx.sty:2158: Package pdfx Error: No color profile sRGB_IEC61966-2-1_black_scaled.icc found to use\n")
    found = toolchain.missing_from_log(log)
    assert ("file", "ieee.bbx") in found
    assert ("package", "colorprofiles") in found  # pdfx loads it optionally


def test_missing_from_log_pdfx_creationdate():
    log = "./pdfx.sty:1356: Package pdfx Error: CreationDate is not properly supported;\n"
    assert toolchain.missing_from_log(log) == [("package", "luatex85")]


def test_missing_from_log_new_babel_message():
    log = ("! Package babel Error: Unknown option 'french'. Either you misspelled it\n"
           "(babel) or the language definition file french.ldf was not found.\n")
    assert ("file", "french.ldf") in toolchain.missing_from_log(log)


def test_missing_from_log_rejoins_wrapped_lines():
    first = "! LaTeX Error: File `a-really-long-package-name-that-wraps-over-the-line-len"
    assert len(first) < 79
    first = first.ljust(79, "x")  # LaTeX hard-wraps at exactly 79 characters
    log = first + "\ngth.sty' not found.\n"
    found = toolchain.missing_from_log(log)
    assert found and found[0][1].endswith("gth.sty")


def test_missing_from_log_deduplicates():
    log = "File `tikz.sty' not found.\nFile `tikz.sty' not found.\n"
    assert toolchain.missing_from_log(log) == [("file", "tikz.sty")]


def test_missing_helpers(tmp_path, monkeypatch):
    monkeypatch.setattr(toolchain, "command_exists", lambda name: False)
    (tmp_path / "doc.bcf").touch()
    (tmp_path / "doc.aux").write_text("\\bibdata{refs}", encoding="utf-8")
    (tmp_path / "doc.idx").touch()
    assert set(toolchain.missing_helpers(tmp_path)) == {
        ("package", "biber"), ("package", "bibtex"), ("package", "makeindex")}
    monkeypatch.setattr(toolchain, "command_exists", lambda name: True)
    assert toolchain.missing_helpers(tmp_path) == []


# ── Sources ───────────────────────────────────────────────────────────────


def test_required_files(tmp_path):
    (tmp_path / "doc.tex").write_text(
        "\\documentclass[11pt]{beamer}\n"
        "\\usepackage[utf8]{inputenc}\n"
        "\\usepackage{amsmath, tikz}\n"
        "\\usepackage{styles/packages/local}\n"
        "% \\usepackage{commented}\n"
        "\\usetheme{Madrid}\n"
        "\\usecolortheme{beaver}\n"
        "\\usepackage{mystyle}\n"
        "\\newcommand{\\x}[1]{\\usepackage{#1}}\n"
        "\\bibliographystyle{plain}\n",
        encoding="utf-8",
    )
    (tmp_path / "mystyle.sty").write_text("\\RequirePackage{xcolor}\n", encoding="utf-8")
    names = toolchain.required_files(tmp_path)
    assert names[:1] == ["beamer.cls"]
    for expected in ("inputenc.sty", "amsmath.sty", "tikz.sty", "beamerthemeMadrid.sty",
                     "beamercolorthemebeaver.sty", "xcolor.sty", "plain.bst"):
        assert expected in names
    assert "mystyle.sty" not in names  # shipped with the project
    assert "commented.sty" not in names
    assert not any("local" in n or "#" in n for n in names)


# ── Installing packages ───────────────────────────────────────────────────


def test_install_packages_batch_then_one_by_one(monkeypatch):
    calls = []

    class R:
        def __init__(self, code):
            self.returncode = code
            self.stdout = ""
            self.stderr = ""

    def fake_run(args, **kw):
        calls.append(args[2:])
        names = args[2:]
        return R(1 if "doesnotexist" in names else 0)

    monkeypatch.setattr(toolchain, "command_exists", lambda name: True)
    monkeypatch.setattr(toolchain, "_run", fake_run)
    assert toolchain.install_packages(["pgf", "doesnotexist"]) == ["pgf"]
    assert calls[0] == ["doesnotexist", "pgf"]  # one batched attempt first


def test_install_packages_skips_names_missing_from_repository(monkeypatch):
    """l3backend was merged into l3kernel upstream: don't fall back to N calls."""
    calls = []

    class R:
        def __init__(self, code, text=""):
            self.returncode = code
            self.stdout = text
            self.stderr = ""

    def fake_run(args, **kw):
        names = args[2:]
        calls.append(names)
        if "l3backend" in names:
            return R(1, "tlmgr install: package l3backend not present in repository.\n")
        return R(0)

    monkeypatch.setattr(toolchain, "command_exists", lambda name: True)
    monkeypatch.setattr(toolchain, "_run", fake_run)
    assert toolchain.install_packages(["pgf", "l3backend", "siunitx"]) == ["pgf", "siunitx"]
    assert calls == [["l3backend", "pgf", "siunitx"], ["pgf", "siunitx"]]


def test_install_packages_updates_tlmgr_when_it_asks_to(monkeypatch):
    """A repository with a newer tlmgr makes `tlmgr install` do nothing (exit 0 on Windows)."""
    calls = []
    updated = []

    class R:
        def __init__(self, code, text=""):
            self.returncode = code
            self.stdout = text
            self.stderr = ""

    def fake_run(args, **kw):
        calls.append(args[1:])
        if args[1:] == ["update", "--self"]:
            updated.append(True)
            return R(0)
        if not updated:
            return R(0, "tlmgr itself needs to be updated.\ntlmgr: Terminating; please see warning above!\n")
        return R(0)

    monkeypatch.setattr(toolchain, "command_exists", lambda name: True)
    monkeypatch.setattr(toolchain, "_run", fake_run)
    assert toolchain.install_packages(["pgf", "siunitx"]) == ["pgf", "siunitx"]
    assert calls == [["install", "pgf", "siunitx"], ["update", "--self"], ["install", "pgf", "siunitx"]]


def test_install_packages_gives_up_when_tlmgr_cannot_update(monkeypatch):
    calls = []

    class R:
        def __init__(self, code, text=""):
            self.returncode = code
            self.stdout = text
            self.stderr = ""

    def fake_run(args, **kw):
        calls.append(args[1:])
        if args[1:] == ["update", "--self"]:
            return R(1)
        return R(0, "tlmgr itself needs to be updated.\n")

    monkeypatch.setattr(toolchain, "command_exists", lambda name: True)
    monkeypatch.setattr(toolchain, "_run", fake_run)
    assert toolchain.install_packages(["pgf", "siunitx"]) == []
    assert calls.count(["update", "--self"]) == 1


def test_ensure_packages_drops_unknown_names(monkeypatch):
    monkeypatch.setattr(toolchain, "installed_packages", lambda: set())
    monkeypatch.setattr(toolchain, "package_index", lambda out=print: ({}, {"pgf"}))
    seen = []
    monkeypatch.setattr(toolchain, "install_packages", lambda pkgs, out=print, stream=False: seen.extend(pkgs) or list(pkgs))
    toolchain.ensure_packages(["pgf", "l3backend"])
    assert seen == ["pgf"]


def test_ensure_packages_only_installs_missing(monkeypatch):
    monkeypatch.setattr(toolchain, "installed_packages", lambda: {"pgf", "latex"})
    seen = []
    monkeypatch.setattr(toolchain, "install_packages", lambda pkgs, out=print, stream=False: seen.extend(pkgs) or list(pkgs))
    assert toolchain.ensure_packages(["pgf", "siunitx", "latex"]) == ["siunitx"]
    assert seen == ["siunitx"]


def test_ensure_project_packages_skips_unmanaged_distributions(tmp_path, monkeypatch):
    monkeypatch.setattr(toolchain, "detect_distribution", lambda: {"kind": "miktex", "can_install_packages": True})

    def boom(*a, **k):
        raise AssertionError("must not install anything")

    monkeypatch.setattr(toolchain, "ensure_packages", boom)
    assert toolchain.ensure_project_packages(tmp_path, declared=["pgf"]) is True


def test_ensure_project_packages_declared_list(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(toolchain, "detect_distribution", lambda: {"kind": "tinytex", "can_install_packages": True})
    monkeypatch.setattr(toolchain, "ensure_packages", lambda pkgs, out=print: ["siunitx"])
    monkeypatch.setattr(toolchain, "compile_once", lambda *a, **k: pytest.fail("no test compile needed"))
    assert toolchain.ensure_project_packages(tmp_path, "doc.tex", declared=["pgf", "siunitx"]) is True
    assert "siunitx" in capsys.readouterr().out


def test_ensure_project_packages_compile_loop(tmp_path, monkeypatch):
    (tmp_path / "doc.tex").write_text("\\documentclass{article}\n", encoding="utf-8")
    monkeypatch.setattr(toolchain, "detect_distribution", lambda: {"kind": "tinytex", "can_install_packages": True})
    monkeypatch.setattr(toolchain, "unresolved_files", lambda names: [])
    monkeypatch.setattr(toolchain, "missing_helpers", lambda d: [])
    logs = iter([(False, "File `tikz.sty' not found."), (True, "")])
    monkeypatch.setattr(toolchain, "compile_once", lambda *a, **k: next(logs))
    monkeypatch.setattr(toolchain, "package_for", lambda r, out=print: "pgf")
    installed = []
    monkeypatch.setattr(toolchain, "install_packages", lambda pkgs, out=print: installed.extend(pkgs) or list(pkgs))
    assert toolchain.ensure_project_packages(tmp_path, "doc.tex", "pdflatex") is True
    assert installed == ["pgf"]


def test_ensure_project_packages_never_raises(tmp_path, monkeypatch):
    def broken():
        raise RuntimeError("boom")

    monkeypatch.setattr(toolchain, "detect_distribution", broken)
    assert toolchain.ensure_project_packages(tmp_path) is True


# ── TinyTeX download & install ────────────────────────────────────────────


def test_tinytex_platform(monkeypatch):
    monkeypatch.setattr(toolchain, "detect_os", lambda: "macos")
    assert toolchain.tinytex_platform() == ("darwin", "tar.xz")
    monkeypatch.setattr(toolchain, "detect_os", lambda: "windows")
    assert toolchain.tinytex_platform() == ("windows", "exe")
    monkeypatch.setattr(toolchain, "detect_os", lambda: "linux")
    monkeypatch.setattr(toolchain, "_is_musl", lambda: False)
    monkeypatch.setattr(toolchain.platform, "machine", lambda: "x86_64")
    assert toolchain.tinytex_platform() == ("linux-x86_64", "tar.xz")
    monkeypatch.setattr(toolchain.platform, "machine", lambda: "aarch64")
    assert toolchain.tinytex_platform() == ("linux-arm64", "tar.xz")
    monkeypatch.setattr(toolchain.platform, "machine", lambda: "armv7l")
    assert toolchain.tinytex_platform() is None
    monkeypatch.setattr(toolchain, "_is_musl", lambda: True)
    monkeypatch.setattr(toolchain.platform, "machine", lambda: "x86_64")
    assert toolchain.tinytex_platform() == ("linuxmusl-x86_64", "tar.xz")


def test_tinytex_urls(monkeypatch):
    monkeypatch.setattr(toolchain, "tinytex_platform", lambda: ("darwin", "tar.xz"))
    base = toolchain.TINYTEX_RELEASES
    assert toolchain.tinytex_urls("light", "2026.10") == [
        f"{base}/download/v2026.10/TinyTeX-1-darwin-v2026.10.tar.xz",
        f"{base}/download/daily/TinyTeX-1-darwin.tar.xz",
    ]
    # TinyTeX-2 (all of TeX Live) is only published as a daily build.
    assert toolchain.tinytex_urls("full", "2026.10") == [f"{base}/download/daily/TinyTeX-2-darwin.tar.xz"]
    assert toolchain.tinytex_urls("light", None) == [f"{base}/download/daily/TinyTeX-1-darwin.tar.xz"]


def test_download_reports_progress(tmp_path):
    source = tmp_path / "source.bin"
    source.write_bytes(os.urandom(3 * (1 << 20)))
    target = tmp_path / "target.bin"
    lines = []
    toolchain.download(source.as_uri(), target, out=lines.append)
    assert target.read_bytes() == source.read_bytes()
    assert any("100%" in line for line in lines)
    assert not (tmp_path / "target.bin.part").exists()


def test_download_failure_raises(tmp_path):
    with pytest.raises(RuntimeError):
        toolchain.download((tmp_path / "nope").as_uri(), tmp_path / "x", out=None, attempts=1)


_FAKE_TLMGR = """#!/bin/sh
echo "$@" >> "$(dirname "$0")/tlmgr.log"
case "$1" in
  info) cat "$(dirname "$0")/installed.txt" 2>/dev/null ;;
  install) shift; for p in "$@"; do echo "$p" >> "$(dirname "$0")/installed.txt"; echo "[1/1] install: $p"; done ;;
esac
exit 0
"""


def _fake_tinytex_archive(tmp_path: Path, top: str) -> Path:
    """A miniature TinyTeX bundle: a fake tlmgr that records its calls."""
    staging = tmp_path / "staging"
    bin_dir = staging / top / "bin" / "x86_64-linux"
    (staging / top / "tlpkg").mkdir(parents=True)
    _executable(bin_dir / "tlmgr", _FAKE_TLMGR)
    for tool in ("lualatex", "latexmk", "kpsewhich"):
        _executable(bin_dir / tool)
    archive = tmp_path / "TinyTeX-1-linux-x86_64.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(staging / top, arcname=top)
    return archive


@unix_only
def test_install_tinytex_end_to_end(home, tmp_path, monkeypatch):
    monkeypatch.setattr(toolchain, "detect_os", lambda: "linux")
    monkeypatch.setattr(toolchain, "tinytex_platform", lambda: ("linux-x86_64", "tar.gz"))
    monkeypatch.setattr(toolchain, "latest_tinytex_version", lambda: "2026.10")
    monkeypatch.setenv("SHELL", "/bin/zsh")
    archive = _fake_tinytex_archive(tmp_path, ".TinyTeX")
    urls = []

    def fake_download(url, dest, out=print, attempts=3):
        urls.append(url)
        dest.write_bytes(archive.read_bytes())

    monkeypatch.setattr(toolchain, "download", fake_download)
    lines = []
    assert toolchain.install_tinytex("light", out=lines.append, extra_packages=["pgf"]) is True

    root = home / ".TinyTeX"
    bin_dir = root / "bin" / "x86_64-linux"
    assert urls[0].endswith("/v2026.10/TinyTeX-1-linux-x86_64-v2026.10.tar.gz")
    calls = (bin_dir / "tlmgr.log").read_text()
    assert f"option sys_bin {home / '.local' / 'bin'}" in calls
    assert "postaction install script xetex" in calls
    assert "path add" in calls
    installed = (bin_dir / "installed.txt").read_text().split()
    assert {"latexmk", "biber", "pgf"} <= set(installed)
    assert "# >>> latex-forge >>>" in (home / ".zshrc").read_text()
    assert any(line.startswith("==> ") for line in lines)
    # No leftovers from the download/extraction next to the install.
    assert [p.name for p in home.iterdir() if p.name.startswith("latex-forge-tinytex")] == []


@unix_only
def test_install_tinytex_reuses_existing_install(home, monkeypatch):
    monkeypatch.setattr(toolchain, "detect_os", lambda: "linux")
    bin_dir = home / ".TinyTeX" / "bin" / "x86_64-linux"
    (home / ".TinyTeX" / "tlpkg").mkdir(parents=True)
    _executable(bin_dir / "tlmgr", _FAKE_TLMGR)
    for tool in ("lualatex", "latexmk"):
        _executable(bin_dir / tool)
    monkeypatch.setattr(toolchain, "download", lambda *a, **k: pytest.fail("must not download again"))
    assert toolchain.install_tinytex("light", out=lambda m: None, modify_path=False) is True


def test_install_tinytex_refuses_without_space(home, monkeypatch):
    monkeypatch.setattr(toolchain, "detect_os", lambda: "linux")
    monkeypatch.setattr(toolchain.shutil, "which", lambda name, path=None: "/usr/bin/perl" if name == "perl" else None)
    monkeypatch.setattr(toolchain, "tinytex_platform", lambda: ("linux-x86_64", "tar.xz"))

    class Usage:
        free = 10

    monkeypatch.setattr(toolchain.shutil, "disk_usage", lambda path: Usage())
    lines = []
    assert toolchain.install_tinytex("full", out=lines.append) is False
    assert any("disk space" in line for line in lines)


def test_install_tinytex_needs_perl_on_unix(home, monkeypatch):
    monkeypatch.setattr(toolchain, "detect_os", lambda: "linux")
    monkeypatch.setattr(toolchain.shutil, "which", lambda name, path=None: None)
    lines = []
    assert toolchain.install_tinytex("light", out=lines.append) is False
    assert any("Perl" in line for line in lines)


# ── PATH for new shells ───────────────────────────────────────────────────


def test_ensure_user_bin_on_path(home, monkeypatch):
    monkeypatch.setattr(toolchain, "detect_os", lambda: "macos")
    monkeypatch.setenv("SHELL", "/bin/zsh")
    (home / ".bashrc").write_text('export PATH="$HOME/.local/bin:$PATH"\n', encoding="utf-8")
    changed = toolchain.ensure_user_bin_on_path(out=lambda m: None)
    assert changed == [home / ".zshrc"]  # .bashrc already had it
    assert toolchain.PROFILE_MARKER in (home / ".zshrc").read_text()
    assert toolchain.ensure_user_bin_on_path(out=lambda m: None) == []  # idempotent


def test_ensure_user_bin_on_path_respects_uv_zshenv(home, monkeypatch):
    """`uv tool update-shell` writes ~/.zshenv: no duplicate block in ~/.zshrc."""
    monkeypatch.setattr(toolchain, "detect_os", lambda: "macos")
    monkeypatch.setenv("SHELL", "/bin/zsh")
    (home / ".zshenv").write_text('export PATH="$HOME/.local/bin:$PATH"\n', encoding="utf-8")
    assert toolchain.ensure_user_bin_on_path(out=lambda m: None) == []
    assert not (home / ".zshrc").exists()


def test_ensure_user_bin_on_path_fish(home, monkeypatch):
    monkeypatch.setattr(toolchain, "detect_os", lambda: "linux")
    monkeypatch.setenv("SHELL", "/usr/bin/fish")
    changed = toolchain.ensure_user_bin_on_path(out=lambda m: None)
    assert home / ".config" / "fish" / "conf.d" / "latex-forge.fish" in changed


@unix_only
def test_profile_block_is_valid_sh(home, monkeypatch):
    monkeypatch.setattr(toolchain, "detect_os", lambda: "linux")
    monkeypatch.setenv("SHELL", "/bin/sh")
    toolchain.ensure_user_bin_on_path(out=lambda m: None)
    result = subprocess.run(["sh", "-c", f". '{home / '.profile'}' && echo \"$PATH\""],
                            capture_output=True, text=True, env={"HOME": str(home), "PATH": "/usr/bin:/bin"})
    assert result.stdout.strip().startswith(f"{home}/.local/bin:")


def test_windows_needs_no_profile_changes(monkeypatch):
    monkeypatch.setattr(toolchain, "detect_os", lambda: "windows")
    assert toolchain.ensure_user_bin_on_path() == []


# ── System installs ───────────────────────────────────────────────────────


def test_system_install_refuses_without_a_terminal_for_the_password(monkeypatch):
    """brew's MacTeX cask runs sudo: with no terminal it would fail halfway."""
    monkeypatch.setattr(toolchain, "detect_os", lambda: "macos")
    monkeypatch.setattr(toolchain.shutil, "which", lambda name, path=None: f"/opt/homebrew/bin/{name}")
    monkeypatch.setattr(toolchain, "is_interactive", lambda: False)
    monkeypatch.setattr(toolchain, "_can_elevate", lambda: False)
    monkeypatch.setattr(toolchain.subprocess, "run", lambda *a, **k: pytest.fail("must not run brew"))
    lines = []
    assert toolchain.install_system_distribution(out=lines.append) is False
    assert any("--tex system" in line for line in lines)


def test_system_install_linux_pacman_is_non_interactive(monkeypatch):
    monkeypatch.setattr(toolchain, "detect_os", lambda: "linux")
    monkeypatch.setattr(toolchain, "privilege_prefix", lambda: [])
    monkeypatch.setattr(toolchain.shutil, "which",
                        lambda name, path=None: "/usr/bin/pacman" if name == "pacman" else None)
    commands = []

    class R:
        returncode = 0

    monkeypatch.setattr(toolchain.subprocess, "run", lambda cmd, check=False: commands.append(cmd) or R())
    assert toolchain.install_system_distribution(out=lambda m: None) is True
    assert "--noconfirm" in commands[0]


def test_vscode_cli_found_outside_path(monkeypatch, tmp_path):
    monkeypatch.setattr(toolchain.shutil, "which", lambda name, path=None: None)
    monkeypatch.setattr(toolchain, "detect_os", lambda: "windows")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    code = tmp_path / "Programs" / "Microsoft VS Code" / "bin" / "code.cmd"
    code.parent.mkdir(parents=True)
    code.touch()
    assert toolchain.vscode_cli() == str(code)


# ── Test compile ──────────────────────────────────────────────────────────


def test_verify_toolchain_success(monkeypatch):
    monkeypatch.setattr(toolchain, "command_exists", lambda name: True)
    monkeypatch.setattr(toolchain, "compile_once", lambda *a, **k: (True, ""))
    lines = []
    assert toolchain.verify_toolchain(out=lines.append) is True
    assert any("[ok]" in line for line in lines)


def test_verify_toolchain_installs_what_is_missing(monkeypatch):
    monkeypatch.setattr(toolchain, "command_exists", lambda name: True)
    results = iter([(False, "File `fontspec.sty' not found."), (True, "")])
    monkeypatch.setattr(toolchain, "compile_once", lambda *a, **k: next(results))
    monkeypatch.setattr(toolchain, "package_for", lambda r, out=print: "fontspec")
    monkeypatch.setattr(toolchain, "detect_distribution", lambda: {"can_install_packages": True})
    installed = []
    monkeypatch.setattr(toolchain, "install_packages", lambda pkgs, out=print: installed.extend(pkgs))
    assert toolchain.verify_toolchain(out=lambda m: None) is True
    assert installed == ["fontspec"]


def test_verify_toolchain_reports_first_error(monkeypatch):
    monkeypatch.setattr(toolchain, "command_exists", lambda name: True)
    monkeypatch.setattr(toolchain, "compile_once", lambda *a, **k: (False, "! Undefined control sequence."))
    monkeypatch.setattr(toolchain, "detect_distribution", lambda: {"can_install_packages": False})
    lines = []
    assert toolchain.verify_toolchain(out=lines.append) is False
    assert any("Undefined control sequence" in line for line in lines)


# ── Standalone copy ───────────────────────────────────────────────────────


def test_toolchain_module_is_standalone():
    """scripts/toolchain.py ships alone in projects: no package-relative imports."""
    source = Path(toolchain.__file__).read_text(encoding="utf-8")
    assert "from ." not in source
    assert "import latex_forge" not in source
    assert "from latex_forge" not in source
