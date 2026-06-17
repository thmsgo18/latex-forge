# Contributing

## Development setup

```bash
git clone https://github.com/thmsgo18/latex-forge.git
cd latex-forge
pipx install --editable ".[dev]"
```

The `--editable` flag makes the `latex-forge` command point to your local clone, so every code change is reflected immediately without reinstalling.

### Linting

```bash
pip install ruff
ruff check latex_forge/
```

Ruff is configured in `pyproject.toml`. All checks must pass before submitting a pull request.

## Running the tests

```bash
pytest tests/ -v
```

Tests do not compile LaTeX and do not require a TeX Live installation. They test Python logic: project scaffolding, profile injection, build command construction, template installation, and diagnostics.

Run a single test file:

```bash
pytest tests/test_profile.py -v
```

Run a single test by name:

```bash
pytest tests/test_profile.py::test_latex_escape_handles_specials -v
```

### Test coverage by module

| Test file | Module under test |
|---|---|
| `test_cli.py` | `cli.py` (argument parsing and dispatch) |
| `test_project.py` | `project.py` (project creation, AGENTS.md, rename) |
| `test_build.py` | `build.py` (command construction, engine detection) |
| `test_profile.py` | `profile.py` (injection, escaping, helpers) |
| `test_config.py` | `config.py` (config file loading) |
| `test_diagnose.py` | `diagnose.py` (environment checks) |
| `test_export.py` | `export.py` (ZIP creation) |
| `test_template_manager.py` | `template_manager.py` (install, remove, list) |
| `test_gallery_archive_install.py` | Gallery fast path and archive fallback |
| `test_installed_templates.py` | `installed_templates.py` (metadata CRUD) |
| `test_template_update.py` | `update_templates()` (version comparison) |

## Adding a new CLI command

1. Add a sub-parser in `build_parser()` in `cli.py`.
2. Implement the handler as a branch in `main()`, importing the relevant module lazily (to keep startup fast).
3. Put the business logic in a dedicated module or in an existing one.
4. Add tests for the new functionality.

Imports inside handler branches are intentional: they keep the `latex-forge --version` and `latex-forge --help` invocations fast by not importing heavy modules at startup.

## Adding a built-in template

1. Create `latex_forge/templates/<name>/` with `main.tex` and the standard structure:

    ```
    <name>/
      main.tex
      latexforge.toml         # Required if the engine is not lualatex
      frontmatter/
        metadata.tex          # Use standard \newcommand placeholders
      sections/
      ...
    ```

2. Add a description to `TEMPLATE_DESCRIPTIONS` in `project.py`:

    ```python
    TEMPLATE_DESCRIPTIONS: dict[str, str] = {
        ...
        "my-template": "Short description for list-templates",
    }
    ```

3. Add a family mapping in `write_agents_md()` in `project.py`. Use `"generic"` if no custom AGENTS.md fragments are needed.

4. If the template needs local `.sty` files, add them to `latex_forge/styles/packages/`. They are copied automatically because `create_project` scans `\usepackage{...}` calls.

5. Add a test in `tests/test_project.py`:

    ```python
    def test_create_my_template(tmp_path):
        target, main = create_project("doc", "my-template", tmp_path)
        assert main.exists()
        assert (target / "frontmatter" / "metadata.tex").exists()
    ```

## Adding a new profile field

See [Profile injection](architecture/profile-injection.md#adding-a-new-profile-field) for the step-by-step procedure.

## Versioning and releases

The package version is derived from git tags via `setuptools-scm`. No manual version bump is needed.

To release a new version:

```bash
git tag v1.2.3
git push && git push --tags
```

GitHub Actions publishes the package to PyPI automatically when a tag is pushed.

## Reporting a bug

Open an issue on GitHub and include:

- Your OS and Python version (`python --version`)
- The exact command you ran
- The full error message or unexpected output
- The output of `latex-forge diagnose`

## Pull request checklist

- [ ] All existing tests pass (`pytest tests/ -v`)
- [ ] New tests cover the change
- [ ] `ruff check latex_forge/` passes
- [ ] Commit message is descriptive and does not reference internal tools or ticket numbers
