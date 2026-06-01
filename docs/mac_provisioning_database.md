# Database Structure – SubPro MAC Address Provisioning

## Overview

The database is an embedded **SQLite** database stored locally on the test workstation.
It contains three tables and acts as the single source of truth for the entire MAC provisioning process.

> **File path:** `SubProMACAddresses/db/mac_addresses.db`
> The path is relative to the repository root. The file is created automatically on first use.

---

## Table Overview

| Table | Purpose | Cardinality |
|---|---|---|
| `mac_range` | Configures the allowed MAC address range and maintains a pointer to the next available address. | Exactly 1 row (singleton) |
| `provisioning_log` | Complete audit trail of every provisioning operation – one row per device. | 1 row per serial number |
| `golden_samples` | Protection list: serial numbers that must not be re-provisioned. Devices receive a MAC address first, then are registered here after being designated as golden samples. | 0..n rows |

---

## Table: `mac_range`

Stores exactly **one** configuration row (singleton enforced by `CHECK (id = 1)`).

### Schema

```sql
CREATE TABLE mac_range (
    id             INTEGER PRIMARY KEY CHECK (id = 1),
    start_mac      TEXT NOT NULL,    -- first MAC in the range, e.g. "02:FE:ED:00:00:00"
    end_mac        TEXT NOT NULL,    -- last MAC in the range (inclusive)
    next_mac       TEXT NOT NULL,    -- next MAC to be handed out
    warn_threshold INTEGER NOT NULL  -- warn when remaining MACs <= this value
);
```

### Columns

| Column | Type | Description | Example value |
|---|---|---|---|
| `id` | INTEGER | Always 1 – enforces the singleton constraint. | `1` |
| `start_mac` | TEXT | First MAC address in the configured range. | `02:FE:ED:00:00:00` |
| `end_mac` | TEXT | Last MAC address in the range (inclusive). | `02:FE:ED:0F:FF:FF` |
| `next_mac` | TEXT | Pointer to the next free MAC. Advances by one after every reservation. When it exceeds `end_mac`, the pool is exhausted. | `02:FE:ED:00:00:2B` |
| `warn_threshold` | INTEGER | Pool warning threshold. When remaining MACs drop to or below this value, a warning is logged. | `20` |

### Key property: the pointer only moves forward

> **No recycling.**
> Rolled-back MACs (caused by write or verification failures) are _not_ returned to the pool.
> The `next_mac` pointer moves strictly forward. Every failure permanently consumes one MAC address.

### Calculating available MACs

```
Remaining = max(0, int(end_mac) - int(next_mac) + 1)
Total     = int(end_mac) - int(start_mac) + 1
```

### Example row

| id | start_mac | end_mac | next_mac | warn_threshold |
|---|---|---|---|---|
| 1 | 02:FE:ED:00:00:00 | 02:FE:ED:0F:FF:FF | 02:FE:ED:00:00:2B | 20 |

---

## Table: `provisioning_log`

Complete audit log of every MAC provisioning operation. One row per serial number and MAC assignment.

### Schema

```sql
CREATE TABLE provisioning_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    serial         TEXT NOT NULL,    -- device serial number
    mac            TEXT NOT NULL,    -- assigned MAC address
    workstation_id TEXT,             -- hostname of the test station
    reserved_at    TEXT,             -- ISO-8601 timestamp (UTC)
    written_at     TEXT,             -- ISO-8601 timestamp (UTC)
    verified_at    TEXT,             -- ISO-8601 timestamp (UTC), NULL until confirmed
    status         TEXT NOT NULL     -- 'reserved' | 'written' | 'verified' | 'rolled_back'
);
```

### Columns

| Column | Type | Description | Example value |
|---|---|---|---|
| `id` | INTEGER | Auto-incrementing primary key. | `42` |
| `serial` | TEXT | Device serial number as provided by the AP sequence at test start. | `SN-24110023` |
| `mac` | TEXT | MAC address assigned to this device in `AA:BB:CC:DD:EE:FF` format. | `02:FE:ED:00:00:2A` |
| `workstation_id` | TEXT | Hostname of the executing test station (`socket.gethostname()`). | `WS-EOL-01` |
| `reserved_at` | TEXT | Timestamp when the MAC was reserved for this serial number (UTC, ISO 8601). | `2026-05-27T14:32:01.123456+00:00` |
| `written_at` | TEXT | Timestamp when the OCA write command completed successfully. | `2026-05-27T14:32:02.456789+00:00` |
| `verified_at` | TEXT | Timestamp of successful read-back verification. `NULL` until verified. | `2026-05-27T14:32:06.789012+00:00` |
| `status` | TEXT | Current state of the entry – see status lifecycle below. | `verified` |

### Status values and transitions

```
reserved ──► written ──► verified
    │             │
    └─────────────┴──► rolled_back
```

| Status | Meaning | Next state |
|---|---|---|
| `reserved` | MAC reserved, not yet written to the device. | `written` or `rolled_back` |
| `written` | MAC successfully written via OCA. ARP flush in progress. | `verified` or `rolled_back` |
| `verified` | Read-back verification passed. Provisioning complete. | _(terminal state)_ |
| `rolled_back` | Write or verification failed. MAC permanently consumed. | _(terminal state)_ |

### Example rows

| id | serial | mac | workstation_id | reserved_at | written_at | verified_at | status |
|---|---|---|---|---|---|---|---|
| 41 | SN-24110021 | 02:FE:ED:00:00:28 | WS-EOL-01 | 2026-05-27T14:30:11+00:00 | 2026-05-27T14:30:12+00:00 | 2026-05-27T14:30:16+00:00 | verified |
| 42 | SN-24110022 | 02:FE:ED:00:00:29 | WS-EOL-01 | 2026-05-27T14:31:45+00:00 | 2026-05-27T14:31:46+00:00 | NULL | rolled_back |
| 43 | SN-24110023 | 02:FE:ED:00:00:2A | WS-EOL-01 | 2026-05-27T14:32:01+00:00 | 2026-05-27T14:32:02+00:00 | 2026-05-27T14:32:06+00:00 | verified |

> **Row 42 – rolled_back:**
> MAC `02:FE:ED:00:00:29` was written to device `SN-24110022` but could not be verified on read-back.
> The MAC is permanently lost. The next call reserves `02:FE:ED:00:00:2A`.

---

## Table: `golden_samples`

Protection list for reference and measurement-standard devices. A golden sample **receives a MAC address first** (through the normal provisioning flow), and is registered in this table afterwards. From that point on, the provisioner will reject any attempt to re-provision the same serial number.

### Schema

```sql
CREATE TABLE golden_samples (
    serial   TEXT PRIMARY KEY,
    added_at TEXT NOT NULL,
    note     TEXT
);
```

### Columns

| Column | Type | Description | Example value |
|---|---|---|---|
| `serial` | TEXT | Serial number of the reference device (primary key). | `GS-REF-001` |
| `added_at` | TEXT | ISO-8601 timestamp of registration. | `2026-05-01T08:00:00+00:00` |
| `note` | TEXT | Optional comment (e.g. purpose of the unit). | `Frequency response reference – Lab 3` |

> **Usage in the production line:**
> A device first goes through the normal EOL provisioning flow and receives a MAC address.
> Once it is designated as a golden sample, its serial number is added to this table to prevent accidental re-provisioning.
> Golden samples are currently also identified via the AP project flag `is_golden_sample`.
> The `golden_samples` table is reserved for future extensions (e.g. additional DB-layer validation).

---

## Database File

### Location & creation

```
SubProMACAddresses/
└── db/
    └── mac_addresses.db      ← SQLite file
```

- Created automatically on the first call to `init_mac_db`.
- Can be deleted manually at any time – the next test run will recreate it.
- Should **not** be version-controlled (add to `.gitignore`).

### Technical details

| Parameter | Value | Reason |
|---|---|---|
| Engine | SQLite 3 | No network connection or database server required. |
| Journal mode | DELETE (Rollback Journal) | Simplest and most robust option for single-writer access from the test station. |
| Busy timeout | 5000 ms | Protects against lock contention when an export runs simultaneously with provisioning. |
| Encoding | UTF-8 | SQLite default. |
| Timestamps | ISO 8601 / UTC | `datetime.now(timezone.utc).isoformat()` – unambiguous and sortable. |

---

## CLI Commands for Database Management

| Command | Parameters | Description |
|---|---|---|
| `init_mac_db` | – | Creates the database and all tables (idempotent). |
| `set_mac_range` | `start_mac end_mac [--warn-threshold N]` | Sets the MAC range. Replaces any existing range; resets `next_mac` to `start_mac`. |
| `get_mac_pool_status` | – | Returns remaining, assigned, and reserved MAC counts (JSON). |
| `export_mac_log` | `output_path [--status S] [--serial SN]` | Exports `provisioning_log` as CSV, optionally filtered. |
| `register_golden_sample` | `serial [--note TEXT]` | Registers a serial number in `golden_samples` to prevent re-provisioning. Idempotent – prints `already registered` if the serial is already in the table. |

### Example: setting up a MAC range

```bash
python adam_workstation.py set_mac_range 02:FE:ED:00:00:00 02:FE:ED:0F:FF:FF --warn-threshold 50
```

Creates a range containing **1,048,576 MACs** (16 × 65,536).

### Example: querying pool status

```bash
python adam_workstation.py get_mac_pool_status
```

```json
{
  "range_set": true,
  "start_mac": "02:FE:ED:00:00:00",
  "end_mac":   "02:FE:ED:0F:FF:FF",
  "next_mac":  "02:FE:ED:00:00:2B",
  "warn_threshold": 50,
  "total":     1048576,
  "assigned":  42,
  "reserved":  0,
  "remaining": 1048533,
  "low_pool":  false
}
```

### Example: export with status filter

```bash
python adam_workstation.py export_mac_log export_verified.csv --status verified
```

Produces a CSV containing only devices with a successfully verified MAC:

```
serial,mac,status,reserved_at,written_at,verified_at,workstation_id
SN-24110021,02:FE:ED:00:00:28,verified,2026-05-27T14:30:11+00:00,2026-05-27T14:30:12+00:00,2026-05-27T14:30:16+00:00,WS-EOL-01
SN-24110023,02:FE:ED:00:00:2A,verified,2026-05-27T14:32:01+00:00,2026-05-27T14:32:02+00:00,2026-05-27T14:32:06+00:00,WS-EOL-01
```
