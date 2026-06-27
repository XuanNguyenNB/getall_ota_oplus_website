# Build the static UI stylesheet with the Tailwind v4 standalone CLI (Windows).
#
# No Node/npm required. Downloads the standalone binary to scripts\bin\ on first
# run (git-ignored), then compiles the Tailwind input into the served
# stylesheet. The output (src\ota_backend\static\styles.css) IS committed so the
# FastAPI app can serve it directly.
#
# Usage:
#   pwsh scripts\build-css.ps1            # one-shot minified build
#   pwsh scripts\build-css.ps1 -Watch     # rebuild on change (not minified)
param([switch]$Watch)

$ErrorActionPreference = "Stop"

$RepoRoot  = Split-Path -Parent $PSScriptRoot
$BinDir    = Join-Path $PSScriptRoot "bin"
$StaticDir = Join-Path $RepoRoot "src\ota_backend\static"
$Input     = Join-Path $StaticDir "tailwind.input.css"
$Output    = Join-Path $StaticDir "styles.css"
$Version   = "v4.3.1"
$Bin       = Join-Path $BinDir "tailwindcss.exe"

if (-not (Test-Path $Bin)) {
    Write-Host "Downloading Tailwind CLI $Version (windows-x64)..."
    New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
    $url = "https://github.com/tailwindlabs/tailwindcss/releases/download/$Version/tailwindcss-windows-x64.exe"
    Invoke-WebRequest -Uri $url -OutFile $Bin
}

if ($Watch) {
    & $Bin -i $Input -o $Output --watch
} else {
    & $Bin -i $Input -o $Output --minify
    Write-Host "Built $Output"
}
