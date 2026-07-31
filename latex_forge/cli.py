"""Command-line interface for latex-forge.

Defines the ``latex-forge`` argument parser (``build_parser``) and dispatches
each subcommand to the relevant module (project creation, build, template
management, profile, diagnostics, ...) from ``main``, which is the entry
point registered as the ``latex-forge`` console script.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import argcomplete

from .config import (
    get_default_output_dir,
    get_default_repo_mode,
    get_default_sharing,
    get_default_template,
    get_default_visibility,
)
from .github import gh_authenticated, gh_cli_available
from .project import (
    REPO_MODES,
    TEMPLATE_DESCRIPTIONS,
    available_templates,
    create_project,
    rename_current_project,
    rename_project,
    templates_dir,
    validate_name,
)
from .setup import (
    _prompt_yes_no,
    is_first_run,
    mark_initialized,
    offer_open_vscode,
    run_first_launch_check,
    run_setup,
    warn_if_latex_missing,
)


_SHARING_CHOICES = ("full", "pdf-only")


def _get_version() -> str:
    """Return the installed latex-forge version, or "unknown" if not packaged."""
    try:
        return version("latex-forge")
    except PackageNotFoundError:
        return "unknown"


def _is_interactive() -> bool:
    """Return True if stdin is a TTY, i.e. the user can be prompted."""
    try:
        return sys.stdin.isatty()
    except Exception:
        return False


def _ask_project_name() -> str:
    """Prompt for a project name until a valid one is entered (or exit on EOF/Ctrl-C)."""
    while True:
        try:
            name = input("Project name: ").strip()
        except (EOFError, OSError, KeyboardInterrupt):
            print("")
            sys.exit(1)
        try:
            validate_name(name)
            return name
        except ValueError as exc:
            print(str(exc))


def _select_template_interactively() -> str:
    """Print a numbered list of available templates and prompt for a choice."""
    templates = available_templates()
    width = max(len(t) for t in templates)
    print("Available templates:")
    for i, t in enumerate(templates, 1):
        desc = TEMPLATE_DESCRIPTIONS.get(t, "")
        suffix = f"  {desc}" if desc else ""
        print(f"  {i}. {t:<{width}}{suffix}")
    while True:
        try:
            answer = input(f"Choose a template [1-{len(templates)}]: ").strip()
            idx = int(answer) - 1
            if 0 <= idx < len(templates):
                return templates[idx]
        except (EOFError, OSError, KeyboardInterrupt):
            print("")
            sys.exit(1)
        except ValueError:
            pass
        print(f"Please enter a number between 1 and {len(templates)}.")


def _ask_output_dir() -> Path:
    """Prompt for the output directory, defaulting to the configured or current directory.

    Creates the chosen directory if it doesn't exist yet.
    """
    config_dir = get_default_output_dir()
    default = config_dir if config_dir is not None else Path.cwd()
    try:
        answer = input(f"Create project in [{default}]: ").strip()
    except (EOFError, OSError, KeyboardInterrupt):
        print("")
        sys.exit(1)
    if not answer:
        return default
    path = Path(answer).expanduser().resolve()
    if not path.exists():
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            print(f"Cannot create directory: {exc}", file=sys.stderr)
            sys.exit(1)
    return path


_REPO_MODE_CHOICES = [
    ("create", "Create a new GitHub repository for this project"),
    ("existing", "This folder is already inside a versioned (e.g. GitHub) folder"),
    ("none", "Don't version this project"),
]


def _ask_repo_mode() -> str:
    """Print a numbered list of versioning modes and prompt for a choice."""
    default_mode = get_default_repo_mode() or "none"
    print("How should this project be versioned?")
    for i, (mode, desc) in enumerate(_REPO_MODE_CHOICES, 1):
        marker = " (default)" if mode == default_mode else ""
        print(f"  {i}. {desc}{marker}")
    while True:
        try:
            answer = input(f"Choose [1-{len(_REPO_MODE_CHOICES)}]: ").strip()
        except (EOFError, OSError, KeyboardInterrupt):
            print("")
            sys.exit(1)
        if not answer:
            return default_mode
        try:
            idx = int(answer) - 1
            if 0 <= idx < len(_REPO_MODE_CHOICES):
                return _REPO_MODE_CHOICES[idx][0]
        except ValueError:
            pass
        print(f"Please enter a number between 1 and {len(_REPO_MODE_CHOICES)}.")


def _ask_repo_name(default: str) -> str:
    """Prompt for the new GitHub repository's name, defaulting to the project name."""
    try:
        answer = input(f"GitHub repository name [{default}]: ").strip()
    except (EOFError, OSError, KeyboardInterrupt):
        print("")
        sys.exit(1)
    return answer or default


def _ask_visibility() -> str:
    """Prompt for the new GitHub repository's visibility, defaulting to private."""
    default_visibility = get_default_visibility() or "private"
    try:
        answer = input(f"Visibility [private/public] [{default_visibility}]: ").strip().lower()
    except (EOFError, OSError, KeyboardInterrupt):
        print("")
        sys.exit(1)
    if not answer:
        return default_visibility
    return "public" if answer.startswith("pub") else "private"


def _ask_sharing() -> str:
    """Prompt for what the .gitignore should track, defaulting to 'full'."""
    default_sharing = get_default_sharing() or "full"
    try:
        answer = input(
            f"What should be versioned — full sources + PDF, or pdf-only? [full/pdf-only] [{default_sharing}]: "
        ).strip().lower()
    except (EOFError, OSError, KeyboardInterrupt):
        print("")
        sys.exit(1)
    if not answer:
        return default_sharing
    return "pdf-only" if answer.startswith("pdf") else "full"


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argparse parser with all latex-forge subcommands."""
    parser = argparse.ArgumentParser(
        prog="latex-forge",
        description="Utilities for generating standalone LaTeX projects from the toolbox.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_get_version()}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser(
        "create",
        help="Create a new LaTeX project from a template.",
    )
    create_parser.add_argument(
        "--name",
        default=None,
        help="Name of the project (prompted interactively if omitted).",
    )
    template_arg = create_parser.add_argument(
        "--template",
        default=None,
        help="Template name to use (prompted interactively if omitted).",
    )
    template_arg.completer = lambda **kwargs: available_templates()
    create_parser.add_argument(
        "--output",
        default=None,
        help="Directory where the project will be created (default: current directory).",
    )
    create_parser.add_argument(
        "--repo",
        choices=REPO_MODES,
        default=None,
        help=(
            "How to version the project: 'create' a new GitHub repository (needs "
            "--repo-name/--visibility and the GitHub CLI, authenticated), 'existing' "
            "— this folder already lives inside a versioned (e.g. GitHub) folder, so "
            "nothing git-related is touched, or 'none' (no versioning at all). "
            "Defaults to 'default_repo_mode' in ~/.latex-forge.toml, or 'none'."
        ),
    )
    create_parser.add_argument(
        "--repo-name",
        default=None,
        help="Name of the GitHub repository to create (only with --repo create; defaults to the project name).",
    )
    create_parser.add_argument(
        "--visibility",
        choices=("private", "public"),
        default=None,
        help=(
            "Visibility of the new GitHub repository (only with --repo create). "
            "Defaults to 'default_visibility' in ~/.latex-forge.toml, or 'private'."
        ),
    )
    create_parser.add_argument(
        "--sharing",
        choices=_SHARING_CHOICES,
        default=None,
        help=(
            "What the generated .gitignore tracks (only with --repo create/existing): "
            "'full' (sources + compiled PDF) or 'pdf-only' (compiled PDF only). "
            "Defaults to 'default_sharing' in ~/.latex-forge.toml, or 'full'."
        ),
    )
    create_parser.add_argument(
        "--build-before-commit",
        action="store_true",
        help=(
            "With --repo create, build the project once before the initial commit "
            "so the PDF is included right away instead of only after your first "
            "manual build."
        ),
    )

    build_subparser = subparsers.add_parser(
        "build",
        help="Compile the project to PDF with latexmk.",
    )
    build_subparser.add_argument(
        "project",
        nargs="?",
        default=None,
        help="Project directory (default: current directory).",
    )
    build_subparser.add_argument(
        "--clean",
        action="store_true",
        help="Delete the build/ directory before compiling.",
    )
    build_subparser.add_argument(
        "--verbose",
        action="store_true",
        help="Show the full latexmk output instead of errors only.",
    )

    watch_parser = subparsers.add_parser(
        "watch",
        help="Recompile automatically on every save (latexmk -pvc).",
    )
    watch_parser.add_argument(
        "project",
        nargs="?",
        default=None,
        help="Project directory (default: current directory).",
    )
    watch_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show the full latexmk output instead of errors only.",
    )

    export_parser = subparsers.add_parser(
        "export",
        help="Bundle the project sources and PDF into a clean ZIP for submission.",
    )
    export_parser.add_argument(
        "project",
        nargs="?",
        default=None,
        help="Project directory (default: current directory).",
    )
    export_parser.add_argument(
        "--output",
        default=None,
        help="Path of the ZIP archive to create (default: <project>-export.zip next to it).",
    )

    rename_parser = subparsers.add_parser(
        "rename",
        help="Rename a generated LaTeX project folder and its main .tex file.",
    )
    rename_parser.add_argument(
        "names",
        nargs="+",
        help="Use `old_name new_name` from the parent folder, or only `new_name` from inside the project folder.",
    )

    setup_parser = subparsers.add_parser(
        "setup",
        help="Install VS Code extensions when possible and check LaTeX prerequisites.",
    )
    setup_parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check the current environment without installing VS Code extensions.",
    )
    setup_parser.add_argument(
        "--skip-extensions",
        action="store_true",
        help="Skip VS Code extension installation.",
    )
    setup_parser.add_argument(
        "--install-tex",
        action="store_true",
        help="Try to install a LaTeX distribution with a common package manager for the current OS.",
    )
    setup_parser.add_argument(
        "--install-gh",
        action="store_true",
        help=(
            "Try to install the GitHub CLI (gh) with a common package manager for the current OS. "
            "Needed for `latex-forge create --repo create`."
        ),
    )

    subparsers.add_parser(
        "list-templates",
        help="List the available templates.",
    )

    template_parser = subparsers.add_parser(
        "template",
        help="Install, remove or list templates.",
    )
    template_sub = template_parser.add_subparsers(dest="template_command", required=True)

    t_install = template_sub.add_parser(
        "install",
        help="Install a template from a GitHub URL, ZIP URL, or local path.",
    )
    t_install.add_argument(
        "source",
        help="GitHub URL, ZIP URL, local directory, or local .zip file.",
    )
    t_install.add_argument(
        "--name",
        default=None,
        help="Name to give the installed template (defaults to repo/folder name).",
    )
    t_install.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing user-installed template with the same name.",
    )
    t_install.add_argument(
        "--engine",
        default=None,
        choices=["lualatex", "xelatex", "pdflatex"],
        help=(
            "LaTeX engine for this template, written to its latexforge.toml "
            "(use if the template doesn't already declare one). "
            "See TEMPLATE_COMPATIBILITY.md."
        ),
    )

    t_list = template_sub.add_parser(
        "list",
        help="List built-in and user-installed templates.",
    )
    t_list.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output the template list as JSON.",
    )

    t_update = template_sub.add_parser(
        "update",
        help="Update user-installed templates from the gallery.",
    )
    t_update.add_argument(
        "name",
        nargs="?",
        default=None,
        help="Name of the template to update (updates all if omitted).",
    )
    t_update.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output update results as JSON.",
    )

    # ── profile ──────────────────────────────────────────────────────────
    profile_parser = subparsers.add_parser(
        "profile",
        help="Manage your user profile (auto-fills new projects).",
    )
    profile_sub = profile_parser.add_subparsers(dest="profile_command", required=True)
    profile_sub.add_parser(
        "set",
        help="Set or update profile values interactively.",
    )
    profile_sub.add_parser(
        "show",
        help="Display the current profile.",
    )
    profile_sub.add_parser(
        "clear",
        help="Delete the profile.",
    )

    t_remove = template_sub.add_parser(
        "remove",
        help="Remove a user-installed template.",
    )
    t_remove.add_argument("name", help="Name of the template to remove.")

    diagnose_parser = subparsers.add_parser(
        "diagnose",
        help="Check the latex-forge environment (LaTeX, latexmk, profile, etc.).",
    )
    diagnose_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output diagnostics as JSON.",
    )

    completion_parser = subparsers.add_parser(
        "completion",
        help="Print shell completion setup code.",
    )
    completion_parser.add_argument(
        "--shell",
        choices=["bash", "zsh", "fish"],
        default=None,
        help="Shell type (auto-detected from $SHELL if omitted).",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch to the handler for ``args.command``.

    Each branch below corresponds to one top-level subcommand (and, for
    ``profile``/``template``, a nested sub-subcommand). Imports of the
    relevant modules are deferred to each branch to keep CLI startup fast.
    Returns the process exit code.
    """
    parser = build_parser()
    argcomplete.autocomplete(parser)
    args = parser.parse_args(argv)

    # ── latex-forge profile (set / show / clear) ─────────────────────────
    if args.command == "profile":
        from .profile import (
            PROFILE_SCHEMA,
            SECTION_HEADERS,
            clear_profile,
            load_profile,
            profile_path,
            save_profile,
        )

        if args.profile_command == "set":
            if not _is_interactive():
                print("'profile set' requires an interactive terminal.", file=sys.stderr)
                return 1

            current = load_profile()
            new_values: dict[str, str] = dict(current)

            print("Setting up your latex-forge profile.")
            print("Press Enter to keep the current value. Leave blank to clear a field.")
            print(f"Saved to: {profile_path()}")
            print()

            prev_section: str | None = None
            for key, label, section in PROFILE_SCHEMA:
                if section != prev_section:
                    header = SECTION_HEADERS[section]
                    print(f"── {header} " + "─" * (52 - len(header)))
                    prev_section = section
                cur = current.get(key, "")
                prompt = f"  {label} [{cur}]: " if cur else f"  {label}: "
                try:
                    answer = input(prompt).strip()
                except (EOFError, OSError, KeyboardInterrupt):
                    print("")
                    return 1
                if answer:
                    new_values[key] = answer
                elif key not in new_values:
                    new_values[key] = ""

            save_profile(new_values)
            print()
            print(f"Profile saved to {profile_path()}")
            return 0

        if args.profile_command == "show":
            profile = load_profile()
            if not profile:
                print("No profile set.")
                print("Run 'latex-forge profile set' to create one.")
                return 0

            print(f"Profile — {profile_path()}")
            prev_section = None
            key_width = max(len(label) for _, label, _ in PROFILE_SCHEMA)
            for key, label, section in PROFILE_SCHEMA:
                if section != prev_section:
                    print(f"\n{SECTION_HEADERS[section]}")
                    prev_section = section
                value = profile.get(key, "")
                display = value if value else "(not set)"
                print(f"  {label:<{key_width}}  {display}")
            return 0

        if args.profile_command == "clear":
            clear_profile()
            print("Profile cleared.")
            return 0

    # ── latex-forge template (install / list / update / remove) ─────────
    if args.command == "template":
        from .template_manager import (
            install_template,
            list_all_templates_detailed,
            list_user_templates,
            remove_template,
            update_templates,
        )

        if args.template_command == "install":
            try:
                name, path = install_template(
                    args.source, args.name, force=args.force, engine=args.engine
                )
            except (ValueError, FileNotFoundError, FileExistsError, OSError) as exc:
                print(str(exc), file=sys.stderr)
                return 1
            print(f"Template installed: {name}")
            print(f"Location: {path}")
            print(f"Use it with: latex-forge create --template {name}")
            return 0

        if args.template_command == "list":
            if args.json_output:
                import json
                entries = list_all_templates_detailed()
                print(json.dumps(entries, indent=2))
                return 0
            # Human-readable output (default)
            built_in = sorted(p.name for p in templates_dir().iterdir() if p.is_dir())
            user = list_user_templates()
            width = max((len(t) for t in built_in + user), default=0)
            print("Built-in templates:")
            for t in built_in:
                desc = TEMPLATE_DESCRIPTIONS.get(t, "")
                suffix = f"  {desc}" if desc else ""
                print(f"  {t:<{width}}{suffix}")
            if user:
                print("\nInstalled templates:")
                for t in user:
                    print(f"  {t}")
            else:
                print("\nNo user-installed templates.")
                print("Install one with: latex-forge template install <url-or-path>")
            return 0

        if args.template_command == "update":
            results = update_templates(name=args.name)
            if args.json_output:
                import json
                print(json.dumps(results, indent=2))
                # Exit 2 if everything is up-to-date (nothing actually updated)
                any_updated = any(r.get("status") == "updated" for r in results)
                any_error = any(r.get("status") == "error" for r in results)
                if any_error:
                    return 1
                if not any_updated:
                    return 2
                return 0
            # Human-readable output
            if not results:
                print("No user-installed templates to update.")
                return 2
            any_updated = False
            any_error = False
            for r in results:
                status = r.get("status")
                name_r = r.get("name", "?")
                if status == "updated":
                    any_updated = True
                    print(f"  ✓ {name_r}: {r.get('from')} → {r.get('to')}")
                elif status == "up_to_date":
                    print(f"  — {name_r}: already up to date ({r.get('from')})")
                elif status == "skipped":
                    print(f"  · {name_r}: skipped ({r.get('reason', '')})")
                elif status == "error":
                    any_error = True
                    print(f"  ✗ {name_r}: {r.get('reason', 'error')}", file=sys.stderr)
            if any_error:
                return 1
            if not any_updated:
                return 2
            return 0

        if args.template_command == "remove":
            try:
                remove_template(args.name)
            except (ValueError, FileNotFoundError) as exc:
                print(str(exc), file=sys.stderr)
                return 1
            print(f"Template removed: {args.name}")
            return 0

    # ── latex-forge build / watch ─────────────────────────────────────────
    if args.command in ("build", "watch"):
        from .build import run_build

        project_dir = Path(args.project).expanduser().resolve() if args.project else None
        try:
            return run_build(
                project_dir=project_dir,
                watch=(args.command == "watch"),
                clean=getattr(args, "clean", False),
                verbose=args.verbose,
            )
        except (ValueError, FileNotFoundError) as exc:
            print(str(exc), file=sys.stderr)
            return 1

    # ── latex-forge export ────────────────────────────────────────────────
    if args.command == "export":
        from .export import export_project

        project_dir = Path(args.project).expanduser().resolve() if args.project else None
        output = Path(args.output).expanduser().resolve() if args.output else None
        try:
            archive_path = export_project(project_dir=project_dir, output=output)
        except (ValueError, FileNotFoundError) as exc:
            print(str(exc), file=sys.stderr)
            return 1

        print(f"Exported: {archive_path}")
        directory = (project_dir or Path.cwd()).resolve()
        if not (directory / "build" / f"{directory.name}.pdf").exists():
            print("Note: no compiled PDF found — run `latex-forge build` first to include it.")
        return 0

    # ── latex-forge diagnose ─────────────────────────────────────────────
    if args.command == "diagnose":
        from .diagnose import format_diagnose_text, run_diagnose

        data = run_diagnose()
        if args.json_output:
            import json
            print(json.dumps(data, indent=2))
        else:
            print(format_diagnose_text(data))
        # Exit 1 if any critical check failed
        critical = ("texlive", "latexmk")
        if any(not data[k]["ok"] for k in critical):
            return 1
        return 0

    # ── latex-forge list-templates ───────────────────────────────────────
    if args.command == "list-templates":
        templates = available_templates()
        width = max(len(t) for t in templates)
        for t in templates:
            desc = TEMPLATE_DESCRIPTIONS.get(t, "")
            if desc:
                print(f"  {t:<{width}}  {desc}")
            else:
                print(f"  {t}")
        return 0

    # ── latex-forge completion ───────────────────────────────────────────
    if args.command == "completion":
        shell = args.shell
        if shell is None:
            shell_path = os.environ.get("SHELL", "")
            shell = Path(shell_path).name if shell_path else "bash"
            if shell not in ("bash", "zsh", "fish"):
                shell = "bash"
        print(argcomplete.shellcode(["latex-forge"], shell=shell))
        return 0

    # ── latex-forge create ────────────────────────────────────────────────
    if args.command == "create":
        name = args.name
        template = args.template
        guided = False

        if name is None:
            if not _is_interactive():
                print("--name is required in non-interactive mode.", file=sys.stderr)
                return 1
            name = _ask_project_name()
            guided = True

        if template is None:
            config_template = get_default_template()
            if config_template is not None:
                if config_template in available_templates():
                    template = config_template
                else:
                    print(
                        f"Warning: default_template '{config_template}' in "
                        "~/.latex-forge.toml does not match any available template — ignoring.",
                        file=sys.stderr,
                    )
            if template is None:
                if not _is_interactive():
                    print("--template is required in non-interactive mode.", file=sys.stderr)
                    return 1
                template = _select_template_interactively()
                guided = True

        if args.output is not None:
            output_dir = Path(args.output).resolve()
        elif guided:
            output_dir = _ask_output_dir()
        else:
            config_dir = get_default_output_dir()
            output_dir = config_dir if config_dir is not None else Path.cwd()

        repo_mode_guided = args.repo is None and guided
        repo_mode = args.repo
        if repo_mode is None:
            repo_mode = _ask_repo_mode() if guided else (get_default_repo_mode() or "none")

        repo_name = args.repo_name
        visibility = args.visibility
        sharing = args.sharing

        if repo_mode == "create":
            if repo_mode_guided:
                if repo_name is None:
                    repo_name = _ask_repo_name(name)
                if visibility is None:
                    visibility = _ask_visibility()
            if visibility is None:
                visibility = get_default_visibility() or "private"
            if repo_name is None:
                repo_name = name

            if not gh_cli_available():
                print(
                    "GitHub CLI (gh) not found — run 'latex-forge setup --install-gh' to install it.",
                    file=sys.stderr,
                )
                return 1
            if not gh_authenticated():
                print(
                    "Not authenticated with the GitHub CLI — run 'gh auth login', then try again.",
                    file=sys.stderr,
                )
                return 1

            if repo_mode_guided:
                if not _prompt_yes_no(
                    f"Create a {visibility} repository named '{repo_name}' on your GitHub account?"
                ):
                    print("Aborted.")
                    return 1

        if repo_mode in ("create", "existing"):
            if sharing is None:
                sharing = _ask_sharing() if repo_mode_guided else (get_default_sharing() or "full")
        else:
            sharing = "full"  # irrelevant when repo_mode == "none"

        first_run = is_first_run()
        if first_run:
            run_first_launch_check()
            mark_initialized()

        try:
            target_dir, main_tex_file = create_project(
                name=name,
                template=template,
                output_dir=output_dir,
                repo_mode=repo_mode,
                repo_name=repo_name,
                visibility=visibility or "private",
                sharing=sharing,
                build_before_commit=args.build_before_commit,
            )
        except (ValueError, FileExistsError) as exc:
            print(str(exc), file=sys.stderr)
            return 1

        print(f"Project created: {target_dir}")
        print(f"Edit: {main_tex_file.relative_to(target_dir.parent)}")
        if template in ("cv-fr", "cv-en"):
            first_file = "sections/en-tete.tex" if template == "cv-fr" else "sections/heading.tex"
            print(f"Next: fill in {first_file} then save to compile.")
        else:
            print("Next: fill in frontmatter/metadata.tex then save to compile.")

        if repo_mode == "none":
            print("Versioning: none (local-only project).")
        else:
            print(f"Versioning: {repo_mode}  |  Sharing: {sharing}")

        if repo_mode == "create":
            if (target_dir / ".git").is_dir():
                print("Initialized a git repository with an initial commit.")
            else:
                print(
                    "Warning: could not initialize git (is git installed?).",
                    file=sys.stderr,
                )

            remote_check = subprocess.run(
                ["git", "-C", str(target_dir), "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                check=False,
            )
            if remote_check.returncode == 0:
                print(f"GitHub repo: {remote_check.stdout.strip()}")
            else:
                print(
                    "Warning: could not create the GitHub repository — check `gh auth status` "
                    f"and that '{repo_name}' isn't already taken, then run:\n"
                    f"  cd {target_dir} && gh repo create {repo_name} --{visibility or 'private'} "
                    "--source=. --remote=origin --push",
                    file=sys.stderr,
                )

            pdf_tracked = any((target_dir / "build").glob("*.pdf"))
            if not pdf_tracked:
                print(
                    "Note: the compiled PDF isn't in the initial commit yet — run "
                    "'latex-forge build', then 'git add build/*.pdf && git commit' to share it."
                )
        elif repo_mode == "existing":
            print("This project isn't its own git repo — make sure its parent folder is versioned.")

        if not first_run:
            warn_if_latex_missing()

        offer_open_vscode(target_dir)

        return 0

    # ── latex-forge rename ────────────────────────────────────────────────
    if args.command == "rename":
        try:
            if len(args.names) == 1:
                target_dir, main_tex_file = rename_current_project(
                    new_name=args.names[0],
                )
            elif len(args.names) == 2:
                target_dir, main_tex_file = rename_project(
                    old_name=args.names[0],
                    new_name=args.names[1],
                )
            else:
                print(
                    "Usage: latex-forge rename <new-name> "
                    "or latex-forge rename <old-name> <new-name>",
                    file=sys.stderr,
                )
                return 1
        except (ValueError, FileNotFoundError, FileExistsError) as exc:
            print(str(exc), file=sys.stderr)
            return 1

        print(f"Project renamed: {target_dir}")
        print(f"Main file: {main_tex_file.name}")
        return 0

    # ── latex-forge setup ────────────────────────────────────────────────
    if args.command == "setup":
        return run_setup(
            check_only=args.check_only,
            skip_extensions=args.skip_extensions,
            install_tex=args.install_tex,
            install_gh=args.install_gh,
        )

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
