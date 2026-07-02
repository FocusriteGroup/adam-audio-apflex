# Knowledge Base

## Reference and Limits Generation

### Reference Types

| Type | Basis |
|---|---|
| **EOL** | Median of 10-15 representative production units |
| **Golden Sample** | Measurement(s) of the designated Golden Sample unit |

### Folder Structure

```
References\
├── EOL\
│   ├── RMS.csv
│   ├── Phase.csv
│   ├── THD.csv
│   └── Limits\
│       ├── RMS.csv
│       ├── Phase.csv
│       └── THD.csv
├── GoldenSample\
│   ├── RMS.csv  /  Phase.csv  /  THD.csv
│   └── Limits\
│       └── RMS.csv  /  Phase.csv  /  THD.csv
└── L-R-Diff.csv   (stereo devices only)
```

### File Formats

**Dual mono** - stereo devices (EOL: identical Y columns; Golden Sample: actual L/R values):

```
RMS Level,,,
Ch1,,Ch2,
X,Y,X,Y
Hz,dBSPL,Hz,dBSPL
```

**Single mono** - mono devices:

```
RMS Level,
Ch1,
X,Y
Hz,dBSPL
```

**Limits** - always single mono, Y = relative dB offset:

```
Upper Limit for Acoustic Response...,
Ch1,
X,Y
Hz,dB
```

**L-R-Diff** - single mono, Y in dB (stereo devices only):

```
L-R-Diff Raw,
L-R-Diff Left,
X,Y
Hz,dB
```

### Stereo vs Mono Rules

| | EOL reference | Golden Sample reference |
|---|---|---|
| **Stereo** | Dual mono - X,Y,X,Y with identical Y values | Dual mono - actual L/R values from Golden Sample |
| **Mono** | Single mono - X,Y | Single mono - X,Y |

Limits files are always single mono regardless of device type.

### Manual Process

1. **Collect measurements** - 10-15 units (EOL) or the Golden Sample. Discard runs affected by noise or fixture issues.
2. **Move batch to a new folder** in the same parent directory as the auto-created date folders. Required if DataTools is used.
3. **Compute pointwise median** across all collected CSVs. Output must have the same 4-header AP CSV format.
4. **Define relative limits** - Y values in dB, not absolute SPL. Limits may cover a sub-range only.
5. **Place files** into `References\EOL\`, `References\GoldenSample\`, and their `Limits\` subfolders.
6. **Smoke-test** with a known-good unit (expect PASS) and a known-bad unit (expect FAIL).

### Alternative - DataTools

Use the DataTools application to create references from a collected batch. See [DataTools Documentation](../DataTools/docs/README.md).

### SubPRO - Create Reference Sequence

`SubPRO_v_1_0.approjx` has a dedicated **Create Reference** checklist sequence that ensures gain calibration is at zero during measurement.

**Procedure:**

1. Run the **EOL** sequence first to confirm the unit functions correctly.
2. Switch the APx checklist to **Create Reference**.
3. Run the sequence and follow the reference generation steps above.

See [subpro-v1-sequence.md](subpro-v1-sequence.md) for the full sequence step breakdown.

---

## Python Virtual Environment and PythonRunner

APx projects call the production tool via a **virtual environment** (`.venv`) in the tool root directory. This isolates dependencies from the system Python.

The path to `pythonw.exe` in the venv is stored as the APx project variable **`PythonRunner`** and used as `$(PythonRunner)` in every shell step Command field.

**Set in APx:** Project > Project Properties > Variables tab > `PythonRunner`

```
C:\Users\<User>\OneDrive - Focusrite Group\<Site>\.venv\Scripts\pythonw.exe
```

| Field | Value |
|---|---|
| Command | `$(PythonRunner)` |
| Arguments | `adam_workstation.py <command> [args...]` |
| Working Folder | `$(ProjectDir)` |

Each workstation has its own path. Never hard-code `pythonw.exe` - it resolves to the system Python and bypasses the venv.

---

## Log Files

All workstation activity is written to daily log files. Nothing is printed to the console or APx stdout - logs are the only place to see what the tool actually did.

### Location

```
<tool root>\logs\adam_audio\
    adam_workstation_log_YYYY-MM-DD.log
    adam_service_log_YYYY-MM-DD.log
```

A new file is created each day.

### Format

```
2026-06-23 15:27:01,966 - INFO  - [AdamWorkstation] - Executing command: discover ...
2026-06-23 15:27:03,404 - INFO  - [OCADevice-None]  - Discovery results: {'devices': [...]}
2026-06-23 15:29:57,583 - ERROR - [OCP1ToolWrapper] - Command failed (exit code 1): ...
```

| Column | Content |
|---|---|
| Timestamp | Date, time, milliseconds |
| Level | INFO, WARNING, ERROR |
| Logger | AdamWorkstation, OCADevice, OCP1ToolWrapper, AdamSerialSwitchBox, AdamSerialScanner |
| Message | Command, result, or error detail |

### What to Look For

| Situation | Search for |
|---|---|
| APx step failed | Find the step timestamp, look for ERROR in that block |
| Unexpected stdout value | Search the command name, e.g. set_gain_calibration |
| Hardware not responding | Search SwitchBox or Scanner |
| OCA command failed | Search OCP1ToolWrapper - shows exact CLI argv and stderr |

### Desktop Shortcut

1. Navigate to `<tool root>\logs\adam_audio` in Explorer.
2. Right-click the folder > **Send to > Desktop (create shortcut)**.

---

## Golden Sample Serial Number

> **There must be exactly one production Golden Sample per product. Its serial number must be stored in the APx project properties as the `GoldenSampleSerial` user variable. This is the only way the sequence can reliably detect whether the connected unit is the Golden Sample or an EOL unit.**

For SubPro this is especially critical: the serial number is stored in the device's flash memory and is read back via OCA during the sequence. If a different unit is connected that is not the referenced Golden Sample, the sequence cannot distinguish it and **its measurements will overwrite the Golden Sample reference settings**.

**Rules:**

- Only one Golden Sample per product may be used with the production tool at any time.
- Its serial number must be set in **Project > Project Properties > Variables > `GoldenSampleSerial`** before the first Golden Sample run.
- Never run a Golden Sample sequence with a unit whose serial number has not been entered in `GoldenSampleSerial`.
- If the Golden Sample unit is replaced, update `GoldenSampleSerial` immediately and re-run the reference generation.

---

## DataTools Settings - Database and Folder Paths

DataTools stores all configuration in a local SQLite database (`DataTools\Data\db\datatools.db`). The paths to external databases and measurement folders must be set correctly before DataTools can function. **Incorrect or missing paths will cause DataTools to fail silently or operate on the wrong data.**

This is especially critical when DataTools is used for **MAC provisioning** - if `mac_db_path` does not point to the correct database, MAC addresses will not be read or written correctly.

### Required Settings

Open the DataTools settings panel and configure the following paths for each workstation:

| Setting key | What it must point to |
|---|---|
| `matching_db_path` | `Matching_App\Data\db\matcher.db` in the tool root |
| `sn_fw_db_path` | `SubPro_SN_FW_Workstation\Data\db\workstation.db` in the tool root |
| `mac_db_path` | `SubProMACAddresses\mac_provisioning.db` in the tool root |
| `measurements_root_path` | Root folder where APx stores measurement CSVs |

### Important Rules

- Paths are **absolute** and must be set individually on each workstation - they are not shared automatically.
- If the tool is moved or the OneDrive sync path changes, all paths must be updated.
- `mac_db_path` must point to the **same database** that the APx `provision_mac` command writes to. Using a different copy of the database will cause MAC assignment conflicts.
- After updating paths, restart DataTools to ensure the new settings take effect.

### Verify After Setup

After setting the paths, verify that DataTools can open each database by navigating to the relevant viewer (Matching Viewer, Measurements Viewer). If the viewer shows no data or an error, the path is incorrect.

### Default Password

The default DataTools password is **`admin`**. Change it on first use via the settings panel.

---

## DataTools Installation

DataTools is distributed as a standalone Windows installer. No Python or virtual environment is required on the target machine.

### Installer

The installer is built as part of the release process and found at:

```
DataTools\build\installer\DataTools-Setup-<version>.exe
```

Current release: **DataTools-Setup-1.1.0.exe**

### Install Steps

1. Run `DataTools-Setup-<version>.exe` as Administrator.
2. Follow the setup wizard. Default install location: `C:\Program Files\DataTools`.
3. Optionally enable **Create a desktop icon** in the installer.
4. Launch DataTools after installation.

### First-Time Setup After Install

On first launch, configure the database paths and working folders in the DataTools settings panel before using any features. See the **DataTools Settings - Database and Folder Paths** section above.

### Building a New Release

For developers building a new installer from source:

```powershell
.\.venv\Scripts\Activate.ps1
.\DataTools\build\build_release.ps1 -Version <x.y.z> -Clean
```

This builds the EXE with PyInstaller and produces the installer via Inno Setup. See [DataTools README_RELEASE.md](../DataTools/README_RELEASE.md) for the full build checklist.

---

## DataTools MAC Provisioning

DataTools includes a MAC provisioning feature that writes a valid MAC address directly to a device via OCA. It is used in two scenarios:

**1. Repair parts pre-flashed at the production site**
Replacement PCBs or backplates are delivered to ADAM Audio Berlin already flashed with a valid MAC address by the factory. DataTools is used to verify and register the MAC in the provisioning database without running a full APx EOL sequence.

**2. Decoupled provisioning**
When MAC provisioning needs to be separated from the APx production sequence - for example during rework, repair, or manual provisioning flows - DataTools can provision the MAC independently of the `provision_mac` workstation command.

In both cases the `mac_db_path` setting in DataTools must point to the same MAC provisioning database used by the production tool. See **DataTools Settings - Database and Folder Paths** above.

---

## Firmware Version - Required Updates on Change

The target firmware version is stored in two places. **Both must be updated whenever the production firmware changes.**

| Location | Where to change |
|---|---|
| **APx project user variable** | Project > Project Properties > Variables > `TargetFirmware` |
| **Sub-Pro SN/FW Workstation settings** | Settings panel > Target Firmware Version |

If either location is not updated, the tools will produce errors. The APx sequence will fail with a firmware mismatch and stop. The SN/FW Workstation will either reject units with the new firmware or attempt to flash the wrong version.

---

## Launching the Matching App and SN/FW Workstation

The Matching App and the Sub-Pro SN/FW Workstation are Python applications, not EXE files. They must be launched via the virtual environment Python from the correct working directory. The easiest way to do this on a production workstation is a batch file with a desktop shortcut.

### Locations

| Application | Launch script |
|---|---|
| Matching App | `<tool root>\Matching_App\run.py` |
| Sub-Pro SN/FW Workstation | `<tool root>\SubPro_SN_FW_Workstation\run.py` |

`<tool root>` is the full path to the Audio-Precision repository on the workstation, for example:
```
C:\Users\<User>\OneDrive - Focusrite Group\<Site>\Audio-Precision
```

### Batch Files

Create a `.bat` file for each application. Replace `<tool root>` with the actual path.

**Matching App** - save as e.g. `Launch_MatchingApp.bat`:

```bat
@echo off
cd /d "<tool root>"
"<tool root>\.venv\Scripts\pythonw.exe" Matching_App\run.py
```

**Sub-Pro SN/FW Workstation** - save as e.g. `Launch_SubProWorkstation.bat`:

```bat
@echo off
cd /d "<tool root>"
"<tool root>\.venv\Scripts\pythonw.exe" SubPro_SN_FW_Workstation\run.py
```

Use `pythonw.exe` to suppress the console window. Use `python.exe` instead if you want to see error output during troubleshooting.

### Desktop Shortcut

1. Place the `.bat` file in a convenient location (e.g. the tool root or a shared network folder).
2. Right-click the `.bat` file > **Send to > Desktop (create shortcut)**.
3. Optionally right-click the shortcut > **Properties > Change Icon** to set a custom icon.

---

## Repository

The production tool source code is hosted on GitHub:

**https://github.com/ThiloRode/Audio-Precision**

Clone or update the repository on a new workstation:

```powershell
git clone https://github.com/ThiloRode/Audio-Precision.git
```

After cloning, set up the virtual environment and install dependencies before use. See the **Python Virtual Environment and PythonRunner** section above.

