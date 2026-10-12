# Canonical vector source: assets/Culvert.svg and assets/Culvert-mark.svg.
# Developer-only rendering dependencies: Python, PySide6 and Pillow.
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
python (Join-Path $root 'linux/render-brand.py')
if ($LASTEXITCODE -ne 0) { throw 'Brand rendering failed. Install Python packages PySide6 and Pillow.' }
