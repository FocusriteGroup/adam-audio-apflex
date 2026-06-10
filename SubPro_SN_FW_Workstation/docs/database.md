# Database Structure – Sub-Pro SN/FW Workstation

## Overview

The database is an embedded **SQLite** database stored locally on the workstation.
It is the single source of truth for all provisioning records, configuration, golden-sample registration, and user credentials.

> **File path:** `SubPro_SN_FW_Workstation/Data/subpro_workstation.db`
> The path is relative to the repository root. The file and its parent directory are created automatically on first launch.

---

## Table Overview

| Table | Purpose | Cardinality |
|---|---|---|
| `config` | Key/value store for all application settings | One row per key |
| `golden_samples` | Protection list – product SNs that must never be programmed | 0..n rows per variant |
| `parts_config` | Configurable list of component parts with SN prefixes | One row per part type |
| `units` | Audit log of every complete-unit provisioning session | One row per session |
| `parts_scanned` | Component SNs scanned during each session | One row per part per session |
| `password` | Salted-hash password for access to protected screens | Exactly 1 row |

---

## Table: `config`

Stores all application settings as key/value pairs.

### Schema

```sql
CREATE TABLE config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);
```

### Default keys

| Key | Description | Example value |
|---|---|---|
| `device_name` | mDNS hostname used for all OCA/CLI device calls | `SubPro` |
| `target_fw_version` | The firmware version that must be active before writing SN | `1.0.0rc2` |
| `fw_bin_path` | Path to the firmware `.bin` file (relative to repo root or absolute) | `SubsProFirmware/subpro-firmware-for-updating.bin` |

New keys can be added at any time via `set_config()`. Unknown keys are never deleted automatically.

---

## Table: `golden_samples`

Registers product serial numbers that belong to golden-sample units. These units must never be programmed.

### Schema

```sql
CREATE TABLE golden_samples (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    variant       TEXT    NOT NULL CHECK(variant IN ('A8S','A10S')),
    serial_number TEXT    NOT NULL UNIQUE,
    note          TEXT    NOT NULL DEFAULT '',
    created_at    TEXT    NOT NULL
);
```

### Columns

| Column | Type | Description | Example |
|---|---|---|---|
| `id` | INTEGER | Auto-increment primary key | `1` |
| `variant` | TEXT | Product variant – must be `'A8S'` or `'A10S'` | `A8S` |
| `serial_number` | TEXT | Full 9-character product SN, upper-cased | `CIGS00001` |
| `note` | TEXT | Free-text label (e.g. "Unit 1 – acoustic reference") | `acoustic ref` |
| `created_at` | TEXT | ISO-8601 timestamp of registration | `2026-06-09T09:00:00` |

### Key properties

- Multiple golden samples per variant are supported (at least two per variant are recommended in case one breaks).
- The SN is stored upper-cased and is checked case-insensitively at scan time.
- A golden-sample SN causes an immediate `FAIL` on the workflow screen — it is never written to the device.

---

## Table: `parts_config`

Defines the set of component parts that can be scanned and validated.

### Schema

```sql
CREATE TABLE parts_config (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT    NOT NULL UNIQUE,
    prefix_a8s   TEXT    NOT NULL,
    prefix_a10s  TEXT    NOT NULL,
    required     INTEGER NOT NULL DEFAULT 1
);
```

### Columns

| Column | Type | Description | Example |
|---|---|---|---|
| `id` | INTEGER | Auto-increment primary key | `3` |
| `name` | TEXT | Human-readable part name | `Amp Module` |
| `prefix_a8s` | TEXT | Two-letter SN prefix for A8S units | `AF` |
| `prefix_a10s` | TEXT | Two-letter SN prefix for A10S units | `AG` |
| `required` | INTEGER | `1` = part must be scanned; `0` = optional | `1` |

### Default rows (seeded on first launch)

| Name | Prefix A8S | Prefix A10S | Required |
|---|---|---|---|
| DSP Board | ED | ED | Yes |
| UI Board | DB | DB | Yes |
| AMP+PSU | FD | FD | Yes |
| Amp Module | AF | AG | Yes |
| Woofer Driver | BH | BI | Yes |

Parts with the same prefix for both variants (DSP Board, UI Board, AMP+PSU) accept the same barcode regardless of product variant. Variant-specific parts (Amp Module, Woofer Driver) enforce the correct prefix per variant.

---

## Table: `units`

One row per provisioning session. A row is created as soon as a valid product SN is scanned (result = `INCOMPLETE`) and updated as the session progresses.

### Schema

```sql
CREATE TABLE units (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    product_sn       TEXT    NOT NULL,
    variant          TEXT    NOT NULL,
    fw_version_found TEXT,
    fw_flashed       INTEGER NOT NULL DEFAULT 0,
    fw_version_final TEXT,
    result           TEXT    NOT NULL DEFAULT 'INCOMPLETE',
    timestamp        TEXT    NOT NULL
);
```

### Columns

| Column | Type | Description | Example |
|---|---|---|---|
| `id` | INTEGER | Auto-increment primary key | `42` |
| `product_sn` | TEXT | Scanned product serial number (upper-cased) | `CI6400001` |
| `variant` | TEXT | Product variant resolved from prefix | `A8S` |
| `fw_version_found` | TEXT | Firmware version read from device before any flashing | `1.0.0rc1` |
| `fw_flashed` | INTEGER | `1` if firmware was flashed during this session | `1` |
| `fw_version_final` | TEXT | Firmware version active after the session (may equal `fw_version_found`) | `1.0.0rc2` |
| `result` | TEXT | Final outcome: `INCOMPLETE`, `PASS`, or `FAIL` | `PASS` |
| `timestamp` | TEXT | ISO-8601 timestamp of session creation | `2026-06-09T09:05:00` |

### Result lifecycle

```
create_unit()        → result = 'INCOMPLETE'
update_unit_fw()     → (FW columns filled, result unchanged)
complete_unit(PASS)  → result = 'PASS'   (all required parts scanned)
complete_unit(FAIL)  → result = 'FAIL'   (cancel, GS detected, device error, etc.)
```

If the application crashes mid-session, the row remains `INCOMPLETE`. On next launch the session starts fresh — the `INCOMPLETE` row is preserved in the audit log.

---

## Table: `parts_scanned`

Records each component SN scanned during a session. Multiple rows per unit (one per part).

### Schema

```sql
CREATE TABLE parts_scanned (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id          INTEGER NOT NULL REFERENCES units(id) ON DELETE CASCADE,
    part_name        TEXT    NOT NULL,
    part_sn          TEXT    NOT NULL,
    previous_unit_id INTEGER REFERENCES units(id),
    timestamp        TEXT    NOT NULL
);
```

### Columns

| Column | Type | Description | Example |
|---|---|---|---|
| `id` | INTEGER | Auto-increment primary key | `88` |
| `unit_id` | INTEGER | FK → `units.id` – the unit this part was scanned for | `42` |
| `part_name` | TEXT | Name from `parts_config.name` | `Amp Module` |
| `part_sn` | TEXT | Scanned component SN (upper-cased) | `AF6400005` |
| `previous_unit_id` | INTEGER | If this part was previously on another unit, that unit's `id`; otherwise `NULL` | `39` |
| `timestamp` | TEXT | ISO-8601 scan time | `2026-06-09T09:07:12` |

### Part re-assignment

If a component SN is scanned but was already recorded for a different unit (e.g. a spare part reused after a rework), the scan is still accepted. The `previous_unit_id` column is set to the prior unit's id, creating a full audit trail of the re-assignment.

---

## Table: `password`

Stores a single salted SHA-256 hash protecting access to Settings, Unlock, and other restricted screens.

### Schema

```sql
CREATE TABLE password (
    id   INTEGER PRIMARY KEY CHECK(id = 1),
    hash TEXT    NOT NULL,
    salt TEXT    NOT NULL
);
```

### Columns

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER | Always `1` – enforces singleton |
| `hash` | TEXT | SHA-256 hex digest of `salt + plaintext_password` |
| `salt` | TEXT | 32-byte random hex salt generated on password creation |

### Hash algorithm

```python
salt = os.urandom(32).hex()          # 64-char hex string
hash = sha256((salt + plaintext).encode()).hexdigest()
```

The password is never stored in plaintext. The salt is unique per password change, so two identical passwords produce different hashes.

---

## Foreign Keys and Cascade

```
units  ←──── parts_scanned.unit_id          (ON DELETE CASCADE)
units  ←──── parts_scanned.previous_unit_id (nullable, no cascade)
```

Foreign key enforcement is enabled at connection time with `PRAGMA foreign_keys = ON`.

---

## Indexes

No explicit indexes are created beyond primary keys. Query volume is low (single workstation, one unit at a time) so full-table scans are acceptable.

---

## Backup

The database is a single `.db` file. Back it up by copying `Data/subpro_workstation.db` to a safe location. No special shutdown procedure is required — SQLite flushes atomically on every commit.
