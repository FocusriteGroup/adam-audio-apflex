# Test Suite – SubPro MAC Address Provisioning

## Overview

The provisioning system has two pytest test files, both located in `SubProMACAddresses/`:

| File | Purpose | Tests |
|---|---|---|
| `test_mac_provisioning.py` | Integration tests — all 7 flow paths | 7 |
| `test_mac_stress.py` | Stress + exhaustion tests | 5 + 1 = 6 |

All tests run against a **real physical device** (`ASubsDV1`) connected to the test network.
They call `adam_workstation.py` as a subprocess — exactly as the AP sequence does in production.

---

## How to Run

### Integration tests

```powershell
$pytest = ".venv\Scripts\pytest.exe"
& $pytest SubProMACAddresses/test_mac_provisioning.py -v `
    --html=logs/mac_provisioning_test/report.html `
    --self-contained-html `
    --junitxml=logs/mac_provisioning_test/junit.xml
```

### Stress tests

```powershell
& $pytest SubProMACAddresses/test_mac_stress.py -v `
    --html=logs/mac_stress/report.html `
    --self-contained-html `
    --junitxml=logs/mac_stress/junit.xml `
    --cycles=5 `
    --mac-count=10
```

| Option | Default | Description |
|---|---|---|
| `--cycles N` | 5 | Provisioning cycles per ARP delay value in the stress test |
| `--mac-count N` | 10 | Pool size for the exhaustion test |

---

## Shared Infrastructure

### `conftest.py`

Registers the `--cycles` and `--mac-count` CLI options and exposes them as session-scoped fixtures.

### `device_state` fixture (module-scoped, `test_mac_provisioning.py`)

Runs once for the entire integration test module:

- **Setup:** `init_mac_db` → clear `mac_range` + `provisioning_log` → set range `02:FE:ED:00:00:00` – `02:FE:ED:00:00:09` (10 MACs, warn=3) → read device serial + current MAC
- **Teardown:** restores the device to its original MAC address
- **Shared state dict:** `serial`, `initial_mac`, `default_mac`, `provisioned_mac`

### `stress_state` fixture (session-scoped, `test_mac_stress.py`)

Same pattern but uses range `02:FE:ED:01:00:00` – `02:FE:ED:01:FF:FF` (65,536 MACs).

---

## Integration Tests (`test_mac_provisioning.py`)

Tests are numbered to guarantee execution order. Each test builds on the device state left by the previous one.

---

### test_1_success — First-Test Happy Path

**What it tests:** A brand-new device (default MAC, SN not in DB) goes through the complete first-test path and receives a unique MAC.

**Setup:** Device is in factory default state, DB is empty.

**Steps:**
1. Call `provision_mac ASubsDV1 <serial> <default_mac>`
2. Read the resulting DB entry

**Assertions:**
- stdout == `"successful"`
- Exactly 1 `verified` entry in `provisioning_log` for this serial
- Assigned MAC starts with `02:FE:ED` (within test range)

**Side effect:** Stores `provisioned_mac` in `device_state` for subsequent tests.

**Result:** ✅ PASS — device receives unique MAC, DB entry status = `verified`

---

### test_2_retest_ok — Re-Test Happy Path

**What it tests:** The same device is submitted for provisioning again. It already holds its unique MAC — the provisioner must recognise this and confirm without issuing a new MAC.

**Setup:** Device holds `provisioned_mac` from `test_1`.

**Steps:**
1. Read current MAC from device — confirms it matches `provisioned_mac`
2. Call `provision_mac ASubsDV1 <serial> <default_mac>` again

**Assertions:**
- Current device MAC == `provisioned_mac` (pre-condition)
- stdout == `"successful"`
- No new DB entry created

**Result:** ✅ PASS — re-test confirmed, MAC unchanged

---

### test_3_export_log — Log Export

**What it tests:** The `export_mac_log` command correctly exports the provisioning log to CSV with optional filters.

**Setup:** DB contains 1 real verified entry (from `test_1`) + 2 synthetic rows inserted by this test (`TEST-EXPORT-V` = verified, `TEST-EXPORT-R` = reserved).

**Steps:**
1. Export all rows → `export_all_<ts>.csv`
2. Export filtered `--status verified` → `export_verified_<ts>.csv`
3. Export filtered `--serial <device_serial>` → `export_serial_<ts>.csv`

**Assertions:**

| Export | Assertion |
|---|---|
| All | ≥ 3 rows; real serial + MAC present; both synthetic rows present; all required columns present |
| `--status verified` | All rows have `status=verified`; real device + `TEST-EXPORT-V` included; `TEST-EXPORT-R` excluded |
| `--serial <device>` | Exactly 1 row; correct serial, MAC, status; `reserved_at` and `verified_at` timestamps populated |

**Cleanup:** Synthetic rows removed from DB after test.

**Result:** ✅ PASS — all 3 exports correct, filters work, real timestamps present

---

### test_4_duplicate_sn — Duplicate Serial Number

**What it tests:** A device arrives with the factory default MAC, but its serial number is already registered in the DB (as verified from `test_1`). The provisioner must reject it.

**Setup:** Device is reset to `default_mac` via `set_mac_address`. DB still holds the `verified` entry from `test_1`.

**Steps:**
1. Reset device MAC to `default_mac`
2. Call `provision_mac ASubsDV1 <serial> <default_mac>`

**Assertions:**
- Result is a string (not `"successful"`)
- `"duplicate serial number"` in result
- `provisioned_mac` (the existing DB MAC) is mentioned in the error

**Expected output:**
```
Error: duplicate serial number — SN '<serial>' is already assigned to MAC 02:FE:ED:00:00:00
```

**Result:** ✅ PASS — error returned, no new DB entry created

---

### test_5_mac_mismatch — MAC Mismatch

**What it tests:** The device holds a unique MAC (`ALTERNATE_MAC = 02:FE:ED:FF:FF:01`) that does not match the MAC stored in the DB for this serial number.

**Setup:** Device MAC is overwritten to `ALTERNATE_MAC` via `set_mac_address`. DB still holds the original `provisioned_mac`.

**Steps:**
1. Write `ALTERNATE_MAC` to device
2. Confirm device now reports `ALTERNATE_MAC`
3. Call `provision_mac ASubsDV1 <serial> <default_mac>`

**Assertions:**
- `"MAC mismatch"` in result
- `provisioned_mac` (DB value) mentioned in error
- `ALTERNATE_MAC` (device value) mentioned in error

**Expected output:**
```
Error: MAC mismatch — DB has 02:FE:ED:00:00:00, device reports 02:FE:ED:FF:FF:01
```

**Result:** ✅ PASS — mismatch detected, no DB changes

---

### test_6_unknown_device — Unknown Device

**What it tests:** The device holds a unique (non-default) MAC, but the serial number has no entry in the DB at all.

**Setup:** DB entry for this serial is deleted. Device still holds `ALTERNATE_MAC` from `test_5`.

**Steps:**
1. Delete `provisioning_log` entry for this serial directly via SQL
2. Confirm DB is empty for this serial
3. Confirm device still reports `ALTERNATE_MAC`
4. Call `provision_mac ASubsDV1 <serial> <default_mac>`

**Assertions:**
- `"unknown device"` in result
- `ALTERNATE_MAC` mentioned in error

**Expected output:**
```
Error: unknown device — SN '<serial>' has no DB record but device reports MAC 02:FE:ED:FF:FF:01
```

**Result:** ✅ PASS — unknown device detected

---

### test_7_pool_exhausted — Pool Exhausted

**What it tests:** The MAC pool is fully consumed. A provisioning attempt must be rejected immediately.

**Setup:**
- `next_mac` is set to `FF:FF:FF:FF:FF:FF` directly in the DB (past all valid MACs)
- Device is reset to `default_mac`
- DB entry for this serial was deleted in `test_6`

**Steps:**
1. Set `next_mac = 'FF:FF:FF:FF:FF:FF'` via SQL
2. Verify `get_mac_pool_status` reports `remaining = 0`
3. Reset device to `default_mac`
4. Call `provision_mac ASubsDV1 <serial> <default_mac>`

**Assertions:**
- Pool status `remaining == 0` (pre-condition)
- `"pool exhausted"` in result (case-insensitive)

**Expected output:**
```
Error: MAC pool exhausted — no addresses available
```

**Result:** ✅ PASS — exhaustion detected before any reservation attempt

---

## Stress Tests (`test_mac_stress.py`)

### test_readback_stress — Write/Read-Back Reliability

**What it tests:** OCA write reliability and read-back consistency under rapid successive calls at 5 different ARP flush delay values.

**Parametrized delays:** `[0.0, 0.5, 1.0, 2.0, 3.0]` seconds → 5 separate test cases.

**Per cycle (repeated `--cycles` times per delay):**
1. Reset device to `default_mac`
2. `provision_mac --arp-delay=<delay>` with unique synthetic serial → expect `"successful"`
3. `provision_mac` again with same serial → expect `"successful"` (re-test confirmation)
4. Delete DB entry (MAC pointer stays advanced — intentional)

**Statistics recorded per delay:**

| Metric | Description |
|---|---|
| `success` | Cycles where write + read-back passed |
| `verify_failed` | Cycles where read-back MAC didn't match written MAC |
| `oca_errors` | Cycles with OCA communication failure |
| `retest_ok` | Cycles where re-test confirmed correct MAC |
| `avg / min / max time` | Cycle duration in seconds |

**Assertions:**
- `success == cycles` — every cycle must succeed
- `retest_ok == success` — every successful provision must be confirmed by re-test

**Per-delay CSV** written to `logs/mac_stress/stress_delay<N>_<timestamp>.csv`.

**Results (20 cycles per delay, isolated test network, run 2026-05-27):**

| ARP Delay | Cycles | Success | Verify Failed | OCA Errors | Retest OK | Avg time | Min | Max |
|---|---|---|---|---|---|---|---|---|
| 0.0 s | 20 | 20/20 | 0 | 0 | 20/20 | 1.166 s | 1.094 s | 1.453 s |
| 0.5 s | 20 | 20/20 | 0 | 0 | 20/20 | 1.739 s | 1.610 s | 1.922 s |
| 1.0 s | 20 | 20/20 | 0 | 0 | 20/20 | 2.166 s | 2.031 s | 2.266 s |
| 2.0 s | 20 | 20/20 | 0 | 0 | 20/20 | 3.135 s | 3.062 s | 3.203 s |
| 3.0 s | 20 | 20/20 | 0 | 0 | 20/20 | 4.222 s | 4.157 s | 4.391 s |

> ✅ **Finding:** On an isolated test network, `--arp-delay 0.0` is sufficient (avg cycle time 1.17 s). The production default of 3.0 s provides a safety margin for busier networks.

---

### test_exhaustion_and_beyond — Pool Exhaustion Under Load

**What it tests:** A pool of exactly `--mac-count` MACs is provisioned completely, then one additional attempt is made to confirm the exhaustion error.

**MAC range used:** `02:FE:ED:03:00:00` – `02:FE:ED:03:00:<mac_count-1>` (computed at runtime).

**Steps:**
1. Re-initialise DB with a fresh range of exactly `mac_count` MACs
2. Provision `mac_count` devices (unique synthetic serials), all with `--arp-delay=0.0`
3. Verify `remaining == 0` via `get_mac_pool_status`
4. Attempt one more provisioning → must return pool exhausted error

**Assertions:**
- All `mac_count` provisioning calls return `"successful"`
- `pool["remaining"] == 0` after full provisioning
- The (mac_count + 1)th call returns a string containing `"pool exhausted"`

**Results (default `--mac-count=10`):**

| Metric | Value |
|---|---|
| Pool size | 10 MACs |
| Successful provisions | 10/10 |
| Remaining after full run | 0 |
| Beyond-exhaustion result | `"Error: MAC pool exhausted — no addresses available"` |

**Result:** ✅ PASS — pool boundary correctly enforced

---

## Test Results Summary

| Test | File | Status | Notes |
|---|---|---|---|
| `test_1_success` | provisioning | ✅ PASS | Real device, MAC written + verified |
| `test_2_retest_ok` | provisioning | ✅ PASS | Re-test path confirmed |
| `test_3_export_log` | provisioning | ✅ PASS | All 3 filter combinations correct |
| `test_4_duplicate_sn` | provisioning | ✅ PASS | Correct error string |
| `test_5_mac_mismatch` | provisioning | ✅ PASS | Correct error string with both MACs |
| `test_6_unknown_device` | provisioning | ✅ PASS | Correct error string |
| `test_7_pool_exhausted` | provisioning | ✅ PASS | Exhaustion detected correctly |
| `test_readback_stress[0.0]` | stress | ✅ PASS | 20/20 cycles, avg 1.17 s |
| `test_readback_stress[0.5]` | stress | ✅ PASS | 20/20 cycles, avg 1.74 s |
| `test_readback_stress[1.0]` | stress | ✅ PASS | 20/20 cycles, avg 2.17 s |
| `test_readback_stress[2.0]` | stress | ✅ PASS | 20/20 cycles, avg 3.14 s |
| `test_readback_stress[3.0]` | stress | ✅ PASS | 20/20 cycles, avg 4.22 s |
| `test_exhaustion_and_beyond` | stress | ✅ PASS | 10/10 provisions, boundary enforced |

---

## Test Log (2026-05-27)

> **Note:** Integration tests require the physical device `ASubsDV1` to be connected and reachable on the network.  
> Running without the device yields `Error: OCA communication failure — get_mac_address returned nothing` for every test.  
> The stress test CSV logs in `logs/mac_stress/` were captured with the device present.

---

## Test Runs

| Date | Firmware | Device | Result | Notes |
|---|---|---|---|---|
| 2026-06-08 | `1.0.0rc6` | `169.254.27.208:50001` | ✅ 7/7 PASSED (22.06s) | mDNS unavailable after reboot — addressed via IP |
| 2026-05-28 | — | `ASubsDV1` | ✅ 7/7 PASSED (20.45s) | Initial test run |

---

### Integration tests — `pytest -v` output (2026-06-08, device connected)

```
SubProMACAddresses/test_mac_provisioning.py::test_1_success        PASSED  [ 14%]
SubProMACAddresses/test_mac_provisioning.py::test_2_retest_ok      PASSED  [ 28%]
SubProMACAddresses/test_mac_provisioning.py::test_3_export_log     PASSED  [ 42%]
SubProMACAddresses/test_mac_provisioning.py::test_4_duplicate_sn   PASSED  [ 57%]
SubProMACAddresses/test_mac_provisioning.py::test_5_mac_mismatch   PASSED  [ 71%]
SubProMACAddresses/test_mac_provisioning.py::test_6_unknown_device PASSED  [ 85%]
SubProMACAddresses/test_mac_provisioning.py::test_7_pool_exhausted PASSED  [100%]

7 passed in 22.06s
```

> **Note (2026-06-08):** Device was addressed via IP (`169.254.27.208:50001`) rather than mDNS name
> (`ASubsDV1`) because the mDNS registration was lost after a device reboot. All 7 tests passed
> identically — the OCA protocol behaviour is independent of the addressing method.

### Integration tests — `pytest -v` output (2026-05-28, device connected)

```
SubProMACAddresses/test_mac_provisioning.py::test_1_success        PASSED  [ 14%]
SubProMACAddresses/test_mac_provisioning.py::test_2_retest_ok      PASSED  [ 28%]
SubProMACAddresses/test_mac_provisioning.py::test_3_export_log     PASSED  [ 42%]
SubProMACAddresses/test_mac_provisioning.py::test_4_duplicate_sn   PASSED  [ 57%]
SubProMACAddresses/test_mac_provisioning.py::test_5_mac_mismatch   PASSED  [ 71%]
SubProMACAddresses/test_mac_provisioning.py::test_6_unknown_device PASSED  [ 85%]
SubProMACAddresses/test_mac_provisioning.py::test_7_pool_exhausted PASSED  [100%]

7 passed in 20.45s
```

### Stress test — per-cycle output (delay=0.0 s, 20 cycles)

```
  [0.0s] cycle 00: success → retest=retest_ok  (1.12s)
  [0.0s] cycle 01: success → retest=retest_ok  (1.13s)
  [0.0s] cycle 02: success → retest=retest_ok  (1.13s)
  [0.0s] cycle 03: success → retest=retest_ok  (1.14s)
  [0.0s] cycle 04: success → retest=retest_ok  (1.17s)
  ... (20 cycles total)
  ────────────────────────────────────────────────────────────
  delay=0.0s  cycles=20
  success=20  verify_failed=0  oca_errors=0
  retest_ok=20
  time: avg=1.166s  min=1.094s  max=1.453s
  ────────────────────────────────────────────────────────────
```

> Full per-cycle CSV logs: `logs/mac_stress/stress_delay<N>_<timestamp>.csv`
> Full HTML reports: `logs/mac_provisioning_test/report.html`, `logs/mac_stress/report.html`
