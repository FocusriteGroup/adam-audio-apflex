param(
    [string]$Version = "",
    [switch]$Clean
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$BuildScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DataToolsRoot = Resolve-Path (Join-Path $BuildScriptDir "..")
$RepoRoot = Resolve-Path (Join-Path $DataToolsRoot "..")
$VersionFileSource = Join-Path $DataToolsRoot "VERSION.txt"

$PythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$SpecFile = Join-Path $BuildScriptDir "DataTools.spec"
$DistPath = Join-Path $DataToolsRoot "dist"
$WorkPath = Join-Path $BuildScriptDir "pyi-work"
$VersionFile = Join-Path $DistPath "VERSION.txt"

if ([string]::IsNullOrWhiteSpace($Version)) {
    if (-not (Test-Path $VersionFileSource)) {
        throw "Version file not found at $VersionFileSource"
    }

    $Version = (Get-Content -Path $VersionFileSource -Raw).Trim()
}

if ([string]::IsNullOrWhiteSpace($Version)) {
    throw "Version value is empty. Set DataTools/VERSION.txt or pass -Version explicitly."
}

if (-not (Test-Path $PythonExe)) {
    throw "Python not found at $PythonExe. Create and configure .venv first."
}

if (-not (Test-Path $SpecFile)) {
    throw "Spec file not found at $SpecFile"
}

Write-Host "Using Python:" $PythonExe

function Get-PyInstallerCommand {
    $pyinstallerExe = Join-Path (Split-Path -Parent $PythonExe) "pyinstaller.exe"
    if (Test-Path $pyinstallerExe) {
        return $pyinstallerExe
    }

    return $null
}

$pyinstallerCommand = Get-PyInstallerCommand
if (-not $pyinstallerCommand) {
    Write-Host "Installing PyInstaller into .venv ..."
    & $PythonExe -m pip install pyinstaller
    $pyinstallerCommand = Get-PyInstallerCommand
}

if (-not $pyinstallerCommand) {
    throw "PyInstaller could not be installed or found in .venv\\Scripts."
}

if ($Clean) {
    foreach ($path in @($DistPath, $WorkPath)) {
        if (Test-Path $path) {
            try {
                Remove-Item -Recurse -Force $path -ErrorAction Stop
            }
            catch {
                Write-Warning "Could not remove $path. The path may be in use; continuing with the build."
            }
        }
    }
}

$pyiArgs = @(
    "--noconfirm",
    "--clean",
    "--distpath", $DistPath,
    "--workpath", $WorkPath,
    $SpecFile
)

Write-Host "Running PyInstaller ..."
& $pyinstallerCommand @pyiArgs

if (-not (Test-Path (Join-Path $DistPath "DataTools\DataTools.exe"))) {
    throw "Build failed: DataTools.exe not found in dist output."
}

"$Version" | Set-Content -Path $VersionFile -Encoding ascii
Write-Host "Build complete."
Write-Host "EXE:" (Join-Path $DistPath "DataTools\DataTools.exe")
Write-Host "Version marker:" $VersionFile
