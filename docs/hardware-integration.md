# Hardware Integration

The production workstation controls local serial hardware through [../hardware](../hardware) and [../serial_managers](../serial_managers). Hardware managers are initialized lazily by [../adam_workstation.py](../adam_workstation.py), so the CLI can run helper and OCA commands without requiring serial devices to be connected.

## Components

| Component | Files | Purpose |
|---|---|---|
| Base serial device | [../hardware/serial_device.py](../hardware/serial_device.py) | Shared serial connection and monitoring behavior. |
| SwitchBox | [../hardware/switchbox.py](../hardware/switchbox.py), [../serial_managers/switchbox_manager.py](../serial_managers/switchbox_manager.py) | Routes test channels and opens/releases the physical box. |
| Honeywell scanner | [../hardware/honeywell_scanner.py](../hardware/honeywell_scanner.py), [../serial_managers/scanner_manager.py](../serial_managers/scanner_manager.py) | Triggers and reads barcode/serial scans. |
| Serial manager base | [../serial_managers/base_serial_manager.py](../serial_managers/base_serial_manager.py) | Retry and workstation logging pattern for serial devices. |

## Why The Manager Layer Exists

The manager classes in [../serial_managers](../serial_managers) are not just wrappers. They are the production-stability layer between CLI commands and fragile serial hardware.

Without managers, each CLI command would need to re-implement connection checks, retries, lock handling, disconnect/cleanup, and service logging. The manager layer centralizes this behavior so all hardware commands are consistent and safer under production timing issues.

Key reasons managers are used:

1. Retry behavior is standardized via `BaseSerialManager.execute_with_retry(...)`.
2. Serial reconnection/reset is handled between retry attempts.
3. Thread locks prevent overlapping access to one serial device.
4. Hardware readiness checks happen before command execution.
5. Operation metadata is logged through `WorkstationLogger` for traceability.
6. CLI handler code in [../adam_workstation.py](../adam_workstation.py) stays small and focused on stdout contract.

## Manager Responsibilities

| Layer | Responsibility | Why it matters in production |
|---|---|---|
| `BaseSerialManager` | Shared retry loop, delay between retries, serial readiness checks, reset hook, service log forwarding. | Prevents copy/paste error handling and gives predictable behavior across all devices. |
| `SwitchBoxManager` | Validates channel, opens/closes serial connection per operation, starts/stops listener thread, requests/updates status, retries on failure. | Avoids stale serial state and keeps routing commands deterministic. |
| `ScannerManager` | Checks scanner connection state, triggers scan command, retries failed scans, disconnects cleanly after each scan. | Reduces random scan failures from transient serial issues and guarantees clean device reuse. |
| Hardware classes (`SwitchBox`, `HoneywellScanner`) | Device-specific protocol commands (`SET_CHANNEL_x`, `OPEN_BOX`, scanner trigger bytes). | Keeps protocol details out of workstation command handlers. |

## Command Execution Flow

For all three workstation hardware commands (`set_channel`, `open_box`, `scan_serial`), the flow is:

1. CLI handler in [../adam_workstation.py](../adam_workstation.py) calls the relevant manager method.
2. Manager calls `execute_with_retry(...)` from [../serial_managers/base_serial_manager.py](../serial_managers/base_serial_manager.py).
3. Manager confirms serial device availability (`connected` checks).
4. Manager enters a device lock to avoid concurrent serial access.
5. Manager opens serial connection, executes device-specific command, captures result.
6. Manager logs structured operation metadata through service logging helper.
7. Manager disconnects serial connection in `finally` cleanup.
8. Result is returned to CLI handler and printed as the stdout contract.

This design is why hardware failures usually show up as controlled `Error: ...` or `NaN` output instead of a raw traceback in APx-facing runs.

## Workstation Commands

| Command | Args | Stdout contract | APx use |
|---|---|---|---|
| `set_channel` | `1` or `2` | `Channel set to 1`, `Channel set to 2`, or `Error: ...` | Validate response before measurement routing. |
| `open_box` | none | `Box status: <status>` or `Error: ...` | Often run with output ignored. |
| `scan_serial` | none | Scanned serial number, or `NaN` | Store output in APx variable. |

The current parser only accepts channels `1` and `2`. If an APx project or older README section references additional channels, verify the hardware and parser before using those values.

## APx Pattern

Typical APx shell step for routing:

```xml
<Command>pythonw.exe</Command>
<Arguments>adam_workstation.py --host $(ADAMServiceIP) set_channel 1</Arguments>
<ExpectedResponse>Channel set to 1</ExpectedResponse>
```

Typical APx shell step for scanning:

```xml
<Command>pythonw.exe</Command>
<Arguments>adam_workstation.py scan_serial</Arguments>
<ProgramOutputVariable>SerialNumber</ProgramOutputVariable>
```

The scanner command should be treated as a value getter. APx should store its stdout in a variable; it should not compare it with a fixed string unless a fixed test barcode is intentionally being used.

## Failure Behavior

- `set_channel` and `open_box` print `Error: ...` if the manager or hardware operation raises an exception.
- `scan_serial` logs the exception and prints `NaN` so APx can detect a failed scan without parsing a traceback.
- Hardware initialization happens on first command use; startup failures therefore appear at the first hardware command, not at CLI import time.

## Logging

Hardware operations are logged through the workstation logger and manager layer. Keep these logs out of stdout, because APx shell steps may validate stdout literally.

## Troubleshooting Checklist

1. Confirm the device is visible to Windows and not held open by another process.
2. Run the command from PowerShell in the repository root.
3. Check `logs/adam_audio/adam_workstation_log_YYYY-MM-DD.log`.
4. For APx-only failures, compare the APx `ExpectedResponse` with the live stdout shown by the PowerShell command.
5. If the scanner prints `NaN`, investigate serial connection, scanner trigger behavior, and barcode contents.