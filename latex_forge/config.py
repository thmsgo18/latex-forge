"""User-level configuration for latex-forge.

Reads optional defaults (e.g. preferred template, output directory) from
``~/.latex-forge.toml`` so the CLI can fall back to user preferences when a
command is run without explicit options.
"""
from __future__ import annotations

import sys
from pathlib import Path

# tomllib is part of the standard library since Python 3.11. On older
# versions, fall back to the third-party "tomli" backport if it's installed;
# otherwise configuration loading is silently disabled (load_config returns {}).
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]

_CONFIG_PATH = Path.home() / ".latex-forge.toml"


def load_config() -> dict:
    """Load the user's configuration file as a dict.

    Returns an empty dict if the file is missing, if no TOML parser is
    available, or if the file can't be parsed — configuration is purely
    optional, so any failure here should not break the CLI.
    """
    if tomllib is None or not _CONFIG_PATH.exists():
        return {}
    try:
        with open(_CONFIG_PATH, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return {}


def get_default_template() -> str | None:
    """Return the user's configured default template name, if any.

    Used by ``latex-forge create`` to preselect a template when ``--template``
    is not passed on the command line.
    """
    value = load_config().get("default_template")
    return value if isinstance(value, str) and value else None


def get_default_output_dir() -> Path | None:
    """Return the user's configured default output directory, if valid.

    The configured path is expanded (``~``) and resolved to an absolute
    path, and is only returned if it actually points to an existing
    directory — an outdated or invalid setting is ignored rather than
    causing an error.
    """
    value = load_config().get("default_output_dir")
    if not isinstance(value, str) or not value:
        return None
    path = Path(value).expanduser().resolve()
    return path if path.is_dir() else None


def get_default_sharing() -> str | None:
    """Return the user's configured default sharing mode, if valid.

    Used by ``latex-forge create`` to preselect a ``.gitignore`` sharing mode
    (``full`` or ``pdf-only``) when ``--sharing`` is not passed on the command
    line and versioning is enabled (``--repo create``/``existing``). An
    unrecognized value — including the old ``none``, now expressed via
    ``--repo none`` instead — is ignored rather than causing an error.
    """
    value = load_config().get("default_sharing")
    if not isinstance(value, str) or value not in ("full", "pdf-only"):
        return None
    return value


def get_default_repo_mode() -> str | None:
    """Return the user's configured default versioning mode, if valid.

    Used by ``latex-forge create`` to preselect how the project is versioned
    (``create`` a new GitHub repo, ``existing`` — already inside a versioned
    folder, or ``none``) when ``--repo`` is not passed on the command line.
    """
    value = load_config().get("default_repo_mode")
    if not isinstance(value, str) or value not in ("create", "existing", "none"):
        return None
    return value


def get_default_visibility() -> str | None:
    """Return the user's configured default new-repo visibility, if valid.

    Used by ``latex-forge create --repo create`` to preselect the visibility
    (``private`` or ``public``) of a newly created GitHub repository when
    ``--visibility`` is not passed on the command line.
    """
    value = load_config().get("default_visibility")
    if not isinstance(value, str) or value not in ("private", "public"):
        return None
    return value


