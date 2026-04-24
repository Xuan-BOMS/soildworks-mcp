param(
    [string]$Python = "python",
    [string]$SolidWorksInstallDir = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot

& $Python -m pip install --upgrade pip
& $Python -m pip install -e $repoRoot

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$buildBridgeScript = Join-Path $PSScriptRoot "build_bridge.ps1"
& $buildBridgeScript -Configuration Release -SolidWorksInstallDir $SolidWorksInstallDir
