# System Architecture

The repository contains a general-purpose production backend for ADAM Audio manufacturing. It combines OCA device control, serial hardware integration, AP measurement processing, MAC address provisioning, and driver matching into a single CLI-driven backend that multiple front-ends can call.

The backend was built alongside Audio Precision APx500 projects, but it is not tightly coupled to APx500. Any front-end that can start a process and read stdout can use the same commands. Current callers include APx500 shell steps, two Tkinter desktop GUIs, and direct operator use from a terminal.

The system has four main runtime shapes:

1. APx500 starts Python as an external shell step and reads stdout to validate test results or store values into project variables.
2. A custom GUI or script calls `adam_workstation.py` as a subprocess and reads stdout to drive a workflow.
3. Operators run desktop GUIs for matching and Sub-Pro serial/firmware provisioning.
4. Python modules call each other directly for local processing, database writes, and hardware/OCA access.

## High-Level Flow

```mermaid
flowchart LR
    APx[APx500 ShellStep] -->|pythonw.exe adam_workstation.py ...| WS
    GUI[Custom GUI or Script] -->|subprocess, reads stdout| WS
    Operator[Operator terminal] -->|python adam_workstation.py ...| WS
    WS[AdamWorkstation CLI backend] -->|stdout response| APx
    WS -->|stdout response| GUI
    WS -->|stdout response| Operator
    WS -->|local calls| OCA[OCADevice / OCP1 tool wrapper]
    WS -->|local serial| HW[SwitchBox and Scanner]
    WS -->|local files| CSV[CSV and measurement processing]
    WS -->|SQLite| MatchDB[Matching database]
    WS -->|SQLite| MacDB[MAC provisioning database]
    WS -->|TCP JSON when --server is used (optional)| Service[ADAM Service]
    Service -->|JSON response| WS
    Connector[AdamConnector] -->|UDP discovery / service check| Service
    MatchingApp[Matching App GUI] --> MatchDB
    SubProGUI[Sub-Pro SN/FW GUI] --> OCA
    SubProGUI --> SubProDB[Sub-Pro workstation database]
```

Some workstation commands support optional service execution. When a command has `--server` support, the workstation forwards the request to the service and prints the returned response. Not all commands support service-backed execution; some remain local only.

## Process Boundaries

| Boundary | Mechanism | Main files | Notes |
|---|---|---|---|
| APx500 to workstation | External shell step, stdout text | [../adam_workstation.py](../adam_workstation.py), [../cli/workstation_parser.py](../cli/workstation_parser.py) | Most production-facing behavior lives here. |
| Workstation to service | TCP socket with JSON request and string response | [../adam_workstation.py](../adam_workstation.py), [../adam_service.py](../adam_service.py) | Only commands with `--server` or explicit service logic use this path. |
| Service discovery | UDP broadcast on port `65433` | [../adam_service.py](../adam_service.py), [../adam_connector.py](../adam_connector.py) | Service broadcasts JSON metadata every few seconds. |
| Workstation to OCA devices | `OCADevice` wrapper around `oca_tools.OCP1ToolWrapper` | [../oca/oca_device.py](../oca/oca_device.py) | OCA communication is local to the workstation, not the service. |
| Workstation to serial hardware | Serial managers wrapping hardware classes | [../serial_managers](../serial_managers), [../hardware](../hardware) | SwitchBox and scanner are initialized lazily. |
| Matching measurement upload | Direct SQLite write | [../analysis/measurement_upload.py](../analysis/measurement_upload.py), [../Matching_App/app/database.py](../Matching_App/app/database.py) | `upload_measurement` writes to the matcher DB by default. |
| MAC provisioning | Direct SQLite write plus OCA read/write | [../SubProMACAddresses/mac_provisioner.py](../SubProMACAddresses/mac_provisioner.py), [../SubProMACAddresses/mac_database.py](../SubProMACAddresses/mac_database.py) | APx validates `successful` or `Error: ...`. |

## Repository Areas

| Area | Responsibility |
|---|---|
| Root `*.approjx` files | APx500 project packages. They are ZIP files containing `project.xml` and assets. Shell steps invoke Python tools. |
| [../adam_workstation.py](../adam_workstation.py) | Main CLI dispatcher, stdout API, OCA/device/hardware/CSV/MAC/matching command handlers. |
| [../cli](../cli) | Command-line parser definitions. |
| [../adam_service.py](../adam_service.py) | Optional service for helper functions, CSV processing, biquad calculation, measurement-trial checks, service logging, and measurement ingestion. |
| [../adam_connector.py](../adam_connector.py) | Finds, checks, and can start the ADAM service. |
| [../analysis](../analysis) | CSV processing, AP measurement parsing, gain calibration, measurement upload. |
| [../oca](../oca) | OCA device command wrapper. |
| [../hardware](../hardware) | Low-level serial hardware classes. |
| [../serial_managers](../serial_managers) | Retry/logging wrappers for hardware operations. |
| [../Matching_App](../Matching_App) | Driver matching GUI, matcher DB, Hungarian pairing algorithm. |
| [../SubPro_SN_FW_Workstation](../SubPro_SN_FW_Workstation) | Tkinter app for Sub-Pro firmware check, serial-number write, part capture, and history export. |
| [../SubProMACAddresses](../SubProMACAddresses) | MAC address pool, provisioning log, golden-sample registration, MAC assignment. |
| [../DefaultReferences](../DefaultReferences) | Reference CSV source copied into APx data directories by `setup_references`. |
| [../logs](../logs) | Runtime logs and generated reports. |

## Logging

Workstation logging is configured to file only so APx500 sees clean stdout. Logs are written under `logs/adam_audio` next to the scripts, for example:

- `adam_workstation_log_YYYY-MM-DD.log`
- `adam_service_log_YYYY-MM-DD.log`

Do not add console logging to production commands that are called by APx500. A stray `print()` can break a shell step that expects `True`, `successful`, a serial number, or an output path.

## Local Versus Service Execution

Several workstation commands support `--server`. Without `--server`, they run locally. With `--server`, the workstation sends a JSON command to the service and prints the service response.

Current production operation is local workstation execution. The service path is optional and kept ready for scenarios where centralized helper processing across multiple workstations becomes useful.

`--host` implies `--server` only for commands whose parsed arguments have a `server` attribute. OCA commands commonly accept `--host` in APx project files, but OCA itself still runs locally through `OCADevice`; the host is mainly useful for service-backed helpers and service logging.

## APx Project Program Calls

The *.approjx files contain ShellStep entries such as:

```xml
<Command>pythonw.exe</Command>
<Arguments>adam_workstation.py provision_mac $(ProductName) $(SerialNumber) $(DefaultMACAddress)</Arguments>
<WaitForExit>WaitForExitValidateResponse</WaitForExit>
<ExpectedResponse>successful</ExpectedResponse>
```

The APx shell step can:

- validate stdout against `ExpectedResponse`;
- store stdout in `ProgramOutputVariable`;
- ignore stdout;
- use `DoNotWait` for asynchronous launches.

See [APx500 Integration](apx500-integration.md) for the response contracts.