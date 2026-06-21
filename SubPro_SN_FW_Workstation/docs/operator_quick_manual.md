# Operator Quick Manual - Sub-Pro SN/FW Workstation

This quick guide covers only what operators must do during production.

## Before Starting Shift

1. Power on DUT and connect network.
2. Connect scanner.
3. Start application:

```powershell
cd SubPro_SN_FW_Workstation
python run.py
```

4. Prepare the required component barcodes for the unit.

## Per-Unit Workflow

1. Press `Start`.
2. Scan the product serial number.
3. Wait while the app performs automatic processing:
- device discovery/connection
- firmware check and optional flash
- serial number write and readback verification
4. Scan all required component part serial numbers (order does not matter).
5. Confirm final result:
- `PASS`: unit complete, press `Start Next Unit`
- `FAIL`: read message, fix issue, then restart unit workflow

## What Operators Should Verify

- Product serial is correct variant and fully readable.
- Each required part is scanned once and accepted.
- Final state is `PASS` before moving the unit forward.

## Normal Failure Handling

If the app shows `FAIL`:

1. Read the on-screen error text.
2. Check basics first:
- DUT power and network link
- correct firmware file availability
- scanner connection
- correct barcode for unit/part
3. Restart the unit workflow and rescan.
4. If the same error repeats, escalate to technician/engineer and do not continue that unit blindly.

## Golden Sample Rule

If a scanned product serial is recognized as a golden sample, stop the workflow for that unit and escalate. Do not program it as a normal production unit.

## End Of Shift

1. Ensure the current unit is completed or clearly marked as stopped.
2. Export history if your shift process requires it.
3. Close the application.

## Operator Do/Do Not

Do:

- Use scanner input whenever possible.
- Wait for the app to finish automatic processing before scanning parts.
- Keep one unit in process at a time per station.

Do not:

- Skip failed checks.
- Continue after repeated SN readback or firmware errors.
- Mix parts from different units during one session.
