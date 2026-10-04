# Contributing to LaTeX Forge

Thanks for your interest in contributing!

## Reporting a bug

Open an issue on GitHub and include:
- your OS and Python version
- the exact command you ran
- the full error message

## Setting up the development environment

```bash
git clone https://github.com/thmsgo18/latex-forge.git
cd latex-forge
pipx install --editable ".[dev]"
```

## Running the tests

```bash
pip install -e ".[dev]"
pytest tests/ -v                        # unit tests (no LaTeX needed)
pytest tests/ --cov=latex_forge         # with coverage (CI requires >= 85%)
ruff check .                            # lint
LATEX_FORGE_INTEGRATION=1 pytest -m integration   # compiles for real with your TeX distribution
```

All tests must pass before submitting a pull request. CI runs the unit tests
on Linux, macOS and Windows with Python 3.10 to 3.14, and the integration
tests on all three OSes after installing latex-forge and the light TinyTeX
with `install.sh` / `install.ps1` — exactly what a new user does.

## Adding a template

1. Create a new folder under `latex_forge/templates/your-template-name/`
2. Add a `main.tex` and the required subfolders
3. Make sure `latex-forge create --name test --template your-template-name` works
4. Add its TeX Live packages to `latex_forge/tex_packages.json` (generate them with the
   gallery's `scripts/compute_tex_packages.py --path <created project>`): `tests/test_setup.py`
   fails until you do, and the integration tests compile every built-in template on TinyTeX

## Submitting a pull request

1. Fork the repository
2. Create a branch: `git checkout -b my-fix`
3. Make your changes and run the tests
4. Open a pull request against `main`

## Releasing a new version

Maintainers only:

1. Rename `## [Unreleased]` in `CHANGELOG.md` to `## [X.Y.Z] - YYYY-MM-DD` and commit
2. Tag the release commit: `git tag vX.Y.Z`
3. Push: `git push && git push --tags`

The package version is derived from the git tag via `setuptools-scm` — no
manual bump needed. The publish workflow refuses to release unless the
changelog documents the version and the full CI suite (unit + integration)
passes on the tagged commit; it then publishes to PyPI, creates the GitHub
release with the changelog notes, and installs the release from PyPI on each
OS to check it. The README version badge follows the latest tag.
