"""More tests for latex_forge.toolchain: tlmgr, package index, installers, prompts.

Fake TeX tools are small POSIX shell scripts placed in a directory that
LATEX_FORGE_TEX_DIRS points at, so the real lookup code (`which`, `tex_env`,
`_run`) is exercised end to end without a TeX distribution.
"""
from __future__ import annotations

import io
import lzma
import os
import stat
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from latex_forge import toolchain

unix_only = pytest.mark.skipif(sys.platform == "win32", reason="uses POSIX shell scripts as fake tools")
REAL_PACKAGE_INDEX = toolchain.package_index


def _executable(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return path


@pytest.fixture()
def tools(tmp_path, monkeypatch):
    """An empty fake-TeX bin directory searched by toolchain.which()."""
    bin_dir = tmp_path / "texbin"
    bin_dir.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.delenv("TINYTEX_DIR", raising=False)
    monkeypatch.setenv("LATEX_FORGE_TEX_DIRS", str(bin_dir))
    monkeypatch.setenv("PATH", os.pathsep.join(["/usr/bin", "/bin"]))
    return bin_dir


@pytest.fixture(autouse=True)
def fresh_index(monkeypatch, tmp_path):
    """No network: no package index unless a test asks for the real one."""
    toolchain._index_memo.clear()
    monkeypatch.setattr(toolchain, "cache_dir", lambda: tmp_path / "cache")
    monkeypatch.setattr(toolchain, "package_index", lambda out=print: None)
    yield
    toolchain._index_memo.clear()


@pytest.fixture()
def real_index(monkeypatch):
    monkeypatch.setattr(toolchain, "package_index", REAL_PACKAGE_INDEX)


def _completed(code=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=code, stdout=stdout, stderr=stderr)


# ── Platform helpers ──────────────────────────────────────────────────────


@pytest.mark.parametrize("system,expected", [
    ("Darwin", "macos"), ("Windows", "windows"), ("Linux", "linux"), ("FreeBSD", "freebsd"),
])
def test_detect_os(monkeypatch, system, expected):
    monkeypatch.setattr(toolchain.platform, "system", lambda: system)
    assert toolchain.detect_os() == expected


def test_is_interactive_handles_broken_stdin(monkeypatch):
    class Broken:
        def isatty(self):
            raise ValueError("closed")

    monkeypatch.setattr(toolchain.sys, "stdin", Broken())
    assert toolchain.is_interactive() is False


def test_step_and_say_use_the_given_output():
    lines = []
    toolchain.step("Doing things", lines.append)
    assert lines == ["==> Doing things"]


def test_cache_dir_per_os(monkeypatch, tmp_path):
    monkeypatch.undo()  # the autouse fixture replaced cache_dir
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setattr(toolchain, "detect_os", lambda: "macos")
    assert toolchain.cache_dir() == tmp_path / "Library" / "Caches" / "latex-forge"
    monkeypatch.setattr(toolchain, "detect_os", lambda: "linux")
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    assert toolchain.cache_dir() == tmp_path / "xdg" / "latex-forge"
    monkeypatch.setattr(toolchain, "detect_os", lambda: "windows")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    assert toolchain.cache_dir() == tmp_path / "local" / "latex-forge" / "Cache"


def test_well_known_dirs_per_os(monkeypatch, tmp_path):
    monkeypatch.setattr(toolchain, "detect_os", lambda: "macos")
    assert Path("/Library/TeX/texbin") in toolchain._well_known_tex_dirs()
    monkeypatch.setattr(toolchain, "detect_os", lambda: "windows")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    dirs = toolchain._well_known_tex_dirs()
    assert tmp_path / "Programs" / "MiKTeX" / "miktex" / "bin" / "x64" in dirs
    assert Path("C:/Strawberry/perl/bin") in dirs


def test_is_musl(monkeypatch):
    monkeypatch.setattr(toolchain.Path, "glob", lambda self, pattern: iter([]))
    monkeypatch.setattr(toolchain.subprocess, "run", lambda *a, **k: _completed(stdout="musl libc (x86_64)"))
    assert toolchain._is_musl() is True
    monkeypatch.setattr(toolchain.subprocess, "run", lambda *a, **k: _completed(stdout="ldd (GNU libc) 2.39"))
    assert toolchain._is_musl() is False

    def missing(*a, **k):
        raise OSError("no ldd")

    monkeypatch.setattr(toolchain.subprocess, "run", missing)
    assert toolchain._is_musl() is False


# ── tlmgr ─────────────────────────────────────────────────────────────────


@unix_only
def test_installed_packages(tools):
    assert toolchain.installed_packages() is None  # no tlmgr at all
    _executable(tools / "tlmgr", "#!/bin/sh\nprintf 'pgf\\nlatex\\n\\n'\n")
    assert toolchain.installed_packages() == {"pgf", "latex"}
    _executable(tools / "tlmgr", "#!/bin/sh\nexit 3\n")
    assert toolchain.installed_packages() is None


@unix_only
def test_install_packages_streams_tlmgr_progress(tools):
    _executable(tools / "tlmgr", "#!/bin/sh\n"
                "echo 'tlmgr: package repository https://mirror (verified)'\n"
                "echo '[1/2, ??:??/??:??] install: pgf [3k]'\n"
                "echo '[2/2, 00:01/00:01] install: siunitx [1k]'\n")
    lines = []
    assert toolchain.install_packages(["siunitx", "pgf"], out=lines.append, stream=True) == ["pgf", "siunitx"]
    assert [line.strip() for line in lines] == [
        "[1/2, ??:??/??:??] install: pgf [3k]", "[2/2, 00:01/00:01] install: siunitx [1k]"]


@unix_only
def test_install_packages_warns_about_a_new_tex_live_year(tools):
    _executable(tools / "tlmgr", "#!/bin/sh\n"
                "echo 'tlmgr: Local TeX Live (2026) is older than remote repository (2027).' >&2\nexit 1\n")
    lines = []
    assert toolchain.install_packages(["pgf"], out=lines.append) == []
    assert any("--reinstall-tex" in line for line in lines)


def test_install_packages_without_tlmgr(monkeypatch):
    monkeypatch.setattr(toolchain, "command_exists", lambda name: False)
    assert toolchain.install_packages(["pgf"]) == []
    assert toolchain.install_packages([]) == []


def test_install_packages_reports_tlmgr_crash(monkeypatch):
    monkeypatch.setattr(toolchain, "command_exists", lambda name: True)

    def crash(*a, **k):
        raise OSError("exec format error")

    monkeypatch.setattr(toolchain, "_run", crash)
    lines = []
    assert toolchain.install_packages(["pgf"], out=lines.append) == []
    assert any("could not run" in line for line in lines)


def test_ensure_packages_without_tlmgr(monkeypatch):
    monkeypatch.setattr(toolchain, "installed_packages", lambda: None)
    assert toolchain.ensure_packages(["pgf"]) == []


def test_ensure_packages_nothing_missing(monkeypatch):
    monkeypatch.setattr(toolchain, "installed_packages", lambda: {"pgf"})
    monkeypatch.setattr(toolchain, "install_packages", lambda *a, **k: pytest.fail("nothing to install"))
    assert toolchain.ensure_packages(["pgf"]) == []


@unix_only
def test_repository_url(tools):
    assert toolchain._repository_url() == toolchain._DEFAULT_REPOSITORY  # no tlmgr
    _executable(tools / "tlmgr", "#!/bin/sh\n"
                "echo 'Default package repository (repository): https://example.org/tlnet/'\n")
    assert toolchain._repository_url() == "https://example.org/tlnet"
    _executable(tools / "tlmgr", "#!/bin/sh\necho 'Default package repository (repository): /local/tlnet'\n")
    assert toolchain._repository_url() == toolchain._DEFAULT_REPOSITORY


@unix_only
def test_refresh_user_bin_links(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("TINYTEX_DIR", raising=False)
    monkeypatch.setenv("LATEX_FORGE_TEX_DIRS", "")
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setattr(toolchain, "detect_os", lambda: "linux")
    bin_dir = home / ".TinyTeX" / "bin" / "x86_64-linux"
    tlmgr = _executable(bin_dir / "tlmgr", f"#!/bin/sh\necho \"$@\" >> '{tmp_path}/calls'\n")

    toolchain._refresh_user_bin_links()
    assert not (tmp_path / "calls").exists()  # PATH integration was never set up

    (home / ".local" / "bin").mkdir(parents=True)
    os.symlink(tlmgr, home / ".local" / "bin" / "tlmgr")
    toolchain._refresh_user_bin_links()
    assert (tmp_path / "calls").read_text().strip() == "path add"

    monkeypatch.setattr(toolchain, "detect_os", lambda: "windows")
    toolchain._refresh_user_bin_links()
    assert (tmp_path / "calls").read_text().count("path add") == 1


# ── Package index ─────────────────────────────────────────────────────────

_TLPDB = "name pgf\nrunfiles size=1\n texmf-dist/tex/latex/pgf/tikz.sty\n\nname siunitx\nrunfiles size=1\n texmf-dist/tex/latex/siunitx/siunitx.sty\n"


def _fake_repository(tmp_path: Path) -> str:
    repo = tmp_path / "repo"
    (repo / "tlpkg").mkdir(parents=True)
    (repo / "tlpkg" / "texlive.tlpdb.xz").write_bytes(lzma.compress(_TLPDB.encode()))
    return repo.as_uri()


def test_package_index_downloads_and_caches(tmp_path, monkeypatch, real_index):
    monkeypatch.setattr(toolchain, "_repository_url", lambda: _fake_repository(tmp_path))
    files, packages = toolchain.package_index()
    assert files["tikz.sty"] == ["pgf"]
    assert packages == {"pgf", "siunitx"}
    assert (tmp_path / "cache" / "texlive.tlpdb.xz").exists()
    # Memoised: no second download within the same process.
    monkeypatch.setattr(toolchain, "download", lambda *a, **k: pytest.fail("downloaded twice"))
    assert toolchain.package_index()[1] == packages


def test_package_index_uses_a_stale_cache_when_offline(tmp_path, monkeypatch, real_index):
    cache = tmp_path / "cache" / "texlive.tlpdb.xz"
    cache.parent.mkdir(parents=True)
    cache.write_bytes(lzma.compress(_TLPDB.encode()))
    os.utime(cache, (0, 0))  # very old
    monkeypatch.setattr(toolchain, "_repository_url", lambda: (tmp_path / "nowhere").as_uri())
    monkeypatch.setattr(toolchain.time, "sleep", lambda s: None)
    assert "pgf" in toolchain.package_index()[1]


def test_package_index_unavailable(tmp_path, monkeypatch, real_index):
    monkeypatch.setattr(toolchain, "_repository_url", lambda: (tmp_path / "nowhere").as_uri())
    monkeypatch.setattr(toolchain.time, "sleep", lambda s: None)
    assert toolchain.package_index() is None


def test_package_index_corrupt_cache(tmp_path, monkeypatch, real_index):
    cache = tmp_path / "cache" / "texlive.tlpdb.xz"
    cache.parent.mkdir(parents=True)
    cache.write_bytes(b"not xz")
    assert toolchain.package_index() is None


# ── Sources and compiling ─────────────────────────────────────────────────


@unix_only
def test_unresolved_files(tools):
    assert toolchain.unresolved_files(["tikz.sty"]) == []  # no kpsewhich: can't tell
    _executable(tools / "kpsewhich", "#!/bin/sh\n"
                "for f in \"$@\"; do [ \"$f\" = tikz.sty ] && echo /tex/latex/pgf/tikz.sty; done\n")
    assert toolchain.unresolved_files(["tikz.sty", "siunitx.sty"]) == ["siunitx.sty"]
    assert toolchain.unresolved_files([]) == []


_FAKE_LATEXMK = """#!/bin/sh
for arg in "$@"; do
  case "$arg" in -outdir=*) out="${arg#-outdir=}" ;; *.tex) main="${arg%.tex}" ;; esac
done
mkdir -p "$out"
echo "log of $main" > "$out/$main.log"
if [ -f fail ]; then exit 12; fi
echo pdf > "$out/$main.pdf"
"""


@unix_only
def test_compile_once(tools, tmp_path):
    _executable(tools / "latexmk", _FAKE_LATEXMK)
    project = tmp_path / "proj"
    project.mkdir()
    ok, log = toolchain.compile_once(project, "doc.tex", "pdflatex", tmp_path / "out")
    assert ok is True and log.strip() == "log of doc"
    (project / "fail").touch()
    ok, log = toolchain.compile_once(project, "doc.tex", "pdflatex", tmp_path / "out2")
    assert ok is False and log.strip() == "log of doc"


def test_compile_once_timeout(monkeypatch, tmp_path):
    def slow(*a, **k):
        raise subprocess.TimeoutExpired("latexmk", 1)

    monkeypatch.setattr(toolchain, "_run", slow)
    assert toolchain.compile_once(tmp_path, "doc.tex", "lualatex", tmp_path) == (False, "")


def test_compile_once_without_latexmk(monkeypatch, tmp_path):
    def missing(*a, **k):
        raise OSError("not found")

    monkeypatch.setattr(toolchain, "_run", missing)
    assert toolchain.compile_once(tmp_path, "doc.tex", "lualatex", tmp_path) == (False, "")


def test_ensure_project_packages_from_sources(tmp_path, monkeypatch):
    (tmp_path / "paper.tex").write_text("\\documentclass{article}\\usepackage{siunitx}", encoding="utf-8")
    monkeypatch.setattr(toolchain, "detect_distribution", lambda: {"kind": "tinytex", "can_install_packages": True})
    monkeypatch.setattr(toolchain, "unresolved_files", lambda names: ["siunitx.sty"])
    monkeypatch.setattr(toolchain, "package_for", lambda r, out=print: {"siunitx.sty": "siunitx"}.get(r[1]))
    ensured = []
    monkeypatch.setattr(toolchain, "ensure_packages", lambda pkgs, out=print: ensured.extend(pkgs) or list(pkgs))
    used = {}

    def fake_compile(project_dir, main_file, engine, outdir, timeout=600):
        used["main"] = main_file
        return True, ""

    monkeypatch.setattr(toolchain, "compile_once", fake_compile)
    assert toolchain.ensure_project_packages(tmp_path, None, "pdflatex", out=lambda m: None) is True
    assert ensured == ["siunitx"]
    assert used["main"] == "paper.tex"  # picked when no main file is given


def test_ensure_project_packages_gives_up_on_real_errors(tmp_path, monkeypatch):
    (tmp_path / "doc.tex").write_text("\\documentclass{article}", encoding="utf-8")
    monkeypatch.setattr(toolchain, "detect_distribution", lambda: {"kind": "texlive", "can_install_packages": True})
    monkeypatch.setattr(toolchain, "unresolved_files", lambda names: [])
    monkeypatch.setattr(toolchain, "missing_helpers", lambda d: [])
    monkeypatch.setattr(toolchain, "compile_once", lambda *a, **k: (False, "! Undefined control sequence."))
    assert toolchain.ensure_project_packages(tmp_path, "doc.tex") is True  # not a package problem
    monkeypatch.setattr(toolchain, "compile_once", lambda *a, **k: (False, "File `weird.sty' not found."))
    monkeypatch.setattr(toolchain, "package_for", lambda r, out=print: None)
    assert toolchain.ensure_project_packages(tmp_path, "doc.tex") is False  # missing, but unknown


def test_ensure_project_packages_no_tex_file(tmp_path, monkeypatch):
    monkeypatch.setattr(toolchain, "detect_distribution", lambda: {"kind": "tinytex", "can_install_packages": True})
    monkeypatch.setattr(toolchain, "unresolved_files", lambda names: [])
    assert toolchain.ensure_project_packages(tmp_path) is True


def test_read_tex_packages(tmp_path):
    toml = tmp_path / "latexforge.toml"
    assert toolchain.read_tex_packages(toml) is None
    toml.write_text('tex_packages = [\n  "pgf", # tikz\n  "siunitx",\n]\n', encoding="utf-8")
    assert toolchain.read_tex_packages(toml) == ["pgf", "siunitx"]
    toml.write_text("tex_packages = []\n", encoding="utf-8")
    assert toolchain.read_tex_packages(toml) is None


# ── Downloads ─────────────────────────────────────────────────────────────


def test_download_falls_back_to_curl_on_certificate_errors(tmp_path, monkeypatch):
    def tls_error(url, dest, out):
        raise RuntimeError("<urlopen error [SSL: CERTIFICATE_VERIFY_FAILED]>")

    monkeypatch.setattr(toolchain, "_download_urllib", tls_error)
    monkeypatch.setattr(toolchain.shutil, "which", lambda name, path=None: "/usr/bin/curl")
    calls = []
    monkeypatch.setattr(toolchain.subprocess, "run", lambda cmd, check=False: calls.append(cmd) or _completed())
    toolchain.download("https://example.org/x", tmp_path / "x", out=None)
    assert calls[0][0] == "curl"


def test_download_detects_truncated_transfers(tmp_path, monkeypatch):
    class Response(io.BytesIO):
        headers = {"Content-Length": "100"}

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(toolchain.urllib.request, "urlopen", lambda req, timeout: Response(b"only ten b"))
    monkeypatch.setattr(toolchain.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError, match="incomplete"):
        toolchain.download("https://example.org/x", tmp_path / "x", out=None, attempts=2)


def test_latest_tinytex_version(monkeypatch):
    class Response:
        def __init__(self, url):
            self.url = url

        def geturl(self):
            return self.url

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(toolchain.urllib.request, "urlopen",
                        lambda req, timeout: Response(toolchain.TINYTEX_RELEASES + "/tag/v2026.10"))
    assert toolchain.latest_tinytex_version() == "2026.10"
    monkeypatch.setattr(toolchain.urllib.request, "urlopen", lambda req, timeout: Response("https://github.com/login"))
    assert toolchain.latest_tinytex_version() is None

    def offline(req, timeout):
        raise OSError("offline")

    monkeypatch.setattr(toolchain.urllib.request, "urlopen", offline)
    assert toolchain.latest_tinytex_version() is None


def test_tinytex_urls_unsupported_platform(monkeypatch):
    monkeypatch.setattr(toolchain, "tinytex_platform", lambda: None)
    assert toolchain.tinytex_urls("light", "2026.10") == []


# ── Unpacking & installing TinyTeX ────────────────────────────────────────


def _tarball(tmp_path: Path, members: list[str]) -> Path:
    archive = tmp_path / "bundle.tar.xz"
    with tarfile.open(archive, "w:xz") as tar:
        for name in members:
            data = b"#!/bin/sh\n"
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o755
            tar.addfile(info, io.BytesIO(data))
    return archive


def test_extract_tar_xz(tmp_path):
    archive = _tarball(tmp_path, ["TinyTeX/bin/universal-darwin/tlmgr"])
    work = tmp_path / "work"
    work.mkdir()
    top = toolchain._extract(archive, work)
    assert top == work / "TinyTeX"
    assert (top / "bin" / "universal-darwin" / "tlmgr").exists()


def test_extract_rejects_unexpected_layouts(tmp_path):
    archive = _tarball(tmp_path, ["something-else/file"])
    work = tmp_path / "work"
    work.mkdir()
    with pytest.raises(RuntimeError, match="layout"):
        toolchain._extract(archive, work)


def test_extract_self_extracting_exe_failure(tmp_path, monkeypatch):
    exe = tmp_path / "TinyTeX-1-windows.exe"
    exe.write_bytes(b"MZ")
    monkeypatch.setattr(toolchain.subprocess, "run", lambda *a, **k: _completed(2, stderr="bad archive"))
    with pytest.raises(RuntimeError, match="bad archive"):
        toolchain._extract(exe, tmp_path)


@pytest.fixture()
def linux_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.delenv("TINYTEX_DIR", raising=False)
    monkeypatch.setenv("LATEX_FORGE_TEX_DIRS", "")
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setattr(toolchain, "detect_os", lambda: "linux")
    monkeypatch.setattr(toolchain, "tinytex_platform", lambda: ("linux-x86_64", "tar.xz"))
    monkeypatch.setattr(toolchain, "latest_tinytex_version", lambda: None)
    real_which = toolchain.shutil.which
    monkeypatch.setattr(toolchain.shutil, "which",
                        lambda name, path=None: "/usr/bin/perl" if name == "perl" else real_which(name, path=path))
    return tmp_path / "home"


def test_install_tinytex_download_failure(linux_home, monkeypatch):
    def fail(url, dest, out=print, attempts=3):
        raise RuntimeError("HTTP 503")

    monkeypatch.setattr(toolchain, "download", fail)
    lines = []
    assert toolchain.install_tinytex("light", out=lines.append) is False
    assert any("Could not download TinyTeX" in line and "503" in line for line in lines)
    assert not (linux_home / ".TinyTeX").exists()


def test_install_tinytex_bad_archive(linux_home, monkeypatch):
    monkeypatch.setattr(toolchain, "download", lambda url, dest, out=print, attempts=3: dest.write_bytes(b"garbage"))
    lines = []
    assert toolchain.install_tinytex("light", out=lines.append) is False
    assert any(line.startswith("[error]") for line in lines)


def test_install_tinytex_unsupported_platform(linux_home, monkeypatch):
    monkeypatch.setattr(toolchain, "tinytex_platform", lambda: None)
    lines = []
    assert toolchain.install_tinytex("light", out=lines.append) is False
    assert any("--tex system" in line for line in lines)


_FAKE_TLMGR = """#!/bin/sh
here="$(dirname "$0")"
echo "$@" >> "$here/tlmgr.log"
case "$1" in
  info) cat "$here/installed.txt" 2>/dev/null ;;
  install) shift; for p in "$@"; do echo "$p" >> "$here/installed.txt"; done ;;
esac
exit 0
"""


@unix_only
def test_install_tinytex_reinstall_keeps_packages(linux_home, tmp_path, monkeypatch):
    old_bin = linux_home / ".TinyTeX" / "bin" / "x86_64-linux"
    (linux_home / ".TinyTeX" / "tlpkg").mkdir(parents=True)
    _executable(old_bin / "tlmgr", _FAKE_TLMGR)
    (old_bin / "installed.txt").write_text("pgf\nmy-special-package\n")

    staging = tmp_path / "staging" / ".TinyTeX"
    _executable(staging / "bin" / "x86_64-linux" / "tlmgr", _FAKE_TLMGR)
    for tool in ("lualatex", "latexmk"):
        _executable(staging / "bin" / "x86_64-linux" / tool, "#!/bin/sh\n")
    (staging / "tlpkg").mkdir()
    archive = tmp_path / "new.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(staging, arcname=".TinyTeX")
    monkeypatch.setattr(toolchain, "download",
                        lambda url, dest, out=print, attempts=3: dest.write_bytes(archive.read_bytes()))

    assert toolchain.install_tinytex("light", out=lambda m: None, modify_path=False, reinstall=True) is True
    installed = (linux_home / ".TinyTeX" / "bin" / "x86_64-linux" / "installed.txt").read_text().split()
    assert "my-special-package" in installed  # carried over from the old install
    assert not (linux_home / ".TinyTeX.old").exists()


def test_install_tinytex_upgrades_existing_to_full(linux_home, monkeypatch):
    bin_dir = linux_home / ".TinyTeX" / "bin" / "x86_64-linux"
    bin_dir.mkdir(parents=True)
    (bin_dir / "tlmgr").touch()
    calls = []
    monkeypatch.setattr(toolchain, "install_packages", lambda pkgs, out=print, stream=False: calls.append(list(pkgs)))
    monkeypatch.setattr(toolchain, "_post_install", lambda *a, **k: None)
    monkeypatch.setattr(toolchain, "ensure_packages", lambda *a, **k: [])
    monkeypatch.setattr(toolchain, "tex_ready", lambda: True)
    assert toolchain.install_tinytex("full", out=lambda m: None) is True
    assert calls == [["scheme-full"]]


@unix_only
def test_post_install_without_path_changes(linux_home, tmp_path):
    bin_dir = tmp_path / "TinyTeX" / "bin" / "x86_64-linux"
    _executable(bin_dir / "tlmgr", _FAKE_TLMGR)
    toolchain._post_install(bin_dir, out=lambda m: None, modify_path=False)
    calls = (bin_dir / "tlmgr.log").read_text()
    assert "option sys_bin" in calls and "postaction install script xetex" in calls
    assert "path add" not in calls


@unix_only
def test_uninstall_tinytex(linux_home, tmp_path):
    lines = []
    assert toolchain.uninstall_tinytex(out=lines.append) is True
    assert "No TinyTeX" in lines[0]
    bin_dir = linux_home / ".TinyTeX" / "bin" / "x86_64-linux"
    log = tmp_path / "uninstall.log"
    _executable(bin_dir / "tlmgr", f"#!/bin/sh\necho \"$@\" >> '{log}'\n")
    assert toolchain.uninstall_tinytex(out=lambda m: None) is True
    assert log.read_text().strip() == "path remove"
    assert not (linux_home / ".TinyTeX").exists()


# ── System package managers ───────────────────────────────────────────────


def test_privilege_prefix(monkeypatch):
    monkeypatch.setattr(toolchain.os, "geteuid", lambda: 0, raising=False)
    assert toolchain.privilege_prefix() == []
    monkeypatch.setattr(toolchain.os, "geteuid", lambda: 1000, raising=False)
    monkeypatch.setattr(toolchain.shutil, "which", lambda name, path=None: "/usr/bin/sudo")
    assert toolchain.privilege_prefix() == ["sudo"]
    monkeypatch.setattr(toolchain.shutil, "which", lambda name, path=None: None)
    assert toolchain.privilege_prefix() == []


def test_can_elevate(monkeypatch):
    monkeypatch.setattr(toolchain, "privilege_prefix", lambda: [])
    assert toolchain._can_elevate() is True
    monkeypatch.setattr(toolchain, "privilege_prefix", lambda: ["sudo"])
    monkeypatch.setattr(toolchain, "is_interactive", lambda: True)
    assert toolchain._can_elevate() is True
    monkeypatch.setattr(toolchain, "is_interactive", lambda: False)
    monkeypatch.setattr(toolchain.subprocess, "run", lambda *a, **k: _completed(1))
    assert toolchain._can_elevate() is False
    monkeypatch.setattr(toolchain.subprocess, "run", lambda *a, **k: _completed(0))
    assert toolchain._can_elevate() is True  # passwordless sudo


def test_miktex_bin_dir(tmp_path, monkeypatch):
    for var in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"):
        monkeypatch.delenv(var, raising=False)
    assert toolchain._miktex_bin_dir() is None
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    bin_dir = tmp_path / "Programs" / "MiKTeX" / "miktex" / "bin" / "x64"
    bin_dir.mkdir(parents=True)
    (bin_dir / "mpm.exe").touch()
    assert toolchain._miktex_bin_dir() == bin_dir


def test_ensure_miktex_latexmk_installs_perl(monkeypatch):
    monkeypatch.setattr(toolchain, "_miktex_bin_dir", lambda: None)
    monkeypatch.setattr(toolchain.shutil, "which", lambda name, path=None: None)
    commands = []
    monkeypatch.setattr(toolchain.subprocess, "run", lambda cmd, **k: commands.append(cmd) or _completed())
    toolchain._ensure_miktex_latexmk(out=lambda m: None)
    assert ["mpm", "--install=latexmk"] in commands
    assert any("StrawberryPerl.StrawberryPerl" in c for c in commands)


def test_ensure_miktex_latexmk_reports_missing_tools(monkeypatch):
    monkeypatch.setattr(toolchain, "_miktex_bin_dir", lambda: None)

    def missing(cmd, **k):
        raise OSError("not found")

    monkeypatch.setattr(toolchain.subprocess, "run", missing)
    lines = []
    toolchain._ensure_miktex_latexmk(out=lines.append)
    assert any("MiKTeX Console" in line for line in lines)


@pytest.fixture()
def run_log(monkeypatch):
    commands = []
    monkeypatch.setattr(toolchain.subprocess, "run", lambda cmd, check=False, **k: commands.append(cmd) or _completed())
    monkeypatch.setattr(toolchain, "is_interactive", lambda: True)
    return commands


def _only(*available):
    return lambda name, path=None: f"/usr/bin/{name}" if name in available else None


def test_system_install_windows(monkeypatch, run_log):
    monkeypatch.setattr(toolchain, "detect_os", lambda: "windows")
    monkeypatch.setattr(toolchain.shutil, "which", _only("winget"))
    called = []
    monkeypatch.setattr(toolchain, "_ensure_miktex_latexmk", lambda out=print: called.append(True))
    assert toolchain.install_system_distribution(out=lambda m: None) is True
    assert "MiKTeX.MiKTeX" in run_log[0]
    assert called == [True]


@pytest.mark.parametrize("os_name", ["macos", "windows", "linux"])
def test_system_install_without_package_manager(monkeypatch, run_log, os_name):
    monkeypatch.setattr(toolchain, "detect_os", lambda: os_name)
    monkeypatch.setattr(toolchain.shutil, "which", _only())
    lines = []
    assert toolchain.install_system_distribution(out=lines.append) is False
    assert any("--tex light" in line for line in lines)
    assert run_log == []


@pytest.mark.parametrize("manager,expected", [
    ("apt-get", ["sudo", "apt-get", "install", "-y", "texlive-full", "latexmk", "biber"]),
    ("dnf", ["sudo", "dnf", "install", "-y", "texlive-scheme-full", "latexmk", "biber"]),
])
def test_system_install_linux(monkeypatch, run_log, manager, expected):
    monkeypatch.setattr(toolchain, "detect_os", lambda: "linux")
    monkeypatch.setattr(toolchain, "privilege_prefix", lambda: ["sudo"])
    monkeypatch.setattr(toolchain.shutil, "which", _only(manager, "sudo"))
    assert toolchain.install_system_distribution(out=lambda m: None) is True
    assert run_log[-1] == expected


def test_system_install_macos(monkeypatch, run_log):
    monkeypatch.setattr(toolchain, "detect_os", lambda: "macos")
    monkeypatch.setattr(toolchain.shutil, "which", _only("brew"))
    assert toolchain.install_system_distribution(out=lambda m: None) is True
    assert run_log == [["brew", "install", "--cask", "mactex-no-gui"]]


def test_system_install_failure_and_unknown_os(monkeypatch):
    monkeypatch.setattr(toolchain, "is_interactive", lambda: True)
    monkeypatch.setattr(toolchain, "detect_os", lambda: "macos")
    monkeypatch.setattr(toolchain.shutil, "which", _only("brew"))
    monkeypatch.setattr(toolchain.subprocess, "run", lambda cmd, check=False: _completed(1))
    assert toolchain.install_system_distribution(out=lambda m: None) is False
    monkeypatch.setattr(toolchain, "detect_os", lambda: "haiku")
    assert toolchain.install_system_distribution(out=lambda m: None) is False


@pytest.mark.parametrize("os_name,manager,expected", [
    ("macos", "brew", ["brew", "install", "gh"]),
    ("windows", "winget", ["winget", "install", "-e", "--id", "GitHub.cli",
                           "--accept-source-agreements", "--accept-package-agreements"]),
    ("linux", "apt-get", ["apt-get", "install", "-y", "gh"]),
    ("linux", "dnf", ["dnf", "install", "-y", "gh"]),
    ("linux", "pacman", ["pacman", "-S", "--needed", "--noconfirm", "github-cli"]),
])
def test_install_gh_cli(monkeypatch, run_log, os_name, manager, expected):
    monkeypatch.setattr(toolchain, "detect_os", lambda: os_name)
    monkeypatch.setattr(toolchain, "privilege_prefix", lambda: [])
    monkeypatch.setattr(toolchain.shutil, "which", _only(manager))
    assert toolchain.install_gh_cli(out=lambda m: None) is True
    assert run_log == [expected]


@pytest.mark.parametrize("os_name", ["macos", "windows", "linux", "haiku"])
def test_install_gh_cli_unavailable(monkeypatch, run_log, os_name):
    monkeypatch.setattr(toolchain, "detect_os", lambda: os_name)
    monkeypatch.setattr(toolchain, "privilege_prefix", lambda: [])
    monkeypatch.setattr(toolchain.shutil, "which", _only())
    assert toolchain.install_gh_cli(out=lambda m: None) is False
    assert run_log == []


def test_install_gh_cli_needs_a_password_prompt(monkeypatch):
    monkeypatch.setattr(toolchain, "detect_os", lambda: "linux")
    monkeypatch.setattr(toolchain, "privilege_prefix", lambda: ["sudo"])
    monkeypatch.setattr(toolchain, "_can_elevate", lambda: False)
    lines = []
    assert toolchain.install_gh_cli(out=lines.append) is False
    assert any("--install-gh" in line for line in lines)


def test_install_gh_cli_failure(monkeypatch):
    monkeypatch.setattr(toolchain, "detect_os", lambda: "macos")
    monkeypatch.setattr(toolchain.shutil, "which", _only("brew"))
    monkeypatch.setattr(toolchain.subprocess, "run", lambda cmd, check=False: _completed(1))
    assert toolchain.install_gh_cli(out=lambda m: None) is False


# ── VS Code extensions ────────────────────────────────────────────────────


def test_vscode_cli_on_macos(monkeypatch, tmp_path):
    monkeypatch.setattr(toolchain.shutil, "which", lambda name, path=None: None)
    monkeypatch.setattr(toolchain, "detect_os", lambda: "macos")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    assert toolchain.vscode_cli() is None or toolchain.vscode_cli().endswith("/bin/code")
    code = tmp_path / "Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"
    code.parent.mkdir(parents=True)
    code.touch()
    if not Path("/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code").exists():
        assert toolchain.vscode_cli() == str(code)


@unix_only
def test_install_vscode_extensions(monkeypatch, tmp_path):
    code = _executable(tmp_path / "code", "#!/bin/sh\n[ \"$2\" = bad.ext ] && { echo nope >&2; exit 1; }\nexit 0\n")
    monkeypatch.setattr(toolchain, "vscode_cli", lambda: str(code))
    lines = []
    assert toolchain.install_vscode_extensions(["good.ext"], out=lines.append) is True
    assert toolchain.install_vscode_extensions(["good.ext", "bad.ext"], out=lines.append) is False
    assert any("Could not install extension bad.ext" in line for line in lines)
    monkeypatch.setattr(toolchain, "vscode_cli", lambda: None)
    assert toolchain.install_vscode_extensions(["good.ext"], out=lambda m: None) is False


def test_read_extension_recommendations(tmp_path):
    assert toolchain.read_extension_recommendations(tmp_path / "missing.json") == []
    path = tmp_path / "extensions.json"
    path.write_text('{"recommendations": ["a.b", "c.d"]}', encoding="utf-8")
    assert toolchain.read_extension_recommendations(path) == ["a.b", "c.d"]


# ── Status, prompts & dispatch ────────────────────────────────────────────


def test_verify_toolchain_without_latexmk(monkeypatch):
    monkeypatch.setattr(toolchain, "command_exists", lambda name: False)
    lines = []
    assert toolchain.verify_toolchain(out=lines.append) is False
    assert any("latexmk not found" in line for line in lines)


def test_print_tool_status(monkeypatch):
    monkeypatch.setattr(toolchain, "command_exists", lambda name: name != "biber")
    monkeypatch.setattr(toolchain, "detect_distribution", lambda: {"kind": "tinytex", "label": "TinyTeX", "bin_dir": "/x"})
    lines = []
    assert toolchain.print_tool_status(out=lines.append) == (True, False)
    assert "- biber: missing" in lines
    assert "Distribution: TinyTeX (/x)" in lines


@pytest.mark.parametrize("answers,expected", [
    ([""], "light"), (["1"], "light"), (["2"], "full"), (["3"], "system"),
    (["maybe", "n"], None), (["q"], None),
])
def test_ask_tex_choice(monkeypatch, capsys, answers, expected):
    monkeypatch.setattr(toolchain, "is_interactive", lambda: True)
    replies = iter(answers)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(replies))
    assert toolchain.ask_tex_choice() == expected


def test_ask_tex_choice_eof_and_non_interactive(monkeypatch):
    monkeypatch.setattr(toolchain, "is_interactive", lambda: False)
    assert toolchain.ask_tex_choice() is None
    monkeypatch.setattr(toolchain, "is_interactive", lambda: True)

    def eof(prompt=""):
        raise EOFError

    monkeypatch.setattr("builtins.input", eof)
    assert toolchain.ask_tex_choice() is None


def test_install_tex_dispatch(monkeypatch):
    monkeypatch.setattr(toolchain, "install_system_distribution", lambda out=print: "system")
    seen = {}

    def fake_tinytex(kind, out=print, modify_path=True, extra_packages=None, reinstall=False):
        seen.update(kind=kind, modify_path=modify_path, extra=extra_packages, reinstall=reinstall)
        return "tinytex"

    monkeypatch.setattr(toolchain, "install_tinytex", fake_tinytex)
    assert toolchain.install_tex("system") == "system"
    assert toolchain.install_tex("full", modify_path=False, extra_packages=["pgf"], reinstall=True) == "tinytex"
    assert seen == {"kind": "full", "modify_path": False, "extra": ["pgf"], "reinstall": True}


@pytest.mark.parametrize("os_name,needle", [
    ("macos", "mactex"), ("windows", "Strawberry Perl"), ("linux", "quickinstall"), ("haiku", "--install-tex"),
])
def test_print_os_specific_help(monkeypatch, os_name, needle):
    monkeypatch.setattr(toolchain, "detect_os", lambda: os_name)
    lines = []
    toolchain.print_os_specific_help(out=lines.append)
    assert any(needle in line for line in lines)


# ── scripts/setup.py entry point ──────────────────────────────────────────


@pytest.fixture()
def project(tmp_path):
    proj = tmp_path / "thesis"
    (proj / ".vscode").mkdir(parents=True)
    (proj / "thesis.tex").write_text("\\documentclass{article}", encoding="utf-8")
    (proj / ".vscode" / "settings.json").write_text(
        '{"latex-workshop.latex.tools": [{"args": ["-synctex=1", "-xelatex", "%DOC%"]}]}', encoding="utf-8")
    (proj / ".vscode" / "extensions.json").write_text('{"recommendations": ["James-Yu.latex-workshop"]}',
                                                     encoding="utf-8")
    (proj / "latexforge.toml").write_text('engine = "xelatex"\ntex_packages = ["fontspec"]\n', encoding="utf-8")
    return proj


def test_project_setup_rejects_conflicting_flags(project, capsys):
    assert toolchain.run_project_setup(project, ["--check-only", "--install-tex"]) == 2


def test_project_setup_check_only(project, monkeypatch):
    monkeypatch.setattr(toolchain, "print_tool_status", lambda out=print: (False, False))
    monkeypatch.setattr(toolchain, "install_tex", lambda *a, **k: pytest.fail("check only"))
    assert toolchain.run_project_setup(project, ["--check-only"]) == 1


def test_project_setup_installs_tex_and_project_packages(project, monkeypatch):
    status = iter([(False, False), (True, True)])
    monkeypatch.setattr(toolchain, "print_tool_status", lambda out=print: next(status))
    installed = {}
    monkeypatch.setattr(toolchain, "install_tex", lambda kind, out=print, modify_path=True, **k:
                        installed.update(kind=kind, modify_path=modify_path) or True)
    ensured = {}

    def fake_ensure(project_dir, main_file=None, engine="lualatex", declared=None, out=print, max_rounds=12):
        ensured.update(main=main_file, engine=engine, declared=declared)
        return True

    monkeypatch.setattr(toolchain, "ensure_project_packages", fake_ensure)
    extensions = []
    monkeypatch.setattr(toolchain, "install_vscode_extensions", lambda ids, out=print: extensions.extend(ids) or True)
    assert toolchain.run_project_setup(project, ["--yes", "--no-modify-path"]) == 0
    assert installed == {"kind": "light", "modify_path": False}
    assert ensured == {"main": "thesis.tex", "engine": "xelatex", "declared": ["fontspec"]}
    assert extensions == ["James-Yu.latex-workshop"]


def test_project_setup_reports_incomplete_environment(project, monkeypatch, capsys):
    monkeypatch.setattr(toolchain, "print_tool_status", lambda out=print: (False, False))
    monkeypatch.setattr(toolchain, "ask_tex_choice", lambda: None)
    monkeypatch.setattr(toolchain, "install_vscode_extensions", lambda ids, out=print: False)
    assert toolchain.run_project_setup(project, []) == 1
    out = capsys.readouterr().out
    assert "not yet complete" in out and "VS Code extensions" in out
