# SOP — H715 System Test & Module Matching

**Scope:** End-of-line acoustic testing of H715 headphone assemblies using APx500.  
**Projects:**
- `H715_ModuleMatching_v_1_0_DV2.approjx` — individual driver module measurement (feeds matching database)
- `H715System_Test_v_2_0_DV2.approjx` — complete headphone system test (both channels, limits, L-R compensation)

---

## 1 — Module Matching Measurement

This sequence measures a single driver module and stores its frequency response in the matching database. Run this for every driver module before assembly. Once started, the sequence loops automatically — it waits for the next serial scan after each unit, so the operator does not need to restart APx between modules.

### Steps

| # | Action | Who |
|---|---|---|
| 1 | Peel the serial number sticker off the driver module | Operator |
| 2 | Place the module in the acoustic test fixture | Operator |
| 3 | Close the test box lid manually and confirm it is fully latched | Operator |
| 4 | **First unit only:** open `H715_ModuleMatching_v_1_0_DV2.approjx` in APx500 and start the sequence | Operator |
| 5 | A prompt appears: **"Please enter the Serial Number"** — scan the serial sticker, then click **OK** | Operator |
| 6 | APx runs the acoustic response measurement (single channel) | Auto |
| 7 | APx generates the timestamp, checks reference files, sets measurement type to `EOL`, and verifies the serial | Auto |
| 8 | A **"Store Data"** confirmation prompt appears — click **OK** | Operator |
| 9 | APx uploads the measurement to `Matching_App\Data\db\matcher.db` | Auto |
| 10 | **If PASS:** the sequence restarts automatically and waits at the serial number prompt — open the box, remove the module, and load the next one (return to step 1) | Operator |
| 10 | **If FAIL:** APx stops and offers a retry — investigate the failure, then retry or abort manually | Operator |

> **Golden Sample mode:** Enabled via a separate APx checklist configuration. Follows the same operator steps but stores data under the `GoldenSample` measurement type instead of `EOL`.

---

## 2 — System Test (Complete H715 Assembly)

This sequence tests the fully assembled headphone, validates that the two installed driver modules form a matched pair, measures both channels against limits, and computes the L-R channel difference compensation.

### Prerequisites

- Both driver modules must already be measured and stored in the matching database (see Section 1).
- The headphone is placed in the binaural test fixture with both ear cups seated on the measurement microphones.
- The two serial number stickers (one per driver module) have been peeled off the headphone and are ready to be scanned.

### Per-unit steps

| # | Action | Detail | Who |
|---|---|---|---|
| 1 | Mount the headphone in the test fixture | Both ear cups must be fully seated on the measurement microphones | Operator |
| 2 | Close the test box lid manually and confirm it is fully latched | Box must be closed before the sequence is started | Operator |
| 3 | Start the sequence in APx500 | | Operator |
| 4 | A prompt appears: **Scan Module 1** — scan the serial sticker of the **left** driver module, click **OK** | 60 s timeout | Operator |
| 5 | A prompt appears: **Scan Module 2** — scan the serial sticker of the **right** driver module, click **OK** | 60 s timeout | Operator |
| 6 | APx validates the pair against the matching database — sequence fails if the modules are not a confirmed matched pair | | Auto |
| 7 | APx verifies the system serial is not a golden sample, generates a timestamp, and resolves reference files | System serial number is read automatically by the scanner inside the box | Auto |
| 8 | APx measures the **left ear** (Channel 1) | Exports: RMS Level, Phase, THD, Rub & Buzz CF, Rub & Buzz PR for Ch 1 | Auto |
| 9 | APx switches the SwitchBox to **Channel 2** and measures the **right ear** | Exports: RMS Level, Phase, THD, Rub & Buzz CF, Rub & Buzz PR for Ch 2 | Auto |
| 10 | APx applies limits and computes the L-R compensation for both channels | | Auto |
| 11 | APx sends the **OpenBox** command — the test fixture relay releases | Remove the headphone from the fixture | Auto / Operator |

### Pass / Fail

The sequence uses APx's built-in result comparison. If any limit is exceeded the sequence is marked **Failed**. No manual pass/fail decision is required.

---

## 3 — Calibration (Periodic — Not Part of Normal EOL)

The calibration sub-sequence (`CalibLeft` / `CalibRight`) is **disabled by default** in the EOL checklist. It is only enabled for calibration runs using a calibrated reference microphone.

| # | Action |
|---|---|
| 1 | Switch the APx checklist to **Calibration** mode |
| 2 | Place the calibration microphone in the left ear cup and click **OK** — APx sets the dB SPL reference for Channel 1 |
| 3 | Move the calibration microphone to the right ear cup and click **OK** — APx sets the dB SPL reference for Channel 2 |
| 4 | Switch back to **EOL** mode for normal production testing |

---

## 4 — File Outputs

All measurement CSVs are saved under the path configured in the `DataDirectory` project variable:

```
$(MyDocuments)\<DataDirectory>\Measurements\<EOL|GoldenSample>\<Year>\<MM>_<DD>\
  <SerialNumber>_<Timestamp>_RMS_Level_Ch_1.csv
  <SerialNumber>_<Timestamp>_Phase_Ch_1.csv
  <SerialNumber>_<Timestamp>_THD_Ch_1.csv
  <SerialNumber>_<Timestamp>_RnB_CF_Ch_1.csv
  <SerialNumber>_<Timestamp>_RnB_PR_Ch_1.csv
  <SerialNumber>_<Timestamp>_RMS_Level_Ch_2.csv
  <SerialNumber>_<Timestamp>_Phase_Ch_2.csv
  <SerialNumber>_<Timestamp>_THD_Ch_2.csv
  <SerialNumber>_<Timestamp>_RnB_CF_Ch_2.csv
  <SerialNumber>_<Timestamp>_RnB_PR_Ch_2.csv
```

Matching upload data is written to `Matching_App\Data\db\matcher.db`.

---

## 5 — Project Variables (APx Project Settings)

| Variable | Purpose | Set by |
|---|---|---|
| `DataDirectory` | Root data folder path | APx project setting |
| `MeasurementsDirectory` | Sub-folder name for measurement CSVs | APx project setting |
| `GoldenSampleSN` | Serial number of the designated golden sample | APx project setting |
| `ADAMServiceIP` | IP address of the ADAM Service host (v1 project only) | APx project setting |
| `SerialNumber` | Captured from barcode scanner or operator input | Runtime |
| `Module1Serial` / `Module2Serial` | Captured from operator prompts | Runtime |
| `TimestampExtension` | Generated automatically per unit | Runtime |
| `MeasurementType` | Set to `EOL` or `GoldenSample` by checklist mode | Runtime |
