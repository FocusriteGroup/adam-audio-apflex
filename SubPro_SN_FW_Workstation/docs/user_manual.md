# User Manual – Sub-Pro SN/FW Workstation

## Introduction

The Sub-Pro SN/FW Workstation is a Windows desktop application used in production to:

- Write a unique serial number into each Sub-Pro unit (A8S or A10S) via a network connection.
- Verify and, if necessary, update the device firmware before writing the serial number.
- Record component serial numbers (DSP Board, UI Board, AMP+PSU, Amp Module, Woofer Driver) and link them to the finished unit in a local database.
- Export production records to CSV for reporting.

The application is launched from a terminal:

```powershell
cd "...\Audio-Precision\SubPro_SN_FW_Workstation"
python run.py
```

---

## First Launch – Setting a Password

On the very first launch the application has no password set. A setup screen is shown automatically.

**Steps:**

1. Enter a password (minimum 4 characters) in the **New password** field.
2. Repeat the same password in the **Confirm password** field.
3. Press **Set Password & Continue**.

The application stores a salted hash of the password. The plaintext is never saved. After setting the password, the main workflow screen opens and the setup screen is never shown again.

> **Screenshot placeholder**
> *(Insert first-run password setup screen screenshot here)*

---

## Screen Overview

The application has four screens reachable from the navigation bar at the top:

| Button | Screen | Password required |
|---|---|---|
| Home | Main workflow | No |
| History | Production history | No |
| Unlock | Unlock locked device | Yes |
| Settings | Application settings | Yes |

---

## Screen 1 – Main Workflow (Home)

This is the default screen. It guides the operator through the full provisioning process for one unit.

> **Screenshot placeholder**
> *(Insert main workflow screen screenshot here)*

### Layout

- **Left column:** Step indicator, instruction text, scan input field, status bar, result banner, action buttons.
- **Right panel:** Required Parts checklist showing all configured parts with their expected SN prefix.

### Step-by-Step Process

#### Step 1 – Press Start

Press the **Start** button. The Settings and Unlock navigation buttons are disabled for the duration of the session to prevent accidental configuration changes.

#### Step 2 – Scan Product Serial Number

The scan input field appears and receives keyboard focus automatically. Scan (or type) the 9-character serial number of the complete unit.

- **A8S units:** prefix `CI` (e.g. `CI6400001`)
- **A10S units:** prefix `CJ` (e.g. `CJ6500001`)

The application validates the full serial number format (prefix, year code, month code, 5-digit sequential number). If the format is invalid, an error is shown in the status bar and the field stays active for re-entry.

If the scanned SN matches a registered **Golden Sample**, the session ends immediately with a FAIL banner and the unit is not programmed.

#### Step 3 – Firmware Check and SN Write (automatic)

After a valid product SN is accepted the screen shows "Processing..." and the application performs the following steps automatically, without operator input:

1. **Read firmware version** from the device.
2. If the version does not match the configured target:
   - Flash the target firmware from the configured `.bin` file.
   - Verify the firmware version again after flashing.
3. **Write the product SN** to the device.
4. **Read back the SN** from the device and confirm it matches.

If any step fails, the session ends with a FAIL banner showing the specific error. Press **Restart** to start over.

#### Step 4 – Scan Component Parts

The parts checklist on the right becomes active. Scan each component barcode in **any order**. As each part is scanned:

- The row turns green and is marked with `*`.
- The status bar shows the part name and scanned SN.
- If a part SN was previously used on a different unit (re-assignment), this is noted in the status bar and recorded in the database.

Parts are identified by their SN prefix. If the wrong prefix is scanned (e.g. scanning an A10S Amp Module for an A8S unit), an error is shown and the part is not recorded.

Required parts are defined in Settings. All required parts must be scanned before the session can complete.

#### Step 5 – DONE

When all required parts are scanned the screen shows a green **PASS** banner with the firmware version and a confirmation message. The record is written to the database as `PASS`.

Press **Start Next Unit** to reset the screen and begin the next unit.

### Cancelling a Session

Press **Cancel** at any time during a session to abort. The unit record is written to the database as `FAIL`. The screen resets to idle.

---

## Screen 2 – Settings

Settings is password-protected. Entering the correct password opens the screen with three tabs.

> **Screenshot placeholder**
> *(Insert settings screen screenshot here)*

### Tab 1 – Device & Firmware

| Field | Description |
|---|---|
| Device Name | The mDNS hostname used for all device communication. Must match the device's network name (e.g. `SubPro`). |
| Golden Samples – A8S | List of A8S golden-sample serial numbers. Multiple entries supported. |
| Golden Samples – A10S | List of A10S golden-sample serial numbers. Multiple entries supported. |
| Target Version | The firmware version string that must be active before writing the SN (e.g. `1.0.0rc2`). Leave blank to skip the version check. |
| Firmware .bin path | Path to the firmware binary file used for flashing. Can be relative to the repository root or absolute. |

**Adding a golden sample:**

1. Type the full 9-character serial number in the SN field for the correct variant.
2. Optionally add a note (e.g. `Unit 1 - acoustic reference`).
3. Press **+ Add**.

The application validates the SN format and the prefix (CI for A8S, CJ for A10S). Entering an A10S prefix into the A8S section is rejected with an error message in the input field.

Press **Save** to persist all changes. The device name change takes effect immediately (no restart required).

### Tab 2 – Parts

Shows the configured list of component parts. Each row has:

- **Name** – human-readable part name
- **Prefix A8S** – expected SN prefix for A8S units
- **Prefix A10S** – expected SN prefix for A10S units
- **Req?** – checkbox; uncheck to make the part optional

**To add a new part:** Fill in Name, Prefix A8S, Prefix A10S, check Req? if required, then press **+ Add Part**.

**To remove a part:** Press **Remove** on the corresponding row. This does not delete historical scan records.

Press **Save All Changes** to persist edits to existing rows.

### Tab 3 – Change Password

| Field | Description |
|---|---|
| Current password | Must match the existing password |
| New password | Minimum 4 characters |
| Confirm new password | Must match the new password |

Press **Update Password** to apply. The change takes effect immediately.

---

## Screen 3 – Unlock Device

> **Screenshot placeholder**
> *(Insert unlock screen screenshot here)*

This screen is a placeholder for a future firmware feature that will allow locked units to be unlocked for re-provisioning or rework. The **Unlock Device** button is visible but disabled.

This screen is password-protected. It is intended for service use only.

---

## Screen 4 – History

Shows a searchable, filterable list of all provisioning sessions stored in the database.

> **Screenshot placeholder**
> *(Insert history screen screenshot here)*

### Filters

| Filter | Description |
|---|---|
| From / To | ISO date range filter (format: `YYYY-MM-DD`) |
| SN | Partial product SN filter (case-insensitive) |

Press **Apply** to reload the table with the active filters.

### Table Columns

| Column | Description |
|---|---|
| Timestamp | Date and time the session was created |
| Product SN | Scanned product serial number |
| Variant | A8S or A10S |
| FW Found | Firmware version read from device at session start |
| Flashed | Whether firmware was flashed during this session |
| FW Final | Firmware version active at session end |
| Parts | Parts scanned / required parts count |
| Result | PASS, FAIL, or INCOMPLETE |

### Expanding a Row

Press **>** on any row to open a detail popup showing:

- Full session metadata
- Each component SN scanned, including any re-assignment notes

### Exporting to CSV

Press **Export CSV** to open a folder picker. Choose the destination folder. A timestamped file (`subpro_export_YYYYMMDD_HHMMSS.csv`) is created in the selected folder. The export respects the currently active filters.

CSV columns: `timestamp`, `product_sn`, `variant`, `fw_version_found`, `fw_flashed`, `fw_version_final`, `result`, `parts`.

---

## Serial Number Format

All serial numbers follow the ADAM Audio format:

```
Position  0-1   Part prefix         (two letters, A-Z)
Position  2     Year code           (0 = 2020, 1 = 2021, ... 9 = 2029, A = 2030, ...)
Position  3     Month code          (1-9 = Jan-Sep, A = Oct, B = Nov, C = Dec)
Position  4-8   Sequential number   (5 decimal digits, starts at 00001 each month)
```

**Golden sample encoding:** Year code `G` + month code `S` (e.g. `CIGS00001`).

### Known Prefixes

| Prefix | Part | Variant |
|---|---|---|
| CI | Complete product | A8S |
| CJ | Complete product | A10S |
| ED | DSP Board | A8S & A10S |
| DB | UI Board | A8S & A10S |
| FD | AMP+PSU Board | A8S & A10S |
| AF | Amp Module | A8S |
| AG | Amp Module | A10S |
| BH | Woofer Driver | A8S |
| BI | Woofer Driver | A10S |

---

## Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| "Could not read firmware version" | Device not reachable on network | Check Ethernet connection and device power; verify device name in Settings |
| "Firmware file not found" | `fw_bin_path` in Settings is wrong or file is missing | Update the path in Settings → Device & Firmware |
| "FW version mismatch after flash" | Flash did not complete correctly | Retry; check firmware file integrity |
| "SN readback mismatch" | Device firmware does not yet support SN readback | Confirm firmware version; check with firmware team |
| "Golden Sample detected" | The scanned SN is registered as a golden sample | Use the correct production unit, not the golden sample |
| Export CSV fails | Destination folder does not exist or no write permission | Choose a different folder in the export dialog |
| Password prompt rejects correct password | Database file corrupted or moved | Contact administrator to reset the database |
