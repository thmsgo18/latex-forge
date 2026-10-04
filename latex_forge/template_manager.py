"""Install, remove, list and update user-installed templates.

User-installed templates live alongside the built-in ones (see
``latex_forge/project.py``) but are stored under
``~/.latex-forge/templates/`` and tracked in
``~/.latex-forge/installed_templates.json`` (see ``installed_templates.py``)
so that ``latex-forge template update`` can later detect newer versions
published to the gallery.
"""
from __future__ import annotations

import json
import re
import shutil
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

# URL of the gallery's machine-readable index
GALLERY_JSON_URL = (
    "https://raw.githubusercontent.com/thmsgo18/latex-forge-gallery/main/gallery.json"
)
# URL pattern that identifies a gallery install URL
_GALLERY_HOST = "thmsgo18/latex-forge-gallery"

# Per-template archives published by .github/workflows/build-archives.yml to
# the gallery's `dist` branch — a flat ZIP per template (main.tex at the
# root), so installing one template doesn't require downloading the whole
# gallery repository.
_GALLERY_ARCHIVE_BASE = (
    "https://raw.githubusercontent.com/thmsgo18/latex-forge-gallery/dist/"
)


def _validate_template_name(name: str) -> None:
    """Ensure *name* is a plain directory name inside the user library.

    Rejects anything that could escape ``~/.latex-forge/templates/``
    (path separators, ``..``, absolute paths) or hide the directory.
    """
    if not name or name in (".", ".."):
        raise ValueError(f"Invalid template name: {name!r}")
    if "/" in name or "\\" in name or ":" in name:
        raise ValueError(
            f"Invalid template name: {name!r}. "
            "Template names cannot contain path separators."
        )
    if name.startswith("."):
        raise ValueError(f"Template name cannot start with a dot: {name!r}")


# ── Public API ────────────────────────────────────────────────────────────


_VALID_ENGINES = ("lualatex", "xelatex", "pdflatex")


def install_template(
    source: str,
    name: str | None = None,
    force: bool = False,
    engine: str | None = None,
) -> tuple[str, Path]:
    """Install a template from a GitHub URL, ZIP URL, or local path.

    Returns ``(template_name, installed_path)``.

    Supported sources:
    - ``https://github.com/owner/repo``
    - ``https://github.com/owner/repo/tree/branch/path/to/subdir``
    - Any ``https://`` URL ending in ``.zip``
    - A local directory
    - A local ``.zip`` file

    If *engine* is given (one of ``lualatex``, ``xelatex``, ``pdflatex``), it is
    written to the template's ``latexforge.toml`` so that projects created from
    it use the right compiler — useful for templates that don't already declare
    one (see TEMPLATE_COMPATIBILITY.md).

    Raises ``FileExistsError`` if a user-installed template with the same name
    already exists and *force* is False.
    Raises ``ValueError`` if the name matches a built-in template, or if
    *engine* is not a valid LaTeX engine.
    """
    if engine is not None and engine not in _VALID_ENGINES:
        raise ValueError(
            f"Invalid engine: {engine!r}. Must be one of: {', '.join(_VALID_ENGINES)}"
        )
    source = source.strip()

    if "github.com" in source:
        template_name, path = _install_from_github(source, name, force=force)
    elif source.startswith(("https://", "http://")) and source.endswith(".zip"):
        template_name, path = _install_from_zip_url(source, name, force=force)
    else:
        local = Path(source).expanduser().resolve()
        if local.exists():
            if local.is_dir():
                template_name, path = _install_from_dir(local, name, force=force)
            elif local.suffix == ".zip":
                template_name, path = _install_from_zip_file(local, name, force=force)
            else:
                raise ValueError(
                    f"Cannot install template from: {source!r}\n"
                    "Supported sources:\n"
                    "  - GitHub URL  : https://github.com/owner/repo\n"
                    "  - ZIP URL     : https://example.com/template.zip\n"
                    "  - Local dir   : /path/to/template/\n"
                    "  - Local ZIP   : /path/to/template.zip"
                )
        else:
            raise ValueError(
                f"Cannot install template from: {source!r}\n"
                "Supported sources:\n"
                "  - GitHub URL  : https://github.com/owner/repo\n"
                "  - ZIP URL     : https://example.com/template.zip\n"
                "  - Local dir   : /path/to/template/\n"
                "  - Local ZIP   : /path/to/template.zip"
            )

    if engine is not None:
        _write_engine(path / "latexforge.toml", engine)

    # Persist metadata (version from gallery if available)
    _record_installation(template_name, source)
    return template_name, path


def remove_template(name: str) -> None:
    """Remove a user-installed template.

    Raises ``ValueError`` if the template is built-in.
    Raises ``FileNotFoundError`` if the template is not installed.
    """
    from .project import templates_dir

    _validate_template_name(name)
    if (templates_dir() / name).is_dir():
        raise ValueError(
            f"'{name}' is a built-in template and cannot be removed.\n"
            "Only user-installed templates can be removed."
        )
    dest = _user_template_path(name)
    if not dest.exists():
        raise FileNotFoundError(f"Installed template not found: {name!r}")
    shutil.rmtree(dest)

    from . import installed_templates as _meta
    _meta.remove(name)


def list_user_templates() -> list[str]:
    """Return the names of all user-installed templates (simple list)."""
    d = _user_templates_dir()
    if not d.exists():
        return []
    return sorted(p.name for p in d.iterdir() if p.is_dir())


def list_all_templates_detailed() -> list[dict]:
    """Return a rich list of all templates (built-in + user) with metadata.

    Each entry contains:
    - ``name`` (str)
    - ``type``: ``"builtin"`` | ``"user"``
    - ``installed_version``: version string or ``None``
    - ``install_url``: original source URL or ``None``
    """
    from .project import templates_dir, TEMPLATE_DESCRIPTIONS
    from . import installed_templates as _meta

    result: list[dict] = []
    meta_all = _meta.load_all()

    # Built-in templates
    for p in sorted(templates_dir().iterdir()):
        if p.is_dir():
            result.append({
                "name": p.name,
                "type": "builtin",
                "description": TEMPLATE_DESCRIPTIONS.get(p.name, ""),
                "installed_version": None,
                "install_url": None,
            })

    # User-installed templates
    user_dir = _user_templates_dir()
    if user_dir.exists():
        for p in sorted(user_dir.iterdir()):
            if p.is_dir():
                meta = meta_all.get(p.name, {})
                result.append({
                    "name": p.name,
                    "type": "user",
                    "description": "",
                    "installed_version": meta.get("installed_version"),
                    "install_url": meta.get("install_url"),
                })

    return result


def fetch_gallery_json(url: str = GALLERY_JSON_URL) -> dict:
    """Download and parse the gallery index.

    Returns the parsed dict or raises ``ValueError`` on failure.
    """
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        try:
            urllib.request.urlretrieve(url, tmp_path)
        except urllib.error.HTTPError as exc:
            raise ValueError(f"Failed to fetch gallery (HTTP {exc.code}): {url}") from exc
        except urllib.error.URLError as exc:
            raise ValueError(f"Failed to fetch gallery: {exc.reason}") from exc
        return json.loads(tmp_path.read_text(encoding="utf-8"))
    finally:
        tmp_path.unlink(missing_ok=True)


def update_templates(
    name: str | None = None,
    *,
    _gallery_data: dict | None = None,  # injectable for tests
) -> list[dict]:
    """Check for updates and reinstall outdated gallery templates.

    Args:
        name: If given, update only that template. Otherwise update all.
        _gallery_data: Override gallery fetch (used in tests).

    Returns a list of result dicts:
        {"name", "status", "from", "to"}  or  {"name", "status", "reason"}

    Possible statuses: "updated", "up_to_date", "skipped", "error".
    """
    from . import installed_templates as _meta

    # Resolve which templates to check
    if name:
        user = [name] if (_user_template_path(name).is_dir()) else []
        if not user:
            from .project import templates_dir
            if (templates_dir() / name).is_dir():
                return [{"name": name, "status": "skipped", "reason": "builtin template"}]
            return [{"name": name, "status": "error", "reason": "template not found"}]
    else:
        user = list_user_templates()

    if not user:
        return []

    # Fetch gallery
    try:
        gallery_data = _gallery_data if _gallery_data is not None else fetch_gallery_json()
        gallery_by_name: dict[str, dict] = {
            t["name"]: t for t in gallery_data.get("templates", [])
        }
    except ValueError as exc:
        return [{"name": n, "status": "error", "reason": str(exc)} for n in user]

    meta_all = _meta.load_all()
    results: list[dict] = []

    for tname in user:
        meta = meta_all.get(tname, {})
        install_url = meta.get("install_url", "")

        # Skip templates not installed from the gallery
        if not install_url or _GALLERY_HOST not in install_url:
            results.append({
                "name": tname,
                "status": "skipped",
                "reason": "no gallery install_url",
            })
            continue

        gallery_entry = gallery_by_name.get(tname)
        if not gallery_entry:
            results.append({
                "name": tname,
                "status": "skipped",
                "reason": "not found in gallery",
            })
            continue

        current_ver = meta.get("installed_version")
        latest_ver = gallery_entry.get("version")

        if current_ver == latest_ver:
            results.append({
                "name": tname,
                "status": "up_to_date",
                "from": current_ver,
                "to": latest_ver,
            })
            continue

        # Reinstall
        try:
            install_template(install_url, name=tname, force=True)
            results.append({
                "name": tname,
                "status": "updated",
                "from": current_ver,
                "to": latest_ver,
            })
        except Exception as exc:
            results.append({
                "name": tname,
                "status": "error",
                "reason": str(exc),
            })

    return results


# ── Paths ─────────────────────────────────────────────────────────────────


def _user_templates_dir() -> Path:
    """Return the directory holding all user-installed templates."""
    return Path.home() / ".latex-forge" / "templates"


def _user_template_path(name: str) -> Path:
    """Return the install directory for the user-installed template *name*."""
    return _user_templates_dir() / name


# ── Metadata persistence ──────────────────────────────────────────────────


def _write_engine(toml_path: Path, engine: str) -> None:
    """Set ``engine`` in a template's latexforge.toml, keeping its other keys.

    Gallery templates can carry more than the engine (e.g. their
    ``tex_packages`` list), so the file is edited rather than overwritten.
    """
    line = f'engine = "{engine}"'
    if not toml_path.exists():
        toml_path.write_text(line + "\n", encoding="utf-8")
        return
    text = toml_path.read_text(encoding="utf-8")
    updated, count = re.subn(r'(?m)^engine[ \t]*=[ \t]*["\'][^"\'\n]*["\'][ \t]*$', line, text)
    if count == 0:
        updated = line + "\n" + text
    toml_path.write_text(updated, encoding="utf-8")


def _record_installation(name: str, source: str) -> None:
    """Save install metadata; try to fetch the version from gallery if applicable."""
    from . import installed_templates as _meta

    version: str | None = None

    # If this looks like a gallery URL, try to get the version from gallery.json
    if _GALLERY_HOST in source:
        try:
            data = fetch_gallery_json()
            for t in data.get("templates", []):
                if t.get("name") == name or source.rstrip("/").endswith("/" + t.get("name", "")):
                    version = t.get("version")
                    break
        except ValueError:
            pass  # offline or rate-limited — record without version

    _meta.record(name, install_url=source, version=version)


# ── Download helpers ──────────────────────────────────────────────────────


def _download_url(url: str, dest: Path) -> None:
    """Download *url* to *dest*, raising ``ValueError`` with a clear message on failure."""
    print(f"  Downloading {url} …")
    try:
        urllib.request.urlretrieve(url, dest)
    except urllib.error.HTTPError as exc:
        raise ValueError(f"Download failed (HTTP {exc.code}): {url}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Download failed: {exc.reason}") from exc


# ── Install from various sources ──────────────────────────────────────────


def _install_from_github(url: str, name: str | None, force: bool = False) -> tuple[str, Path]:
    """Install from a GitHub URL, optionally pointing to a subdirectory."""
    parts = url.rstrip("/").split("/")

    try:
        gh_idx = next(i for i, p in enumerate(parts) if p == "github.com")
        owner = parts[gh_idx + 1]
        repo = parts[gh_idx + 2]
    except (StopIteration, IndexError):
        raise ValueError(f"Invalid GitHub URL: {url!r}")

    subdir: str | None = None
    if "tree" in parts:
        tree_idx = parts.index("tree")
        if len(parts) > tree_idx + 2:
            subdir = "/".join(parts[tree_idx + 2:])

    template_name = name or (subdir.split("/")[-1] if subdir else repo)

    archive_url = _gallery_archive_url(owner, repo, subdir)
    if archive_url:
        try:
            with tempfile.TemporaryDirectory() as tmp:
                zip_path = Path(tmp) / "template.zip"
                _download_url(archive_url, zip_path)
                return _extract_and_install(
                    zip_path,
                    extract_to=Path(tmp) / "extracted",
                    subdir=None,
                    name=template_name,
                    force=force,
                )
        except (ValueError, zipfile.BadZipFile):
            pass  # archive not available — fall back to a full repo download

    zip_url = f"https://github.com/{owner}/{repo}/archive/HEAD.zip"

    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "repo.zip"
        _download_url(zip_url, zip_path)
        return _extract_and_install(
            zip_path,
            extract_to=Path(tmp) / "extracted",
            subdir=subdir,
            name=template_name,
            force=force,
        )


def _gallery_archive_url(owner: str, repo: str, subdir: str | None) -> str | None:
    """Return the fast per-template archive URL for a gallery template, or None.

    Only matches URLs of the form
    ``github.com/thmsgo18/latex-forge-gallery/tree/main/templates/<category>/<name>``
    — the gallery's own templates, which have a corresponding flat ZIP on the
    `dist` branch. Anything else (forks, other repos, the gallery root) falls
    back to a full repository download.
    """
    if f"{owner}/{repo}" != _GALLERY_HOST or not subdir:
        return None
    parts = subdir.split("/")
    if len(parts) != 3 or parts[0] != "templates":
        return None
    return _GALLERY_ARCHIVE_BASE + parts[2] + ".zip"


def _install_from_zip_url(url: str, name: str | None, force: bool = False) -> tuple[str, Path]:
    """Download a ZIP from *url* and install it as a template."""
    template_name = name or Path(url.rstrip("/")).stem
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "template.zip"
        _download_url(url=url, dest=zip_path)
        return _extract_and_install(
            zip_path,
            extract_to=Path(tmp) / "extracted",
            subdir=None,
            name=template_name,
            force=force,
        )


def _install_from_zip_file(zip_path: Path, name: str | None, force: bool = False) -> tuple[str, Path]:
    """Install a template from a local ZIP file."""
    template_name = name or zip_path.stem
    with tempfile.TemporaryDirectory() as tmp:
        return _extract_and_install(
            zip_path,
            extract_to=Path(tmp) / "extracted",
            subdir=None,
            name=template_name,
            force=force,
        )


def _install_from_dir(source: Path, name: str | None, force: bool = False) -> tuple[str, Path]:
    """Install a template by copying it from a local directory."""
    template_name = name or source.name
    return _copy_to_user_library(source, template_name, force=force)


# ── Core install logic ────────────────────────────────────────────────────


def _extract_and_install(
    zip_path: Path,
    extract_to: Path,
    subdir: str | None,
    name: str,
    force: bool = False,
) -> tuple[str, Path]:
    """Extract *zip_path* and locate the template root inside it, then install it.

    Handles three archive layouts: a flat ZIP with ``main.tex`` at the root
    (the gallery's per-template archives), a GitHub-style ZIP with everything
    under one top-level directory (optionally narrowed to *subdir*), and the
    case where that directory itself wraps a single further subdirectory.
    """
    extract_to.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_to)

    # Case 1: flat ZIP — main.tex sits directly at the extraction root
    if (extract_to / "main.tex").exists():
        return _copy_to_user_library(extract_to, name, force=force)

    # Case 2: GitHub-style ZIP — files are wrapped inside a top-level directory
    top_dirs = [d for d in extract_to.iterdir() if d.is_dir()]
    if not top_dirs:
        raise ValueError("The archive appears to be empty or has no recognizable structure.")
    root = top_dirs[0]

    source = root / subdir if subdir else root

    if not source.exists():
        raise ValueError(
            f"Path {subdir!r} not found inside the archive.\n"
            f"Available entries: {[d.name for d in root.iterdir()]}"
        )

    # If still no main.tex and there is a single sub-directory, descend one level
    if not (source / "main.tex").exists():
        children = [c for c in source.iterdir() if c.is_dir()]
        if len(children) == 1:
            source = children[0]

    return _copy_to_user_library(source, name, force=force)


def _copy_to_user_library(source: Path, name: str, force: bool = False) -> tuple[str, Path]:
    """Validate and copy a template directory into the user library."""
    from .project import templates_dir as _builtin_templates_dir

    _validate_template_name(name)
    if not (source / "main.tex").exists():
        raise ValueError(
            f"No main.tex found in {source}\n"
            "A valid latex-forge template must contain a main.tex file."
        )

    # Prevent overwriting a built-in template
    if (_builtin_templates_dir() / name).is_dir():
        raise ValueError(
            f"'{name}' is the name of a built-in template and cannot be overwritten.\n"
            "Choose a different name with:\n"
            f"  latex-forge template install <source> --name <new-name>"
        )

    dest = _user_template_path(name)
    _user_templates_dir().mkdir(parents=True, exist_ok=True)

    if dest.exists():
        if not force:
            raise FileExistsError(
                f"Template '{name}' is already installed.\n"
                "To overwrite it, add --force:\n"
                f"  latex-forge template install <source> --name {name} --force\n"
                "Or remove it first:\n"
                f"  latex-forge template remove {name}"
            )
        shutil.rmtree(dest)

    shutil.copytree(source, dest)
    return name, dest
