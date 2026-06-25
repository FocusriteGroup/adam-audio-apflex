# DataTools Build and Release (Windows 11+)

This guide defines a reproducible flow to build and package DataTools as a native Windows application.

## Prerequisites

- Windows 11 (x64) build machine
- Python 3.11 x64
- Virtual environment at .venv in repository root
- Kivy installed in .venv
- Inno Setup 6 (for installer creation)

## Build EXE

From repository root:

```powershell
.\.venv\Scripts\Activate.ps1
.\DataTools\build\build_datatools.ps1 -Clean -Version 0.1.0
```

Expected output:

- EXE folder: DataTools/dist/DataTools
- Main executable: DataTools/dist/DataTools/DataTools.exe

## Build Installer

1. Open DataTools/build/installer/DataTools.iss in Inno Setup.
2. Adjust AppVersion if needed.
3. Compile using ISCC or the GUI.

Command line example:

```powershell
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" .\DataTools\build\installer\DataTools.iss
```

Expected output:

- Setup EXE in DataTools/build/installer

## Recommended Release Checklist

1. Build on Windows 11 x64.
2. Smoke test DataTools.exe on a clean user profile.
3. Build installer and run install/uninstall test.
4. Sign EXE and installer with your code-signing certificate.
5. Archive artifacts with version tag.

## Notes

- Use onedir packaging for Kivy reliability.
- Keep stdout/stderr noise minimal for production diagnostics.
- If modules are added, update DataTools/build/DataTools.spec hidden imports and datas.
