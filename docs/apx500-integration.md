# APx500 Integration

APx500 is one of several possible front-ends for the workstation backend. It integrates through project `ShellStep` entries that run `pythonw.exe` or `python.exe`, pass script arguments, and read stdout as the result of the step.

Because the backend is designed to be called by any front-end that can start a process, APx500 gets the same interface as a custom GUI or a script would: one stdout line per command, a stable contract for success and failure. The main APx-specific detail is that its shell step model can validate stdout literally, store it in a variable, or ignore it entirely.

This is the most important production contract in the repository: for any external caller, stdout is the API.

## Python Executable and Virtual Environment

APx500 shell steps must call the Python executable from the tool's **virtual environment**, not the system Python. The venv isolates the production tool's dependencies so that system-level Python updates or package changes cannot break the tool.

The path to `pythonw.exe` inside the venv is stored as an APx project variable named **`PythonRunner`** and referenced as `$(PythonRunner)` in every shell step's `Command` field.

### Setting `PythonRunner`

In APx500: **Project → Project Properties → Variables tab → add or edit `PythonRunner`**.

Set the value to the full absolute path of `pythonw.exe` inside the venv:

```
C:\Users\<User>\OneDrive - Focusrite Group\<Site>\Production\.venv\Scripts\pythonw.exe
```

Example from a production machine:
```
C:\Users\TristarProduction\OneDrive - Focusrite Group\TristarProduction\.venv\Scripts\pythonw.exe
```

Use `pythonw.exe` (not `python.exe`) to suppress the console window during APx sequences.

> **Per-site configuration:** The venv path is machine- and user-specific. Each production workstation must have its own `PythonRunner` value set in the APx project properties. Do not hard-code `pythonw.exe` in the `Command` field — it will resolve to the system Python and ignore the venv.

### Shell Step Command Field

All shell steps use `$(PythonRunner)` as the `Command`, with `adam_workstation.py` as the first argument:

| Field | Value |
|---|---|
| Command | `$(PythonRunner)` |
| Arguments | `adam_workstation.py <command> [args...]` |
| Working Folder | `$(ProjectDir)` |

---

## Shell Step Model

Typical APx project settings:

| APx field | Typical value | Meaning |
|---|---|---|
| `Command` | `$(PythonRunner)` | Path to `pythonw.exe` inside the venv — set via project variable. |
| `Arguments` | `adam_workstation.py ...` | Script and command arguments. |
| `WorkingDirectory` | `$(ProjectDir)` | Usually the repository root or APx project directory. |
| `WaitForExit` | `WaitForExitValidateResponse` | Wait and compare stdout to `ExpectedResponse`. |
| `ExpectedResponse` | `True`, `successful`, `Channel set to 1` | Exact expected stdout text. |
| `ProgramOutputVariable` | `SerialNumber`, `TimestampExtension`, etc. | Store stdout in an APx variable. |

The active APx project files contain multiple shell steps across common command families: path helpers, timestamp helpers, serial scanning, switchbox routing, reference setup, reference filtering, Sub-Pro EOL setup, MAC provisioning, measurement upload, and matching verification.

### Screenshot: Shell Step Editor UI

**TODO:** Add screenshot showing the APx500 Shell Step dialog with:
- `Command` field set to `pythonw.exe`
- `Arguments` showing a typical call like `adam_workstation.py construct_path <args>`
- `ExpectedResponse` field with validation text
- `ProgramOutputVariable` field capturing stdout into an APx variable

## Stdout Rules

For commands used by APx500:

1. Print only the intended response to stdout.
2. Put diagnostics in the log file, not stdout.
3. Use stable, exact strings when APx validates output.
4. Prefer `Error: ...` for production errors that APx or an operator must recognize.
5. Do not rely on Python return values unless the caller is another Python function.

Examples of stdout contracts:

| Command | APx usage | Expected stdout |
|---|---|---|
| `set_channel 1` | Validate response | `Channel set to 1` |
| `set_channel 2` | Validate response | `Channel set to 2` |
| `scan_serial` | Store output variable | Serial number, or `NaN` on scan failure |
| `generate_timestamp_extension` | Store output variable | Timestamp suffix |
| `construct_path ...` | Store output variable | Constructed path |
| `set_*` OCA commands | Validate response | Usually `True` on success |
| `filter_reference_by_limits ...` | Validate response | `successful` |
| `eol_init_sub ...` | Validate response | `successful`, or `Error: ...` |
| `provision_mac ...` | Validate response | `successful`, or `Error: ...` |
| `upload_measurement ...` | Validate response | `True` or `False` |
| `verify_system ...` | Validate response | `True` or error text |

### Screenshot: APx Variable Usage Examples

**TODO:** Add screenshots showing:
1. Input variable substitution: `Arguments` field with APx variable tokens like `$(ProductName)`, `$(SerialNumber)`, `$(DefaultMACAddress)`
2. Output variable capture: `ProgramOutputVariable` field storing shell step stdout into custom APx variables (e.g., `TimestampExtension`, `GeneratedPath`, `CalculatedGain`)
3. Conditional branching: Using `ProgramOutputVariable` outputs to make go/no-go decisions or route to different test paths

## Common APx Calls Found In Projects

The current APx projects call these `adam_workstation.py` commands most often:

| Command | Typical role |
|---|---|
| `construct_path` | Build APx data, measurement, reference, temp, and statistics paths. |
| `generate_timestamp_extension` | Create per-run filename suffix. |
| `generate_file_prefix` | Combine serial number and timestamp into file prefix. |
| `get_timestamp_subpath` | Create date-based subfolder. |
| `setup_references` | Ensure `References` exists in the active data directory. |
| `set_channel` | Route SwitchBox channel 1 or 2. |
| `open_box` | Open or release the hardware box. |
| `scan_serial` | Read operator-scanned serial into an APx variable. |
| `is_golden_sample` | Branch between production and golden-sample paths. |
| `is_default_serial` | Reject units that still have the expected default serial in EOL mode. |
| `filter_reference_by_limits` | Create temporary reference curves constrained by limit ranges. |
| `compensate_lr_diff` | Apply microphone L/R compensation to AP RMS output. |
| `calibrate_gain` | Calculate gain offset from a measured file and reference file. |
| `set_gain_calibration` | Write calculated gain calibration to the OCA device. |
| `discover_and_unlock_factory_settings` | Find product name and unlock factory settings. |
| `init_sub` / `eol_init_sub` | Initialize Sub-Pro units for test/EOL. |
| `provision_mac` | Assign unique MAC address after successful EOL. |
| `upload_measurement` | Store matching measurement data into the matcher database. |
| `verify_system` | Confirm two matched modules are installed in a system. |

Some older project entries still reference legacy scripts or stale expectations, such as `ap_client.py`, `check_server.py`, `init_asub`, or expected text that does not match the live handler. Treat those APx entries as project-maintenance findings, not as current Python API.

## Important Stale/Mismatch Findings

These are documentation-relevant because they affect production debugging:

| Finding | Current source behavior | Impact |
|---|---|---|
| `get_device_biquad` and `set_device_biquad` exist in the argparse parser but are absent from `AdamWorkstation.command_map`. | The command parses, then exits as unknown command. | Do not document them as usable until handlers are added. |
| Some APx `scan_serial` shell steps include `ExpectedResponse=Channel set to 1` while storing `SerialNumber`. | The live handler prints the scanned serial or `NaN`. | The `ExpectedResponse` field is not active in those steps; the actual stdout is stored correctly into the variable regardless. Legacy copy-paste artifact. |
| Some APx `open_box` shell steps include `ExpectedResponse=Channel set to 2`. | The live handler prints `Box status: ...` or `Error: ...`. | Validate project behavior before changing code or APx expectations. |
| Some APx `calibrate_gain` shell steps expect `True`. | The live handler prints a numeric dB offset such as `-1.25`, or `ERROR: ...`. | In output-variable mode the numeric value is correct; the expected text is stale. |
| `init_asub` appears in an APx project. | Live command is `init_sub`. | Project entry is legacy or broken. |

## Adding A New APx-Callable Command

1. Add the parser entry in [../cli/workstation_parser.py](../cli/workstation_parser.py).
2. Add the command to `AdamWorkstation.command_map` in [../adam_workstation.py](../adam_workstation.py).
3. Implement the handler so it prints one clear response.
4. If it can fail in production, use `Error: <human-readable reason>`.
5. Add the exact stdout contract to [Workstation CLI Reference](workstation-cli-reference.md).
6. Update the APx `ShellStep` `ExpectedResponse` or `ProgramOutputVariable` accordingly.

## Choosing Response Shapes

Use these conventions for new commands:

| Command type | Preferred stdout |
|---|---|
| APx pass/fail gate | `successful` or `Error: ...` |
| Boolean helper | `True` or `False` |
| Value getter | Bare value only, for example serial number, firmware version, path, or numeric offset |
| Structured admin command | JSON object on one line |
| Multi-file processing command | One output path per line, or JSON when the caller is service/client code |

Avoid adding banners, debug traces, or explanatory paragraphs to stdout.

### Screenshot: Complete Parameter Flow Example

**TODO:** Add annotated screenshot showing a real APx project shell step that:
- Takes multiple inputs from APx variables (e.g., `$(ProductName)`, `$(SerialNumber)`)
- Passes them as command arguments to `adam_workstation.py`
- Validates or captures the stdout response
- Stores output in a downstream variable (e.g., `$(CalculatedGainOffset)`)
- Shows how that output is then used in subsequent test steps or conditionals