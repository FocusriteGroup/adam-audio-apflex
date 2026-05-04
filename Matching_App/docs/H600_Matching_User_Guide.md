# H600 Matching – User Guide

---

## Table of Contents

1. [Overview](#1-overview)
2. [Starting the Application](#2-starting-the-application)
3. [Main Screen](#3-main-screen)
   - 3.1 [Status Bar (Top)](#31-status-bar-top)
   - 3.2 [Frequency Response Chart (Center)](#32-frequency-response-chart-center)
   - 3.3 [Scan Area (Bottom)](#33-scan-area-bottom)
4. [Loading Measurement Data](#4-loading-measurement-data)
5. [Pairing Drivers – Step by Step](#5-pairing-drivers--step-by-step)
   - 5.1 [Scan the First Driver](#51-scan-the-first-driver)
   - 5.2 [Scan the Partner Driver](#52-scan-the-partner-driver)
   - 5.3 [Pairing Confirmed](#53-pairing-confirmed)
6. [Understanding Status Messages](#6-understanding-status-messages)
7. [Management Area](#7-management-area)
   - 7.1 [PIN Entry](#71-pin-entry)
   - 7.2 [RMSE Threshold](#72-rmse-threshold)
   - 7.3 [Frequency Range](#73-frequency-range)
   - 7.4 [Apply & Rematch](#74-apply--rematch)
   - 7.5 [Waiting List](#75-waiting-list)
   - 7.6 [Paired Drivers](#76-paired-drivers)
8. [Files and Directories](#8-files-and-directories)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Overview

The **H600 Matching** application is used for optimal pairing of speaker drivers during production. Measured drivers (Left = IA, Right = IB) are automatically matched into pairs based on their frequency responses. The goal is to find a left and right driver whose frequency responses are as similar as possible.

**Workflow Overview:**

1. Drivers are measured at the measurement station → a JSON file is generated
2. The JSON file is copied into the `Data/` folder → the app detects it automatically
3. The app computes optimal pairs (Hungarian algorithm)
4. The operator scans the assigned drivers via QR code → the pair is confirmed

> 📷 `[Screenshot: Full application overview with loaded data]`

---

## 2. Starting the Application

The application is started via the file `run.py`:

```
python3 run.py
```

After startup, the main window opens. The app immediately begins monitoring the `Data/` folder for new JSON measurement files.

> 📷 `[Screenshot: Application immediately after startup, empty state]`

---

## 3. Main Screen

The main screen is divided into three areas:

> 📷 `[Screenshot: Main screen with labels for the three areas]`

### 3.1 Status Bar (Top)

The top bar shows the current pool status:

| Display | Meaning |
|---------|---------|
| **In pool: X** | Number of drivers that do not yet have a pair (unmatched) |
| **Matched: X** | Number of drivers that have been assigned a partner but not yet physically paired |
| **Paired: X** | Number of drivers that have been successfully scanned and confirmed |

On the right side is the **Manage** button, which opens the management area (PIN-protected).

> 📷 `[Screenshot: Status bar with example values, e.g. "In pool: 3 | Matched: 8 | Paired: 4"]`

### 3.2 Frequency Response Chart (Center)

The chart displays the frequency response of scanned drivers:

- **Blue curve** = Left driver (IA)
- **Orange curve** = Right driver (IB)
- **X-axis**: Frequency in Hz (logarithmic)
- **Y-axis**: Level in dB SPL

After scanning a driver, its frequency response is displayed. After scanning the partner, both curves are overlaid so the match quality can be visually verified.

> 📷 `[Screenshot: Chart with two overlaid frequency responses (blue + orange)]`

### 3.3 Scan Area (Bottom)

At the bottom of the screen:

- **Scan input field**: The QR code of a driver is automatically read here. The cursor is permanently in this field — no clicking required.
- **Status line**: Shows instructions and feedback in color:
  - **Gray** = Ready / neutral message
  - **Red** = Error
  - **Green** = Success

> 📷 `[Screenshot: Scan area with status message "Scan first driver..."]`

---

## 4. Loading Measurement Data

Measurement data is provided as JSON files. To load them into the app:

1. **Copy (or move) the JSON file into the `Data/` folder**
2. The app detects the file automatically within a few seconds
3. The drivers are imported into the database
4. All existing match assignments (not yet physically confirmed) are re-evaluated together with the new drivers to find the globally optimal pairs
5. The status bar updates automatically
6. The JSON file is automatically moved to the `Data/Archive/` folder

Multiple JSON files can be placed simultaneously or one after another.

**Important:**
- Only drivers with serial numbers starting with **IA** (left) or **IB** (right) are imported
- Already imported drivers are not loaded a second time
- Already physically confirmed pairs (status "paired") are never affected — only unconfirmed matches are re-evaluated

> 📷 `[Screenshot: Status bar before/after — pool numbers change after JSON import]`

---

## 5. Pairing Drivers – Step by Step

### 5.1 Scan the First Driver

1. Pick a driver from the shelf
2. Scan the QR code with the handheld scanner
3. The system displays the frequency response and shows the assigned partner

**Possible messages:**

| Message | Meaning |
|---------|---------|
| `IA6300005 scanned — now scan partner: IB6300012` | Success — now scan the indicated partner |
| `IA6300005 has no match yet — still in pool` | This driver has no partner yet (counterparts are missing) |
| `IA6300005 already paired with IB6300012` | This pair has already been confirmed |
| `Unknown driver: XY123` | This serial number is not in the database |

> 📷 `[Screenshot: After first scan — status line shows partner instruction, chart shows single curve]`

### 5.2 Scan the Partner Driver

1. Pick the displayed partner driver from the shelf
2. Scan its QR code
3. The system verifies it is the correct partner

**If the wrong driver is scanned:**
- Error message: `Expected IB6300012, got IB6300099 — try again`
- The process resets — start again from step 5.1

> 📷 `[Screenshot: Error message after incorrect second scan (red status line)]`

### 5.3 Pairing Confirmed

After successfully scanning both drivers:

- Green success message: `Paired: IA6300005 + IB6300012`
- The chart shows both frequency responses overlaid
- The status bar updates (Matched decreases, Paired increases)
- After 3 seconds the system is ready for the next pair

> 📷 `[Screenshot: Successful pairing — green message, both curves in chart]`

---

## 6. Understanding Status Messages

| Color | Meaning | Examples |
|-------|---------|----------|
| 🔴 **Red** | Error — action not possible | Wrong partner, unknown driver, already paired |
| 🟢 **Green** | Success — pairing confirmed | `Paired: IA6300005 + IB6300012` |
| ⚪ **Gray** | Neutral — ready for input | `Scan first driver...` |

The status message resets automatically after 3 seconds.

---

## 7. Management Area

The management area is **PIN-protected** and allows configuration of the matching algorithm as well as driver management.

### 7.1 PIN Entry

1. Click the **Manage** button in the top right
2. Enter the PIN (default: **1234**)
3. Confirm with **Enter** or the **OK** button

If the wrong PIN is entered, "Wrong PIN" is displayed and the field is cleared.

> 📷 `[Screenshot: PIN entry dialog]`

### 7.2 RMSE Threshold

The **RMSE Threshold** determines how similar two drivers must be to qualify as a pair.

- **Unit**: dB (decibel)
- **Range**: 0.10 dB – 2.00 dB
- **Default**: 1.00 dB

**Lower value** = stricter matching → fewer pairs, but better consistency
**Higher value** = more tolerant matching → more pairs, but larger deviations allowed

The current value is displayed above the slider (e.g. `RMSE Threshold: 0.85 dB`).

> 📷 `[Screenshot: Management popup with threshold slider]`

### 7.3 Frequency Range

The two frequency sliders define which frequency range is considered for matching:

- **Freq Min** (left slider): 20 Hz – 2,000 Hz (default: 200 Hz)
- **Freq Max** (right slider): 2,000 Hz – 20,000 Hz (default: 8,000 Hz)

**Why limit the range?**
- Very low frequencies (< 200 Hz) are heavily influenced by room modes and are less meaningful for driver pairing
- Very high frequencies (> 8,000 Hz) are sensitive to microphone positioning
- The mid-range (200 – 8,000 Hz) is acoustically most relevant for perceived matching quality

> 📷 `[Screenshot: Frequency range sliders with label "Freq Range: 200 Hz – 8000 Hz"]`

### 7.4 Apply & Rematch

The green **"Apply & Rematch"** button applies the changed settings:

1. All current matching assignments are dissolved (not the already confirmed pairs!)
2. The algorithm runs again with the new settings
3. A status message shows the result: `Reset X drivers, formed Y new pairs`
4. The settings are saved and persist after app restart

**Important:** Already physically paired drivers (status "paired") are **not** reset.

> 📷 `[Screenshot: Result after rematch — green info message]`

### 7.5 Waiting List

The waiting list shows all drivers that do **not yet have a pair** (status: unmatched):

- **Left column**: IA drivers (left) with count
- **Right column**: IB drivers (right) with count

Each driver has an **X** button for deletion. Deleting permanently removes the driver from the database.

**Use case:** When a driver is defective or was imported by mistake, it can be removed here.

> 📷 `[Screenshot: Waiting list with IA and IB drivers, X buttons visible]`

### 7.6 Paired Drivers

At the bottom of the management popup is the list of all physically confirmed pairs:

- Each row shows: `IA number + IB number`
- The **Unpair** button dissolves the pairing → both drivers return to the pool

**Use case:** When a pair was confirmed by mistake or a driver is found to be defective after pairing.

> 📷 `[Screenshot: Paired drivers list with Unpair buttons]`

---

## 8. Files and Directories

| Path | Description |
|------|-------------|
| `Data/` | Input folder — place JSON measurement files here |
| `Data/Archive/` | Automatic archive — processed files are stored here (with timestamp) |
| `Data/db/matcher.db` | SQLite database with all drivers and pair assignments |
| `Data/db/settings.json` | Saved settings (threshold, frequency range, PIN) |

**Note:** The files in `Data/db/` should not be edited manually. If problems occur, the database (`matcher.db`) can be deleted — the app will recreate it on the next startup. Measurement data must then be copied from the archive back into the `Data/` folder.

---

## 9. Troubleshooting

| Problem | Solution |
|---------|----------|
| App does not start | Verify that Python 3.9+ is installed and all dependencies are available |
| JSON file is not detected | File must be placed directly in the `Data/` folder (not in a subfolder) |
| Driver has no partner | Counterparts of the other side are missing (IA ↔ IB) — load more measurement data |
| No driver gets a pair despite available counterparts | RMSE threshold is too low — increase it in the management area |
| Cursor is not in the scan field | Click the app window once — focus is automatically restored |
| Settings are lost | Check that `Data/db/settings.json` exists and is writable |
| PIN forgotten | Default PIN is `1234`. The PIN can be viewed/changed in the file `Data/db/settings.json` |
| Reset database | Delete the file `Data/db/matcher.db` and restart the app — all data will be lost |

---

*Last updated: March 2026 – Version 1.0*
