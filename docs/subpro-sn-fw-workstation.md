# Sub-Pro SN/FW Workstation

The Sub-Pro SN/FW Workstation is a Tkinter desktop application in [../SubPro_SN_FW_Workstation](../SubPro_SN_FW_Workstation). It guides production operators through firmware verification, serial-number programming, component part scanning, history capture, and CSV export.

Operator usage is documented in [../SubPro_SN_FW_Workstation/docs/user_manual.md](../SubPro_SN_FW_Workstation/docs/user_manual.md). Additional code/database/test notes are in that folder's `docs` directory.

## Starting The App

```powershell
cd SubPro_SN_FW_Workstation
python run.py
```

## Main Responsibilities

| Area | Files | Responsibility |
|---|---|---|
| App entry | [../SubPro_SN_FW_Workstation/run.py](../SubPro_SN_FW_Workstation/run.py), [../SubPro_SN_FW_Workstation/app/main.py](../SubPro_SN_FW_Workstation/app/main.py) | Launch and screen navigation. |
| Workflow screens | [../SubPro_SN_FW_Workstation/app/screens](../SubPro_SN_FW_Workstation/app/screens) | First-run password, main workflow, settings, history, unlock placeholder. |
| Device service | [../SubPro_SN_FW_Workstation/app/services/device_service.py](../SubPro_SN_FW_Workstation/app/services/device_service.py) | OCA device discovery, firmware read/flash, serial read/write, unlock. |
| Serial validation | [../SubPro_SN_FW_Workstation/app/services/sn_validator.py](../SubPro_SN_FW_Workstation/app/services/sn_validator.py) | Product and part serial-number format validation. |
| Database | [../SubPro_SN_FW_Workstation/app/db/database.py](../SubPro_SN_FW_Workstation/app/db/database.py) | Settings, sessions, parts, golden samples, password hash, export. |
| UI components | [../SubPro_SN_FW_Workstation/app/components](../SubPro_SN_FW_Workstation/app/components) | Reusable Tkinter widgets and password popup. |

## Device Communication

`DeviceService` wraps the repository-level `OCADevice`. Its public methods return tuples:

```python
(success: bool, value: str | None, error: str | None)
```

Important operations:

| Method | Purpose |
|---|---|
| `discover` / `discover_with_retries` | Find the Sub-Pro device and update the active mDNS target. |
| `get_firmware_version` | Read current firmware version. |
| `flash_firmware` | Flash configured firmware binary. |
| `get_serial_number` | Read factory serial number. |
| `set_serial_number` | Write product serial number. |
| `unlock_factory_settings` | Unlock factory settings with signature. |

Discovery first tries the repository CLI command `adam_workstation.py discover --timeout ...` and falls back to direct `OCADevice.discover`.

## Production Workflow

1. Operator presses Start.
2. Operator scans product serial number.
3. App validates serial format and golden-sample restrictions.
4. App discovers/connects to device.
5. App reads firmware version.
6. If configured target firmware differs, app flashes firmware and verifies version again.
7. App writes product serial number and reads it back.
8. Operator scans required component parts in any order.
9. App writes PASS/FAIL/INCOMPLETE session record.
10. History screen can filter and export records.

Supported product prefixes in the manual:

| Variant | Prefix |
|---|---|
| A8S | `CI` |
| A10S | `CJ` |

## Security Model

The first run forces password setup. The plaintext password is not stored; the app stores a salted hash. Settings and Unlock screens require the password. The Unlock screen is currently a placeholder for future rework/service functionality.

## Relationship To APx Workstation Commands

This desktop app is separate from APx shell-step workflows, but it reuses the same OCA layer as [../adam_workstation.py](../adam_workstation.py). The APx-side Sub-Pro EOL flow uses commands such as `eol_init_sub`, `init_sub`, `get_serial_number`, and `provision_mac`; the desktop app provides a guided GUI for the serial/firmware workstation use case.