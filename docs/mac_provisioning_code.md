# Code & Implementation – SubPro MAC Address Provisioning

## Overview

The provisioning system is split across four files with clear responsibilities:

| File | Responsibility |
|---|---|
| `SubProMACAddresses/mac_database.py` | SQLite database layer — all reads and writes |
| `SubProMACAddresses/mac_provisioner.py` | Provisioning logic — decision flow, OCA calls |
| `adam_workstation.py` | CLI handler — bridges argparse args to provisioner, formats stdout |
| `cli/workstation_parser.py` | Argument definitions for all CLI commands |

The AP sequence calls `adam_workstation.py` as a subprocess and reads its `stdout`. Only two outputs matter to AP: `"successful"` (pass) and any string starting with `"Error:"` (fail).

---

## `mac_database.py`

Pure data layer. No OCA, no networking. All functions open a fresh SQLite connection, do their work, and close it.

### Connection settings

```python
# DELETE mode: each transaction writes a rollback-journal file, then deletes it on commit.
# This avoids the -wal / -shm sidecar files that WAL mode leaves on disk,
# which can confuse network drives and backup tools in a shared-network setup.
con.execute("PRAGMA journal_mode=DELETE")

# If a concurrent connection holds a write lock, SQLite retries internally for 5 000 ms
# before raising OperationalError("database is locked").
# Relevant when two AP workstations share a DB file over a network share.
con.execute("PRAGMA busy_timeout=5000")
```

`journal_mode=DELETE` is the SQLite default and is explicit here to avoid WAL mode, which can leave `-wal` / `-shm` sidecar files in production.

### MAC arithmetic

MACs are stored as strings (`"02:AB:CD:00:00:01"`) and converted to integers only for arithmetic:

```python
def _mac_to_int(mac: str) -> int:
    # Strip the six colon separators, leaving a 12-digit hex string,
    # then interpret it as a base-16 integer (range 0 .. 2^48 - 1).
    # Example: "02:AB:CD:00:00:01" → "02ABCD000001" → 738 135 187 457
    return int(mac.replace(":", ""), 16)

def _int_to_mac(val: int) -> str:
    # Format the integer as exactly 12 uppercase hex digits (zero-padded to 48 bits).
    hex_str = f"{val:012X}"
    # Split into 6 two-character byte groups and join with colons.
    # Example: 738 135 187 457 → "02ABCD000001" → "02:AB:CD:00:00:01"
    return ":".join(hex_str[i:i+2] for i in range(0, 12, 2))
```

The pointer (`next_mac`) is advanced by 1 on every `reserve_mac()` call, regardless of whether the reservation ultimately succeeds. A rolled-back MAC is permanently skipped — it is never re-issued.

### Key functions

#### `init_db()`
Creates all three tables if they do not exist. Safe to call on every startup.

#### `set_mac_range(start_mac, end_mac, warn_threshold=20)`
Inserts or replaces the singleton row in `mac_range`. Resets `next_mac` to `start_mac`.

```python
# id=1 is the singleton row — there is always exactly one MAC range configured.
# ON CONFLICT turns this into an upsert: insert on first call, update on subsequent calls.
cur.execute(
    """INSERT INTO mac_range (id, start_mac, end_mac, next_mac, warn_threshold)
       VALUES (1, ?, ?, ?, ?)
       ON CONFLICT(id) DO UPDATE SET
           start_mac      = excluded.start_mac,       -- new lower address boundary
           end_mac        = excluded.end_mac,          -- new upper address boundary
           next_mac       = excluded.next_mac,         -- always reset to start_mac
           warn_threshold = excluded.warn_threshold""",  -- low-pool alert level (count)
    (start_mac, end_mac, start_mac, warn_threshold)
    # next_mac is always reset to start_mac, not preserved from the previous range.
    # Calling set_mac_range() after provisioning has started will reuse addresses from the top.
)
```

#### `reserve_mac(serial, workstation_id=None) → (mac, low_pool)`
Atomically takes the next MAC and advances the pointer:

```python
mac = row["next_mac"]     # the MAC address to hand out in this call
ts = _now()               # UTC timestamp, written to reserved_at in the log

# Advance the pool pointer by one position before inserting the log entry.
# Both updates run inside the same DB transaction, so a crash between them
# cannot leave the pool in an inconsistent state (SQLite atomicity guarantee).
new_next = _int_to_mac(next_int + 1)
cur.execute("UPDATE mac_range SET next_mac = ? WHERE id = 1", (new_next,))

# Record the reservation with status='reserved'. The address is now committed
# to this serial number — it will not be issued to any other device,
# even if the provisioning step later fails and the entry is rolled back.
cur.execute(
    """INSERT INTO provisioning_log (serial, mac, workstation_id, reserved_at, status)
       VALUES (?, ?, ?, ?, 'reserved')""",
    (serial, mac, workstation_id, ts)
)
```

Returns `(None, False)` if the range is exhausted.

#### `confirm_mac_written(serial, mac)` / `confirm_mac_verified(serial, mac)`
Transition the `provisioning_log` entry through `reserved → written → verified`:

```python
cur.execute(
    """UPDATE provisioning_log
       SET written_at = ?, status = 'written',
           -- COALESCE keeps the workstation_id recorded at reserve time if it was already set.
           -- Only overwrites if NULL, which shouldn't happen in normal flow.
           workstation_id = COALESCE(?, workstation_id)
       -- Guard: only advance entries that are still in 'reserved' state.
       -- Prevents double-confirm if the step is retried after a partial failure.
       WHERE serial = ? AND mac = ? AND status = 'reserved'""",
    (_now(), workstation_id, serial, mac)
)
# Returns True if rowcount == 1, meaning the expected status transition happened.
# A False return means the entry was already advanced or rolled back — unexpected in normal flow.
```

Both return `True` if exactly one row was updated.

#### `rollback_mac(serial, mac)`
Sets status to `rolled_back` for a `reserved` or `written` entry. The MAC pointer is **not** moved back.

```python
def rollback_mac(serial: str, mac: str, reason: str = None) -> bool:
    con = _get_connection()
    cur = con.cursor()
    cur.execute(
        """UPDATE provisioning_log
           SET status = 'rolled_back'
           -- Guard: only roll back entries that are not yet verified.
           -- A 'verified' entry is the permanent canonical record — never overwrite it.
           WHERE serial = ? AND mac = ? AND status IN ('reserved', 'written')""",
        (serial, mac)
    )
    # rowcount > 0 confirms the entry existed and was in a rollback-eligible state.
    updated = cur.rowcount > 0
    con.commit()
    con.close()
    # The MAC pool pointer is NOT moved back. The address is permanently skipped.
    # Intentional design: re-issuing rolled-back MACs would require complex bookkeeping
    # and risks double-provisioning if a crash occurs mid-rollback.
    return updated
```

#### `get_assigned_mac(serial) → str | None`
Returns the `verified` MAC for a serial number, or `None` if not found. Used by the re-test path.

```python
def get_assigned_mac(serial: str):
    con = _get_connection()
    cur = con.cursor()
    cur.execute(
        # Only 'verified' entries are considered canonical.
        # 'reserved' or 'written' entries that never reached 'verified'
        # are treated as incomplete provisioning attempts and are ignored.
        "SELECT mac FROM provisioning_log WHERE serial = ? AND status = 'verified'"
        " ORDER BY id DESC LIMIT 1",  # newest record wins (handles rare manual DB repairs)
        (serial,)
    )
    row = cur.fetchone()
    con.close()
    return row["mac"] if row else None  # None → SN has never been successfully provisioned
```

#### `is_golden_sample(serial) → bool`
Checks the `golden_samples` table. If `True`, `mac_provisioner` refuses to provision.

```python
def is_golden_sample(serial: str) -> bool:
    con = _get_connection()
    cur = con.cursor()
    # SELECT 1 is the conventional existence check — fetches no column data,
    # just returns a row if the serial is present in the golden_samples table.
    cur.execute("SELECT 1 FROM golden_samples WHERE serial = ?", (serial,))
    # fetchone() returns a sqlite3.Row object if found, or None if not found.
    result = cur.fetchone() is not None
    con.close()
    return result  # True → skip provisioning; this is a reference / golden unit
```

#### `get_pool_status() → dict`
Returns a snapshot of the pool:

```python
{
    "range_set": True,
    "start_mac": "02:FE:ED:00:00:00",
    "end_mac":   "02:FE:ED:FF:FF:FF",
    "next_mac":  "02:FE:ED:00:01:0A",
    "total":     16777216,
    "assigned":  265,
    "reserved":  0,
    "remaining": 16776951,
    "low_pool":  False
}
```

#### `get_provisioning_log(serial=None) → list[dict]`
Returns all rows from `provisioning_log`, optionally filtered by serial number.

```python
def get_provisioning_log(serial: str = None) -> list:
    con = _get_connection()
    cur = con.cursor()
    if serial:
        # Filtered query — used by export_mac_log --serial and test helpers.
        cur.execute(
            "SELECT * FROM provisioning_log WHERE serial = ? ORDER BY id",
            (serial,)
        )
    else:
        # Full table dump — used by the default export and pool diagnostics.
        cur.execute("SELECT * FROM provisioning_log ORDER BY id")
    # Convert sqlite3.Row objects to plain dicts so callers don't need to know
    # the sqlite3.Row API and so that json.dumps() works directly on the result.
    rows = [dict(r) for r in cur.fetchall()]
    con.close()
    return rows
```

---

## `mac_provisioner.py`

Contains the decision logic. Calls `mac_database` functions and OCA device methods. Returns dicts — never prints to stdout.

### Module constant

```python
ARP_FLUSH_DELAY = 3.0  # seconds to wait after flushing ARP cache
```

### Public function

`provision_mac()` ist bewusst kurz — sie liest nur die aktuelle MAC und delegiert dann an einen der beiden internen Pfade:

```python
def provision_mac(
    device,
    serial: str,
    workstation_id: str,
    default_mac: str,
    arp_delay: float = None,
) -> dict:
    # Normalise the default MAC to uppercase colon-separated format
    # ("02:00:00:00:00:00") so string comparisons are reliable regardless
    # of how the AP sequence passes it (lowercase, without colons, etc.).
    default_mac = _normalise_mac(default_mac)

    # First OCA call: read the MAC currently programmed in device firmware.
    # If this fails (device unreachable, OCA timeout), abort immediately —
    # no DB writes have happened yet, so there is nothing to roll back.
    current_mac = _read_mac(device)
    if current_mac is None:
        return {"status": "error", "reason": "oca_error",
                "detail": "get_mac_address returned nothing"}

    # Branching decision:
    # - Factory-fresh device still has the default MAC → first-test path (write a new MAC).
    # - Any other MAC → device was provisioned previously → re-test path (verify it matches DB).
    if current_mac == default_mac:
        return _provision_first_test(device, serial, workstation_id, arp_delay=arp_delay)

    return _provision_retest(serial, current_mac)
```

### First-Test path: `_provision_first_test()`

```python
def _provision_first_test(device, serial, workstation_id, arp_delay=None):
    # GUARD — Duplicate serial check.
    # If this SN already has a verified MAC in the DB, the device should not still have
    # the default MAC. If it does, something went wrong: firmware was reflashed,
    # the wrong SN label was applied, or the device was factory-reset after provisioning.
    # Abort without touching the MAC pool — the operator must investigate.
    db_mac = get_assigned_mac(serial)
    if db_mac is not None:
        logger.error("[%s] DUPLICATE SN — DB already has MAC %s.", serial, db_mac)
        return {
            "status": "error",
            "reason": "duplicate_sn",
            "db_mac": db_mac,
            "detail": f"Serial {serial!r} is already assigned to MAC {db_mac}.",
        }

    # STEP 1 — Reserve the next available MAC from the pool.
    # The pool pointer is advanced atomically inside the same DB transaction as
    # the log insert, so the address is claimed before it is written to the device.
    # Returns (None, False) if the range is exhausted.
    mac, low_pool = reserve_mac(serial, workstation_id)
    if mac is None:
        logger.error("[%s] MAC range exhausted.", serial)
        return {"status": "error", "reason": "pool_exhausted", "detail": "MAC range is exhausted."}

    # STEP 2 — Write the MAC to the device via OCA set_mac_address.
    # On failure, roll back the DB entry to mark the address as permanently skipped.
    # The MAC is consumed and will not be re-issued, to avoid double-provisioning risk.
    if not _write_mac(device, mac):              # OCA: set_mac_address
        rollback_mac(serial, mac, reason="OCA write failed")
        return {
            "status": "error",
            "reason": "oca_error",
            "detail": "set_mac_address call failed; MAC rolled back.",
        }

    # STEP 3 — Record that the write command was sent successfully.
    # Status transition: reserved → written.
    confirm_mac_written(serial, mac, workstation_id)

    # STEP 4 — Flush ARP cache and wait.
    # After writing a new MAC, the device re-joins the network under its new identity.
    # Other hosts may still cache the old IP→MAC mapping in their ARP table.
    # Flushing forces a fresh ARP lookup; the sleep gives the device time to
    # re-announce itself before the verification OCA call.
    delay = arp_delay if arp_delay is not None else ARP_FLUSH_DELAY
    _flush_arp_cache()
    time.sleep(delay)

    # STEP 5 — Read back the MAC from the device to confirm the write was persisted.
    # This is the end-to-end check: the firmware must have stored the new MAC in NVM.
    read_back = _read_mac(device)                # OCA: get_mac_address (verify)
    if read_back is None:
        rollback_mac(serial, mac, reason="OCA read-back failed after write")
        return {
            "status": "error",
            "reason": "oca_error",
            "detail": "get_mac_address returned nothing after write; MAC rolled back.",
        }

    # STEP 6 — Compare read-back against what we wrote.
    # A mismatch indicates a firmware bug or a corrupt / partial OCA write.
    if read_back != mac:
        rollback_mac(serial, mac, reason=f"verify failed: read back {read_back!r}")
        return {
            "status": "error",
            "reason": "verify_failed",
            "written": mac,
            "read_back": read_back,
            "detail": "Device MAC after write does not match expected value; MAC rolled back.",
        }

    # STEP 7 — Finalise. Status transition: written → verified.
    # The MAC is now permanently associated with this serial number in the DB.
    confirm_mac_verified(serial, mac, workstation_id)
    pool = get_pool_status()
    return {
        "status": "success",
        "mac": mac,
        "low_pool": low_pool,           # True if remaining MACs < warn_threshold
        "remaining": pool.get("remaining", 0),
    }
```

### Re-Test path: `_provision_retest()`

```python
def _provision_retest(serial: str, current_mac: str) -> dict:
    # Look up the verified MAC recorded for this serial number.
    # None means the device has a non-default MAC but was never successfully
    # provisioned in our system — this should not occur in normal production flow.
    db_mac = get_assigned_mac(serial)

    if db_mac is None:
        logger.error("[%s] UNKNOWN DEVICE — has MAC %s but SN not in DB.", serial, current_mac)
        return {
            "status": "error",
            "reason": "unknown_device",
            "current_mac": current_mac,
            "detail": f"Device has MAC {current_mac!r} but serial {serial!r} has no DB record.",
        }

    # MAC mismatch: the device's current MAC differs from what our DB says it should be.
    # Possible causes: hardware swap, provisioning error on a different line, DB corruption.
    # Do not attempt automatic re-provisioning — flag for manual investigation.
    if current_mac != db_mac:
        logger.error("[%s] MAC MISMATCH — DB has %s, device reports %s.", serial, db_mac, current_mac)
        return {
            "status": "error",
            "reason": "mac_mismatch",
            "db_mac": db_mac,
            "device_mac": current_mac,
            "detail": "Device MAC differs from DB record. Manual investigation required.",
        }

    # Happy path: device MAC matches the DB record exactly.
    # No DB write is needed — the device is already correctly provisioned.
    logger.info("[%s] Re-test OK — MAC %s matches DB record.", serial, db_mac)
    return {"status": "retest_ok", "mac": db_mac}
```

Alle internen Pfade geben ein Dict zurück:

| `status` | `reason` | Meaning |
|---|---|---|
| `"success"` | — | First-test: MAC written and verified |
| `"retest_ok"` | — | Re-test: device MAC matches DB |
| `"error"` | `"duplicate_sn"` | SN in DB but device has Default MAC |
| `"error"` | `"pool_exhausted"` | No MACs left in range |
| `"error"` | `"verify_failed"` | Read-back after write did not match |
| `"error"` | `"unknown_device"` | Unique MAC on device, SN not in DB |
| `"error"` | `"mac_mismatch"` | Re-test: device MAC ≠ DB record |
| `"error"` | `"oca_error"` | OCA call failed |

### Decision flow

```
provision_mac()
│
├─ _read_mac(device)
│     └─ None?  →  error: oca_error
│
├─ current_mac == default_mac?
│     YES  →  _provision_first_test()
│     NO   →  _provision_retest()
│
_provision_first_test()
│
├─ get_assigned_mac(serial) is not None?  →  error: duplicate_sn
├─ reserve_mac()  →  None?               →  error: pool_exhausted
├─ _write_mac(device, mac)  →  False?    →  rollback → error: oca_error
├─ confirm_mac_written()
├─ _flush_arp_cache() + sleep(arp_delay)
├─ _read_mac(device)  →  None?           →  rollback → error: oca_error
├─ read_back != mac?                     →  rollback → error: verify_failed
└─ confirm_mac_verified()               →  success
│
_provision_retest()
│
├─ get_assigned_mac(serial)  →  None?    →  error: unknown_device
├─ current_mac != db_mac?               →  error: mac_mismatch
└─ match                                →  retest_ok
```

### ARP flush

```python
def _flush_arp_cache() -> None:
    if sys.platform == "win32":
        # Delete all ARP table entries. Requires the process to run as Administrator.
        # If not elevated, arp -d * exits with a non-zero code — intentionally ignored
        # via check=False so the provisioning flow is not aborted by a permission error.
        subprocess.run(["arp", "-d", "*"], check=False, capture_output=True)
    else:
        # Flush the neighbour (ARP/NDP) table for all interfaces on Linux.
        # Requires CAP_NET_ADMIN (root or sudo).
        subprocess.run(["ip", "neigh", "flush", "all"], check=False, capture_output=True)
    # check=False on both platforms: the ARP flush is best-effort.
    # The sleep(arp_delay) that follows is the real safeguard — it gives the device
    # time to re-announce itself even if the flush command was a no-op.
```

Requires elevated privileges on Windows. The `check=False` ensures a permission error does not abort provisioning — the sleep still happens, which is usually enough.

---

## `adam_workstation.py` — MAC provisioning methods

The workstation class contains one method per CLI command. Each method receives parsed `args`, calls the appropriate database or provisioner function, and writes to `stdout`.

### `provision_mac(args)`

The main production command. Connects to the OCA device, calls the provisioner, and translates the result dict into a single `stdout` line for AP:

```python
def provision_mac(self, args):
    # Open a TCP connection to the OCA device (e.g. "ASubsDV1").
    # Fails fast if the device is unreachable — raises before any DB write happens.
    device = self._get_oca_device(args)   # OCADevice(target, port, workstation_id)
    result = mac_provisioner.provision_mac(
        device=device,
        serial=args.serial,
        workstation_id=self.workstation_id,   # hostname — written to DB for audit trail
        default_mac=args.default_mac,         # factory-default MAC, configured in AP sequence
        arp_delay=args.arp_delay,             # None → uses ARP_FLUSH_DELAY constant (3.0 s)
    )
    # Log the full result dict for post-run diagnostics. AP does not read this output.
    WORKSTATION_LOGGER.info("provision_mac [%s]: %s", args.serial, result)
    # Warn the operator log if the pool is running low (remaining < warn_threshold).
    # AP does not see this warning — it is purely for the operator log file.
    if result.get("low_pool"):
        WORKSTATION_LOGGER.warning(
            "MAC pool running low — %s MACs remaining.", result.get("remaining")
        )
    status = result.get("status")
    if status in ("success", "retest_ok"):
        # AP reads "successful" as PASS — this is the only stdout line it checks.
        print("successful")
    else:
        # Map the machine-readable reason code to a human-readable Error: string.
        # AP treats any stdout string starting with "Error:" as FAIL and stops the sequence.
        reason = result.get("reason", "error")
        if reason == "duplicate_sn":
            msg = (
                f"Error: duplicate serial number — "
                f"SN {args.serial!r} is already assigned to MAC {result.get('db_mac', '?')}"
            )
        elif reason == "pool_exhausted":
            msg = "Error: MAC pool exhausted — no addresses available"
        elif reason == "verify_failed":
            msg = (
                f"Error: MAC write verification failed — "
                f"wrote {result.get('written', '?')}, read back {result.get('read_back', '?')}"
            )
        elif reason == "unknown_device":
            msg = (
                f"Error: unknown device — "
                f"SN {args.serial!r} has no DB record but device reports MAC {result.get('current_mac', '?')}"
            )
        elif reason == "mac_mismatch":
            msg = (
                f"Error: MAC mismatch — "
                f"DB has {result.get('db_mac', '?')}, device reports {result.get('device_mac', '?')}"
            )
        elif reason == "oca_error":
            msg = f"Error: OCA communication failure — {result.get('detail', 'no detail')}"
        else:
            msg = f"Error: {reason}"
        print(msg)
```

stdout contract (the only thing AP reads):
- `"successful"` — pass
- `"Error: ..."` — fail

### `init_mac_db(args)`

```python
mac_database.init_db()
print(json.dumps({"status": "ok", "detail": "MAC database initialized."}))
```

### `set_mac_range(args)`

```python
def set_mac_range(self, args):
    # Delegate entirely to the database layer — no OCA or provisioner involvement.
    mac_database.set_mac_range(
        start_mac=args.start_mac,
        end_mac=args.end_mac,
        warn_threshold=args.warn_threshold,  # default: 20, configured in argparse
    )
    # Log the change so it is visible alongside subsequent provision_mac calls
    # in the operator log file.
    WORKSTATION_LOGGER.info(
        "MAC range set: %s – %s (warn_threshold=%d)",
        args.start_mac, args.end_mac, args.warn_threshold,
    )
    # Return the new range configuration as JSON.
    # AP does not read this output — it is used by post-setup verification scripts.
    print(json.dumps({
        "status": "ok",
        "start_mac": args.start_mac,
        "end_mac": args.end_mac,
        "warn_threshold": args.warn_threshold,
    }))
```

### `get_mac_pool_status(args)`

```python
status = mac_database.get_pool_status()
print(json.dumps(status))
```

### `export_mac_log(args)`

```python
def export_mac_log(self, args):
    # getattr guards against a missing attribute if --serial was not passed by the caller.
    # The `or None` converts an empty string (argparse default) to None.
    serial_filter = getattr(args, "serial", None) or None
    rows = mac_database.get_provisioning_log(serial=serial_filter)

    # Optional status filter applied in Python rather than SQL for simplicity.
    # Typical use: --status verified → export only successfully provisioned devices.
    if args.status:
        rows = [r for r in rows if r["status"] == args.status]

    # Column order mirrors the provisioning lifecycle timeline (reserve → write → verify).
    fieldnames = ["serial", "mac", "status", "reserved_at", "written_at", "verified_at", "workstation_id"]
    with open(args.output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        # extrasaction="ignore" silently drops any extra keys returned by the DB
        # (e.g. if a future schema migration adds columns). Keeps the CSV schema stable.
        writer.writerows(rows)
    WORKSTATION_LOGGER.info("export_mac_log: %d entries written to %s", len(rows), args.output_path)
    # JSON summary lets a calling script verify the export count and confirm the output path.
    print(json.dumps({"status": "ok", "exported": len(rows), "path": args.output_path}))
```

Optional filters: `--status` (one of `reserved / written / verified / rolled_back`) and `--serial`.

### `register_golden_sample(args)`

```python
def register_golden_sample(self, args):
    # Idempotent guard: calling this command twice with the same SN is safe.
    # AP sequences often run setup steps on every startup — this prevents duplicate rows.
    if mac_database.is_golden_sample(args.serial):
        print(f"already registered: {args.serial}")
        return
    # Add to the golden_samples table. The optional --note argument
    # (e.g. "reference unit #3, rack slot 2") is stored for inventory reference.
    mac_database.add_golden_sample(serial=args.serial, note=args.note)
    print(f"registered: {args.serial}")
```

stdout: `"registered: <serial>"` or `"already registered: <serial>"`

---

## `cli/workstation_parser.py` — MAC provisioning arguments

All MAC provisioning commands are registered in the `build_workstation_parser()` function under the `# MAC provisioning` section.

### `provision_mac`

```
python adam_workstation.py provision_mac <target> <serial> <default_mac> [port] [--arp-delay N]
```

| Argument | Type | Description |
|---|---|---|
| `target` | str | OCA device name or IP (e.g. `ASubsDV1`) |
| `serial` | str | Device serial number |
| `default_mac` | str | Factory default MAC (e.g. `02:00:00:00:00:00`) |
| `port` | int (optional) | OCA port (resolved automatically if omitted) |
| `--arp-delay` | float | Override ARP flush delay in seconds (default: 3.0) |

### `init_mac_db`

No arguments. Run once during workstation setup.

### `set_mac_range`

```
python adam_workstation.py set_mac_range <start_mac> <end_mac> [--warn-threshold N]
```

### `get_mac_pool_status`

No arguments. Prints JSON to stdout.

### `export_mac_log`

```
python adam_workstation.py export_mac_log <output_path> [--status STATUS] [--serial SERIAL]
```

### `register_golden_sample`

```
python adam_workstation.py register_golden_sample <serial> [--note "text"]
```

---

## Error handling philosophy

- **OCA errors** are treated as transient. The provisioner rolls back any reserved MAC and returns an error dict. The AP sequence shows the error and stops the test.
- **Rolled-back MACs** are permanently skipped (wasted). This is intentional — it avoids complex re-use logic and the risk of double-issuing a MAC.
- **Database errors** (e.g. disk full, corrupted DB) are not caught explicitly. They propagate as exceptions and will appear as unhandled errors in the AP sequence log.
- **Elevated privileges** for ARP flush: failure is logged as a warning, not an error. The ARP flush is best-effort.
