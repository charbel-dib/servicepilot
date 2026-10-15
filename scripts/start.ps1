param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'Install uv first: python -m pip install uv'
}
uv sync --frozen --extra dev
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
uv run --frozen servicepilot demo --port $Port
