# Install LaTeX Forge and LaTeX on Windows — no Python, pipx or admin rights needed:
#
#   powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/thmsgo18/latex-forge/main/install.ps1 | iex"
#
# 1. installs uv (https://docs.astral.sh/uv/) if it's missing,
# 2. installs the latex-forge CLI with it, on a Python that uv manages,
# 3. runs `latex-forge setup` to install LaTeX (light TinyTeX by default),
#    then compiles a test document.
#
# Environment variables:
#   LATEX_FORGE_TEX   light | full | system | none (none: don't install LaTeX)
#   LATEX_FORGE_SPEC  what to install (default: latex-forge from PyPI)

$ErrorActionPreference = 'Stop'

$tex = if ($env:LATEX_FORGE_TEX) { $env:LATEX_FORGE_TEX } else { 'light' }
$spec = if ($env:LATEX_FORGE_SPEC) { $env:LATEX_FORGE_SPEC } else { 'latex-forge' }
$binDir = Join-Path $env:USERPROFILE '.local\bin'

if ($tex -notin @('light', 'full', 'system', 'none')) {
    throw "LATEX_FORGE_TEX must be light, full, system or none (got '$tex')"
}

# 1. uv
$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
if ($uvCommand) {
    $uv = $uvCommand.Source
} elseif (Test-Path (Join-Path $binDir 'uv.exe')) {
    $uv = Join-Path $binDir 'uv.exe'
} else {
    Write-Host '==> Installing uv (it installs latex-forge and the Python it runs on)'
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    $uv = Join-Path $binDir 'uv.exe'
    if (-not (Test-Path $uv)) { throw "uv was not installed in $binDir" }
}

# 2. latex-forge (installed or upgraded)
Write-Host '==> Installing the latex-forge CLI'
& $uv tool install --managed-python --force --upgrade $spec
if ($LASTEXITCODE -ne 0) { throw 'uv could not install latex-forge' }
& $uv tool update-shell | Out-Null
$lf = Join-Path $binDir 'latex-forge.exe'
& $lf --version

# 3. LaTeX
if ($tex -eq 'none') {
    Write-Host '==> Skipping LaTeX (LATEX_FORGE_TEX=none). Install it later with: latex-forge setup --install-tex'
} else {
    & $lf setup --install-tex --tex $tex --yes --skip-extensions
}

Write-Host ''
Write-Host '==> Done. Open a new terminal, then run:  latex-forge create'
