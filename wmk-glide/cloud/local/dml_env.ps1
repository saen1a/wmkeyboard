# Creates a SEPARATE venv (NOT in repo, NOT /opt/wmlm-venv) with Python 3.12
# via uv, installs PyTorch 2.4.1 + torch-directml (the only artifact on PyPI
# as of 2026-10-31), then runs directml_probe.py. Safe to re-run; prints the
# exact pip command. Caller time-boxes and decides whether to execute.
#
# This script does NOT auto-execute. Invoke it explicitly:
#   powershell -ExecutionPolicy Bypass -File wmk-glide\cloud\local\dml_env.ps1

[CmdletBinding()]
param(
    [string]$ProbeArgs = "--device dml --batch 8 --ctx 40 --vocab 24576 --k 24"
)

$ErrorActionPreference = "Stop"

# Resolve repo (parent of this script's directory).
$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot    = (Resolve-Path (Join-Path $ScriptDir "..\..\..")).Path
$ProbePath   = Join-Path $RepoRoot "wmk-glide\cloud\local\directml_probe.py"

if (-not (Test-Path $ProbePath)) {
    Throw "probe not found at $ProbePath"
}

# Venv lives in %TEMP%\wmkl-dml-venv, never inside the repo or /opt/wmlm-venv.
$VenvRoot = Join-Path $env:TEMP "wmkl-dml-venv"

# Use uv for fast Python 3.12 retrieval.
$uv = (Get-Command uv -ErrorAction SilentlyContinue)
if (-not $uv) {
    Throw "uv not on PATH. Install with: winget install --id=astral-sh.uv  (or)  pip install uv"
}

# Resolve a Python 3.12 interpreter; uv will fetch if absent.
$Py312 = $uv exec --python 3.12 python -c "import sys;print(sys.executable)" 2>$null
Write-Host "using python 3.12 at: $Py312"

# Create venv once.
if (-not (Test-Path (Join-Path $VenvRoot "pyvenv.cfg"))) {
    Write-Host "creating venv at $VenvRoot (NOT under repo, NOT /opt/wmlm-venv)"
    & $uv.Path venv --python 3.12 $VenvRoot 2>&1 | Write-Host
} else {
    Write-Host "venv already exists: $VenvRoot"
}

# Build the EXACT pip commands that would be run. Print them, then run.
# torch-directml==0.2.5.dev240914 (the newest artifact on PyPI) pairs with
# torch==2.4.1 (the only stable torch-directml target).
$PipCmd = @(
    "--python `"$(Join-Path $VenvRoot 'Scripts\python.exe')`""
    "pip", "install", "--no-cache-dir",
    "torch==2.4.1",
    "torch-directml==0.2.5.dev240914"
)
Write-Host ""
Write-Host "EXACT pip command (will be run):"
Write-Host ("& " + ($uv.Path -replace "\\","/") + " " + ($PipCmd -join " "))
Write-Host ""

& $uv.Path @PipCmd 2>&1 | Write-Host

# Run the probe.
$VenvPython = Join-Path $VenvRoot "Scripts\python.exe"
$ProbeArgsList = $ProbeArgs -split "\s+"
Write-Host ""
Write-Host "running probe:"
Write-Host "& `"$VenvPython`" `"$ProbePath`" $ProbeArgs"
& $VenvPython $ProbePath @ProbeArgsList
$code = $LASTEXITCODE

Write-Host ""
Write-Host "exit code $code"
exit $code
