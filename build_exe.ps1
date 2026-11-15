# Build the portable Windows executable for the Baseline Drift demo.
# Usage: .\build_exe.ps1
#        .\build_exe.ps1 -Python "C:\path\to\python.exe"
param([string]$Python = "python")
$ErrorActionPreference = "Stop"

& $Python -m pip install --upgrade pyinstaller
& $Python -m PyInstaller --noconfirm --clean --onefile --name BaselineDrift --console `
  --add-data "web/app;web/app" `
  --collect-submodules pipeline `
  --collect-all parselmouth `
  --collect-all soundfile `
  --collect-submodules uvicorn `
  --hidden-import uvicorn.logging `
  --hidden-import uvicorn.loops.auto `
  --hidden-import uvicorn.protocols.http.auto `
  --hidden-import uvicorn.protocols.websockets.auto `
  --hidden-import uvicorn.lifespan.on `
  baseline_drift_exe.py

Write-Output "Built dist\BaselineDrift.exe"
