# Profile

The profile stores your personal information once in `~/.latex-forge/profile.toml` and injects it automatically into every new project at creation time. You never have to retype your name, email, or university.

## Fields

### Identity

| Key | Label | Example |
|---|---|---|
| `first_name` | First name | `Thomas` |
| `last_name` | Last name | `Gourmelen` |
| `email` | Email | `thomas@example.edu` |
| `phone` | Phone | `+33 6 00 00 00 00` |
| `website` | Website | `https://thmsgo18.github.io` |

### Online profiles

| Key | Label | Notes |
|---|---|---|
| `github` | GitHub username | Username only, not the full URL |
| `linkedin` | LinkedIn username | Username from `linkedin.com/in/<username>` |

### Academic

| Key | Label | Example |
|---|---|---|
| `university` | University | `Universite Paris Cite` |
| `faculty` | Faculty / UFR | `UFR Mathematiques et Informatique` |
| `program` | Program | `Master Informatique` |
| `supervisor` | Supervisor | `Prof. Jane Smith` |

### Professional

| Key | Label | Example |
|---|---|---|
| `company` | Company | `Acme Corp` |
| `department` | Department | `Engineering` |
| `job_title` | Job title | `Software Engineer` |

## How injection works

When `latex-forge create` runs, it calls `apply_profile_to_project()` after copying the template files. Injection is dispatched by template type:

| Template type | Injection function | Target file |
|---|---|---|
| `cv-en`, `cv-fr` (built-in) | `_apply_cv` | `sections/heading.tex` or `sections/en-tete.tex` |
| `project-report-en/fr`, `research`, `blank` | `_apply_metadata` | `frontmatter/metadata.tex` |
| Gallery and installed templates | `_apply_gallery_metadata` | `frontmatter/metadata.tex` |

Each function uses regex helpers that match `\newcommand{\cmd}{OLD}` and replace the value. Fields that are unset in the profile are silently skipped, so a partial profile never corrupts a project.

### LaTeX escaping

Before any profile value is written into a `.tex` file, it is passed through `_latex_escape()`, which escapes the ten LaTeX special characters:

```
& % $ # _ { } ~ ^ \
```

For example, a university named `Arts & Crafts` becomes `Arts \& Crafts` in the generated file, so compilation never breaks because of a value the user typed.

GitHub and LinkedIn handles are the only fields not escaped, because they are injected into URLs and contain only URL-safe characters (letters, digits, hyphens).

## Configuration file

In addition to the profile (personal data), LaTeX Forge reads optional defaults from `~/.latex-forge.toml`:

```toml
# ~/.latex-forge.toml

# Pre-select a template so --template can be omitted from `create`
default_template = "project-report-fr"

# Create new projects in this directory by default
default_output_dir = "~/Documents/LaTeX"
```

The profile and the config file are separate:

| File | Purpose |
|---|---|
| `~/.latex-forge/profile.toml` | Personal data injected into `.tex` files |
| `~/.latex-forge.toml` | CLI behaviour defaults |

## Storage format

The profile is a plain TOML file with section comments:

```toml
# -- Identity -------------------------------------------------------
first_name = "Thomas"
last_name = "Gourmelen"
email = "thomas@example.edu"
phone = ""
website = ""

# -- Online profiles ------------------------------------------------
github = "thmsgo18"
linkedin = ""

# -- Academic -------------------------------------------------------
university = "Universite Paris Cite"
faculty = ""
program = "Master Informatique"
supervisor = ""

# -- Professional ---------------------------------------------------
company = ""
department = ""
job_title = ""
```

A corrupted or missing profile file is treated as an empty profile. It never prevents a project from being created.
