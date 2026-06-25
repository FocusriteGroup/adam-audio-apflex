param(
    [string]$Version = "",
    [switch]$Clean,
    [switch]$SkipInstaller
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DataToolsRoot = Resolve-Path (Join-Path $ScriptDir "..")
$RepoRoot = Resolve-Path (Join-Path $DataToolsRoot "..")
$VersionFileSource = Join-Path $DataToolsRoot "VERSION.txt"
$InstallerDir = Join-Path $ScriptDir "installer"
$InstallerScript = Join-Path $InstallerDir "DataTools.iss"
$ExeBuildScript = Join-Path $ScriptDir "build_datatools.ps1"

if ([string]::IsNullOrWhiteSpace($Version)) {
    if (-not (Test-Path $VersionFileSource)) {
        throw "Version file not found at $VersionFileSource"
    }

    $Version = (Get-Content -Path $VersionFileSource -Raw).Trim()
}

if ([string]::IsNullOrWhiteSpace($Version)) {
    throw "Version value is empty. Set DataTools/VERSION.txt or pass -Version explicitly."
}

if (-not (Test-Path $ExeBuildScript)) {
    throw "Build script not found at $ExeBuildScript"
}

if (-not (Test-Path $InstallerScript)) {
    throw "Installer script not found at $InstallerScript"
}

Write-Host "Building DataTools executable..."
& $ExeBuildScript -Version $Version -Clean:$Clean

if ($SkipInstaller) {
    Write-Host "Skipping installer build as requested."
    return
}

function Get-InnoSetupCompiler {
    $candidates = @(
        (Get-Command ISCC.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    ) | Where-Object { $_ -and (Test-Path $_) }

    return $candidates | Select-Object -First 1
}

$isccExe = Get-InnoSetupCompiler
if (-not $isccExe) {
    throw "Inno Setup compiler not found. Install Inno Setup 6 or add ISCC.exe to PATH."
}

Write-Host "Building installer with:" $isccExe

Push-Location $InstallerDir
try {
    & $isccExe "/DAppVersion=$Version" "/O$InstallerDir" $InstallerScript
}
finally {
    Pop-Location
}

Write-Host "Release build complete."
Write-Host "Executable folder:" (Join-Path $DataToolsRoot "dist\DataTools")
Write-Host "Installer output folder:" $InstallerDir
