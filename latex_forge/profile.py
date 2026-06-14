"""User profile — read, write and apply personal information to projects.

The profile (name, email, university, etc.) is stored once in
``~/.latex-forge/profile.toml`` and then substituted into the placeholders of
every new project (CVs, reports, gallery templates), so the user doesn't have
to retype the same information each time they run ``latex-forge new``.
"""
from __future__ import annotations

import re
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]


# ── Schema ────────────────────────────────────────────────────────────────

# Defines every field the interactive `latex-forge profile set` prompt asks
# for, its display label, and which section of the TOML file it belongs to.
# (key, display_label, section)
PROFILE_SCHEMA: list[tuple[str, str, str]] = [
    ("first_name",  "First name",            "identity"),
    ("last_name",   "Last name",             "identity"),
    ("email",       "Email",                 "identity"),
    ("phone",       "Phone",                 "identity"),
    ("website",     "Website",               "identity"),
    ("github",      "GitHub username",       "online"),
    ("linkedin",    "LinkedIn username",     "online"),
    ("university",  "University",            "academic"),
    ("faculty",     "Faculty / UFR",         "academic"),
    ("program",     "Program / Formation",   "academic"),
    ("supervisor",  "Supervisor",            "academic"),
    ("company",     "Company",               "professional"),
    ("department",  "Department / Service",  "professional"),
    ("job_title",   "Job title",             "professional"),
]

# Human-readable headers written as comments above each group of fields in
# the generated profile.toml, in PROFILE_SCHEMA's grouping order.
SECTION_HEADERS: dict[str, str] = {
    "identity":     "Identity",
    "online":       "Online profiles",
    "academic":     "Academic",
    "professional": "Professional",
}


# ── File path ─────────────────────────────────────────────────────────────


def profile_path() -> Path:
    """Return the path to the user's stored profile file."""
    return Path.home() / ".latex-forge" / "profile.toml"


# ── Load / Save / Clear ───────────────────────────────────────────────────


def load_profile() -> dict[str, str]:
    """Return the stored profile as a flat dict.

    Returns {} if no file exists or if the file is corrupted, so a broken
    profile never blocks project creation.
    """
    p = profile_path()
    if not p.exists():
        return {}
    try:
        with open(p, "rb") as fh:
            data = tomllib.load(fh)
    except (tomllib.TOMLDecodeError, OSError):
        return {}
    return {k: str(v) for k, v in data.items() if isinstance(v, str)}


def save_profile(values: dict[str, str]) -> None:
    """Persist *values* to the profile file with readable section comments."""
    p = profile_path()
    p.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    current_section: str | None = None

    for key, _label, section in PROFILE_SCHEMA:
        if section != current_section:
            if lines:
                lines.append("")
            header = SECTION_HEADERS[section]
            lines.append(f"# ── {header} " + "─" * (55 - len(header)))
            current_section = section
        value = values.get(key, "").replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'{key} = "{value}"')

    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


def clear_profile() -> None:
    """Delete the profile file."""
    p = profile_path()
    if p.exists():
        p.unlink()


# ── Apply profile to a newly created project ──────────────────────────────


def apply_profile_to_project(
    target_dir: Path, template: str, profile: dict[str, str]
) -> None:
    """Substitute profile values into a newly created project.

    Works for all gallery templates whose metadata.tex uses the standard
    newcommand / renewcommand / def patterns defined in this module.
    Silent no-op for unset profile fields or missing commands.
    """
    if not profile:
        return

    first = profile.get("first_name", "").strip()
    last  = profile.get("last_name",  "").strip()
    full_name = f"{first} {last}".strip()

    if template in ("cv-en", "cv-fr"):
        _apply_cv(target_dir, template, profile, full_name)
    elif template in ("project-report-en", "project-report-fr", "research", "blank"):
        _apply_metadata(target_dir, template, profile, full_name)
    else:
        # All other gallery templates: inject into frontmatter/metadata.tex
        # using whichever standard commands the template declares.
        _apply_gallery_metadata(target_dir, profile, full_name)


# ── CV templates ──────────────────────────────────────────────────────────


def _apply_cv(
    target_dir: Path, template: str, profile: dict[str, str], full_name: str
) -> None:
    """Fill in personal details for the built-in cv-en / cv-fr templates.

    Handles both the built-in layout (placeholders directly in
    sections/heading.tex or en-tete.tex) and the gallery-style layout
    (frontmatter/metadata.tex with \\cvname / \\cvemail / ... commands),
    since either file may be present depending on how the template was
    generated.
    """
    if template == "cv-en":
        heading_file  = target_dir / "sections" / "heading.tex"
        default_name  = "First LAST"
        default_phone = "+1 000.000.0000"
        default_li    = "first-last"
    else:
        heading_file  = target_dir / "sections" / "en-tete.tex"
        default_name  = "Prénom NOM"
        default_phone = "+33 6.00.00.00.00"
        default_li    = "prenom-nom"

    metadata_file = target_dir / "frontmatter" / "metadata.tex"

    # Built-in template format: personal info lives in the heading section file
    if heading_file.exists():
        content = heading_file.read_text(encoding="utf-8")

        if full_name:
            content = content.replace(default_name, full_name)
        if profile.get("phone"):
            content = content.replace(default_phone, profile["phone"])
        if profile.get("email"):
            content = content.replace("email@example.com", profile["email"])
        if profile.get("github"):
            g = profile["github"]
            content = content.replace(
                r"\href{https://github.com/username}{\texttt{username}}",
                r"\href{https://github.com/" + g + r"}{\texttt{" + g + "}}",
            )
        if profile.get("linkedin"):
            li = profile["linkedin"]
            content = content.replace(
                r"\href{https://www.linkedin.com/in/" + default_li + r"/}{\texttt{" + default_li + "}}",
                r"\href{https://www.linkedin.com/in/" + li + r"/}{\texttt{" + li + "}}",
            )

        heading_file.write_text(content, encoding="utf-8")

    # Gallery / installed template format: personal info in frontmatter/metadata.tex
    # via \newcommand{\cvname}{...}, \newcommand{\cvemail}{...} etc.
    if metadata_file.exists():
        content = metadata_file.read_text(encoding="utf-8")

        if full_name:
            content = _replace_newcmd(content, "cvname", full_name)
        if profile.get("phone"):
            content = _replace_newcmd(content, "cvphone", profile["phone"])
        if profile.get("email"):
            content = _replace_newcmd(content, "cvemail", profile["email"])
        if profile.get("github"):
            content = _replace_newcmd(content, "cvgithub", profile["github"])
        if profile.get("linkedin"):
            content = _replace_newcmd(content, "cvlinkedin", profile["linkedin"])

        metadata_file.write_text(content, encoding="utf-8")


# ── Report / blank templates ──────────────────────────────────────────────


def _apply_metadata(
    target_dir: Path, template: str, profile: dict[str, str], full_name: str
) -> None:
    """Fill in personal/institutional details for report-style templates.

    Covers ``blank`` (plain \\author{...}) and the project-report-en/fr and
    research templates, which use \\newcommand placeholders and an
    \\addauthor{LASTNAME Firstname}{...} entry following each template's
    national naming convention.
    """
    metadata = target_dir / "frontmatter" / "metadata.tex"
    if not metadata.exists():
        return

    content = metadata.read_text(encoding="utf-8")

    if template == "blank":
        # \author{Author Name}
        if full_name:
            content = _replace_cmd(content, "author", full_name)
    else:
        # project-report-en/fr, research
        if profile.get("university"):
            content = _replace_newcmd(content, "universityname", profile["university"])
        if profile.get("program"):
            content = _replace_newcmd(content, "facultyname", profile["program"])

        first = profile.get("first_name", "").strip()
        last  = profile.get("last_name",  "").strip()
        if first or last:
            # Templates use "LASTNAME Firstname" / "NOM Prenom" convention
            author_arg = f"{last} {first}".strip()
            placeholder = "NOM Prenom" if template == "project-report-fr" else "LASTNAME Firstname"
            content = _replace_addauthor(content, placeholder, author_arg)

    metadata.write_text(content, encoding="utf-8")


# ── Gallery templates ─────────────────────────────────────────────────────


def _apply_gallery_metadata(
    target_dir: Path, profile: dict[str, str], full_name: str
) -> None:
    """Apply profile to any gallery template using standard command patterns.

    Tries every known standard command; _replace_* helpers are no-ops when
    the command is not present in the file, so this is always safe.
    """
    metadata = target_dir / "frontmatter" / "metadata.tex"
    if not metadata.exists():
        return

    content = metadata.read_text(encoding="utf-8")

    # ── Non-CV author fields ──────────────────────────────────────────────
    if full_name:
        content = _replace_newcmd(content, "authorname", full_name)
    if profile.get("email"):
        content = _replace_newcmd(content, "authoremail", profile["email"])
    if profile.get("phone"):
        content = _replace_newcmd(content, "authorphone", profile["phone"])

    # ── CV author fields ──────────────────────────────────────────────────
    if full_name:
        content = _replace_newcmd(content,   "cvname", full_name)
        content = _replace_renewcmd(content, "cvname", full_name)  # twenty-seconds-cv uses \renewcommand
    if profile.get("first_name"):
        content = _replace_newcmd(content, "cvfirstname", profile["first_name"])
    if profile.get("last_name"):
        content = _replace_newcmd(content, "cvlastname", profile["last_name"])
    if profile.get("email"):
        content = _replace_newcmd(content, "cvemail",  profile["email"])
        content = _replace_newcmd(content, "cvmail",   profile["email"])  # twenty-seconds-cv variant
    if profile.get("phone"):
        content = _replace_newcmd(content, "cvphone",  profile["phone"])
    if profile.get("github"):
        content = _replace_newcmd(content, "cvgithub",   profile["github"])
    if profile.get("linkedin"):
        content = _replace_newcmd(content, "cvlinkedin", profile["linkedin"])

    # ── Academic / institutional fields ──────────────────────────────────
    if profile.get("university"):
        content = _replace_newcmd(content, "universityname", profile["university"])
        content = _replace_newcmd(content, "cvuniversity",   profile["university"])
    if profile.get("program"):
        content = _replace_newcmd(content, "facultyname", profile["program"])
        content = _replace_newcmd(content, "cvposition",  profile["program"])
    if profile.get("supervisor"):
        content = _replace_newcmd(content, "supervisorname", profile["supervisor"])

    # ── Project-UPC: uses \renewcommand ──────────────────────────────────
    if profile.get("supervisor"):
        content = _replace_renewcmd(content, "projetEncadrant", profile["supervisor"])
    if full_name:
        # UPC convention: "NOM Prenom" — swap last/first for the first author
        first = profile.get("first_name", "").strip()
        last  = profile.get("last_name",  "").strip()
        upc_author = f"{last} {first}".strip() if (first or last) else full_name
        content = _replace_renewcmd(content, "projetAuteurs", upc_author)

    metadata.write_text(content, encoding="utf-8")


# ── Regex helpers ─────────────────────────────────────────────────────────


def _replace_newcmd(content: str, cmd: str, value: str) -> str:
    r"""\\newcommand{\cmd}{OLD} → \\newcommand{\cmd}{value}."""
    pat = re.compile(r"(\\newcommand\{\\" + re.escape(cmd) + r"\}\{)[^}]*(\})")
    return pat.sub(lambda m: m.group(1) + value + m.group(2), content)


def _replace_renewcmd(content: str, cmd: str, value: str) -> str:
    r"""\\renewcommand{\cmd}{OLD} → \\renewcommand{\cmd}{value}."""
    pat = re.compile(r"(\\renewcommand\{\\" + re.escape(cmd) + r"\}\{)[^}]*(\})")
    return pat.sub(lambda m: m.group(1) + value + m.group(2), content)


def _replace_cmd(content: str, cmd: str, value: str) -> str:
    r"""\\cmd{...} → \\cmd{value}. Applied only to non-commented lines."""
    pat = re.compile(r"(^\s*\\" + re.escape(cmd) + r"\{)[^}]*(\})", re.MULTILINE)
    return pat.sub(lambda m: m.group(1) + value + m.group(2), content)


def _replace_addauthor(content: str, placeholder: str, value: str) -> str:
    r"""Replace first \\addauthor{placeholder}{} → \\addauthor{value}{}."""
    pat = re.compile(r"(\\addauthor\{)" + re.escape(placeholder) + r"(\}\{)")
    return pat.sub(lambda m: m.group(1) + value + m.group(2), content, count=1)
