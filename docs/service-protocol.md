# ADAM Service Protocol

The ADAM service is an optional TCP/IP helper process implemented in [../adam_service.py](../adam_service.py). It is used for helper functions, CSV processing, biquad calculation, measurement-trial checks, workstation logging, and service-side measurement insertion.

In the current setup, workstation commands are typically executed locally without the service. Service integration is prepared and can be enabled when needed, especially for multi-workstation or centralized-processing scenarios.

If service mode is enabled, [../adam_connector.py](../adam_connector.py) is the key discovery and startup helper. It handles the practical cases of:

1. Service already running, but IP unknown.
2. Service not running yet and must be started.
3. Specific target IP provided, with discovery fallback if unreachable.

OCA device communication is intentionally not handled by the service. OCA commands run locally on the workstation through [../oca/oca_device.py](../oca/oca_device.py).

## Starting The Service

```powershell
python adam_service.py
```

Defaults:

| Setting | Default |
|---|---|
| Host binding | `0.0.0.0` |
| TCP command port | `65432` |
| UDP discovery port | `65433` |
| Service name | `ADAMService` |
| Discovery interval | `2` seconds after startup burst |

## Discovery Broadcast

The service broadcasts JSON over UDP port `65433`. The payload includes:

| Field | Meaning |
|---|---|
| `service` | Service name, usually `ADAMService`. |
| `company` | `ADAM Audio`. |
| `ip` | Service IP address selected from the primary network route. |
| `port` | TCP command port. |
| `hostname` | Windows hostname. |
| `timestamp` | Broadcast timestamp. |
| `version` | Service protocol version string. |
| `capabilities` | Capability list such as `BiquadFilters`, `MeasurementTrials`, `ProductionLogging`, `HelperFunctions`, `WorkstationSupport`. |
| `discovery_port` | UDP discovery port. |
| `status` | `running` or `goodbye`. |
| `note` | Notes such as `OCA communication handled locally by workstations`. |

[../adam_connector.py](../adam_connector.py) listens for these broadcasts and can also check or start the service from APx shell steps.

## AdamConnector: Check, Find, Start

[../adam_connector.py](../adam_connector.py) provides two main modes:

1. `--check`: returns availability status.
2. `--find`: returns a usable service IP.

Common commands:

```powershell
# Quick availability check via discovery
python adam_connector.py --check

# Check specific IP first, then discovery fallback
python adam_connector.py --check --ip 192.168.1.100

# Find service IP (prints IP to stdout)
python adam_connector.py --find

# Find specific IP first, then discovery fallback
python adam_connector.py --find --ip 192.168.1.100

# Start service if needed, then find IP
python adam_connector.py --find --start-service
```

Observed outputs used by automation:

| Mode | Success stdout | Failure stdout/stderr | Exit code |
|---|---|---|---|
| `--check` | `ADAM Service available` | `No ADAM Service available` | `0` success, `1` failure |
| `--find` | `<service_ip>` | `Warning: No ADAM service found` (stderr) | `0` success, `1` failure |

Startup behavior with `--start-service`:

1. Check specific IP first when `--ip` is provided.
2. Check discovery for any running service.
3. If none found, start `adam_service.py` using current Python interpreter.
4. Poll until reachable or timeout.
5. If startup timeout is reached, terminate the spawned process and return failure.

## TCP Command Format

Workstation clients open a TCP connection, send one JSON object encoded as UTF-8, and read a UTF-8 response string. The service reads until the JSON parses successfully, processes the command, sends the response, and closes the connection.

Minimal request:

```json
{"action": "generate_timestamp_extension"}
```

Example CSV request:

```json
{
  "action": "extract_csv_columns",
  "input_path": "C:/Data/source.csv",
  "columns": [0, 1, 2],
  "output_filename": "extracted.csv",
  "output_dir": "C:/Data/Temp"
}
```

The response is always a string. Some actions return plain text paths, some return JSON encoded as a string, and failures return strings starting with `Error:`.

## Service Actions

| Action | Request fields | Response |
|---|---|---|
| `generate_timestamp_extension` | none | Timestamp suffix string. |
| `construct_path` | `paths: list[str]` | Joined path or `Error: ...`. |
| `get_timestamp_subpath` | none | Date/time subpath string. |
| `generate_file_prefix` | `strings: list[str]` | Combined prefix or `Error: ...`. |
| `extract_csv_columns` | `input_path`, `columns`, `output_filename`, optional `output_dir` | Output path or `Error: ...`. |
| `split_ap_distortion_csv` | `input_path`, optional `output_dir`, `fraction`, `output_prefix` | JSON mapping metric names to paths or `Error: ...`. |
| `octave_smooth_ap_csv` | `input_path`, `fraction`, optional `output_filename`, `output_dir` | Output path or `Error: ...`. |
| `merge_ap_distortion_csvs` | `input_paths`, optional `output_dir`, `fraction`, `output_prefix` | JSON mapping metric names to paths or `Error: ...`. |
| `get_biquad_coefficients` | `filter_type`, `gain`, `peak_freq`, `Q`, `sample_rate` | JSON/list coefficient string or `Error: ...`. |
| `check_measurement_trials` | `serial_number`, `csv_path`, `max_trials` | Permission/result text. |
| `log_workstation_task` | workstation log payload | Logging result text. |
| `add_measurement` | measurement payload | JSON result or `Error: ...`. |

## Workstation `--server` Path

For commands that define `--server`, [../adam_workstation.py](../adam_workstation.py) builds a JSON command, sends it to the service, and prints the raw response to stdout. This means APx500 still sees only stdout, even when the actual work was done by the service.

Host resolution behavior for service-backed commands:

1. If `--host` is provided, workstation connects directly to that IP.
2. If `--host` is omitted, workstation calls `AdamConnector.find_service_ip(...)` (discovery) to resolve a service IP.
3. If discovery fails, workstation prints `Error: No ADAM service available. Use --host to specify manually.`

Examples:

```powershell
# Local execution (no service)
python adam_workstation.py extract_csv_columns input.csv 0 1 out.csv

# Service-backed execution with explicit IP
python adam_workstation.py --host 192.168.1.166 extract_csv_columns input.csv 0 1 out.csv

# Service-backed execution with auto-discovery
python adam_workstation.py extract_csv_columns input.csv 0 1 out.csv --server
```

## Error Handling

Invalid command objects return `Error: Invalid command format.` Unknown actions return `Error: Unknown action.` Validation failures and exceptions return `Error: ...`.

For APx-facing workflows, prefer workstation commands over direct service calls so the stdout contract stays in one place.