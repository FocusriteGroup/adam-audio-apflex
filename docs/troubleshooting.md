# Troubleshooting

This page focuses on failures seen at the APx500/Python boundary, service boundary, hardware layer, and production databases.

## First Rule: Check Stdout Separately From Logs

APx500 usually sees only stdout. The workstation log may contain detailed errors, but APx validates or stores the printed text.

Run the exact command from PowerShell in the repository root:

```powershell
python adam_workstation.py <command> <args...>
```

Then compare stdout with the APx `ExpectedResponse` or `ProgramOutputVariable` usage.

Logs are under:

```text
logs/adam_audio/
```

## APx Step Fails Even Though Python Works

Likely causes:

| Symptom | Cause | Fix |
|---|---|---|
| APx expects `True`, command prints a number | Stale `ExpectedResponse`, common with `calibrate_gain`. | Store output in variable or update expected behavior. |
| APx expects `Channel set to 1`, command stores serial | Stale `ExpectedResponse` on `scan_serial`. | Use output-variable mode and validate serial separately. |
| APx expects `Channel set to 2`, command runs `open_box` | Stale copied expected response. | Ignore output or expect `Box status: ...`. |
| Command parses in `--help` but exits unknown | Parser command missing from `AdamWorkstation.command_map`. | Add dispatcher mapping and handler. Current examples: `get_device_biquad`, `set_device_biquad`. |
| APx command references `init_asub` | Legacy command name. | Use `init_sub`. |

## Service Not Found

Checks:

```powershell
python adam_service.py
python adam_connector.py --find --service-name ADAMService
```

If discovery fails:

- confirm the service host firewall allows UDP `65433` and TCP `65432`;
- confirm the workstation and service are on the same network segment for broadcast discovery;
- pass `--host <ip>` explicitly;
- check `logs/adam_audio/adam_service_log_YYYY-MM-DD.log`.

## OCA Device Not Found

Checks:

```powershell
python adam_workstation.py discover --timeout 3
python adam_workstation.py get_firmware_version <ProductNameOrIP>
```

If discovery works but a later command fails:

- confirm the APx variable contains the discovered product name without extra text;
- confirm factory settings are unlocked before writing serial/MAC fields;
- verify firmware supports the requested OCA command;
- after MAC provisioning, allow rediscovery because the mDNS name may change with the MAC suffix.

## Hardware Commands Fail

For SwitchBox:

```powershell
python adam_workstation.py set_channel 1
python adam_workstation.py set_channel 2
python adam_workstation.py open_box
```

For scanner:

```powershell
python adam_workstation.py scan_serial
```

If `scan_serial` prints `NaN`, inspect scanner connection, trigger behavior, barcode contents, and whether another program has the serial port open.

## MAC Provisioning Fails

`provision_mac` prints `successful` or `Error: ...` for APx. Important error reasons from [../SubProMACAddresses/mac_provisioner.py](../SubProMACAddresses/mac_provisioner.py):

| Reason | Meaning |
|---|---|
| `duplicate_sn` | Serial number already has an assignment while device still has default MAC. |
| `pool_exhausted` | No MAC addresses left in the configured pool. |
| `verify_failed` | Written MAC could not be read back correctly. |
| `unknown_device` | Device has a unique MAC but serial number is not in the DB. |
| `mac_mismatch` | Retest device MAC differs from the DB assignment. |
| `oca_error` | OCA communication failed. |

Useful commands:

```powershell
python adam_workstation.py get_mac_pool_status
python adam_workstation.py export_mac_log logs\mac_log.csv
```

See [mac_provisioning_workflow.md](mac_provisioning_workflow.md) for detailed recovery paths.

## Matching Upload Fails

`upload_measurement` prints `True` or `False`. Common causes:

- serial number does not start with `IA` or `IB`;
- AP CSV does not contain usable `Ch1` levels;
- database path is wrong relative to APx `WorkingDirectory`;
- row is already `paired` and must be unpaired before remeasurement;
- SQLite DB is locked by another process.

Run manually with an explicit DB path:

```powershell
python adam_workstation.py upload_measurement "C:\path\measurement.csv" -s IA6400001 --write-db --db-path Matching_App\Data\db\matcher.db
```

## CSV Output Missing Or Unexpected

CSV utilities may write a fallback filename when the requested output file is locked. Check stdout for the actual output path, and check the output directory for files ending in `_1.csv`, `_2.csv`, etc.

For APx steps that ignore output, a fallback filename can be easy to miss. Prefer storing the output path when a downstream step needs the generated file.

## Documentation/Code Drift Checks

Run this when updating command docs:

```powershell
python adam_workstation.py --help
```

Also compare:

- parser commands in [../cli/workstation_parser.py](../cli/workstation_parser.py);
- dispatch mappings in `AdamWorkstation.command_map` in [../adam_workstation.py](../adam_workstation.py);
- APx `ShellStep` `ExpectedResponse` strings inside `*.approjx` `project.xml`.

The safest rule: a command is production-callable only when it exists in both the parser and `command_map`, and its handler prints the documented stdout response.