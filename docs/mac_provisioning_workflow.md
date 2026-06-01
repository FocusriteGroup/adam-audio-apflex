# Provisioning Workflow – SubPro MAC Address Provisioning

## Overview

The provisioning workflow is triggered once a device has **passed the APx500 EOL test**.
The AP sequence calls `adam_workstation.py provision_mac` with the device's target name, serial number, and factory default MAC.
The command prints `successful` on success or a human-readable error string that the AP sequence can compare against.

---

## Entry Point: `provision_mac` CLI Command

```bash
python adam_workstation.py provision_mac <target> <serial> <default_mac> [--arp-delay SECONDS]
```

| Argument | Description | Example |
|---|---|---|
| `target` | OCA device name (mDNS) or IP address | `ASubsDV1` |
| `serial` | Device serial number, read at test start | `SN-24110023` |
| `default_mac` | Factory default MAC — identifies a never-provisioned device | `02:00:00:00:00:00` |
| `--arp-delay` | Seconds to wait after ARP flush before read-back (default: 3.0 s) | `0.0` |

**stdout contract** (compared by the AP sequence):

| Outcome | Output |
|---|---|
| Success (first test or re-test) | `successful` |
| Any error | Human-readable error string, starts with `Error:` |

---

## High-Level Flow

```
provision_mac called
        │
        ▼
  Read MAC from device (OCA)
        │
        ├─── read fails ──────────────────────────────► OCA Error
        │
        ▼
  current_mac == default_mac?
        │
        ├── YES ──► First-Test Path
        │
        └── NO  ──► Re-Test Path
```

---

## First-Test Path (device has factory default MAC)

A device arrives at the test station with its factory-programmed default MAC.
This is the normal case for a brand-new unit.

```
First-Test Path
        │
        ▼
  SN already in DB (verified)?
        ├── YES ──► DUPLICATE SN error  ──► HALT
        └── NO
                │
                ▼
          Pool empty?
                ├── YES ──► POOL EXHAUSTED error  ──► HALT
                └── NO
                        │
                        ▼
                  reserve_mac()
                  (DB: status = 'reserved', next_mac advances)
                        │
                        ▼
                  Write MAC to device (OCA set_mac_address)
                        │
                        ├── OCA write fails ──► rollback_mac()  ──► OCA Error  ──► HALT
                        └── OK
                                │
                                ▼
                          confirm_mac_written()
                          (DB: status = 'written')
                                │
                                ▼
                          Flush ARP cache
                          Sleep(arp_delay)
                                │
                                ▼
                          Read back MAC (OCA get_mac_address)
                                │
                                ├── read fails ──► rollback_mac()  ──► OCA Error  ──► HALT
                                └── OK
                                        │
                                        ▼
                                  read_back == reserved_mac?
                                        ├── NO ──► rollback_mac()  ──► VERIFY FAILED  ──► HALT
                                        └── YES
                                                │
                                                ▼
                                          confirm_mac_verified()
                                          (DB: status = 'verified')
                                                │
                                                ▼
                                          Print: successful
```

### DB state after a successful first-test

| Step | `provisioning_log.status` | `mac_range.next_mac` |
|---|---|---|
| Before call | _(no entry)_ | `02:FE:ED:00:00:2A` |
| After `reserve_mac` | `reserved` | `02:FE:ED:00:00:2B` |
| After `confirm_mac_written` | `written` | `02:FE:ED:00:00:2B` |
| After `confirm_mac_verified` | `verified` | `02:FE:ED:00:00:2B` |

---

## Re-Test Path (device already has a unique MAC)

A device returns to the test station after having already been provisioned (e.g. a failed functional test, rework, or repeat measurement).
The device already carries its unique MAC — no new MAC is issued.

```
Re-Test Path
        │
        ▼
  SN found in DB (verified)?
        ├── NO  ──► UNKNOWN DEVICE error  ──► HALT
        └── YES
                │
                ▼
          db_mac == current_mac?
                ├── NO  ──► MAC MISMATCH error  ──► HALT
                └── YES
                        │
                        ▼
                  Print: successful
                  (no DB changes — already verified)
```

### When does a device enter the re-test path?

- The device was provisioned in a previous run (status `verified` in DB).
- The device failed a subsequent test step and was sent back for re-testing.
- The MAC is already correctly programmed — the provisioner confirms this without touching the DB.

---

## Error Scenarios

### 1. Duplicate Serial Number

**Trigger:** Device has the factory default MAC, but the serial number already has a `verified` entry in the DB.

**Cause:** Two physical devices share the same serial number (production defect), or the same unit was factory-reset after provisioning.

**Output:**
```
Error: duplicate serial number — SN 'SN-24110023' is already assigned to MAC 02:FE:ED:00:00:2A
```

**DB state:** Unchanged (no reservation made).

---

### 2. Pool Exhausted

**Trigger:** `next_mac` has advanced past `end_mac` — no more addresses in the configured range.

**Output:**
```
Error: MAC pool exhausted — no addresses available
```

**Action required:** Run `set_mac_range` to configure a new or extended range, then re-test the device.

---

### 3. Verify Failed

**Trigger:** The MAC was written to the device, but the read-back returned a different value.

**Output:**
```
Error: MAC write verification failed — wrote 02:FE:ED:00:00:2A, read back 02:FE:ED:00:00:2B
```

**DB state:** Entry set to `rolled_back`. The reserved MAC is **permanently consumed** — it will not be reused.

---

### 4. Unknown Device

**Trigger:** The device has a unique (non-default) MAC, but its serial number has no `verified` entry in the DB.

**Cause:** Device was provisioned on a different system without DB access, or the DB was reset after provisioning.

**Output:**
```
Error: unknown device — SN 'SN-24110023' has no DB record but device reports MAC 02:FE:ED:00:00:2A
```

**Action required:** Manual investigation. If the MAC is correct, the DB entry can be reconstructed manually.

---

### 5. MAC Mismatch

**Trigger:** Re-test path — the device's current MAC differs from the MAC stored in the DB for that serial number.

**Cause:** The device MAC was changed after provisioning (firmware flash, OCA write from another tool), or the device serial was reassigned.

**Output:**
```
Error: MAC mismatch — DB has 02:FE:ED:00:00:2A, device reports 02:FE:ED:00:00:FF
```

**Action required:** Manual investigation. Do not overwrite the DB entry without understanding why the MACs diverged.

---

### 6. OCA Communication Failure

**Trigger:** `get_mac_address` or `set_mac_address` throws an exception or returns no value.

**Output:**
```
Error: OCA communication failure — get_mac_address returned nothing
```

**Cause:** Device not reachable (wrong target name, network issue, device powered off), OCA timeout.

---

## ARP Flush and Read-Back Delay

After writing the new MAC via OCA, the OS ARP cache still maps the device's mDNS hostname to the old MAC.
The provisioner flushes the ARP table and waits `arp_delay` seconds before reading back.

| Platform | ARP flush command |
|---|---|
| Windows | `arp -d *` (requires elevated privileges) |
| Linux / macOS | `ip neigh flush all` |

**Default delay:** 3.0 s (`ARP_FLUSH_DELAY` in `mac_provisioner.py`).

On an isolated test network with a short mDNS re-announcement interval, `--arp-delay 0.0` has been validated to work reliably (stress test: 0 verify failures across all delay values).

---

## Pool Warning

If the remaining MAC count drops to or below `warn_threshold` after a successful provisioning, the workstation logger emits a `WARNING`:

```
MAC pool running low — 18 MACs remaining.
```

The `provision_mac` stdout output is still `successful` — the warning is logged only, not printed.
Check pool status at any time with:

```bash
python adam_workstation.py get_mac_pool_status
```

---

## Complete Example: First-Test (Happy Path)

```bash
python adam_workstation.py provision_mac ASubsDV1 SN-24110023 02:00:00:00:00:00 --arp-delay 1.0
```

**stdout:**
```
successful
```

**Log (INFO level):**
```
[SN-24110023] Current device MAC: 02:00:00:00:00:00
[SN-24110023] Reserved MAC: 02:FE:ED:00:00:2A
[SN-24110023] MAC written: 02:FE:ED:00:00:2A
[SN-24110023] Provisioning SUCCESS — MAC 02:FE:ED:00:00:2A verified.
```

**DB after call:**

| serial | mac | status | reserved_at | written_at | verified_at |
|---|---|---|---|---|---|
| SN-24110023 | 02:FE:ED:00:00:2A | verified | 2026-05-27T14:32:01+00:00 | 2026-05-27T14:32:02+00:00 | 2026-05-27T14:32:06+00:00 |
