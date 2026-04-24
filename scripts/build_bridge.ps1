param(
    [ValidateSet("Debug", "Release")]
    [string]$Configuration = "Release",
    [string]$SolidWorksInstallDir = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$projectPath = Join-Path $repoRoot "bridge\SolidWorksBridge.csproj"

if (-not (Test-Path $projectPath)) {
    throw "Bridge project not found: $projectPath"
}

$msbuildArgs = @(
    "build",
    $projectPath,
    "-c", $Configuration
)

if ($SolidWorksInstallDir) {
    $msbuildArgs += "/p:SolidWorksInstallDir=$SolidWorksInstallDir"
}

dotnet @msbuildArgs
