# FAQ

## General

**Where is the repository?**
https://github.com/ThiloRode/Audio-Precision

**Where are the log files?**
`<tool root>\logs\adam_audio\adam_workstation_log_YYYY-MM-DD.log`
Create a desktop shortcut to `logs\adam_audio` for quick access.

**What is the default DataTools password?**
`admin` - change it on first use.

---

## APx Sequence Errors

**An APx shell step fails with no obvious error. Where do I look?**
Open the log file for the day of the failure. Find the timestamp of the failed step and search for `ERROR` in that block. The log shows the exact command, arguments, result, and any exception.

**APx stores an unexpected value in a variable (e.g. empty or wrong serial number).**
The command printed something other than expected to stdout. Check the log for the command output. Common causes: device not connected, OCA timeout, scanner returned `NaN`.

**The sequence fails with "firmware mismatch" or rejects units after a firmware update.**
The `TargetFirmware` user variable in the APx project has not been updated. Update it in Project > Project Properties > Variables > `TargetFirmware`. Also update the Sub-Pro SN/FW Workstation settings if used.

**APx step expected `True` but got something else.**
Check the log for the exact stdout value printed by the command. Common causes: OCA command failed (device not responding), wrong device connected, factory settings not unlocked.

---

## Hardware

**Scanner returns `NaN`.**
The scanner is not connected, the USB driver is not loaded, or another process has the serial port open. Check Device Manager. Reconnect the scanner. Check the log for retry attempts under `AdamSerialScanner`.

**SwitchBox does not respond / `set_channel` fails.**
Check USB connection. The SwitchBox firmware (`Switch.ino`) must be flashed on the Raspberry Pi Pico. Check Device Manager for the COM port. Check the log for `AdamSerialSwitchBox` entries.

**Hardware commands work in isolation but fail during APx sequences.**
APx may be setting a different working directory. The tool resolves hardware via USB vendor/product ID, not COM port name, so this is usually not the cause. Check the log for the exact error.

---

## OCA / Device

**"discover" fails or returns no device.**
The device is not powered, not on the same network, or the mDNS name has changed. Try connecting via IP address directly. Check the log for `OCP1ToolWrapper` entries showing the CLI command and stderr output.

**"discover_and_unlock_factory_settings" returns an error.**
The unlock signature in the APx project variable `UnlockSignature` may be wrong, or the device is not discoverable. Verify the device is powered and on the network.

**OCA command fails after firmware update.**
The new firmware may have changed a command or parameter. Check the `OCP1ToolWrapper` log entries for the exact CLI stderr output. Update `TargetFirmware` in both the APx project and the SN/FW Workstation settings.

---

## MAC Provisioning

**`provision_mac` fails with "pool exhausted".**
The MAC address pool is empty. Run `get_mac_pool_status` to check remaining MACs. A new pool range must be configured with `set_mac_range`.

**`provision_mac` fails with "duplicate serial number".**
The serial number has already been provisioned with a different MAC. Check the provisioning log with `export_mac_log`. This usually means the unit was already processed.

**`provision_mac` fails with "MAC write verification failed".**
The OCA write succeeded but the read-back did not match. This is a device or OCA communication issue. Retry once. If it fails again, check the device hardware.

**DataTools MAC provisioning does not find the database.**
The `mac_db_path` setting in DataTools is not pointing to the correct file. Set it to `SubProMACAddresses\mac_provisioning.db` in the tool root. See the KB article for details.

---

## References

**APx cannot import references - "file not found".**
The `References` folder has not been created yet, or `setup_references` was not called. Run `setup_references` from the APx sequence or manually copy the correct reference files into `References\EOL\` and `References\GoldenSample\`.

**Measurements fail limits that should pass.**
The reference may be outdated or created from a non-representative sample set. Verify the reference was computed as the median of 10-15 good units. Check that the correct `MeasurementType` (EOL vs GoldenSample) is set.

**The Golden Sample sequence measures the wrong unit.**
The `GoldenSampleSerial` project variable does not match the connected unit's serial number. Update the variable to match the actual Golden Sample serial. Only one Golden Sample may be designated at a time.

---

## Matching App and SN/FW Workstation

**The Matching App or SN/FW Workstation will not start.**
These are Python scripts, not EXE files. They must be launched via the virtual environment Python. Use the batch files described in the KB article. Check that the venv exists and dependencies are installed.

**The Matching App shows no data.**
The `matching_db_path` in DataTools settings (or the `--db-path` argument) does not point to the correct `matcher.db`. Verify the path in the settings.

**A driver module cannot be uploaded - "status blocked".**
The module is currently in `paired` status. It must be unpaired in the Matching App before a new measurement can overwrite it.

---

## DataTools

**DataTools opens but shows no data in any viewer.**
Database paths are not configured. Open Settings and set `matching_db_path`, `mac_db_path`, `sn_fw_db_path`, and `measurements_root_path` to the correct locations.

**DataTools was working but stopped finding data after a system change.**
The OneDrive sync path or the tool root directory has changed. All absolute paths stored in DataTools settings must be updated to the new location.

**DataTools installer - where is it?**
`DataTools\build\installer\DataTools-Setup-<version>.exe` in the repository. Current version: 1.1.0.

---

## New Workstation Setup

**What needs to be done when setting up the tool on a new workstation?**

1. Clone the repository: `git clone https://github.com/ThiloRode/Audio-Precision.git`
2. Create the virtual environment and install dependencies (see the KB article).
3. Install the `adam-audio-tools` package: `cd .venv\src\adam-audio-tools && python rebuild_and_reinstall.py`
4. Set `PythonRunner` in each APx project: full path to `.venv\Scripts\pythonw.exe`.
5. Install DataTools via the installer EXE.
6. Configure DataTools database paths and measurements root in the settings panel.
7. Create desktop shortcuts for the Matching App and SN/FW Workstation batch files.
8. Create a desktop shortcut to `logs\adam_audio` for log access.
9. Set `GoldenSampleSerial` and `TargetFirmware` in each APx project.

**How do I update the tool to the latest version?**

```powershell
git pull
cd .venv\src\adam-audio-tools
python rebuild_and_reinstall.py
```

Then rebuild the DataTools installer if a new DataTools version was released.

---

## Matching System

**How does the matching algorithm work?**
The algorithm computes RMSE between every left/right driver combination and uses the Hungarian assignment algorithm to find the globally optimal pairing. Only pairs below the configured RMSE threshold are matched.

**What is the RMSE threshold and how is it configured?**
Default is `1.0` dB over the frequency range `200-8000 Hz`. Change it in the Matching App settings panel. The PIN is `1234` by default.

**A module is stuck in "matched" status and cannot be remeasured.**
`matched` modules can be remeasured - a new upload overwrites the existing measurement. If the module is `paired`, it must be unpaired first in the Matching App.

**A module is in "quarantined" status.**
The module was manually quarantined or exceeded the maximum age (default 14 days). Release it from quarantine in the Matching App before it can re-enter the pool.

**The Matching App shows modules but no matches are being found.**
Either the RMSE threshold is too tight, or the measurements are too spread. Check the RMSE values in the Matching Viewer. Consider re-measuring the outlier modules.

---

## SubPRO Specifics

**How does the APx sequence know whether the unit is a Sub8PRO or Sub10PRO?**
The `get_product_type` command reads the serial number prefix (`CI` = Sub8PRO, `CJ` = Sub10PRO) and sets the `DataDirectory` variable accordingly. The same APx project handles both variants automatically.

**The SubPRO sequence fails at "Init SubPro EOL" with an error about the serial number.**
Either the scanned serial matches the `DefaultSerial` variable (default unit connected) or matches the `GoldenSampleSerial` (Golden Sample connected during an EOL run). Verify the correct unit is connected.

**When should the "Create Reference" sequence be used instead of EOL?**
Always use "Create Reference" when generating new reference curves for SubPRO. This sequence ensures gain calibration is at zero during measurement so the reference is not biased. Run the EOL sequence first to confirm the unit is functional, then switch to "Create Reference".

---

## APx Project Variables

**Where is the complete list of APx project variables for each project?**
The sequence walkthroughs document all variables for each project:
- SubPRO: [subpro-v1-sequence.md](subpro-v1-sequence.md)
- H715 System Test: [h715-system-test-sequence.md](h715-system-test-sequence.md)
- ASubsTristar: [asubstristar-v0-2-sequence.md](asubstristar-v0-2-sequence.md)

**APx validates a response but gets the wrong string after a code update.**
The `ExpectedResponse` in the APx shell step is stale. The live command may print a different string than was expected when the project was created. Run the command manually in PowerShell and compare stdout with the `ExpectedResponse` field.

---

## L-R Diff and Stereo Compensation

**What is the L-R-Diff.csv and when is it needed?**
It captures the left/right microphone imbalance of the measurement setup. Used only for stereo devices. The compensation is applied to RMS measurements so that systematic mic differences do not appear as device defects.

**How is L-R-Diff.csv created?**
Measure a known-good unit with identical left and right acoustic output (or use a reference source). The difference between Ch1 and Ch2 in the RMS measurement is the mic imbalance. Save this as a mono CSV in the `References\` root.

**L-R-Diff.csv is zero everywhere - is that correct?**
Yes, if the measurement microphones are well-matched. A file with all-zero Y values has no effect on compensation and is a valid placeholder.

