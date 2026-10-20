$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { throw "Python not found. Install Python 3 to build the exe." }

& $python -m pip install -q -r requirements-build.txt

$dist = Join-Path $PSScriptRoot "dist"
$work = Join-Path $PSScriptRoot "build"
New-Item -ItemType Directory -Force -Path $dist | Out-Null

& $python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name "SplitView" `
  --distpath $dist `
  --workpath $work `
  --specpath $PSScriptRoot `
  --paths (Join-Path $PSScriptRoot "src") `
  --hidden-import winsplit `
  --hidden-import open_browser `
  --hidden-import split_gemini `
  --hidden-import overlay `
  --hidden-import shortcuts `
  --hidden-import paths `
  (Join-Path $PSScriptRoot "src\main.py")

if (-not (Test-Path (Join-Path $dist "SplitView.exe"))) {
  throw "Build failed: dist\SplitView.exe not found"
}

$packName = [string]::Concat([char]0x914D, [char]0x5E03, [char]0x7528)
$pack = Join-Path $PSScriptRoot $packName
New-Item -ItemType Directory -Force -Path $pack | Out-Null
Copy-Item (Join-Path $dist "SplitView.exe") (Join-Path $pack "SplitView.exe") -Force
$readmeSrc = Get-ChildItem -LiteralPath $PSScriptRoot -Filter "README_*.md" | Select-Object -First 1
if ($readmeSrc) {
  Copy-Item -LiteralPath $readmeSrc.FullName -Destination (Join-Path $pack "README.txt") -Force
}

Write-Host ""
Write-Host "OK: $pack\SplitView.exe"
Write-Host "Copy that folder to other PCs. Double-click SplitView.exe (Python not required)."
