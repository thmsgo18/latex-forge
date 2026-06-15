"""Core project generation: scaffold a new LaTeX project from a template.

This module implements ``latex-forge create`` (and ``rename``): copying a
template's files into a new project directory, pulling in the local style
files (``.sty``) it depends on, and writing the generated companion files
every project gets — VS Code settings, a ``.gitignore``, standalone setup
scripts, a ``GETTING_STARTED.md``, and an ``AGENTS.md`` briefing for AI
assistants.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path


# Short descriptions shown in `latex-forge list-templates` and the
# interactive template picker.
TEMPLATE_DESCRIPTIONS: dict[str, str] = {
    "blank": "Blank document — minimal pdfLaTeX starter (article class, title, one section)",
    "cv-en": "CV / résumé — education, experience, projects, involvement, skills",
    "cv-fr": "CV — formation, expérience, projets, engagement, compétences",
    "project-report-en": "Project report — ISO/IEEE (requirements, architecture, testing, bibliography, appendices)",
    "project-report-fr": "Rapport de projet — AFNOR/ISO (cahier des charges, architecture, tests, bibliographie, annexes)",
    "research": "Research article — two-column (related work, methodology, experiments, bibliography)",
}

# Build artifacts produced when *compiling* a template's own example PDF;
# never copied into a newly created project (see `should_ignore`/`copy_tree`).
LATEX_BUILD_SUFFIXES = {
    ".aux",
    ".bbl",
    ".bcf",
    ".blg",
    ".fdb_latexmk",
    ".fls",
    ".log",
    ".out",
    ".run.xml",
    ".synctex.gz",
    ".toc",
}

# OS/editor files never copied into a newly created project.
IGNORED_NAMES = {
    ".DS_Store",
}

# Matches \usepackage{...} / \RequirePackage{...} so required local style
# files (styles/packages/*.sty) can be discovered from a template's main.tex.
LOCAL_STYLE_PATTERN = re.compile(
    r"\\(?:RequirePackage|usepackage)(?:\[[^\]]*\])?\{([^}]*)\}"
)

_FORBIDDEN_NAME_CHARS = re.compile(r'[ /\\:*?"<>|]')


_ENGINE_DISPLAY = {
    "lualatex": "LuaLaTeX",
    "xelatex": "XeLaTeX",
    "pdflatex": "pdfLaTeX",
}

_ENGINE_LATEXMK_FLAG = {
    "lualatex": "-lualatex",
    "xelatex": "-xelatex",
    "pdflatex": "-pdf",
}


def _agents_templates_dir() -> Path:
    """Directory of AGENTS.md fragments assembled by `write_agents_md`."""
    return package_dir() / "agents_templates"


def _getting_started_templates_dir() -> Path:
    """Directory of GETTING_STARTED.md fragments assembled by `write_getting_started_guide`."""
    return package_dir() / "getting_started_templates"


def _read_fragment(base_dir: Path, *parts: str) -> str:
    """Read a fragment file (relative to *base_dir*) as text."""
    return base_dir.joinpath(*parts).read_text(encoding="utf-8")


def _read_fragment_if_exists(base_dir: Path, *parts: str) -> str:
    """Read a fragment file, or return "" if it has no entry for this template."""
    path = base_dir.joinpath(*parts)
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _render(template_text: str, replacements: dict[str, str]) -> str:
    """Replace every ``@@TOKEN@@`` in *template_text* with its value from *replacements*.

    Runs two passes so tokens that arrive embedded in another token's
    replacement value (e.g. a ``@@COMPILE_MANUAL@@`` fragment that itself
    contains ``@@NAME@@``) get resolved as well.
    """
    for _ in range(2):
        for token, value in replacements.items():
            template_text = template_text.replace(token, value)
    return template_text


def write_agents_md(target_dir: Path, name: str, template: str, engine: str = "lualatex") -> None:
    """Generate AGENTS.md by assembling the fragments under `agents_templates/`."""
    is_cv = template in ("cv-fr", "cv-en")
    has_bibliography = template in ("project-report-fr", "project-report-en", "research")

    if template == "blank":
        family = "blank"
    elif is_cv:
        family = template
    elif template == "research":
        family = "research"
    else:
        family = "report"
    commands_family = "cv" if is_cv else family

    templates_dir = _agents_templates_dir()

    def read(*parts: str) -> str:
        return _read_fragment(templates_dir, *parts)

    replacements = {
        "@@NAME@@": name,
        "@@TEMPLATE@@": template,
        "@@DESCRIPTION@@": TEMPLATE_DESCRIPTIONS.get(template, template),
        "@@LANG_NOTE@@": "French" if template in ("cv-fr", "project-report-fr") else "English",
        "@@ENGINE@@": engine,
        "@@ENGINE_DISPLAY@@": _ENGINE_DISPLAY.get(engine, engine),
        "@@LATEXMK_FLAG@@": _ENGINE_LATEXMK_FLAG.get(engine, "-lualatex"),
        "@@BIBLIOGRAPHY@@": "biblatex + biber" if has_bibliography else "none",
        "@@COMPILE_MANUAL@@": read(
            "compile", "with_bibliography.md" if has_bibliography else "without_bibliography.md"
        ),
        "@@STRUCTURE_ROWS@@": read("structure", f"{family}.md"),
        "@@CUSTOM_COMMANDS@@": read("commands", f"{commands_family}.md"),
        "@@ADD_CONTENT@@": read("content", f"{family}.md"),
        "@@WRITING_GUIDE@@": read("writing", "academic.md") if family in ("report", "research") else "",
        "@@BIB_ERRORS@@": read("bib_errors.md") if has_bibliography else "",
    }

    content = _render(read("base.md"), replacements)
    (target_dir / "AGENTS.md").write_text(content, encoding="utf-8")


def write_getting_started_guide(
    target_dir: Path, name: str, template: str, engine: str = "lualatex"
) -> None:
    """Generate GETTING_STARTED.md by assembling the fragments under `getting_started_templates/`."""
    templates_dir = _getting_started_templates_dir()

    def read(*parts: str) -> str:
        return _read_fragment(templates_dir, *parts)

    engine_display = _ENGINE_DISPLAY.get(engine, engine)

    if template in ("cv-fr", "cv-en"):
        content = _render(read(f"{template}.md"), {"@@NAME@@": name})
    elif template == "blank":
        content = _render(
            read("blank.md"),
            {"@@NAME@@": name, "@@ENGINE@@": engine, "@@ENGINE_DISPLAY@@": engine_display},
        )
    else:
        content = _render(
            read("generic", "base.md"),
            {
                "@@NAME@@": name,
                "@@ENGINE@@": engine,
                "@@ENGINE_DISPLAY@@": engine_display,
                "@@EXTRA_FOLDERS@@": _read_fragment_if_exists(
                    templates_dir, "generic", "extra_folders", f"{template}.md"
                ),
                "@@BIBLIOGRAPHY_SECTION@@": _read_fragment_if_exists(
                    templates_dir, "generic", "bibliography", f"{template}.md"
                ),
            },
        )

    (target_dir / "GETTING_STARTED.md").write_text(content, encoding="utf-8")


def validate_name(name: str) -> None:
    """Raise ValueError if *name* isn't a safe project/folder name.

    Project names become directory and file names (`<name>/<name>.tex`), so
    spaces, path separators and other filesystem-special characters are
    rejected, as is a leading dot (hidden directory).
    """
    if not name:
        raise ValueError("Project name cannot be empty.")
    if _FORBIDDEN_NAME_CHARS.search(name):
        raise ValueError(
            f"Invalid project name: {name!r}. "
            "Avoid spaces and special characters — use hyphens (e.g. my-project)."
        )
    if name.startswith("."):
        raise ValueError(f"Project name cannot start with a dot: {name!r}.")


def package_dir() -> Path:
    """Return the root directory of the installed latex-forge package."""
    return Path(__file__).resolve().parent


def templates_dir() -> Path:
    """Return the directory containing the built-in templates."""
    return package_dir() / "templates"


def user_templates_dir() -> Path:
    """Directory where user-installed templates are stored."""
    return Path.home() / ".latex-forge" / "templates"


def styles_dir() -> Path:
    """Return the directory containing the shared .sty style files."""
    return package_dir() / "styles" / "packages"


def logos_dir() -> Path:
    """Return the directory containing the bundled university/project logo assets."""
    return package_dir() / "assets" / "logos"


def available_templates() -> list[str]:
    """Return the sorted names of all built-in and user-installed templates."""
    built_in = {p.name for p in templates_dir().iterdir() if p.is_dir()}
    user_dir = user_templates_dir()
    user = {p.name for p in user_dir.iterdir() if p.is_dir()} if user_dir.exists() else set()
    return sorted(built_in | user)


def _find_template_source(template: str) -> Path:
    """Resolve a template name to its source directory (built-in or user-installed)."""
    built_in = templates_dir() / template
    if built_in.is_dir():
        return built_in
    user = user_templates_dir() / template
    if user.is_dir():
        return user
    available = ", ".join(available_templates())
    raise ValueError(f"Unknown template: {template}. Available: {available}")


def _read_template_engine(source_dir: Path) -> str:
    """Read the LaTeX engine from latexforge.toml in the template directory.

    Returns one of 'lualatex', 'xelatex', 'pdflatex'. Defaults to 'lualatex'.
    """
    toml_path = source_dir / "latexforge.toml"
    if not toml_path.exists():
        return "lualatex"
    for line in toml_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("engine"):
            parts = line.split("=", 1)
            if len(parts) == 2:
                value = parts[1].strip().strip('"').strip("'")
                if value in ("lualatex", "xelatex", "pdflatex"):
                    return value
    return "lualatex"


def should_ignore(path: Path) -> bool:
    """Return True if *path* is an OS file or LaTeX build artifact that shouldn't be copied."""
    if path.name in IGNORED_NAMES:
        return True
    return any(path.name.endswith(suffix) for suffix in LATEX_BUILD_SUFFIXES)


def copy_tree(source: Path, destination: Path) -> None:
    """Recursively copy *source* into *destination*, skipping ignored files (see `should_ignore`)."""
    for source_path in source.rglob("*"):
        if should_ignore(source_path):
            continue

        relative_path = source_path.relative_to(source)
        destination_path = destination / relative_path

        if source_path.is_dir():
            destination_path.mkdir(parents=True, exist_ok=True)
            continue

        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)


def patch_local_style(style_path: Path) -> None:
    """Rewrite asset paths in a copied .sty file for its new location.

    Within the latex-forge source tree, style files reference shared assets
    (e.g. logos) via ``../../assets/...`` relative to their original location
    under ``styles/packages/``. Once copied into a project's own
    ``styles/packages/`` directory, those assets live at ``assets/...``
    instead, so the relative prefix is rewritten accordingly.
    """
    if not style_path.exists():
        return
    content = style_path.read_text(encoding="utf-8")
    patched = re.sub(r"\.\./\.\./assets/", "assets/", content)
    if patched != content:
        style_path.write_text(patched, encoding="utf-8")


def local_style_dependencies(file_path: Path) -> list[str]:
    """Return the styles/packages/*.sty files that *file_path* \\usepackage's directly."""
    content = file_path.read_text(encoding="utf-8")
    dependencies: list[str] = []

    for match in LOCAL_STYLE_PATTERN.finditer(content):
        packages = [item.strip() for item in match.group(1).split(",")]
        for package_name in packages:
            if not package_name.startswith("styles/packages/"):
                continue
            style_name = package_name.removeprefix("styles/packages/")
            if not style_name.endswith(".sty"):
                style_name += ".sty"
            dependencies.append(style_name)

    return dependencies


def required_style_files(source_dir: Path) -> list[Path]:
    """Return every styles/packages/*.sty file *source_dir*'s main.tex needs, transitively.

    Starts from main.tex's direct \\usepackage references and follows each
    .sty file's own dependencies, so a style that itself depends on another
    local style is included too.
    """
    main_tex = source_dir / "main.tex"
    if not main_tex.exists():
        return []

    pending = local_style_dependencies(main_tex)
    resolved: set[str] = set()

    while pending:
        style_name = pending.pop()
        if style_name in resolved:
            continue

        style_path = styles_dir() / style_name
        if not style_path.exists():
            continue

        resolved.add(style_name)
        pending.extend(local_style_dependencies(style_path))

    return [styles_dir() / style_name for style_name in sorted(resolved)]


def write_project_vscode_settings(target_dir: Path, engine: str = "lualatex") -> None:
    """Write .vscode/settings.json configuring LaTeX Workshop for *engine*.

    Defines a single latexmk-based recipe/tool named after *engine* (e.g.
    "lualatexmk") so the generated project compiles on save with the right
    compiler; `build.py`'s `_detect_latexmk_flag` reads this file back to
    keep `latex-forge build` in sync with VS Code.
    """
    vscode_dir = target_dir / ".vscode"
    vscode_dir.mkdir(parents=True, exist_ok=True)

    latexmk_flag = _ENGINE_LATEXMK_FLAG.get(engine, "-lualatex")
    tool_name = f"{engine}mk"

    settings = {
        "[latex]": {"editor.wordWrap": "on"},
        "[tex]": {"editor.wordWrap": "on"},
        "latex-workshop.view.pdf.viewer": "tab",
        "latex-workshop.latex.autoBuild.run": "onSave",
        "latex-workshop.latex.recipe.default": "first",
        "latex-workshop.latex.outDir": "%DIR%/build",
        "latex-workshop.latex.clean.subfolder.enabled": True,
        "latex-workshop.linting.chktex.enabled": False,
        "latex-workshop.linting.lacheck.enabled": False,
        "latex-workshop.latex.tools": [
            {
                "name": tool_name,
                "command": "latexmk",
                "args": [
                    "-synctex=1",
                    "-interaction=nonstopmode",
                    "-file-line-error",
                    latexmk_flag,
                    "-outdir=%OUTDIR%",
                    "%DOC%",
                ],
            }
        ],
        "latex-workshop.latex.recipes": [
            {"name": tool_name, "tools": [tool_name]}
        ],
    }

    settings_path = vscode_dir / "settings.json"
    settings_path.write_text(
        json.dumps(settings, indent=2) + "\n",
        encoding="utf-8",
    )


def write_project_vscode_extensions(target_dir: Path) -> None:
    """Copy latex-forge's recommended .vscode/extensions.json into the new project."""
    source_path = package_dir() / ".vscode" / "extensions.json"
    if not source_path.exists():
        return

    vscode_dir = target_dir / ".vscode"
    vscode_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, vscode_dir / "extensions.json")


def write_project_gitignore(target_dir: Path) -> None:
    """Write a .gitignore covering LaTeX build artifacts for the new project."""
    gitignore_content = """build/
.DS_Store
*.aux
*.acn
*.acr
*.alg
*.bbl
*.bcf
*.blg
*.dvi
*.fdb_latexmk
*.fls
*.glg
*.glo
*.gls
*.idx
*.ilg
*.ind
*.ist
*.lof
*.log
*.lot
*.nav
*.nlo
*.out
*.ps
*.run.xml
*.snm
*.synctex.gz
*.toc
*.vrb
*.xdv
_minted-*/
"""
    (target_dir / ".gitignore").write_text(gitignore_content, encoding="utf-8")


def write_project_setup_scripts(target_dir: Path) -> None:
    """Write standalone scripts/setup.{py,sh,bat} into the new project.

    These scripts are copied verbatim from ``scripts_templates/`` and are a
    self-contained re-implementation of the checks in ``latex_forge/setup.py``,
    so a project can be set up on a machine that doesn't have latex-forge
    installed (e.g. after cloning it from GitHub) by running
    ``scripts/setup.sh`` / ``scripts/setup.bat`` directly.
    """
    scripts_dir = target_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    templates_dir = package_dir() / "scripts_templates"
    for filename in ("setup.py", "setup.sh", "setup.bat"):
        (scripts_dir / filename).write_text(_read_fragment(templates_dir, filename), encoding="utf-8")

    (scripts_dir / "setup.py").chmod(0o755)
    (scripts_dir / "setup.sh").chmod(0o755)


def init_git_repo(target_dir: Path) -> bool:
    """Initialize a git repository with an initial commit. Returns True on success."""
    if shutil.which("git") is None:
        return False
    try:
        subprocess.run(["git", "init"], cwd=target_dir, capture_output=True, check=True)
        subprocess.run(["git", "add", "-A"], cwd=target_dir, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=target_dir,
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return False
    return True


def create_project(
    name: str,
    template: str,
    output_dir: Path | None = None,
    init_git: bool = False,
) -> tuple[Path, Path]:
    """Scaffold a new project named *name* from *template* under *output_dir*.

    Copies the template, brings in its required local .sty files and shared
    logo assets, generates the VS Code/.gitignore/setup-script/GETTING_STARTED/
    AGENTS.md companion files, applies the user's saved profile (if any), and
    optionally initializes a git repository. The partially created directory
    is removed if any step fails.

    Returns ``(target_dir, main_tex_file)``.
    """
    validate_name(name)

    source_dir = _find_template_source(template)

    base_dir = (output_dir or Path.cwd()).resolve()
    target_dir = base_dir / name
    main_tex_file = target_dir / f"{name}.tex"
    local_style_dir = target_dir / "styles" / "packages"

    if target_dir.exists():
        raise FileExistsError(f"Folder already exists: {target_dir}")

    target_dir.mkdir(parents=True, exist_ok=False)
    try:
        copy_tree(source_dir, target_dir)

        copied_main = target_dir / "main.tex"
        if copied_main.exists():
            copied_main.rename(main_tex_file)

        local_style_dir.mkdir(parents=True, exist_ok=True)
        for style_path in required_style_files(source_dir):
            shutil.copy2(style_path, local_style_dir / style_path.name)

        (target_dir / "assets" / "logos").mkdir(parents=True, exist_ok=True)
        for copied_style in local_style_dir.glob("*.sty"):
            patch_local_style(copied_style)

        for logo_path in sorted(logos_dir().iterdir()):
            if should_ignore(logo_path):
                continue
            destination = target_dir / "assets" / "logos" / logo_path.name
            if logo_path.is_dir():
                shutil.copytree(logo_path, destination)
            else:
                shutil.copy2(logo_path, destination)

        (target_dir / "assets" / "logos" / ".gitkeep").touch(exist_ok=True)
        engine = _read_template_engine(source_dir)
        write_project_vscode_settings(target_dir, engine)
        write_project_vscode_extensions(target_dir)
        write_project_gitignore(target_dir)
        write_project_setup_scripts(target_dir)

        write_getting_started_guide(target_dir, name, template, engine=engine)
        write_agents_md(target_dir, name, template, engine=engine)

        from .profile import apply_profile_to_project, load_profile
        apply_profile_to_project(target_dir, template, load_profile())

        if init_git:
            init_git_repo(target_dir)
    except Exception:
        shutil.rmtree(target_dir, ignore_errors=True)
        raise

    return target_dir, main_tex_file


def _rename(old_dir: Path, new_name: str) -> tuple[Path, Path]:
    """Rename a project directory and every file that follows the `<old_name>.*` convention.

    Renames the main .tex file, any root files named after the project
    (e.g. a project-specific .bib), and matching build/ artifacts, then
    renames the directory itself.
    """
    validate_name(new_name)

    new_dir = old_dir.parent / new_name
    old_name = old_dir.name

    if not old_dir.is_dir():
        raise FileNotFoundError(f"Project not found: {old_dir}")
    if new_dir.exists():
        raise FileExistsError(f"Target folder already exists: {new_dir}")

    old_main_tex = old_dir / f"{old_name}.tex"
    new_main_tex = old_dir / f"{new_name}.tex"
    if not old_main_tex.exists():
        raise FileNotFoundError(
            f"Main file not found: {old_main_tex}. "
            "The main file name must match the folder name."
        )

    old_main_tex.rename(new_main_tex)

    # Keep the full multi-part extension (e.g. .synctex.gz), not just .suffix
    build_dir = old_dir / "build"
    if build_dir.is_dir():
        for build_file in build_dir.glob(f"{old_name}.*"):
            extension = build_file.name[len(old_name):]
            build_file.rename(build_dir / f"{new_name}{extension}")

    for root_file in old_dir.glob(f"{old_name}.*"):
        if root_file.name == new_main_tex.name:
            continue
        extension = root_file.name[len(old_name):]
        root_file.rename(old_dir / f"{new_name}{extension}")

    # Windows: cannot rename a directory that is the current working directory.
    if Path.cwd().resolve() == old_dir.resolve():
        os.chdir(old_dir.parent)
    old_dir.rename(new_dir)
    return new_dir, new_dir / f"{new_name}.tex"


def rename_project(old_name: str, new_name: str) -> tuple[Path, Path]:
    """Rename the project ``<old_name>`` found in the current directory to *new_name*."""
    return _rename(Path.cwd().resolve() / old_name, new_name)


def rename_current_project(new_name: str) -> tuple[Path, Path]:
    """Rename the project whose directory is the current working directory to *new_name*."""
    return _rename(Path.cwd().resolve(), new_name)
