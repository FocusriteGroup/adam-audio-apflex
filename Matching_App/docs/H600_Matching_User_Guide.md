# H600 Driver Matching App – User Guide

---

## Table of Contents

1. [Overview](#1-overview)
2. [Starting the Application](#2-starting-the-application)
3. [Main Screen](#3-main-screen)
   - 3.1 [Status Bar (Top)](#31-status-bar-top)
   - 3.2 [Frequency Response Chart (Center)](#32-frequency-response-chart-center)
   - 3.3 [Scan Area (Bottom)](#33-scan-area-bottom)
4. [Driver Status Model](#4-driver-status-model)
5. [Loading Measurement Data](#5-loading-measurement-data)
6. [Pairing Drivers – Step by Step](#6-pairing-drivers--step-by-step)
   - 6.1 [Scan the First Driver](#61-scan-the-first-driver)
   - 6.2 [Scan the Partner Driver](#62-scan-the-partner-driver)
   - 6.3 [Pairing Confirmed](#63-pairing-confirmed)
7. [Understanding Status Messages](#7-understanding-status-messages)
8. [Operation Windows (PIN-Protected)](#8-operation-windows-pin-protected)
   - 8.1 [PIN Entry](#81-pin-entry)
   - 8.2 [Paired Window](#82-paired-window)
   - 8.3 [Pool Window](#83-pool-window)
   - 8.4 [Quarantine Window](#84-quarantine-window)
   - 8.5 [Settings Window](#85-settings-window)
9. [Data Export](#9-data-export)
10. [System Build Verification (Workstation CLI)](#10-system-build-verification-workstation-cli)
11. [Files and Directories](#11-files-and-directories)
12. [Troubleshooting](#12-troubleshooting)
13. [Database Synchronisation and Integrity](#13-database-synchronisation-and-integrity)
    - 13.1 [How the Database is Shared Between Stations](#131-how-the-database-is-shared-between-stations)
    - 13.2 [Out-of-Sync Scenarios and Mitigation](#132-out-of-sync-scenarios-and-mitigation)
    - 13.3 [USB Transfer Workflow](#133-usb-transfer-workflow)
    - 13.4 [Database Corruption: Causes and Prevention](#134-database-corruption-causes-and-prevention)
    - 13.5 [Rules Summary](#135-rules-summary)

---

## 1. Overview

The **H600 Matching** application is used for optimal pairing of speaker drivers during production. Measured drivers (Left = IA, Right = IB) are automatically matched into pairs based on their frequency responses. The goal is to find a left and right driver whose frequency responses are as similar as possible.

**Workflow Overview:**

1. Drivers are measured at the measurement station → measurement data is written directly into the database
2. The app detects new data automatically within 1 second
3. The app computes optimal pairs (Hungarian algorithm)
4. The operator scans the assigned drivers via QR code → the pair is confirmed
5. (Optional) At the EOL test station, the system serial number and the two installed driver serials are verified against the database

> `[Screenshot: Full application overview with loaded data]`

---

## 2. Starting the Application

The application is started via the file `run.py` inside the `Matching_App/` folder:

```
python run.py
```

After startup, the main window opens. The app immediately reads the database and begins polling for new measurement data every second.

> `[Screenshot: Application immediately after startup, empty state]`

---

## 3. Main Screen

The main screen is divided into three areas:

> `[Screenshot: Main screen with annotations for the three areas]`

### 3.1 Status Bar (Top)

The top bar shows the current pool status:

| Display | Meaning |
|---------|---------|
| **In pool: X** | Number of drivers that do not yet have a pair (unmatched) |
| **Matched: X** | Number of drivers that have been assigned a partner but not yet physically confirmed |
| **Paired: X** | Number of drivers that have been successfully scanned and confirmed as a physical pair |

On the right side are the operation buttons — all PIN-protected:

| Button | Opens |
|--------|-------|
| **Paired** | List of all confirmed pairs — unpair individually or by serial scan |
| **Pool** | Unmatched and matched drivers — remove individual drivers |
| **Quarantine** | Quarantined drivers — restore to pool or permanently delete |
| **Settings** | Matching algorithm parameters and module age threshold |
| **Export** | Export driver data as CSV and JSON with time-window filter |

> `[Screenshot: Status bar with example values and all five operation buttons visible]`

### 3.2 Frequency Response Chart (Center)

The chart displays the frequency response of scanned drivers:

- **Blue curve** = Left driver (IA)
- **Orange curve** = Right driver (IB)
- **X-axis**: Frequency in Hz (logarithmic)
- **Y-axis**: Level in dB SPL

After scanning a driver, its frequency response is displayed. After scanning the partner, both curves are overlaid so the match quality can be visually verified.

> `[Screenshot: Chart with two overlaid frequency responses (blue + orange)]`

### 3.3 Scan Area (Bottom)

At the bottom of the screen:

- **Scan input field**: The QR code of a driver is automatically read here. The cursor is permanently in this field — no clicking required.
- **Status line**: Shows instructions and feedback in color:
  - **Gray** = Ready / neutral message
  - **Red** = Error
  - **Green** = Success

> `[Screenshot: Scan area with gray status message "Scan first driver..."]`

---

## 4. Driver Status Model

Every driver in the database has one of four statuses:

| Status | Meaning |
|--------|---------|
| **unmatched** | In pool, no partner assigned yet |
| **matched** | Partner assigned by algorithm, not yet physically confirmed |
| **paired** | Both drivers physically scanned and confirmed — locked |
| **quarantined** | Removed from active pool due to age or manual action |

**Status transitions:**

- `unmatched` → `matched`: Automatic when the algorithm finds a valid pair
- `matched` → `paired`: Operator scans both drivers (physical confirmation)
- `matched` → `unmatched`: Automatic when the driver is remeasured
- `paired` → `unmatched`: Manual unpair action in the Paired window
- `unmatched` / `matched` → `quarantined`: Manual or automatic age-based quarantine
- `quarantined` → `unmatched`: Manual restore in the Quarantine window

**Remeasure rules:**
- A driver with status `unmatched` or `matched` can be remeasured — the new measurement overwrites the old one and triggers a rematch
- A driver with status `paired` **cannot** be remeasured — it must be unpaired first
- When a `matched` driver is remeasured, its former match partner is automatically reset to `unmatched`

---

## 5. Loading Measurement Data

Measurement data is written directly into the database by the workstation measurement script (`adam_workstation.py upload_measurement`). No manual file copying is needed.

The app polls the database every second. When new data is detected (new rows or updated timestamps), it automatically:

1. Imports all new drivers
2. Re-evaluates all current matching assignments (unmatched and matched drivers)
3. Finds the globally optimal pairs using the Hungarian algorithm
4. Updates the status bar

**Important:**
- Only drivers with serial numbers starting with **IA** (left) or **IB** (right) are accepted
- Already imported drivers are updated only if their current status allows it (not `paired`)
- Already physically confirmed pairs (status `paired`) are never affected

> `[Screenshot: Status bar updating after new measurement data arrives]`

---

## 6. Pairing Drivers – Step by Step

### 6.1 Scan the First Driver

1. Pick a driver from the shelf
2. Scan the QR code with the handheld scanner
3. The system looks up the driver and displays its frequency response

**Possible messages:**

| Message | Meaning |
|---------|---------|
| `IA6300005 scanned — now scan partner: IB6300012` | Success — now scan the indicated partner |
| `IA6300005 has no match yet — still in pool` | This driver has no partner assigned yet |
| `IA6300005 already paired with IB6300012` | This pair has already been physically confirmed |
| `Unknown driver: XY123` | Serial number not found in the database |

> `[Screenshot: After first scan — gray/green status line shows partner instruction, chart shows one curve]`

### 6.2 Scan the Partner Driver

1. Pick the displayed partner driver from the shelf
2. Scan its QR code
3. The system verifies it is the correct partner

**If the wrong driver is scanned:**
- Error message: `Expected IB6300012, got IB6300099 — try again`
- The process resets — start again from step 6.1

> `[Screenshot: Red error message after incorrect second scan]`

### 6.3 Pairing Confirmed

After successfully scanning both drivers:

- Green success message: `Paired: IA6300005 + IB6300012`
- The chart shows both frequency responses overlaid
- The status bar updates (Matched count decreases, Paired count increases)
- After 3 seconds the system is ready for the next pair

> `[Screenshot: Successful pairing — green status line, both frequency response curves in chart]`

---

## 7. Understanding Status Messages

| Color | Meaning | Examples |
|-------|---------|----------|
| 🔴 **Red** | Error — action not possible | Wrong partner, unknown driver, already paired |
| 🟢 **Green** | Success — pairing confirmed | `Paired: IA6300005 + IB6300012` |
| ⚪ **Gray** | Neutral — ready for input or informational | `Scan first driver...`, `IA6300005 scanned — now scan partner: IB6300012` |

The status message resets automatically to "Scan first driver..." after 3 seconds.

---

## 8. Operation Windows (PIN-Protected)

All operation windows require PIN entry before opening. The default PIN is **1234**.

### 8.1 PIN Entry

1. Click any operation button (Paired, Pool, Quarantine, Settings)
2. The PIN dialog opens — type the PIN
3. Confirm with **Enter** or the **OK** button

If the wrong PIN is entered, "Wrong PIN" is displayed and the field is cleared.

> `[Screenshot: PIN entry dialog]`

### 8.2 Paired Window

Shows all physically confirmed driver pairs.

> `[Screenshot: Paired window — side-by-side pair rows with X buttons]`

**Layout:**
- Each row shows a pair side by side: `IA number [X]   IB number [X]`
- The **X** button on either driver opens a confirmation dialog before unpairing
- At the bottom: a scan/type field to unpair by serial number directly

**Unpair by button:**
1. Click the **X** next to any driver in a pair
2. Confirm the dialog
3. Both drivers return to the pool as `unmatched` — the algorithm re-evaluates

**Unpair by serial scan:**
1. Scan or type a serial number into the bottom field
2. Press **Enter** or click **Unpair Serial**
3. A confirmation dialog is shown before the unpair is executed

**Use case:** When a pair was confirmed by mistake, or a driver needs to be remeasured.

### 8.3 Pool Window

Shows all drivers currently in the active pool — both unmatched (no partner yet) and matched (partner assigned, not yet confirmed).

> `[Screenshot: Pool window — two columns with divider, unmatched left, matched pairs right]`

**Layout:**
- **Left column**: Unmatched drivers — one row per driver with **X** button
- **Blue vertical divider**: Visual separator
- **Right column**: Matched drivers — shown as side-by-side pairs, each driver has its own **X** button
- At the bottom: a scan/type field to remove a driver directly by serial

**Remove a driver:**
1. Click **X** next to the driver, or scan/type its serial in the bottom field
2. The driver is permanently deleted from the database
3. If the driver was matched, its former partner is reset to `unmatched`
4. The algorithm re-evaluates automatically

**Use case:** Removing a defective driver that was imported by mistake or is no longer usable.

### 8.4 Quarantine Window

Shows all quarantined drivers and allows manual or automatic quarantine management.

> `[Screenshot: Quarantine window — list of quarantined serials with ↑ and X buttons]`

**Layout:**
- Header: count of quarantined drivers and the current age threshold
- **"Quarantine Old Modules Now"** button: immediately moves all pool drivers older than the age threshold to quarantine
- Scrollable list of quarantined serials — each row has:
  - **↑ (green)**: Restore the driver back to pool (status → `unmatched`)
  - **X**: Permanently delete the driver from the database
- At the bottom: a scan/type field to restore or delete by serial

**Quarantine old modules:**
1. Click **"Quarantine Old Modules Now"**
2. All drivers in `unmatched` or `matched` status that are older than the configured age threshold are moved to `quarantined`
3. If a matched driver is quarantined, its partner is reset to `unmatched`
4. The algorithm re-evaluates automatically

**Restore a driver:**
1. Click **↑** next to the driver, or scan/type the serial and click **Restore**
2. The driver moves back to `unmatched` status and re-enters the pool
3. The algorithm re-evaluates automatically

**Use case:** Drivers that have been in the pool for too long without being paired are quarantined to keep the pool clean. They can be restored later if still needed.

### 8.5 Settings Window

Configures the matching algorithm parameters and the module age threshold.

> `[Screenshot: Settings window with all three sliders]`

**RMSE Threshold**

Determines how similar two drivers must be to be considered a valid pair.

- **Unit**: dB
- **Range**: 0.10 dB – 2.00 dB
- **Default**: 1.00 dB

Lower value → stricter matching, fewer pairs, higher consistency.
Higher value → more tolerant matching, more pairs, larger allowed deviation.

**Frequency Range**

Defines which frequency range is used for the RMSE calculation:

- **Freq Min**: 20 Hz – 2,000 Hz (default: 200 Hz)
- **Freq Max**: 2,000 Hz – 20,000 Hz (default: 8,000 Hz)

The mid-range (200–8,000 Hz) is most relevant for perceived matching quality. Very low and very high frequencies are often influenced by room conditions and microphone positioning.

**Max Module Age**

Sets the age threshold for the "Quarantine Old Modules" function:

- **Unit**: days
- **Range**: 1 – 120 days
- **Default**: 14 days

Drivers loaded more than this many days ago are eligible for quarantine when the button in the Quarantine window is pressed.

**Apply & Rematch**

1. Adjust sliders to desired values
2. Click the green **"Apply & Rematch"** button
3. All current matching assignments (not confirmed pairs) are dissolved
4. The algorithm runs again with the new settings
5. Result message shows: `Reset X drivers, formed Y new pairs`
6. Settings are saved permanently to `Data/db/settings.json`

> `[Screenshot: Settings window after rematch — green result message]`

---

## 9. Data Export

The **Export** button (no PIN required) opens the export options window.

> `[Screenshot: Export options popup with time window controls]`

**Export options:**

| Option | Values |
|--------|--------|
| **Window Type** | Matching time / Load time |
| **Time Range** | Full snapshot, Last 24h, Last 3d, Last 7d, Last 14d, Last 30d, Last 60d, Last 90d |

- **Window Type**: Filters by when the driver was *matched* (`matched_at` timestamp) or when it was *loaded* into the database (`loaded_at` timestamp)
- **Time Range**: Restricts the export to a recent window. "Full snapshot" exports all data regardless of time

**Procedure:**

1. Click **Export** in the top bar
2. Choose Window Type and Time Range using the cycle buttons
3. Click **"Choose Folder & Export"**
4. A native folder picker opens — select the destination folder
5. A timestamped subfolder is created automatically (e.g. `export_20260512_143022/`)
6. Export files are written to that folder

**Export files generated:**

| File | Contents |
|------|----------|
| `summary.csv` | Total counts per status (unmatched, matched, paired, quarantined) |
| `unmatched.csv` | All unmatched drivers with serial, side, loaded_at |
| `matched_pairs.csv` | All matched pairs (left serial, right serial, matched_at) |
| `paired.csv` | All confirmed pairs (left serial, right serial, matched_at) |
| `quarantined.csv` | All quarantined drivers with serial, side, loaded_at |
| `all_devices.csv` | All drivers in all statuses — full overview |
| `all_devices.json` | Full export with status, partner, loaded_at, matched_at, and raw level data |

> `[Screenshot: Example export folder contents in Windows Explorer]`

---

## 10. System Build Verification (Workstation CLI)

After a system is assembled, the two installed driver serial numbers and the system serial number can be verified against the database. This is done via the workstation command line on the EOL test station.

**Command:**

```
python adam_workstation.py verify_system <system_sn> <module_sn_1> <module_sn_2>
```

**Example:**

```
python adam_workstation.py verify_system H6001234 IA6800066 IB6800069
```

**Output:**

- Prints `True` if the two modules form a valid matched or paired pair
- Prints `False` if verification fails — a popup window explains the reason

**Verification logic:**

| Condition | Result |
|-----------|--------|
| Either module not found in database | `False` |
| Either module is not in `matched` or `paired` status | `False` |
| Modules are not matched to each other | `False` |
| Either module is already paired to a different partner | `False` |
| Modules are matched to each other (status: `matched`) | `True` — auto-paired and system link created |
| Modules are already paired to each other (status: `paired`) | `True` — system link created/updated |

**Auto-pairing:**
If both modules are in `matched` status and match each other, they are automatically promoted to `paired` status. This handles the case where physical assembly happened correctly but the pairing scan was missed.

**System linking:**
A record is created in the database linking `system_sn` to the two module serials with a timestamp. If a previous system link existed for the same modules or the same system serial, it is replaced.

**Database path:**
By default the command uses `Matching_App/Data/db/matcher.db`. Use `--db-path` if the database is located elsewhere:

```
python adam_workstation.py verify_system H6001234 IA6800066 IB6800069 --db-path "C:/path/to/matcher.db"
```

**Cross-station sync:**
The database is stored as a single file (`matcher.db`) and can be synced via cloud storage (e.g. OneDrive) between the matching station and the EOL station. No sidecar files are created. If the database has not yet synced (e.g. no internet connection), the modules will not be found and `False` is returned — the operator should verify the sync status and retry.

> `[Screenshot: Audio Precision test sequence showing verify_system command result]`

---

## 11. Files and Directories

| Path | Description |
|------|-------------|
| `Matching_App/run.py` | Application entry point |
| `Matching_App/Data/db/matcher.db` | SQLite database — all drivers, pairs, system builds |
| `Matching_App/Data/db/settings.json` | Saved settings (threshold, frequency range, PIN, max module age) |
| `Matching_App/Data/Archive/` | Archive of processed JSON files (legacy import path) |

**Note:** The database file `matcher.db` should not be edited manually. If the database needs to be reset, delete the file — the app recreates it on next startup. All driver and pairing data will be lost.

---

## 12. Troubleshooting

| Problem | Solution |
|---------|----------|
| App does not start | Verify Python 3.9+ is installed and all dependencies from `requirements.txt` are available |
| New measurement data not appearing | Check that the measurement workstation is writing to the same `matcher.db` path; verify the database is synced if on a different machine |
| Driver has no partner | Counterparts of the other side are missing — more measurement data needs to be loaded |
| No pairs formed despite available counterparts | RMSE threshold may be too low — increase it in Settings |
| Cursor not in the scan field | Click the app window once — focus is automatically restored within 0.2 seconds |
| Settings are lost after restart | Check that `Data/db/settings.json` is writable |
| PIN forgotten | Default PIN is `1234`. The PIN can be read or changed directly in `Data/db/settings.json` |
| `verify_system` returns `False` unexpectedly | Check that the database is synced to the EOL station; check the popup message for the specific reason |
| Paired driver cannot be remeasured | Unpair the driver first via the Paired window, then remeasure |
| Export folder not created | Ensure the selected destination folder is writable; check for available disk space |

---

---

## 13. Database Synchronisation and Integrity

The database (`matcher.db`) is a single SQLite file shared between the **matching station** and the **EOL test station**. Understanding how and when these two copies stay in sync — and what can go wrong — is essential for reliable production.

---

### 13.1 How the Database is Shared Between Stations

The database is normally shared via **cloud storage (OneDrive)**. Both stations point to the same synced folder. Changes made on the matching station are pushed by OneDrive and pulled to the EOL station within seconds (typically < 30 s on a stable connection).

```
 Matching Station                    EOL Station
 ┌────────────────┐   OneDrive sync  ┌────────────────┐
 │  matcher.db    │ ───────────────► │  matcher.db    │
 │  (read/write)  │                  │  (read only)   │
 └────────────────┘                  └────────────────┘
```

> **Design note:** The database uses SQLite's `DELETE` journal mode (not WAL). This means there are **no sidecar files** (`-wal`, `-shm`) that OneDrive would need to sync separately. The entire state is always contained in the single `.db` file.

---

### 13.2 Out-of-Sync Scenarios and Mitigation

| Scenario | Symptom | Mitigation |
|----------|---------|------------|
| **OneDrive not connected** at the matching station | Pairs are formed locally but never reach the EOL station | Restore internet connection and wait for OneDrive to finish syncing before running EOL tests |
| **OneDrive not connected** at the EOL station | `verify_system` returns `False` — drivers not found | Check OneDrive sync status on the EOL PC; retry after sync completes |
| **Sync delay** (data written seconds ago) | `verify_system` called immediately after pairing; DB not yet pushed | Wait 30–60 seconds after the last pairing operation and retry |
| **Two stations writing simultaneously** | Locking contention; one write waits up to 5 s (busy timeout) | Only the matching station should write driver and pair records; the EOL station is effectively read-only for driver data |
| **OneDrive conflict file created** | A second copy appears: `matcher (ThiloRode's conflicted copy …).db` | The conflict copy is ignored by the app. Identify which version is authoritative (always the matching station's), delete the conflict copy, and trigger a full sync |
| **Matching station offline for an extended period** | EOL station accumulates units that cannot be verified | Use the USB transfer workflow described below |

**How to check OneDrive sync status:**
- Look for the OneDrive icon in the system tray
- A spinning icon means upload/download is in progress
- A green tick means the folder is fully synced
- A red X or cloud-with-cross means sync is paused or has an error

---

### 13.3 USB Transfer Workflow

When cloud sync is unavailable (no internet, network outage, or the EOL station is on a separate network), the database can be transferred manually via USB stick.

**Procedure — Matching Station → EOL Station:**

1. **Close the Matching App** on the matching station before copying (ensures no write is in progress)
2. Copy `Matching_App/Data/db/matcher.db` from the matching station to the USB stick
3. Insert the USB stick into the EOL station
4. Copy `matcher.db` from the USB stick to the expected path on the EOL station:
   `Matching_App/Data/db/matcher.db`
5. **Overwrite the existing file** — the new copy is always the authoritative one from the matching station
6. The app on the EOL station detects the file change automatically; no restart is needed if the app is running

> ⚠️ **Direction is one-way only:** Never copy a DB from the EOL station back to the matching station. The EOL station does not add driver or pairing data — copying in the wrong direction would overwrite newer matching data with a stale copy.

**After the outage is resolved:**
- Resume normal cloud sync
- Copy the latest `matcher.db` from the matching station to OneDrive
- Confirm on the EOL station that OneDrive shows the file as up-to-date before switching back to cloud-based operation

**Frequency of manual transfers:**
For extended outages, repeat the USB transfer after each production shift so the EOL station always has data for the drivers produced in that shift.

---

### 13.4 Database Corruption: Causes and Prevention

SQLite is robust by design — a properly managed database will survive power loss, process crashes, and concurrent access. However, certain actions can still lead to a corrupted or inconsistent database.

#### Causes of Corruption

| Cause | Risk | Details |
|-------|------|---------|
| **Power loss during a write** | Low | SQLite's atomic commit ensures the DB stays consistent; an interrupted transaction is rolled back automatically on next open |
| **File copied while app is writing** | Medium | If the DB file is copied mid-write (e.g. OneDrive syncing a partially written file), the copy may be inconsistent. OneDrive usually handles this correctly by locking the file during upload |
| **Two app instances writing at the same time** | Medium | The 5-second busy timeout prevents most conflicts, but running two full matching app instances against the same DB is not supported |
| **Manual editing with DB browser tools** | High | Tools like *DB Browser for SQLite* or *SQLiteOnline* can modify the schema or data in ways the app does not expect — **always close the app first and make a backup before any manual edit** |
| **File system corruption (USB stick)** | High | Cheap or failing USB sticks can silently corrupt files during transfer. Always verify the copy with a checksum or re-open the DB in the app to confirm it starts correctly |
| **OneDrive conflict merge** | High | OneDrive never merges SQLite files — it creates a conflict copy. If the wrong copy is kept, paired records from one station may be lost |
| **Disk full during write** | High | A write that runs out of disk space will leave the DB in a partially written state. Monitor available disk space on both stations |

#### Recovery from Corruption

If the app fails to start or shows unexpected errors after a database issue:

1. **Check the export archive** — if regular exports were made (see Section 9), the paired and matched driver data can be reconstructed
2. **Check OneDrive version history** — OneDrive keeps previous versions of synced files. Right-click `matcher.db` → *Version history* → restore the last known-good version
3. **Delete and rebuild** — as a last resort, delete `matcher.db`; the app creates a new empty database on next start. All driver and pairing data must be reimported via the measurement workstations

---

### 13.5 Rules Summary

Follow these rules at all times to keep the database consistent and corruption-free:

| # | Rule |
|---|------|
| 1 | **Only one station writes driver/pair data** — the matching station is the sole writer; the EOL station is read-only for driver records |
| 2 | **Never run two Matching App instances** against the same database simultaneously |
| 3 | **Never copy the database file while the app is running** — always close the app first |
| 4 | **Never edit the database manually** with third-party tools while the app is in use; back up first if manual editing is necessary |
| 5 | **USB transfers are one-way only** — matching station → EOL station, never the reverse |
| 6 | **Resolve OneDrive conflict copies immediately** — always keep the matching station's version; delete the conflict copy |
| 7 | **Monitor OneDrive sync status** before every EOL test shift — a red icon means data may be stale |
| 8 | **Export regularly** (Section 9) — CSV exports provide a human-readable backup that can be used for reconstruction if the DB is lost |
| 9 | **Do not fill the disk** — ensure at least 500 MB of free space on the drive hosting the database at all times |

---

*Last updated: May 2026 – Version 2.0*
