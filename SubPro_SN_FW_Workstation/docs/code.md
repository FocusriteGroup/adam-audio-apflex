# Code & Implementation – Sub-Pro SN/FW Workstation

## Overview

The application is split into clearly-separated layers:

| File / Module | Responsibility |
|---|---|
| `run.py` | Entry point – adds the parent repo to `sys.path`, launches the Kivy app |
| `app/main.py` | `SubProApp` – creates the database, device service, and all screens; owns `navigate_to()` |
| `app/db/database.py` | `Database` – SQLite CRUD layer, password hashing, CSV export |
| `app/services/sn_validator.py` | Pure-function SN validation and decoding |
| `app/services/device_service.py` | `DeviceService` – thin wrapper around `OCADevice` |
| `app/screens/workflow_screen.py` | Main scan workflow (state machine) |
| `app/screens/settings_screen.py` | Settings UI (device, golden samples, parts, password) |
| `app/screens/history_screen.py` | History table, detail popup, CSV export |
| `app/screens/unlock_screen.py` | Unlock placeholder |
| `app/screens/first_run_screen.py` | First-launch password setup |
| `app/components/ui_components.py` | Shared color palette, widget helpers, `NavBar` |
| `app/components/password_popup.py` | Modal password prompt |

---

## `app/db/database.py` — `Database`

The database class is instantiated once in `SubProApp.build()` and passed to every screen that needs it.

### Construction

```python
db = Database(path: Path)
```

Opens (or creates) the SQLite file at `path`. Runs the full schema migration and seeds default config and parts rows.

### Config

```python
db.get_config(key: str, default: str = '') -> str
db.set_config(key: str, value: str)
```

Read/write a key in the `config` table. `set_config` uses `INSERT … ON CONFLICT DO UPDATE` (upsert).

### Password

```python
db.has_password() -> bool
db.set_password(plaintext: str)
db.check_password(plaintext: str) -> bool
```

`set_password` generates a fresh 32-byte random salt, hashes `salt + plaintext` with SHA-256, and upserts the single-row `password` table. `check_password` re-derives the hash from the stored salt and compares.

### Golden Samples

```python
db.get_golden_samples(variant: str | None = None) -> list[dict]
db.add_golden_sample(variant: str, serial_number: str, note: str = '') -> int
db.remove_golden_sample(gs_id: int)
db.is_golden_sample(serial_number: str) -> bool
```

`variant` must be `'A8S'` or `'A10S'` (enforced by a `CHECK` constraint). `serial_number` is stored upper-cased. `is_golden_sample` is called on every product SN scan – it is the golden-sample gate.

### Parts Configuration

```python
db.get_parts_config() -> list[dict]
db.add_part_config(name, prefix_a8s, prefix_a10s, required) -> int
db.update_part_config(part_id, name, prefix_a8s, prefix_a10s, required)
db.remove_part_config(part_id)
```

The parts list drives both the scanning checklist on the workflow screen and the prefix validation logic. Changes take effect immediately – no restart required.

### Unit Lifecycle

```python
db.create_unit(product_sn: str, variant: str) -> int           # returns unit_id
db.update_unit_fw(unit_id, fw_found, fw_flashed, fw_final)
db.complete_unit(unit_id, result: str)                          # 'PASS' or 'FAIL'
```

A unit row is created as soon as a valid, non-golden product SN is scanned. This means interrupted sessions are preserved as `INCOMPLETE` records in the audit log.

### Parts Scanning

```python
db.add_part_scan(unit_id, part_name, part_sn, previous_unit_id=None)
db.get_latest_unit_for_part_sn(part_sn: str) -> int | None
db.get_product_sn_for_unit(unit_id: int) -> str | None
```

`get_latest_unit_for_part_sn` is called before every part is recorded. If it returns a `unit_id` different from the current session's `unit_id`, the part is flagged as a re-assignment and `previous_unit_id` is set. `get_product_sn_for_unit` resolves the human-readable product SN for display in the workflow status bar and CSV export.

### Query and Export

```python
db.get_units(product_sn_filter='', date_from='', date_to='') -> list[dict]
db.get_parts_for_unit(unit_id: int) -> list[dict]
db.export_csv(path: Path, product_sn_filter='', date_from='', date_to='')
```

`get_units` applies optional filters and orders results by `timestamp DESC, id DESC` (newest first; `id` breaks ties within the same second). `export_csv` writes a CSV with one row per unit; the `parts` column contains a semicolon-separated list of `name=SN` pairs, with `[reassigned from <product_sn>]` appended for re-assigned parts.

---

## `app/services/sn_validator.py` — SN Validation

All validation is pure-functional (no side effects, no DB access).

### SN Format

```
Position  0-1   Part ID prefix      (two uppercase letters, A-Z)
Position  2     Year code           (0-9 = 2020-2029, A-Z = 2030-2055; G is reserved for golden-sample encoding)
Position  3     Month hex           (1-9 = Jan-Sep, A = Oct, B = Nov, C = Dec; S is reserved for golden-sample encoding)
Position  4-8   Sequential number   (5 decimal digits, 00001 onwards)
```

Golden-sample encoding: positions 2-3 must both be `GS`. `G` in position 2 paired with any character other than `S` in position 3 is rejected. The sequential number is unrestricted for golden samples.

### Key functions

```python
validate_sn(sn: str) -> (ok: bool, error: str)
```
Full validation: length (9), alpha prefix, valid year code, valid month code, 5-digit number. Returns `(True, '')` on success, `(False, human-readable message)` on failure.

```python
get_product_variant(sn: str) -> str | None
```
Maps `CI` → `'A8S'`, `CJ` → `'A10S'`, anything else → `None`.

```python
is_golden_sample_format(sn: str) -> bool
```
Returns `True` if positions 2-3 are `GS`. Note: the DB is the authoritative golden-sample registry — format alone is not enough.

```python
validate_part_sn(sn, part_name, expected_prefix) -> (ok: bool, error: str)
```
Runs `validate_sn` then checks the two-character prefix against `expected_prefix`.

```python
decode_sn(sn: str) -> dict
```
Returns `{'prefix', 'year', 'month', 'number', 'is_golden_sample'}`. Assumes the SN has already been validated.

---

## `app/services/device_service.py` — `DeviceService`

Wraps `OCADevice` from `oca/oca_device.py` (parent repo). The device name is the discovered mDNS hostname cached for later CLI calls.

```python
DeviceService(device_name: str, port: int = 50001, timeout: int = 10)
```

`OCADevice` is lazily imported on first use so the workstation can start without a device connected.

### Methods

All methods return `(success: bool, value: str | None, error: str | None)`.

```python
device_service.update_device_name(name: str)          # hot-reload without restart
device_service.discover(timeout=2)                    # mDNS discovery; updates cached hostname
device_service.get_firmware_version()                 # reads via model-description get
device_service.flash_firmware(fw_path: Path)          # firmware update (up to 120 s)
device_service.get_serial_number()                    # factory-settings get-serial-number
device_service.set_serial_number(sn: str)             # factory-settings set-serial-number
```

### Error handling

On any exception from `OCADevice`, the method logs the error and returns `(False, None, error_string)`. The workflow screen translates this into a `FAIL` state with the error string displayed.

---

## `app/screens/workflow_screen.py` — State Machine

The main screen runs a six-state finite state machine:

```
IDLE  →  SCAN_PRODUCT  →  PROCESSING  →  SCAN_PARTS  →  DONE
                ↓               ↓
              FAIL            FAIL
```

| State | Trigger to advance | Trigger to fail |
|---|---|---|
| `IDLE` | Start button | — |
| `SCAN_PRODUCT` | Valid, non-GS product SN scanned | Invalid SN, GS detected |
| `PROCESSING` | All backend steps succeed | FW read/flash error, SN write/readback error |
| `SCAN_PARTS` | All required parts scanned | — (invalid scans show error, stay in state) |
| `DONE` | — (terminal) | — |
| `FAIL` | — (terminal; Restart resets to IDLE) | — |

### Backend steps (`_run_backend`)

Executed automatically after `SCAN_PRODUCT` succeeds:

1. `device_service.get_firmware_version()` — if this fails → FAIL
2. If `fw_found != target_fw`: FAIL and remove the unit from the production flow; firmware must be flashed separately.
3. `device_service.set_serial_number(product_sn)` — if this fails → FAIL
4. `device_service.get_serial_number()` — readback verification — if mismatch → FAIL
5. Update DB (`update_unit_fw`) → advance to `SCAN_PARTS`

### Part scanning (`_handle_part_scan`)

- Full `validate_sn()` check on every barcode.
- Prefix matched against the variant-correct prefix from `parts_config`.
- Re-assignment detection via `get_latest_unit_for_part_sn()`. If re-assigned, `get_product_sn_for_unit()` resolves the prior unit's product SN for display.
- Status bar shows `[re-assigned from <product_sn>]` (e.g. `[re-assigned from CI9485949]`).
- Checklist refreshed after every successful scan.
- When all required parts are scanned: `complete_unit('PASS')` → `DONE`.

### Focus management

The scan input field keeps keyboard focus whenever it is visible. A `focus` binding re-grabs focus if the operator accidentally clicks elsewhere. `on_enter` also restores focus when returning from another screen.

---

## `app/components/ui_components.py` — Shared Widgets

### Color palette `C`

All colors are defined once in the `C` dict:

| Key | Usage |
|---|---|
| `bg` | Main background |
| `nav` | NavBar background |
| `panel` / `panel2` | Card and row backgrounds |
| `input` | TextInput background |
| `accent` | Buttons, active tab, NavBar highlight |
| `green` | PASS, scanned parts, success messages |
| `red` | FAIL, error messages, Remove buttons |
| `text` | Primary text |
| `dim` | Secondary/hint text |
| `disabled` | Disabled buttons |

### Helper factories

```python
lbl(text, size, color, bold, halign, valign, **kw) -> Label
btn(text, on_press, bg, disabled, **kw) -> Button
inp(hint, password, on_submit, **kw) -> TextInput
section_hdr(text) -> BgBox            # darker header bar
spacer(h=12) -> Widget                # vertical gap
```

### `NavBar`

Rendered at the top of every screen. Constructor parameters:

```python
NavBar(current='workflow', session_active=False)
```

- `current` highlights and disables the button for the active screen.
- `session_active=True` greys out Settings and Unlock to prevent mid-scan navigation.
- Each enabled button calls `App.get_running_app().navigate_to(screen_name, require_password)`.

---

## `app/main.py` — `SubProApp`

```python
SubProApp().run()
```

### `build()`

1. Opens `Database` at `Data/subpro_workstation.db`.
2. Creates `DeviceService` using `config['device_name']`.
3. Builds the `ScreenManager` with all five screens.
4. Routes to `'first_run'` (if no password is set) or `'workflow'`.

### `navigate_to(screen_name, require_password=False)`

The central navigation method called by `NavBar` and screens. If `require_password=True`, opens a `PasswordPopup` first; the transition only happens on correct password entry.
