# ADAM Audio Production System

Production backend for automated end-of-line testing and device provisioning at ADAM Audio manufacturing sites. Integrates Audio Precision APx500 measurements, OCA device control, serial hardware, MAC address provisioning, driver matching, and operator tooling into a single CLI-driven system.

Repository: **https://github.com/ThiloRode/Audio-Precision**

Full documentation: **[docs/index.md](docs/index.md)**

---

## Architecture

The system is built around a single CLI backend (`adam_workstation.py`) that any front-end can call by starting a process and reading stdout. Current callers: APx500 shell steps, Tkinter desktop GUIs, batch scripts, and operators in a terminal.

```
APx500 ShellStep  ─┐
Custom GUI        ─┤──► adam_workstation.py ──► stdout (one stable line per command)
Operator terminal ─┘         │
                             ├──► OCADevice / adam-audio-asubs-cli.exe ──► AES70 device (TCP)
                             ├──► SwitchBox / Scanner (USB serial)
                             ├──► analysis/ (CSV processing)
                             ├──► Matching_App/Data/db/matcher.db (SQLite)
                             ├──► SubProMACAddresses/ (MAC provisioning)
                             └──► adam_service.py (optional TCP helper, future cloud adapter)
```

---

## Applications

| Application | Type | Purpose |
|---|---|---|
| `adam_workstation.py` | CLI | Main production backend. Called by APx500 and all other front-ends. |
| `adam_service.py` | TCP service | Optional centralized helper and future cloud integration point. |
| `Matching_App/` | Tkinter GUI | L/R driver module matching using RMSE and Hungarian algorithm. |
| `SubPro_SN_FW_Workstation/` | Tkinter GUI | Firmware check, serial-number programming, part scanning, history. |
| `DataTools/` | Kivy EXE | Measurement data viewer, database browser, MAC provisioning. |
| `Switch/Switch.ino` | RP2040 firmware | SwitchBox audio routing controller (Raspberry Pi Pico). |

---

## Setup

### Prerequisites

- Python 3.8+ (3.11 recommended for DataTools builds)
- Git

### Clone and install

```powershell
git clone https://github.com/ThiloRode/Audio-Precision.git
cd Audio-Precision
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Install the OCA tools package

```powershell
cd .venv\src\adam-audio-tools
python rebuild_and_reinstall.py
cd ..\..\..
```

### APx500 integration

Set the `PythonRunner` user variable in each APx project to:
```
<repo root>\.venv\Scripts\pythonw.exe
```

All shell steps use `$(PythonRunner)` as the `Command` field.

---

## Quick Start

```powershell
# OCA device — discover and read serial number
python adam_workstation.py discover_and_unlock_factory_settings DEADBEEF
python adam_workstation.py get_serial_number SubPro-4923EE

# SwitchBox routing
python adam_workstation.py set_channel 1
python adam_workstation.py open_box

# Barcode scanner
python adam_workstation.py scan_serial

# CSV processing
python adam_workstation.py generate_timestamp_extension
python adam_workstation.py setup_references "C:\Data\Sub8PRO" --mono

# MAC provisioning
python adam_workstation.py provision_mac SubPro-4923EE CI6600007 DE:AD:BE:EF:00:00
```

```powershell
# Optional: start the ADAM Service
python adam_service.py

# Find service on network
python adam_connector.py --find
```

---

## Launching the Desktop Apps

The Matching App and SN/FW Workstation are Python scripts. Use batch files with desktop shortcuts:

**Matching App:**
```bat
@echo off
cd /d "<repo root>"
"<repo root>\.venv\Scripts\pythonw.exe" Matching_App\run.py
```

**Sub-Pro SN/FW Workstation:**
```bat
@echo off
cd /d "<repo root>"
"<repo root>\.venv\Scripts\pythonw.exe" SubPro_SN_FW_Workstation\run.py
```

DataTools is distributed as a Windows installer: `DataTools\build\installer\DataTools-Setup-1.1.0.exe`

---

## Documentation

| Document | Contents |
|---|---|
| [docs/overview.md](docs/overview.md) | System overview, architecture, technology stack |
| [docs/workstation-cli-reference.md](docs/workstation-cli-reference.md) | All CLI commands and stdout contracts |
| [docs/apx500-integration.md](docs/apx500-integration.md) | APx500 shell step patterns, PythonRunner setup |
| [docs/service-protocol.md](docs/service-protocol.md) | ADAM Service TCP/UDP protocol |
| [docs/hardware-integration.md](docs/hardware-integration.md) | SwitchBox and scanner architecture |
| [docs/ocp1-tool-wrapper.md](docs/ocp1-tool-wrapper.md) | OCP1ToolWrapper internals and build instructions |
| [docs/matching-system.md](docs/matching-system.md) | Matching DB, pairing algorithm, verify_system |
| [docs/mac_provisioning_workflow.md](docs/mac_provisioning_workflow.md) | MAC provisioning flow |
| [docs/kb.md](docs/kb.md) | Knowledge Base: references, venv, logs, DataTools setup |
| [docs/faq.md](docs/faq.md) | FAQ: common failures and how to resolve them |
| [docs/index.md](docs/index.md) | Full documentation map |

