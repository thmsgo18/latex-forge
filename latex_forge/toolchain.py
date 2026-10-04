"""LaTeX toolchain management: find, install and drive a TeX distribution.

Everything latex-forge needs to know about the machine's LaTeX setup lives
here: locating a TeX distribution even when it isn't on PATH yet (fresh
installs, editors started from the Dock), installing one without admin rights
(TinyTeX, a portable TeX Live, in the user's home), installing the LaTeX
packages a document needs on the fly, and checking the result with a real
test compile.

This module is deliberately standalone — standard library only, no imports
from the rest of the ``latex_forge`` package, Python 3.8 compatible — because
a copy of it ships inside every generated project as ``scripts/toolchain.py``:
the project's own ``scripts/setup.py`` uses it to set LaTeX up on a machine
where latex-forge itself isn't installed (e.g. after cloning the project).
"""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path


# ── Platform ───────────────────────────────────────────────────────────────


def detect_os() -> str:
    """Return a short OS identifier: "macos", "windows", "linux", or the raw platform name."""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    if system == "linux":
        return "linux"
    return system


def _say(out, message: str = "") -> None:
    """Print through *out* (a ``print``-like callable), flushing for live progress."""
    if out is print:
        print(message, flush=True)
    else:
        out(message)


def step(title: str, out=print) -> None:
    """Announce a setup step. The VS Code extension turns these lines into progress."""
    _say(out, f"==> {title}")


def is_interactive() -> bool:
    """True when stdin is a terminal, i.e. the user can answer prompts."""
    try:
        return sys.stdin.isatty()
    except Exception:
        return False


# ── Where TeX lives ────────────────────────────────────────────────────────
#
# TinyTeX's own installers use these exact locations (and honour the same
# TINYTEX_DIR variable), so a TinyTeX installed by R/Quarto is reused as-is.


def tinytex_parent_dir() -> Path:
    """Directory that contains the TinyTeX folder (``TINYTEX_DIR`` overrides it)."""
    override = os.environ.get("TINYTEX_DIR")
    if override:
        return Path(override).expanduser()
    current = detect_os()
    if current == "macos":
        return Path.home() / "Library"
    if current == "windows":
        appdata = os.environ.get("APPDATA", "")
        # TeX Live can't live under a path with spaces or non-ASCII characters.
        if appdata and re.fullmatch(r"[!-~]+", appdata):
            return Path(appdata)
        return Path(os.environ.get("ProgramData", r"C:\ProgramData"))
    return Path.home()


def tinytex_root() -> Path:
    """Root of the (possibly not yet installed) TinyTeX distribution."""
    name = "TinyTeX" if detect_os() in ("macos", "windows") else ".TinyTeX"
    return tinytex_parent_dir() / name


def tinytex_bin_dir(root: Path | None = None) -> Path | None:
    """The ``bin/<platform>`` directory of an installed TinyTeX, or None."""
    root = root or tinytex_root()
    bin_root = root / "bin"
    if not bin_root.is_dir():
        return None
    for candidate in sorted(bin_root.iterdir()):
        if (candidate / "tlmgr").exists() or (candidate / "tlmgr.bat").exists():
            return candidate
    return None


def user_bin_dir() -> Path:
    """Per-user executable directory (also where uv and pipx put latex-forge)."""
    return Path.home() / ".local" / "bin"


def _well_known_tex_dirs() -> list[Path]:
    """Install locations of the usual distributions, newest first."""
    current = detect_os()
    dirs: list[Path] = []
    if current == "macos":
        dirs.append(Path("/Library/TeX/texbin"))  # MacTeX / BasicTeX
    if current in ("macos", "linux"):
        for year_dir in sorted(Path("/usr/local/texlive").glob("[0-9][0-9][0-9][0-9]"), reverse=True):
            dirs.extend(sorted((year_dir / "bin").glob("*")))
    if current == "windows":
        for year_dir in sorted(Path("C:/texlive").glob("[0-9][0-9][0-9][0-9]"), reverse=True):
            dirs.extend(sorted((year_dir / "bin").glob("*")))
        for env_var in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"):
            base = os.environ.get(env_var)
            if base:
                dirs.append(Path(base) / "Programs" / "MiKTeX" / "miktex" / "bin" / "x64")
                dirs.append(Path(base) / "MiKTeX" / "miktex" / "bin" / "x64")
        # MiKTeX's latexmk is a Perl script: Strawberry Perl must be reachable.
        dirs.append(Path("C:/Strawberry/perl/bin"))
    return dirs


def extra_tex_dirs() -> list[Path]:
    """Directories searched for TeX tools on top of PATH.

    The managed TinyTeX comes first, then the well-known install locations
    (``LATEX_FORGE_TEX_DIRS``, an os.pathsep-separated list, replaces those).
    This is what lets a distribution installed a minute ago — or one missing
    from the PATH of an editor launched from the Dock — work without a restart.
    """
    dirs: list[Path] = []
    managed = tinytex_bin_dir()
    if managed:
        dirs.append(managed)
    override = os.environ.get("LATEX_FORGE_TEX_DIRS")
    if override is not None:
        dirs.extend(Path(p) for p in override.split(os.pathsep) if p)
    else:
        dirs.extend(_well_known_tex_dirs())
    return [d for d in dirs if d.is_dir()]


def search_path() -> str:
    """PATH, followed by every extra TeX directory it doesn't already contain."""
    entries = [e for e in os.environ.get("PATH", "").split(os.pathsep) if e]
    seen = {os.path.normcase(os.path.normpath(e)) for e in entries}
    for directory in extra_tex_dirs():
        key = os.path.normcase(os.path.normpath(str(directory)))
        if key not in seen:
            entries.append(str(directory))
            seen.add(key)
    return os.pathsep.join(entries)


def which(name: str) -> str | None:
    """Like ``shutil.which``, but also looking in the extra TeX directories.

    Returns a full path, which matters on Windows: ``tlmgr`` and ``code`` are
    ``.bat``/``.cmd`` files that subprocess can only launch by full name.
    """
    return shutil.which(name, path=search_path())


def tex_env() -> dict:
    """``os.environ`` with PATH extended by :func:`search_path`, for subprocesses."""
    env = dict(os.environ)
    env["PATH"] = search_path()
    return env


def command_exists(name: str) -> bool:
    """Return True if *name* resolves to an executable (PATH + TeX directories)."""
    return which(name) is not None


def _run(args: list[str], capture: bool = True, timeout: float | None = None,
         cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a tool resolved through :func:`which`, with the TeX-aware environment."""
    resolved = which(args[0]) or args[0]
    return subprocess.run(
        [resolved, *args[1:]],
        capture_output=capture,
        text=True,
        check=False,
        timeout=timeout,
        cwd=str(cwd) if cwd else None,
        env=tex_env(),
        errors="replace",
    )


# ── What is installed ──────────────────────────────────────────────────────


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def detect_distribution() -> dict:
    """Describe the TeX distribution latex-forge would use.

    Keys: ``kind`` (tinytex, texlive, miktex, distro, unknown or none),
    ``label`` (human-readable), ``bin_dir``, ``root`` (TEXMFROOT for TeX Live
    based installs), ``tlmgr`` (full path or None), ``managed`` (the TinyTeX
    latex-forge installs) and ``can_install_packages`` (tlmgr can install
    packages without admin rights, or MiKTeX installs them on the fly).
    """
    # Engines first: in TeX Live, latexmk and tlmgr are symlinks into
    # texmf-dist/scripts, which would hide the bin directory once resolved.
    found = None
    for tool in ("lualatex", "pdflatex", "xelatex", "latexmk", "tlmgr"):
        found = which(tool)
        if found:
            break
    if not found:
        return {
            "kind": "none", "label": "none", "bin_dir": None, "root": None,
            "tlmgr": None, "managed": False, "can_install_packages": False,
        }

    real_bin = Path(os.path.realpath(found)).parent
    tlmgr = which("tlmgr")
    root: Path | None = None
    lowered = str(real_bin).lower()

    tinytex = tinytex_root()
    if tinytex.exists() and _is_within(real_bin, Path(os.path.realpath(tinytex))):
        kind, label = "tinytex", "TinyTeX"
        root = Path(os.path.realpath(tinytex))
    elif "miktex" in lowered:
        kind, label = "miktex", "MiKTeX"
    elif real_bin.parent.name == "bin" and (real_bin.parent.parent / "tlpkg").is_dir():
        kind = "texlive"
        root = real_bin.parent.parent
        label = f"TeX Live {root.name}" if re.fullmatch(r"\d{4}", root.name) else "TeX Live"
        if detect_os() == "macos" and "/usr/local/texlive" in str(root):
            label = f"MacTeX ({label})"
    elif lowered.startswith(("/usr/bin", "/bin", "/usr/local/bin", "/opt/homebrew/bin")):
        kind, label = "distro", "TeX Live (system packages)"
    else:
        kind, label = "unknown", "unknown distribution"

    if kind in ("tinytex", "texlive"):
        can_install = bool(tlmgr) and root is not None and os.access(root / "tlpkg", os.W_OK)
    elif kind == "miktex":
        can_install = True  # MiKTeX installs missing packages on the fly
    else:
        can_install = False

    return {
        "kind": kind,
        "label": label,
        "bin_dir": str(real_bin),
        "root": str(root) if root else None,
        "tlmgr": tlmgr,
        "managed": kind == "tinytex",
        "can_install_packages": can_install,
    }


def tex_ready() -> bool:
    """True when the minimal toolchain (latexmk + LuaLaTeX) is reachable."""
    return all(command_exists(tool) for tool in ("latexmk", "lualatex"))


# ── tlmgr ──────────────────────────────────────────────────────────────────


def installed_packages() -> set | None:
    """Names of the installed TeX Live packages, or None if tlmgr is unusable."""
    if not command_exists("tlmgr"):
        return None
    try:
        result = _run(["tlmgr", "info", "--list", "--only-installed", "--data", "name"], timeout=120)
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


_CROSS_RELEASE = re.compile(r"older than remote repository|Local TeX Live \(\d+\) is older", re.IGNORECASE)


def install_packages(packages, out=print, stream: bool = False) -> list:
    """Install TeX Live *packages* with tlmgr; return the names that got installed.

    Tries one batched ``tlmgr install`` first (fast), then falls back to one
    package at a time so a single unknown name doesn't block the others.
    With *stream*, tlmgr's own progress lines are shown as they arrive.
    """
    wanted = sorted({p for p in packages if p})
    if not wanted or not command_exists("tlmgr"):
        return []

    unknown: list = []

    def attempt(names: list) -> bool:
        try:
            if stream:
                proc = subprocess.Popen(
                    [which("tlmgr") or "tlmgr", "install", *names],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, errors="replace", env=tex_env(),
                )
                assert proc.stdout is not None
                output = []
                for line in proc.stdout:
                    output.append(line)
                    if line.lstrip().startswith("[") or "install:" in line:
                        _say(out, "    " + line.rstrip())
                proc.wait()
                text, code = "".join(output), proc.returncode
            else:
                result = _run(["tlmgr", "install", *names], timeout=1800)
                text, code = result.stdout + result.stderr, result.returncode
        except (OSError, subprocess.SubprocessError) as exc:
            _say(out, f"[warn] tlmgr could not run: {exc}")
            return False
        if code != 0 and _CROSS_RELEASE.search(text):
            _say(out, "[warn] Your TeX Live is older than the package repository (a new TeX Live")
            _say(out, "       year was released). Run `latex-forge setup --reinstall-tex` to upgrade it.")
        unknown.extend(_NOT_IN_REPOSITORY.findall(text))
        return code == 0

    def done(names: list) -> list:
        _refresh_user_bin_links()
        return names

    if attempt(wanted):
        return done(wanted)
    # A package renamed or retired upstream makes the whole batch fail: retry
    # the batch without it before falling back to one call per package.
    known = [name for name in wanted if name not in unknown]
    if unknown and known and attempt(known):
        return done(known)
    if len(known) <= 1:
        return []
    installed = [name for name in known if attempt([name])]
    return done(installed) if installed else []


_NOT_IN_REPOSITORY = re.compile(r"package (\S+) not present in repository")


def _refresh_user_bin_links() -> None:
    """Symlink newly installed TinyTeX programs (biber...) into ~/.local/bin.

    ``tlmgr path add`` only links what exists when it runs, so it's re-run
    after installs — only for the managed TinyTeX, and only once it was set up
    to link into ~/.local/bin.
    """
    if detect_os() == "windows":
        return
    tlmgr = which("tlmgr")
    if not tinytex_bin_dir() or not tlmgr:
        return
    if not _is_within(Path(os.path.realpath(tlmgr)), Path(os.path.realpath(tinytex_root()))):
        return
    if not (user_bin_dir() / "tlmgr").exists():
        return  # the user opted out of PATH integration (--no-modify-path)
    subprocess.run([tlmgr, "path", "add"], capture_output=True, check=False, env=tex_env())


def ensure_packages(packages, out=print, stream: bool = False) -> list:
    """Install whichever of *packages* aren't installed yet; return those installed.

    Names the repository no longer knows (packages get merged or renamed
    between TeX Live years) are skipped rather than failing the batch.
    """
    current = installed_packages()
    if current is None:
        return []
    missing = sorted(set(packages) - current)
    if not missing:
        return []
    index = package_index(out=out)
    if index:
        missing = [name for name in missing if name in index[1]]
    return install_packages(missing, out=out, stream=stream)


# ── Which package provides a file ──────────────────────────────────────────
#
# Mapping "tikz.sty" → "pgf" is what makes on-the-fly installs work. Asking
# `tlmgr search --global --file` costs a few seconds per file, so we download
# the repository's package database once (≈3 MB, cached for a week) and look
# files up locally; tlmgr search remains the fallback.

_DEFAULT_REPOSITORY = "https://mirror.ctan.org/systems/texlive/tlnet"
_INDEX_MAX_AGE = 7 * 24 * 3600


def cache_dir() -> Path:
    """Per-user cache directory for latex-forge."""
    current = detect_os()
    if current == "macos":
        return Path.home() / "Library" / "Caches" / "latex-forge"
    if current == "windows":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "latex-forge" / "Cache"
    return Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "latex-forge"


def _repository_url() -> str:
    """The http(s) package repository tlmgr is configured with (CTAN mirror by default)."""
    try:
        result = _run(["tlmgr", "option", "repository"], timeout=60)
        match = re.search(r"(https?://\S+)", result.stdout)
        if match:
            return match.group(1).rstrip("/")
    except (OSError, subprocess.SubprocessError):
        pass
    return _DEFAULT_REPOSITORY


def parse_tlpdb(text: str) -> tuple:
    """Parse a texlive.tlpdb into (files, packages).

    *files* maps a runfile's base name to the packages shipping it;
    *packages* is the set of package names. Architecture-specific binary
    packages (``luatex.x86_64-linux``) are skipped — tlmgr picks those itself.
    """
    files: dict = {}
    packages: set = set()
    package = None
    in_runfiles = False
    for line in text.splitlines():
        if line.startswith("name "):
            name = line[5:].strip()
            package = None if "." in name else name
            if package:
                packages.add(package)
            in_runfiles = False
        elif line.startswith("runfiles"):
            in_runfiles = True
        elif line.startswith(" ") and in_runfiles and package:
            path = line.strip().split(" ", 1)[0]
            base = path.rsplit("/", 1)[-1]
            files.setdefault(base, [])
            if package not in files[base]:
                files[base].append(package)
        elif line and not line.startswith(" "):
            in_runfiles = False
    return files, packages


_index_memo: dict = {}


def package_index(out=print) -> tuple | None:
    """The (files, packages) index of the remote repository, or None if unavailable."""
    if "index" in _index_memo:
        return _index_memo["index"]
    try:
        import lzma
    except ImportError:  # Python built without xz support
        _index_memo["index"] = None
        return None

    target = cache_dir() / "texlive.tlpdb.xz"
    fresh = target.exists() and time.time() - target.stat().st_mtime < _INDEX_MAX_AGE
    if not fresh:
        url = _repository_url() + "/tlpkg/texlive.tlpdb.xz"
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            download(url, target, out=None)
        except Exception:
            if not target.exists():
                _index_memo["index"] = None
                return None
    try:
        text = lzma.decompress(target.read_bytes()).decode("utf-8", errors="replace")
    except (OSError, lzma.LZMAError):
        _index_memo["index"] = None
        return None
    _index_memo["index"] = parse_tlpdb(text)
    return _index_memo["index"]


def _tlmgr_search_file(filename: str) -> str | None:
    """Ask tlmgr which package ships *filename* (slow fallback)."""
    try:
        result = _run(["tlmgr", "search", "--global", "--file", f"/{filename}"], timeout=300)
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    package = None
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip("\t "))
        if indent == 0:
            continue  # the searched-for file name itself
        if indent == 1:
            package = line.strip().rstrip(":")
        elif package:
            return package
    return None


def _normalise_font(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


_FONT_SUFFIXES = (".otf", ".ttf", ".ttc", ".pfb")


def package_for(requirement: tuple, out=print) -> str | None:
    """Resolve a ``(kind, name)`` requirement (see :func:`missing_from_log`) to a package."""
    kind, name = requirement
    if kind == "package":
        return name
    index = package_index(out=out)
    if kind == "file":
        if index is None:
            return _tlmgr_search_file(name)
        owners = index[0].get(name)
        return owners[0] if owners else None
    if kind == "font" and index:
        wanted = _normalise_font(name)
        best = None
        for base, owners in index[0].items():
            if not base.lower().endswith(_FONT_SUFFIXES):
                continue
            stem = _normalise_font(base.rsplit(".", 1)[0])
            if stem == wanted:
                return owners[0]
            if stem.startswith(wanted) and (best is None or len(stem) < best[0]):
                best = (len(stem), owners[0])
        return best[1] if best else None
    if kind == "hyphen" and index:
        candidate = f"hyphen-{name.lower()}"
        return candidate if candidate in index[1] else None
    return None


# ── Reading LaTeX logs ─────────────────────────────────────────────────────

_LOG_PATTERNS = [
    (re.compile(r"File `([^']+)' not found"), "file"),
    (re.compile(r"! I can't find file `([^']+)'"), "file"),
    (re.compile(r"\(file ([^)\s]+)\): cannot open"), "file"),
    (re.compile(r"language definition file ([\w.-]+\.ldf) was not found"), "file"),
    (re.compile(r"Package babel Error: Unknown option [`']([\w-]+)'"), "ldf"),
    (re.compile(r"! Font [^=]+=([^\s:]+)\s+at [^ ]+ not loadable: Metric \(TFM\) file"), "tfm"),
    (re.compile(r"! Font [^=]+=([^\s:]+) not loadable: Metric \(TFM\) file"), "tfm"),
    (re.compile(r"Package biblatex Error: Style '([^']+)' not found"), "bbx"),
    # pdfx loads these optionally (\IfFileExists), so their absence only shows
    # up as a downstream error rather than a "file not found".
    (re.compile(r"No color profile [\w.-]+\.icc found"), "pkg:colorprofiles"),
    (re.compile(r"Package pdfx Error: CreationDate is not properly supported"), "pkg:luatex85"),
    (re.compile(r'The font "([^"]+)" cannot be'), "font"),
    (re.compile(r'luaotfload \| [^\n]*?font "([^"]+)" not found', re.IGNORECASE), "font"),
    (re.compile(r"No hyphenation patterns were preloaded for\s+(?:\(babel\)\s+)?the language [`']([\w-]+)'"), "hyphen"),
]


_USER_FILE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".eps", ".pdf", ".bib")


def missing_from_log(text: str) -> list:
    """Extract what a failed compile was missing, as ``(kind, name)`` tuples.

    Kinds: ``file`` (a .sty/.cls/... file name), ``font`` (an OpenType font
    family) and ``hyphen`` (a babel language without hyphenation patterns).
    """
    # LaTeX wraps long log lines at 79 characters; joining continuation lines
    # keeps "File `long-name.sty' not found" patterns intact.
    unwrapped = re.sub(r"(?m)^(.{79})\n", r"\1", text)
    found: list = []
    for pattern, kind in _LOG_PATTERNS:
        for match in pattern.findall(unwrapped):
            name = match.strip()
            if kind == "file" and name.lower().endswith(_USER_FILE_SUFFIXES):
                continue  # the user's own image or bibliography, not a package
            if kind.startswith("pkg:"):
                item = ("package", kind[4:])
            elif kind == "ldf":
                item = ("file", f"{name}.ldf")
            elif kind == "bbx":  # biblatex style → its bibliography style file
                item = ("file", f"{name}.bbx")
            elif kind == "tfm":
                item = ("file", f"{name}.tfm")
            else:
                item = (kind, name)
            if item not in found:
                found.append(item)
    return found


def missing_helpers(build_dir: Path) -> list:
    """Helper programs a build needs but can't find (biber, bibtex, makeindex)."""
    needed = []
    if any(build_dir.glob("*.bcf")) and not command_exists("biber"):
        needed.append(("package", "biber"))
    if any(build_dir.glob("*.idx")) and not command_exists("makeindex"):
        needed.append(("package", "makeindex"))
    for aux in build_dir.glob("*.aux"):
        try:
            if "\\bibdata" in aux.read_text(encoding="utf-8", errors="replace") and not command_exists("bibtex"):
                needed.append(("package", "bibtex"))
                break
        except OSError:
            continue
    return needed


# ── Making a project compile ───────────────────────────────────────────────

_OPTIONAL_ARG = r"\s*(?:\[[^\]]*\])?\s*"
# (pattern, file-name prefix, file-name suffix) — e.g. \usetheme{Madrid} loads
# beamerthemeMadrid.sty.
_REQUIREMENT_PATTERNS = [
    (re.compile(r"\\documentclass" + _OPTIONAL_ARG + r"\{([^}]+)\}"), "", ".cls"),
    (re.compile(r"\\LoadClass(?:WithOptions)?" + _OPTIONAL_ARG + r"\{([^}]+)\}"), "", ".cls"),
    (re.compile(r"\\(?:usepackage|RequirePackage)" + _OPTIONAL_ARG + r"\{([^}]+)\}"), "", ".sty"),
    (re.compile(r"\\usetheme" + _OPTIONAL_ARG + r"\{([^}]+)\}"), "beamertheme", ".sty"),
    (re.compile(r"\\usecolortheme" + _OPTIONAL_ARG + r"\{([^}]+)\}"), "beamercolortheme", ".sty"),
    (re.compile(r"\\usefonttheme" + _OPTIONAL_ARG + r"\{([^}]+)\}"), "beamerfonttheme", ".sty"),
    (re.compile(r"\\useinnertheme" + _OPTIONAL_ARG + r"\{([^}]+)\}"), "beamerinnertheme", ".sty"),
    (re.compile(r"\\useoutertheme" + _OPTIONAL_ARG + r"\{([^}]+)\}"), "beameroutertheme", ".sty"),
    (re.compile(r"\\bibliographystyle\s*\{([^}]+)\}"), "", ".bst"),
]


def required_files(project_dir: Path) -> list:
    """File names a project's sources load (\\usepackage, \\documentclass, ...).

    Local files (anything shipped in the project, or referenced by path) are
    left out: only what has to come from the TeX distribution is returned.
    """
    local = {p.name for p in project_dir.rglob("*") if p.is_file()}
    names: list = []
    for source in sorted(project_dir.rglob("*")):
        if source.suffix not in (".tex", ".sty", ".cls") or "build" in source.relative_to(project_dir).parts:
            continue
        try:
            text = source.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        text = re.sub(r"(?<!\\)%.*", "", text)  # drop comments
        for pattern, prefix, suffix in _REQUIREMENT_PATTERNS:
            for group in pattern.findall(text):
                for item in group.split(","):
                    item = item.strip()
                    if not item or any(c in item for c in "/\\#{} "):
                        continue  # local path or macro argument, not a package name
                    candidate = item if item.endswith(suffix) else f"{prefix}{item}{suffix}"
                    if candidate not in local and candidate not in names:
                        names.append(candidate)
    return names


def unresolved_files(names) -> list:
    """Which of *names* kpathsea can't find in the installed distribution."""
    names = list(names)
    if not names or not command_exists("kpsewhich"):
        return []
    try:
        result = _run(["kpsewhich", *names], timeout=120)
    except (OSError, subprocess.SubprocessError):
        return []
    found = {Path(line.strip()).name for line in result.stdout.splitlines() if line.strip()}
    return [n for n in names if n not in found]


_TEX_PACKAGES_BLOCK = re.compile(r"^tex_packages\s*=\s*\[([^\]]*)\]", re.MULTILINE)


def read_tex_packages(toml_path: Path) -> list | None:
    """The ``tex_packages`` array of a latexforge.toml, or None if it has none.

    A regex rather than a TOML parser: tomllib only exists from Python 3.11,
    and this module must run on whatever Python a cloned project finds.
    """
    try:
        text = toml_path.read_text(encoding="utf-8")
    except OSError:
        return None
    match = _TEX_PACKAGES_BLOCK.search(text)
    if not match:
        return None
    body = re.sub(r"#[^\n]*", "", match.group(1))
    packages = re.findall(r"[\"']([A-Za-z0-9_.+-]+)[\"']", body)
    return packages or None


def _latexmk_flag(engine: str) -> str:
    return {"lualatex": "-lualatex", "xelatex": "-xelatex", "pdflatex": "-pdf"}.get(engine, "-lualatex")


def compile_once(project_dir: Path, main_file: str, engine: str, outdir: Path,
                 timeout: float = 600) -> tuple:
    """Compile with latexmk into *outdir*; return (succeeded, log text).

    ``-g`` forces a full run: after installing a package, latexmk would
    otherwise answer "Nothing to do" because the sources didn't change.
    """
    try:
        result = _run(
            ["latexmk", "-g", "-interaction=nonstopmode", "-file-line-error", _latexmk_flag(engine),
             f"-outdir={outdir}", main_file],
            cwd=project_dir, timeout=timeout,
        )
        ok = result.returncode == 0
    except subprocess.TimeoutExpired:
        ok = False
    except OSError:
        return False, ""
    log = outdir / (Path(main_file).stem + ".log")
    text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    pdf = outdir / (Path(main_file).stem + ".pdf")
    return ok and pdf.exists(), text


def ensure_project_packages(project_dir: Path, main_file: str | None = None, engine: str = "lualatex",
                            declared=None, out=print, max_rounds: int = 12) -> bool:
    """Install the TeX packages *project_dir* needs, when the distribution allows it.

    No-op unless tlmgr can install packages without admin rights (TinyTeX, or
    a TeX Live in the user's home). Three passes, cheapest first:

    1. the template's declared ``tex_packages`` list, if it has one — done;
    2. otherwise the packages its sources load, resolved with kpathsea;
    3. then a test compile in a throwaway directory, installing whatever the
       log says is missing, until it compiles or nothing new can be found.

    Never raises; returns False only when the project still can't compile
    because of missing packages.
    """
    try:
        dist = detect_distribution()
        if dist["kind"] not in ("tinytex", "texlive") or not dist["can_install_packages"]:
            return True

        if declared:
            installed = ensure_packages(declared, out=out)
            if installed:
                _say(out, f"Installed LaTeX packages: {', '.join(installed)}")
            return True

        tried: set = set()
        wanted = []
        for name in unresolved_files(required_files(project_dir)):
            pkg = package_for(("file", name), out=out)
            if pkg and pkg not in wanted:
                wanted.append(pkg)
        if wanted:
            installed = ensure_packages(wanted, out=out)
            tried.update(wanted)
            if installed:
                _say(out, f"Installed LaTeX packages: {', '.join(installed)}")

        if main_file is None:
            candidates = sorted(project_dir.glob("*.tex"))
            if not candidates:
                return True
            main_file = candidates[0].name

        with tempfile.TemporaryDirectory(prefix="latex-forge-check-") as tmp:
            outdir = Path(tmp)
            for _ in range(max_rounds):
                ok, log = compile_once(project_dir, main_file, engine, outdir)
                if ok:
                    return True
                needed = missing_from_log(log) + missing_helpers(outdir)
                packages = []
                for requirement in needed:
                    pkg = package_for(requirement, out=out)
                    if pkg and pkg not in tried and pkg not in packages:
                        packages.append(pkg)
                if not packages:
                    # Either a genuine LaTeX error (not ours to fix) or
                    # something we can't map to a package.
                    return not needed
                _say(out, f"Installing LaTeX packages: {', '.join(packages)}")
                tried.update(packages)
                install_packages(packages, out=out)
        return False
    except Exception as exc:  # never break project creation over this
        _say(out, f"[warn] Could not check the project's LaTeX packages: {exc}")
        return True


# ── Downloading ────────────────────────────────────────────────────────────


def download(url: str, dest: Path, out=print, attempts: int = 3) -> None:
    """Download *url* to *dest*, reporting progress every 5% through *out*.

    Falls back to curl when Python's TLS setup can't verify certificates (a
    classic with python.org builds on macOS).
    """
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            _download_urllib(url, dest, out)
            return
        except Exception as exc:  # network hiccup, TLS, HTTP error...
            last_error = exc
            if "CERTIFICATE_VERIFY_FAILED" in str(exc) and shutil.which("curl"):
                result = subprocess.run(["curl", "-fsSL", "--retry", "3", "-o", str(dest), url], check=False)
                if result.returncode == 0:
                    return
            if attempt < attempts:
                time.sleep(2 * attempt)
    raise RuntimeError(f"Download failed: {url} ({last_error})")


def _download_urllib(url: str, dest: Path, out) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "latex-forge"})
    with urllib.request.urlopen(request, timeout=60) as response:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        next_report = 5
        tmp = dest.with_name(dest.name + ".part")
        with open(tmp, "wb") as fh:
            while True:
                chunk = response.read(1 << 20)
                if not chunk:
                    break
                fh.write(chunk)
                done += len(chunk)
                if out is not None and total:
                    percent = done * 100 // total
                    if percent >= next_report:
                        _say(out, f"    downloading {percent}% ({done / 1e6:.0f} of {total / 1e6:.0f} MB)")
                        next_report = percent - percent % 5 + 5
        if total and done < total:
            raise RuntimeError(f"incomplete download ({done} of {total} bytes)")
        os.replace(tmp, dest)


# ── Installing TinyTeX ─────────────────────────────────────────────────────

TINYTEX_RELEASES = "https://github.com/rstudio/tinytex-releases/releases"
BUNDLES = {"light": "TinyTeX-1", "full": "TinyTeX-2"}
# Disk space needed during install (download + extraction), in bytes.
REQUIRED_SPACE = {"light": 1_000_000_000, "full": 7_000_000_000}

# What every latex-forge user needs on top of TinyTeX-1: the build tools and
# everything the built-in templates load (see tex_packages.json).
BASE_PACKAGES = ["latexmk", "biber"]


def _is_musl() -> bool:
    if any(Path("/lib").glob("ld-musl-*.so.1")):
        return True
    try:
        result = subprocess.run(["ldd", "--version"], capture_output=True, text=True, check=False)
        return "musl" in (result.stdout + result.stderr).lower()
    except OSError:
        return False


def tinytex_platform() -> tuple | None:
    """(asset suffix, extension) of the prebuilt TinyTeX for this machine, or None."""
    current = detect_os()
    machine = platform.machine().lower()
    if current == "macos":
        return "darwin", "tar.xz"
    if current == "windows":
        return "windows", "exe"
    if current == "linux":
        if machine in ("x86_64", "amd64"):
            return ("linuxmusl-x86_64" if _is_musl() else "linux-x86_64"), "tar.xz"
        if machine in ("aarch64", "arm64") and not _is_musl():
            return "linux-arm64", "tar.xz"
    return None


def latest_tinytex_version() -> str | None:
    """Tag of the latest monthly TinyTeX release (e.g. "2026.10"), or None."""
    try:
        request = urllib.request.Request(f"{TINYTEX_RELEASES}/latest", headers={"User-Agent": "latex-forge"})
        with urllib.request.urlopen(request, timeout=30) as response:
            final = response.geturl()
    except Exception:
        return None
    match = re.search(r"/tag/v([\d.]+)$", final)
    return match.group(1) if match else None


def tinytex_urls(kind: str, version: str | None) -> list:
    """Download URLs to try, most stable first (monthly release, then daily build)."""
    target = tinytex_platform()
    if target is None:
        return []
    suffix, ext = target
    bundle = BUNDLES[kind]
    urls = []
    if version and kind == "light":  # TinyTeX-2 (full) only exists as a daily build
        urls.append(f"{TINYTEX_RELEASES}/download/v{version}/{bundle}-{suffix}-v{version}.{ext}")
    urls.append(f"{TINYTEX_RELEASES}/download/daily/{bundle}-{suffix}.{ext}")
    return urls


def _extract(archive: Path, workdir: Path) -> Path:
    """Unpack a TinyTeX bundle into *workdir*; return the extracted top folder."""
    if archive.suffix == ".exe":
        # Self-extracting 7-Zip archive: unpacks a TinyTeX folder into its cwd.
        result = subprocess.run([str(archive), "-y"], cwd=str(workdir), check=False,
                                capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"could not unpack {archive.name}: {result.stderr.strip() or result.stdout.strip()}")
    else:
        try:
            import tarfile
            with tarfile.open(archive) as tar:
                if hasattr(tarfile, "data_filter"):
                    tar.extractall(workdir, filter="tar")
                else:
                    tar.extractall(workdir)
        except Exception:
            # Python without lzma support: let the system tar do it.
            result = subprocess.run(["tar", "-xf", str(archive), "-C", str(workdir)], check=False)
            if result.returncode != 0:
                raise
    tops = [p for p in workdir.iterdir() if p.is_dir() and "tinytex" in p.name.lower()]
    if len(tops) != 1:
        raise RuntimeError("unexpected TinyTeX archive layout")
    return tops[0]


def _tlmgr_at(bin_dir: Path) -> str:
    for name in ("tlmgr.bat", "tlmgr"):
        if (bin_dir / name).exists():
            return str(bin_dir / name)
    return str(bin_dir / "tlmgr")


def _post_install(bin_dir: Path, out=print, modify_path: bool = True) -> None:
    """Hook TinyTeX into the system the way its official installers do."""
    tlmgr = _tlmgr_at(bin_dir)

    def quiet(*args: str) -> None:
        subprocess.run([tlmgr, *args], capture_output=True, text=True, check=False, env=tex_env())

    if detect_os() != "windows":
        # Symlink the tools into ~/.local/bin (no admin rights needed) rather
        # than /usr/local/bin, TinyTeX's default on macOS.
        local = Path.home() / ".local"
        user_bin_dir().mkdir(parents=True, exist_ok=True)
        quiet("option", "sys_bin", str(user_bin_dir()))
        quiet("option", "sys_man", str(local / "share" / "man"))
        quiet("option", "sys_info", str(local / "share" / "info"))
    quiet("postaction", "install", "script", "xetex")  # TinyTeX issue #313
    if modify_path:
        quiet("path", "add")  # symlinks on Unix, user PATH (registry) on Windows
        ensure_user_bin_on_path(out=out)


def install_tinytex(kind: str = "light", out=print, modify_path: bool = True,
                    extra_packages=None, reinstall: bool = False) -> bool:
    """Install TinyTeX in the user's home — no admin rights, no package manager.

    *kind* is ``light`` (TinyTeX-1, ~70 MB download; further packages are
    installed on demand) or ``full`` (TinyTeX-2: all of TeX Live, ~2 GB).
    An existing TinyTeX is reused (and upgraded to full if asked) unless
    *reinstall* is set, in which case its packages are reinstalled afterwards.
    """
    root = tinytex_root()
    existing = tinytex_bin_dir(root)
    keep_packages: list = []

    if existing and not reinstall:
        step(f"TinyTeX already installed in {root}", out)
        if kind == "full":
            step("Upgrading TinyTeX to the full TeX Live (scheme-full) — this takes a while", out)
            install_packages(["scheme-full"], out=out, stream=True)
    else:
        if detect_os() != "windows" and not shutil.which("perl"):
            _say(out, "[error] Perl is required by TeX Live's package manager but wasn't found.")
            _say(out, "        Install it with your package manager (e.g. `sudo apt install perl`), then retry.")
            return False
        if tinytex_platform() is None:
            _say(out, f"[error] No prebuilt TinyTeX for this platform ({platform.system()} {platform.machine()}).")
            _say(out, "        Use `latex-forge setup --install-tex --tex system`, or see https://yihui.org/tinytex/")
            return False

        parent = tinytex_parent_dir()
        parent.mkdir(parents=True, exist_ok=True)
        free = shutil.disk_usage(str(parent)).free
        if free < REQUIRED_SPACE[kind]:
            _say(out, f"[error] Not enough disk space in {parent}: {free / 1e9:.1f} GB free, "
                      f"{REQUIRED_SPACE[kind] / 1e9:.0f} GB needed.")
            return False

        if existing and reinstall:
            keep_packages = sorted(installed_packages() or [])

        with tempfile.TemporaryDirectory(prefix="latex-forge-tinytex-", dir=str(parent)) as tmp:
            workdir = Path(tmp)
            version = latest_tinytex_version()
            label = "full TeX Live" if kind == "full" else "light"
            step(f"Downloading TinyTeX ({label}{', v' + version if version and kind == 'light' else ''})", out)
            archive = None
            errors = []
            for url in tinytex_urls(kind, version):
                candidate = workdir / url.rsplit("/", 1)[-1]
                try:
                    download(url, candidate, out=out)
                    archive = candidate
                    break
                except Exception as exc:
                    errors.append(str(exc))
            if archive is None:
                _say(out, "[error] Could not download TinyTeX: " + "; ".join(errors))
                return False

            step("Unpacking TinyTeX", out)
            try:
                extracted = _extract(archive, workdir)
            except Exception as exc:
                _say(out, f"[error] {exc}")
                return False
            archive.unlink()

            try:
                if root.exists():
                    backup = root.with_name(root.name + ".old")
                    shutil.rmtree(backup, ignore_errors=True)
                    os.replace(root, backup)
                    shutil.rmtree(backup, ignore_errors=True)
                shutil.move(str(extracted), str(root))
            except OSError as exc:
                _say(out, f"[error] Could not put TinyTeX in {root}: {exc}")
                _say(out, "        Close the programs using LaTeX (e.g. an editor compiling), then retry.")
                return False

    bin_dir = tinytex_bin_dir(root)
    if bin_dir is None:
        _say(out, f"[error] TinyTeX was unpacked to {root} but tlmgr is missing.")
        return False

    step("Configuring TinyTeX", out)
    _post_install(bin_dir, out=out, modify_path=modify_path)

    wanted = list(BASE_PACKAGES) + list(extra_packages or []) + keep_packages
    step("Installing the LaTeX packages latex-forge needs", out)
    ensure_packages(wanted, out=out, stream=True)
    return tex_ready()


def uninstall_tinytex(out=print) -> bool:
    """Remove the managed TinyTeX (and the symlinks/PATH entry it added)."""
    root = tinytex_root()
    bin_dir = tinytex_bin_dir(root)
    if not root.exists():
        _say(out, f"No TinyTeX found in {root}.")
        return True
    if bin_dir:
        subprocess.run([_tlmgr_at(bin_dir), "path", "remove"], capture_output=True, check=False, env=tex_env())
    shutil.rmtree(root, ignore_errors=True)
    _say(out, f"Removed {root}.")
    return not root.exists()


# ── PATH for new terminals ─────────────────────────────────────────────────

PROFILE_MARKER = "# >>> latex-forge >>>"
_PROFILE_BLOCK = """
# >>> latex-forge >>>
# Added by `latex-forge setup`: puts latex-forge and its LaTeX tools on PATH.
case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) export PATH="$HOME/.local/bin:$PATH" ;;
esac
# <<< latex-forge <<<
"""
_FISH_BLOCK = """# Added by `latex-forge setup`: puts latex-forge and its LaTeX tools on PATH.
fish_add_path -g $HOME/.local/bin
"""


def ensure_user_bin_on_path(out=print) -> list:
    """Make sure new shells have ~/.local/bin on PATH; return the files changed.

    Appends a small, clearly marked block to the shell startup files that
    don't already mention ~/.local/bin (e.g. from `pipx ensurepath` or `uv
    tool update-shell`). The current PATH can't be trusted for this: the VS
    Code extension adds ~/.local/bin when it runs the CLI. Windows needs
    nothing: tlmgr and uv register their directories in the user's PATH.
    """
    if detect_os() == "windows":
        return []
    home = Path.home()
    shell = Path(os.environ.get("SHELL", "")).name
    changed = []

    if shell == "fish":
        conf = home / ".config" / "fish" / "conf.d" / "latex-forge.fish"
        if not conf.exists():
            conf.parent.mkdir(parents=True, exist_ok=True)
            conf.write_text(_FISH_BLOCK, encoding="utf-8")
            changed.append(conf)

    candidates = [home / ".zshrc", home / ".bashrc", home / ".bash_profile", home / ".profile"]
    targets = [p for p in candidates if p.exists()]
    primary = {"zsh": home / ".zshrc", "bash": home / ".bashrc"}.get(shell, home / ".profile")
    if shell != "fish" and primary not in targets:
        targets.append(primary)

    def mentions_user_bin(path: Path) -> bool:
        try:
            content = path.read_text(encoding="utf-8") if path.exists() else ""
        except OSError:
            return True  # unreadable: leave it alone
        return PROFILE_MARKER in content or bool(re.search(r"\.local/bin", content))

    # Startup files read by the same shell: e.g. `uv tool update-shell` writes
    # ~/.zshenv, which zsh reads before ~/.zshrc.
    families = [
        [home / ".zshenv", home / ".zprofile", home / ".zshrc"],
        [home / ".bash_profile", home / ".bashrc"],
    ]

    for profile in targets:
        siblings = next((f for f in families if profile in f), [profile])
        if any(mentions_user_bin(p) for p in siblings):
            continue
        try:
            with open(profile, "a", encoding="utf-8") as fh:
                fh.write(_PROFILE_BLOCK)
            changed.append(profile)
        except OSError:
            continue

    if changed:
        names = ", ".join(str(p).replace(str(home), "~") for p in changed)
        _say(out, f"Added ~/.local/bin to PATH in {names} (new terminals pick it up).")
    return changed


# ── Installing through the system package manager ──────────────────────────


def privilege_prefix() -> list:
    """Return the command prefix needed for privileged installs on Linux.

    Empty if already running as root or if `sudo` is unavailable (in which
    case the install command is attempted without elevation and may fail).
    """
    geteuid = getattr(os, "geteuid", None)
    if geteuid is not None and geteuid() == 0:
        return []
    if shutil.which("sudo"):
        return ["sudo"]
    return []


def _can_elevate() -> bool:
    """True if a sudo password prompt can be answered (or isn't needed)."""
    prefix = privilege_prefix()
    if not prefix or is_interactive():
        return True
    return subprocess.run(["sudo", "-n", "true"], capture_output=True, check=False).returncode == 0


def _miktex_bin_dir() -> Path | None:
    """Locate MiKTeX's bin directory right after a winget install (PATH isn't refreshed yet)."""
    for env_var in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"):
        base = os.environ.get(env_var)
        if not base:
            continue
        for candidate in (Path(base) / "Programs" / "MiKTeX" / "miktex" / "bin" / "x64",
                          Path(base) / "MiKTeX" / "miktex" / "bin" / "x64"):
            if (candidate / "mpm.exe").exists():
                return candidate
    return None


def _ensure_miktex_latexmk(out=print) -> None:
    """Enable MiKTeX's on-the-fly installs and pull in latexmk, biber and Perl.

    The winget package ships neither latexmk/biber nor the Perl interpreter
    MiKTeX's latexmk script needs — without Perl, latexmk fails with "MiKTeX
    could not find the script engine 'perl'".
    """
    bin_dir = _miktex_bin_dir()

    def tool(name: str) -> str:
        return str(bin_dir / f"{name}.exe") if bin_dir else name

    step("Configuring MiKTeX (auto-install missing packages, latexmk, biber)", out)
    steps = [
        [tool("initexmf"), "--set-config-value=[MPM]AutoInstall=1"],
        [tool("mpm"), "--update-db"],
        [tool("mpm"), "--install=latexmk"],
        [tool("mpm"), "--install=biber"],
    ]
    for command in steps:
        try:
            result = subprocess.run(command, check=False, capture_output=True, text=True)
        except OSError:
            _say(out, f"[warn] Could not run: {' '.join(command)}")
            _say(out, "       Open 'MiKTeX Console' -> Packages and install 'latexmk' and 'biber' manually.")
            return
        if result.returncode != 0:
            _say(out, f"[warn] Command failed: {' '.join(command)}")
            detail = result.stderr.strip() or result.stdout.strip()
            if detail:
                _say(out, detail)

    if not shutil.which("perl", path=search_path()):
        step("Installing Perl (needed by MiKTeX's latexmk)", out)
        subprocess.run(
            ["winget", "install", "-e", "--id", "StrawberryPerl.StrawberryPerl",
             "--accept-source-agreements", "--accept-package-agreements"],
            check=False,
        )


def install_system_distribution(out=print) -> bool:
    """Install a TeX distribution with the OS package manager (needs admin rights).

    MacTeX via Homebrew, MiKTeX via winget, or a full TeX Live via
    apt/dnf/pacman. Those installers ask for an administrator password, so this
    refuses to start when nobody can type it (e.g. when called from an editor
    in the background) instead of failing halfway through.
    """
    current = detect_os()
    commands: list = []
    description = ""
    needs_password = False

    if current == "macos":
        if not shutil.which("brew"):
            _say(out, "Homebrew not found. Cannot install TeX automatically on macOS.")
            _say(out, "Install MacTeX manually: https://www.tug.org/mactex/")
            _say(out, "Or use the no-admin option: latex-forge setup --install-tex --tex light")
            return False
        description = "Installing MacTeX (no GUI apps) via Homebrew"
        commands = [["brew", "install", "--cask", "mactex-no-gui"]]
        needs_password = True  # the MacTeX .pkg installer runs through sudo
    elif current == "windows":
        if not shutil.which("winget"):
            _say(out, "winget not found. Cannot install TeX automatically on Windows.")
            _say(out, "MiKTeX: https://miktex.org/howto/install-miktex")
            _say(out, "TeX Live: https://www.tug.org/texlive/windows.html")
            _say(out, "Or use the no-admin option: latex-forge setup --install-tex --tex light")
            return False
        description = "Installing MiKTeX via winget"
        commands = [[
            "winget", "install", "-e", "--id", "MiKTeX.MiKTeX",
            "--accept-source-agreements", "--accept-package-agreements",
        ]]
    elif current == "linux":
        sudo_prefix = privilege_prefix()
        needs_password = bool(sudo_prefix)
        if shutil.which("apt-get"):
            description = "Installing full TeX Live via apt"
            commands = [
                [*sudo_prefix, "apt-get", "update"],
                [*sudo_prefix, "apt-get", "install", "-y", "texlive-full", "latexmk", "biber"],
            ]
        elif shutil.which("dnf"):
            description = "Installing full TeX Live via dnf"
            commands = [[*sudo_prefix, "dnf", "install", "-y", "texlive-scheme-full", "latexmk", "biber"]]
        elif shutil.which("pacman"):
            description = "Installing TeX Live via pacman"
            commands = [[*sudo_prefix, "pacman", "-S", "--needed", "--noconfirm", "texlive-meta", "biber"]]
        else:
            _say(out, "No supported package manager detected automatically on Linux.")
            _say(out, "Install TeX Live manually: https://www.tug.org/texlive/quickinstall.html")
            _say(out, "Or use the no-admin option: latex-forge setup --install-tex --tex light")
            return False
    else:
        _say(out, f"OS not supported for automatic installation: {current}")
        return False

    if needs_password and not is_interactive() and not _can_elevate():
        _say(out, "[error] This installation needs your administrator password, which can't be")
        _say(out, "        typed here. Run it in a terminal instead:")
        _say(out, "          latex-forge setup --install-tex --tex system")
        _say(out, "        or pick the light option, which needs no admin rights.")
        return False

    step(description, out)
    if current == "macos":
        _say(out, "This may take 20-30 minutes — Homebrew will show its progress below.")
    else:
        _say(out, "This may take several minutes.")
    for command in commands:
        _say(out, "")
        _say(out, "Running command:")
        _say(out, " ".join(command))
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            _say(out, "")
            _say(out, "[warn] Automatic installation failed.")
            return False

    if current == "windows":
        _ensure_miktex_latexmk(out=out)

    _say(out, "")
    _say(out, "[ok] Installation commands completed.")
    return True


def install_gh_cli(out=print) -> bool:
    """Install the GitHub CLI (``gh``) with the OS package manager.

    Needed for ``latex-forge create --repo create``. Doesn't touch GitHub
    authentication — the user still has to run ``gh auth login`` themselves.
    """
    current = detect_os()
    command: list = []
    if current == "macos":
        if not shutil.which("brew"):
            _say(out, "Homebrew not found. Cannot install the GitHub CLI automatically on macOS.")
            _say(out, "Install it manually: https://cli.github.com/")
            return False
        command = ["brew", "install", "gh"]
    elif current == "windows":
        if not shutil.which("winget"):
            _say(out, "winget not found. Cannot install the GitHub CLI automatically on Windows.")
            _say(out, "Install it manually: https://cli.github.com/")
            return False
        command = ["winget", "install", "-e", "--id", "GitHub.cli",
                   "--accept-source-agreements", "--accept-package-agreements"]
    elif current == "linux":
        sudo_prefix = privilege_prefix()
        if sudo_prefix and not _can_elevate():
            _say(out, "[error] Installing the GitHub CLI needs your password — run in a terminal:")
            _say(out, "          latex-forge setup --install-gh")
            return False
        if shutil.which("apt-get"):
            command = [*sudo_prefix, "apt-get", "install", "-y", "gh"]
        elif shutil.which("dnf"):
            command = [*sudo_prefix, "dnf", "install", "-y", "gh"]
        elif shutil.which("pacman"):
            command = [*sudo_prefix, "pacman", "-S", "--needed", "--noconfirm", "github-cli"]
        else:
            _say(out, "No supported package manager detected automatically on Linux.")
            _say(out, "Install the GitHub CLI manually: https://cli.github.com/")
            return False
    else:
        _say(out, f"OS not supported for automatic installation: {current}")
        return False

    step("Installing the GitHub CLI (gh)", out)
    _say(out, " ".join(command))
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        _say(out, "")
        _say(out, "[warn] Automatic installation failed.")
        return False
    _say(out, "")
    _say(out, "[ok] GitHub CLI installed. Run `gh auth login` to authenticate.")
    return True


# ── VS Code extensions ─────────────────────────────────────────────────────


def vscode_cli() -> str | None:
    """Full path of VS Code's ``code`` command, even when it isn't on PATH."""
    found = shutil.which("code")
    if found:
        return found
    candidates = []
    if detect_os() == "macos":
        candidates.append(Path("/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"))
        candidates.append(Path.home() / "Applications/Visual Studio Code.app/Contents/Resources/app/bin/code")
    elif detect_os() == "windows":
        for env_var in ("LOCALAPPDATA", "PROGRAMFILES"):
            base = os.environ.get(env_var)
            if base:
                candidates.append(Path(base) / "Programs" / "Microsoft VS Code" / "bin" / "code.cmd")
                candidates.append(Path(base) / "Microsoft VS Code" / "bin" / "code.cmd")
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def install_vscode_extensions(extensions, out=print) -> bool:
    """Install every extension in *extensions* via the ``code`` CLI.

    Returns False if ``code`` can't be found, or if any extension failed to
    install (a warning is printed per failure but the rest still proceed).
    """
    code = vscode_cli()
    if code is None:
        _say(out, "VS Code CLI not found: `code` is not in PATH.")
        _say(out, "On macOS, open VS Code then run:")
        _say(out, "Shell Command: Install 'code' command in PATH")
        return False

    all_ok = True
    for extension in extensions:
        result = subprocess.run([code, "--install-extension", extension, "--force"],
                                check=False, capture_output=True, text=True)
        if result.returncode == 0:
            _say(out, f"[ok] Extension installed or already present: {extension}")
        else:
            all_ok = False
            _say(out, f"[warn] Could not install extension {extension}")
            detail = result.stderr.strip() or result.stdout.strip()
            if detail:
                _say(out, detail)
    return all_ok


def read_extension_recommendations(extensions_file: Path) -> list:
    """Extension IDs listed in a ``.vscode/extensions.json``."""
    if not extensions_file.exists():
        return []
    data = json.loads(extensions_file.read_text(encoding="utf-8"))
    return list(data.get("recommendations", []))


# ── Checking the result ────────────────────────────────────────────────────

BASE_TOOLS = ["latexmk", "lualatex"]
TEMPLATE_SPECIFIC_TOOLS = ["bibtex", "biber"]

_SMOKE_TEST = r"""\documentclass{article}
\begin{document}
latex-forge test document.
\end{document}
"""


def verify_toolchain(engine: str = "lualatex", out=print) -> bool:
    """Compile a tiny document end to end; the only real proof LaTeX works.

    The first LuaLaTeX run also builds its font cache, which is better done
    now than on the user's first save.
    """
    step(f"Checking that LaTeX compiles a test document ({engine})", out)
    if not command_exists("latexmk"):
        _say(out, "[warn] latexmk not found — cannot run the test compile.")
        return False
    with tempfile.TemporaryDirectory(prefix="latex-forge-verify-") as tmp:
        work = Path(tmp)
        (work / "test.tex").write_text(_SMOKE_TEST, encoding="utf-8")
        ok, log = compile_once(work, "test.tex", engine, work / "build", timeout=900)
        if not ok:
            # A bare TinyTeX can still miss something the engine needs.
            needed = missing_from_log(log)
            packages = [p for p in (package_for(r, out=out) for r in needed) if p]
            if packages and detect_distribution()["can_install_packages"]:
                install_packages(packages, out=out)
                ok, log = compile_once(work, "test.tex", engine, work / "build", timeout=900)
    if ok:
        _say(out, "[ok] LaTeX works: the test document compiled.")
    else:
        _say(out, "[warn] The test document did not compile. Run `latex-forge diagnose` for details.")
        for line in log.splitlines():
            if line.startswith("!"):
                _say(out, "       " + line)
                break
    return ok


def print_tool_status(out=print) -> tuple:
    """Print availability of required and template-specific LaTeX tools.

    Returns (base_ready, extra_ready): whether all of BASE_TOOLS and all of
    TEMPLATE_SPECIFIC_TOOLS, respectively, were found.
    """
    base_ready = True
    extra_ready = True
    _say(out, "Checking LaTeX tools:")
    for tool in BASE_TOOLS:
        exists = command_exists(tool)
        _say(out, f"- {tool}: {'ok' if exists else 'missing'}")
        base_ready = base_ready and exists
    _say(out, "Tools useful for some templates:")
    for tool in TEMPLATE_SPECIFIC_TOOLS:
        exists = command_exists(tool)
        _say(out, f"- {tool}: {'ok' if exists else 'missing'}")
        extra_ready = extra_ready and exists
    dist = detect_distribution()
    if dist["kind"] != "none":
        _say(out, f"Distribution: {dist['label']} ({dist['bin_dir']})")
    return base_ready, extra_ready


TEX_CHOICES = ("light", "full", "system")

_CHOICE_TEXT = """\
LaTeX is not installed. Which distribution should be installed?
  1. Light  — TinyTeX in your home folder (~500 MB, a few minutes, no admin rights);
              extra packages install automatically when a document needs them  [recommended]
  2. Full   — all of TeX Live in your home folder (~2 GB download, everything offline)
  3. System — MacTeX / MiKTeX / TeX Live via your package manager (admin password)
  n. Not now"""


def ask_tex_choice() -> str | None:
    """Ask which distribution to install; None means "not now"."""
    if not is_interactive():
        return None
    print(_CHOICE_TEXT)
    while True:
        try:
            answer = input("Choose [1]: ").strip().lower()
        except (EOFError, OSError, KeyboardInterrupt):
            print("")
            return None
        if answer in ("", "1"):
            return "light"
        if answer in ("2", "3"):
            return TEX_CHOICES[int(answer) - 1]
        if answer in ("n", "no", "q"):
            return None
        print("Please answer 1, 2, 3 or n.")


def install_tex(kind: str, out=print, modify_path: bool = True, extra_packages=None,
                reinstall: bool = False) -> bool:
    """Install a TeX distribution of the given *kind* (light, full or system)."""
    if kind == "system":
        return install_system_distribution(out=out)
    return install_tinytex(kind, out=out, modify_path=modify_path,
                           extra_packages=extra_packages, reinstall=reinstall)


def print_os_specific_help(out=print) -> None:
    """Print manual TeX-distribution installation instructions for the detected OS."""
    current = detect_os()
    _say(out, "")
    _say(out, "Installing LaTeX by hand:")
    _say(out, "- No admin rights needed: latex-forge setup --install-tex  (TinyTeX)")
    if current == "macos":
        _say(out, "- MacTeX: https://www.tug.org/mactex/")
    elif current == "windows":
        _say(out, "- TeX Live: https://www.tug.org/texlive/windows.html")
        _say(out, "- MiKTeX: https://miktex.org/howto/install-miktex (also install Strawberry Perl for latexmk)")
    elif current == "linux":
        _say(out, "- TeX Live: https://www.tug.org/texlive/quickinstall.html")
    _say(out, "Then verify: latexmk --version && lualatex --version")


# ── Standalone use (scripts/setup.py in generated projects) ────────────────


def run_project_setup(project_root: Path, argv=None) -> int:
    """``scripts/setup.py`` entry point: set a cloned project up on this machine."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="setup.py",
        description="Install LaTeX (if needed) and everything this project needs to compile.",
    )
    parser.add_argument("--check-only", action="store_true", help="Only report what's installed.")
    parser.add_argument("--skip-extensions", action="store_true", help="Don't install the recommended VS Code extensions.")
    parser.add_argument("--install-tex", action="store_true", help="Install LaTeX if it's missing (light by default).")
    parser.add_argument("--tex", choices=TEX_CHOICES, help="Which distribution to install (implies --install-tex).")
    parser.add_argument("--yes", "-y", action="store_true", help="Don't ask questions; use the recommended choices.")
    parser.add_argument("--no-modify-path", action="store_true", help="Don't add ~/.local/bin to your shell's PATH.")
    args = parser.parse_args(argv)

    if args.check_only and (args.install_tex or args.tex):
        print("`--check-only` and `--install-tex` cannot be used together.")
        return 2

    print(f"OS detected: {detect_os()}")
    print(f"Python: {sys.executable}")
    print("")

    extensions_ok = True
    if args.skip_extensions:
        print("VS Code extension installation skipped.")
    elif args.check_only:
        print("Check-only mode: no VS Code extensions will be installed.")
    else:
        step("Installing recommended VS Code extensions")
        extensions_ok = install_vscode_extensions(
            read_extension_recommendations(project_root / ".vscode" / "extensions.json"))

    print("")
    base_ready, extra_ready = print_tool_status()

    if not base_ready and not args.check_only:
        kind = args.tex or ("light" if (args.install_tex or args.yes) else ask_tex_choice())
        if kind:
            print("")
            install_tex(kind, modify_path=not args.no_modify_path)
            print("")
            base_ready, extra_ready = print_tool_status()

    if base_ready and not args.check_only:
        engine = "lualatex"
        settings = project_root / ".vscode" / "settings.json"
        try:
            for arg in json.loads(settings.read_text(encoding="utf-8"))["latex-workshop.latex.tools"][0]["args"]:
                engine = {"-pdf": "pdflatex", "-xelatex": "xelatex", "-lualatex": "lualatex"}.get(arg, engine)
        except (OSError, ValueError, KeyError, IndexError, TypeError):
            pass
        step("Installing the LaTeX packages this project needs")
        main_tex = project_root / f"{project_root.name}.tex"
        ensure_project_packages(project_root, main_tex.name if main_tex.exists() else None, engine,
                                declared=read_tex_packages(project_root / "latexforge.toml"))

    if not base_ready:
        print_os_specific_help()
        print("")
        print("[warn] The LaTeX environment is not yet complete.")
        if not extensions_ok:
            print("[warn] Some VS Code extensions could not be installed automatically.")
        return 1

    print("")
    print("[ok] The environment for compiling this project is ready.")
    if not extra_ready:
        print("[warn] Some bibliography tools are still missing for certain templates.")
    return 0
