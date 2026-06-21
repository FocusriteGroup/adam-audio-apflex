# OCA Device Control

OCA device control is implemented by [../oca/oca_device.py](../oca/oca_device.py). The `OCADevice` class is a thin production wrapper around `oca_tools.oca_utilities.OCP1ToolWrapper`.

## Targeting

`OCADevice(target, port=50001, timeout=5, workstation_id=None, service_host=None, service_port=65432)` accepts either:

- an IPv4 address, in which case the wrapper is created with `target_ip` and `port`; or
- a device/mDNS name, in which case OCA CLI options include `--target <name>`.

The workstation helper `_get_oca_device(args)` constructs `OCADevice` instances from parsed CLI arguments.

## Supported Operations

| Workstation command | OCADevice method | OCA command path |
|---|---|---|
| `discover` | `discover` | `discover --timeout ...` |
| `get_gain_calibration` | `get_gain_calibration` | `gain-calibration get` |
| `set_gain_calibration` | `set_gain_calibration` | `gain-calibration set --value ...` |
| `get_mode` | `get_mode` | `mode get` |
| `set_mode` | `set_mode` | `mode set --position ...` |
| `get_audio_input` | `get_audio_input` | `audio-input get` |
| `set_audio_input` | `set_audio_input` | `audio-input set --position ...` |
| `get_bass_management` | `get_bass_management` | `bass-management mode get` |
| `set_bass_management` | `set_bass_management` | `bass-management mode set --position ...` |
| `get_bass_management_bypass` | `get_bass_management_bypass` | `bass-management bypass get` |
| `set_bass_management_bypass` | `set_bass_management_bypass` | `bass-management bypass set --position ...` |
| `get_gain` | `get_gain` | `gain get` |
| `set_gain` | `set_gain` | `gain set --value ...` |
| `get_phase_delay` | `get_phase_delay` | `phase-delay get` |
| `set_phase_delay` | `set_phase_delay` | `phase-delay set --position ...` |
| `get_mute` | `get_mute` | `mute get` |
| `set_mute` | `set_mute` | `mute set --position ...` |
| `get_mac_address` | `get_mac_address` | `factory-settings get-mac-address` |
| `set_mac_address` | `set_mac_address` | `factory-settings set-mac-address --value ...` |
| `get_serial_number` | `get_serial_number` | `factory-settings get-serial-number` |
| `set_serial_number` | `set_serial_number` | `factory-settings set-serial-number --value ...` |
| `get_model_description` | `get_model_description` | factory/device identity query |
| `get_firmware_version` | `get_firmware_version` | firmware version query |
| `update_firmware` | `update_firmware` | firmware flashing command |
| `lock_factory_settings` | `lock_factory_settings` | factory lock command |
| `unlock_factory_settings` | `unlock_factory_settings` | factory unlock command with signature |

## Stdout Through Workstation

`OCADevice` returns dictionaries or strings depending on the underlying OCA wrapper. [../adam_workstation.py](../adam_workstation.py) normalizes these into stdout for APx500:

- getters print a single value when possible;
- setters generally print `True`/`False` or a fallback result;
- firmware update, factory lock, and unlock print `successful` or `Error: ...`;
- discovery prints the discovered device name.

APx project files often store discovered product names in variables and reuse them as OCA targets in later steps.

## Factory Settings And EOL Flow

Sub-Pro EOL uses factory-settings commands to read/write serial numbers and MAC addresses. `eol_init_sub` combines several operations:

1. reject default serials when production units should be measured;
2. reject golden-sample serials when EOL units should be measured;
3. read firmware version;
4. flash firmware if needed;
5. verify firmware version;
6. run `init_sub` to set known default test configuration.

`provision_mac` then reads the current MAC, assigns a unique MAC if the device still has the default MAC, verifies it, or validates the existing assignment on retest.

## Service Logging

When an `OCADevice` has `workstation_id` and `service_host`, it can send task logs to the ADAM service through `WorkstationLogger`. This logging must not be confused with the stdout response consumed by APx500.

## Extension Checklist

When adding a new OCA operation:

1. Add a method to `OCADevice` using the appropriate OCA command path.
2. Add a parser command in [../cli/workstation_parser.py](../cli/workstation_parser.py).
3. Add a handler in [../adam_workstation.py](../adam_workstation.py).
4. Add it to `AdamWorkstation.command_map`.
5. Define and document the stdout contract before adding it to APx500.