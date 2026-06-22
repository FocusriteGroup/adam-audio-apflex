# ASubsTristar v0.2 APx Sequence Walkthrough

This document describes what happens in `ASubsTristar_v_0_2.approjx`, based on the `project.xml` sequence and shell-step definitions.

## Scope

- Project package: `ASubsTristar_v_0_2.approjx`
- Source analyzed: `project.xml` inside the `.approjx` ZIP package
- Focus:
  - execution sequence at high level
  - shell commands in document order
  - command purpose and APx variable use
  - measurement/export flow

## High-Level Runtime Flow

1. Prepare references and runtime metadata:
- ensure reference files exist (`setup_references`)
- generate timestamp suffix (`generate_timestamp_extension`)
- set measurement type to `EOL` via inline Python print

2. Discover and initialize DUT for EOL:
- discover device and unlock factory settings
- read serial number
- validate that DUT is not default-serial and not a golden-sample run
- run EOL init path (includes firmware target inputs)

3. Calibration stage:
- APx runs generator/analyze/measurement steps
- exports pre-calibration RMS CSV
- computes calibration offset (`calibrate_gain`)
- writes calibration offset to DUT (`set_gain_calibration`)

4. Main measurement stage:
- APx runs measurement steps for RMS/phase/distortion/RnB
- imports references and limits
- derives THD reference constrained by limits (`filter_reference_by_limits`)
- exports final result CSV files

5. End-of-line provisioning:
- provisions MAC address (`provision_mac`)

## Shell Commands In Sequence Order

| # | Command | APx wait mode | APx output handling | Purpose |
|---|---|---|---|---|
| 1 | `adam_workstation.py calibrate_gain "..._RMS_Level_Sub_pre_calibration.csv" "...\References\$(MeasurementType)\RMS.csv" -f $(CalibrationFrequencies)` | `WaitForExitStoreOutputInVariable` | Stores to `CalibrationOffset` | Calculate gain offset from measured vs reference RMS data. |
| 2 | `adam_workstation.py set_gain_calibration $(CalibrationOffset) $(ProductName)` | `WaitForExitValidateResponse` | Expects `True` | Apply calculated gain calibration to DUT. |
| 3 | `adam_workstation.py filter_reference_by_limits "...\References\$(MeasurementType)\THD.csv" "...\References\$(MeasurementType)\Limits\THD.csv" --output-filename THD_Ref.csv --output-dir "...\Temp"` | `WaitForExitValidateResponse` | Expects `successful` | Build THD reference filtered by allowed limits. |
| 4 | `adam_workstation.py discover_and_unlock_factory_settings DEADBEEF` | `WaitForExitStoreOutputInVariable` | Stores to `ProductName` | Discover DUT identity and unlock factory settings context. |
| 5 | `adam_workstation.py setup_references "$(MyDocuments)\$(DataDirectory)" --mono` | `WaitForExitIgnoreResponse` | Output ignored | Prepare/copy required references for mono flow. |
| 6 | `adam_workstation.py generate_timestamp_extension` | `WaitForExitStoreOutputInVariable` | Stores to `TimestampExtension` | Create per-run timestamp suffix for filenames. |
| 7 | `-c "print('EOL')"` | `WaitForExitStoreOutputInVariable` | Stores to `MeasurementType` | Set APx runtime measurement type variable to `EOL`. |
| 8 | `adam_workstation.py get_serial_number $(ProductName)` | `WaitForExitStoreOutputInVariable` | Stores to `SerialNumber` | Read DUT serial number for identification and file naming. |
| 9 | `adam_workstation.py is_default_serial $(SerialNumber) $(DefaultSerial) False` | `WaitForExitValidateResponse` | Expects `False` | Guard: fail path if DUT still has default serial. |
| 10 | `adam_workstation.py is_golden_sample $(SerialNumber) $(GoldenSampleSerial) False` | `WaitForExitValidateResponse` | Expects `False` | Guard: ensure this path is not golden-sample mode. |
| 11 | `adam_workstation.py eol_init_sub $(ProductName) $(SerialNumber) $(DefaultSerial) $(GoldenSampleSerial) $(TargetFirmware)` | `WaitForExitValidateResponse` | Expects `successful` | Initialize Sub EOL state and firmware prerequisites. |
| 12 | `adam_workstation.py provision_mac $(ProductName) $(SerialNumber) $(DefaultMACAddress)` | `WaitForExitValidateResponse` | Expects `successful` | Assign/provision MAC address at end of successful EOL run. |

## Measurement Steps Observed In Sequence

APx sequence step names indicate these operations:

- `Turn Generator On`
- `Measure and Set DUT Delay`
- `MeasurementStep`/`AnalyzeStep`
- `Import Reference`
- `Import Limits` / `Import Upper Limits Data` / `Import Lower Limits Data`
- `Refresh Defined Result(s)`
- `Save Generator Waveform`
- Final data exports

Sequence groups present in project metadata:

- `DUT`
- `Golden Sample`
- `Calibration`

## Measurands And Result Families

The project content references these main result families:

- RMS Level
- Phase (vs frequency)
- THD Ratio / THD Level
- THD+N Ratio / THD+N Level
- Rub and Buzz
- Rub and Buzz Crest Factor
- Rub and Buzz Peak Ratio
- SoneTrac Rub and Buzz / Loudness references

## Key Exported Files

Pre-calibration export used for calibration math:

- `..._RMS_Level_Sub_pre_calibration.csv`

Final exports used for production artifacts:

- `..._RMS_Level_Sub.csv`
- `..._Phase_Sub.csv`
- `..._THD.csv`
- `..._RnB_CF_Sub.csv`
- `..._RnB_PR_Sub.csv`

## Reference/Limit Inputs Used

Key referenced files in this project include:

- `...\References\$(MeasurementType)\RMS.csv`
- `...\References\$(MeasurementType)\THD.csv`
- `...\References\$(MeasurementType)\Phase.csv`
- `...\References\$(MeasurementType)\Limits\RMS.csv`
- `...\References\$(MeasurementType)\Limits\THD.csv`
- `...\References\$(MeasurementType)\Limits\PhaseUpper.csv`
- `...\References\$(MeasurementType)\Limits\PhaseLower.csv`
- Derived temp file: `...\Temp\THD_Ref.csv`

## Notes And Potential Maintenance Findings

- `get_serial_number` is configured as `WaitForExitStoreOutputInVariable` (stores `SerialNumber`) and also carries `ExpectedResponse=Initialization successful`.
- In practice, this pattern is often used in output-variable mode where literal expected text is not active. Keep project settings consistent with intended APx wait mode.

## Practical Interpretation

In production terms, this project performs:

1. DUT discovery and EOL preparation.
2. Calibration measurement and gain correction write-back.
3. Full acoustic/electrical measurement run against references and limits.
4. Result export for traceability.
5. MAC provisioning when all prior gates pass.
