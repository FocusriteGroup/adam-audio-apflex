# Audio Precision Production Tool Documentation

This documentation describes the Python backend tools, APx500 integration, desktop applications, and production databases in this repository.

## Design Philosophy

`adam_workstation.py` and the supporting modules are general-purpose backend components. They are built around APx500 workflows but are not limited to them. The same CLI commands can be called from other front-ends, custom GUIs, scripts, and operator tools. APx500 is the primary consumer today, but the design intentionally keeps the backend decoupled from any single front-end.

Because multiple kinds of callers are expected, the stdout-based communication model is deliberate: any process that can run a command and read its output can integrate with the workstation backend. This includes APx500 shell steps, batch scripts, custom GUI applications, and direct operator use.

The printed output is the API contract for external callers. Return values inside Python are implementation details unless the caller is another Python module.

## Documentation Map

| Document | Purpose |
|---|---|
| [System Architecture](architecture.md) | Repository structure, process boundaries, data flow, logging, and runtime dependencies. |
| [APx500 Integration](apx500-integration.md) | How APx project files call Python, how stdout is validated, and the important response contracts. |
| [Workstation CLI Reference](workstation-cli-reference.md) | Live command surface from `cli/workstation_parser.py` and `adam_workstation.py`. |
| [ADAM Service Protocol](service-protocol.md) | TCP command protocol, UDP discovery broadcast, and service-backed operations. |
| [CSV and Measurement Processing](csv-and-measurements.md) | AP CSV formats, smoothing, distortion splitting, reference filtering, L/R compensation, uploads. |
| [OCA Device Control](oca-device-control.md) | OCA wrapper responsibilities and supported device operations. |
| [Hardware Integration](hardware-integration.md) | SwitchBox, scanner, serial manager responsibilities, and production stdout behavior. |
| [Matching System](matching-system.md) | Matching app database, upload path, pairing algorithm, and system verification. |
| [Sub-Pro SN/FW Workstation](subpro-sn-fw-workstation.md) | Desktop workflow for firmware checks, serial-number programming, part capture, and history. |
| [Troubleshooting](troubleshooting.md) | Common production failures, stale APx project expectations, logs, and validation commands. |
| [MAC Provisioning Workflow](mac_provisioning_workflow.md) | First-test and retest MAC provisioning behavior. |
| [MAC Provisioning Code](mac_provisioning_code.md) | Code-level walkthrough of MAC provisioning. |
| [MAC Provisioning Database](mac_provisioning_database.md) | SQLite schema and backup behavior for MAC provisioning. |
| [MAC Provisioning Tests](mac_provisioning_tests.md) | Functional and stress test coverage. |
| [Filter Reference By Limits](filter_reference_by_limits.md) | Algorithm details for reference filtering. |
| [Matching App User Guide](../Matching_App/docs/H600_Matching_User_Guide.md) | Operator manual for the matching GUI. |
| [Sub-Pro SN/FW User Manual](../SubPro_SN_FW_Workstation/docs/user_manual.md) | Operator manual for the Sub-Pro provisioning GUI. |

## Main Executables

| File | Role |
|---|---|
| [../adam_workstation.py](../adam_workstation.py) | General-purpose production backend CLI. Called by APx500 shell steps, desktop GUIs, scripts, and operators directly. |
| [../cli/workstation_parser.py](../cli/workstation_parser.py) | Authoritative argparse command definitions. |
| [../adam_service.py](../adam_service.py) | Optional TCP service for helper functions, CSV operations, biquad calculation, and measurement support. |
| [../adam_connector.py](../adam_connector.py) | Service discovery and service start/check helper. |
| [../Matching_App/run.py](../Matching_App/run.py) | Matching GUI launcher. |
| [../SubPro_SN_FW_Workstation/run.py](../SubPro_SN_FW_Workstation/run.py) | Sub-Pro SN/FW workstation GUI launcher. |
| [../SubProMACAddresses/generate_mac_pool.py](../SubProMACAddresses/generate_mac_pool.py) | MAC pool setup utility. |

## Integration Rule

The backend is designed to be called from any front-end. When adding or changing a command:

1. Add the argparse command in [../cli/workstation_parser.py](../cli/workstation_parser.py).
2. Add the same command to `AdamWorkstation.command_map` in [../adam_workstation.py](../adam_workstation.py).
3. Make the handler print exactly one stable response. This is the contract for all callers, not just APx500.
4. Keep logging out of stdout. Workstation logs go to `logs/adam_audio/adam_workstation_log_YYYY-MM-DD.log`.
5. Update [APx500 Integration](apx500-integration.md) and [Workstation CLI Reference](workstation-cli-reference.md).

When the caller is APx500, it can store output in a project variable, ignore output, or compare output with an expected string. When the caller is a custom GUI, it reads the same stdout. The rule is the same regardless of front-end: one stable response per command, no diagnostic noise in stdout.