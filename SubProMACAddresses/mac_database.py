"""
MAC address provisioning database for SubPro EOL production.

Schema
------
mac_range:
    id INTEGER PRIMARY KEY CHECK (id = 1)   -- singleton row
    start_mac TEXT NOT NULL                 -- first MAC in range
    end_mac TEXT NOT NULL                   -- last MAC in range (inclusive)
    next_mac TEXT NOT NULL                  -- next MAC to hand out
    warn_threshold INTEGER NOT NULL         -- warn when remaining <= this value

provisioning_log:
    id INTEGER PRIMARY KEY AUTOINCREMENT
    serial TEXT NOT NULL        -- device serial number
    mac TEXT NOT NULL           -- MAC address written to device
    workstation_id TEXT         -- which test station performed the action
    reserved_at TEXT            -- when MAC was reserved
    written_at TEXT             -- when MAC was written to device
    verified_at TEXT            -- when read-back matched (NULL if not yet)
    status TEXT NOT NULL        -- 'reserved' | 'written' | 'verified' | 'rolled_back'

golden_samples:
    serial TEXT PRIMARY KEY     -- SNs that must never receive a MAC
    added_at TEXT NOT NULL
    note TEXT
"""

import logging
import os
import shutil
import sqlite3
import string
import subprocess
import sys
from datetime import datetime, timezone

_DB_DIR = os.path.join(os.path.dirname(__file__), "db")
DB_PATH = os.path.join(_DB_DIR, "mac_addresses.db")

DEFAULT_WARN_THRESHOLD = 20
BACKUP_DIR_ENV_VAR = "MAC_DB_BACKUP_DIR"
AUTO_BACKUP_SUBDIR = "ADAM_MAC_DB_Backups"

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MAC arithmetic helpers
# ---------------------------------------------------------------------------

def _mac_to_int(mac: str) -> int:
    # Strip colons and parse as base-16 integer (range 0 .. 2^48 - 1).
    # Example: "02:AB:CD:00:00:01" → "02ABCD000001" → 738 135 187 457
    return int(mac.replace(":", ""), 16)


def _int_to_mac(val: int) -> str:
    # Format as zero-padded 12-char uppercase hex, then insert colons every 2 chars.
    # Example: 738 135 187 457 → "02ABCD000001" → "02:AB:CD:00:00:01"
    hex_str = f"{val:012X}"
    return ":".join(hex_str[i:i + 2] for i in range(0, 12, 2))


def _normalise_mac(mac: str) -> str:
    return mac.strip().upper()


def _validate_mac(mac: str) -> None:
    parts = mac.split(":")
    if len(parts) != 6:
        raise ValueError(f"Invalid MAC address: {mac!r}")
    for part in parts:
        if len(part) != 2 or not all(c in "0123456789ABCDEFabcdef" for c in part):
            raise ValueError(f"Invalid MAC octet {part!r} in: {mac!r}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_connection() -> sqlite3.Connection:
    os.makedirs(_DB_DIR, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    # DELETE mode: each transaction writes a rollback-journal file, then deletes it on
    # commit. Avoids the -wal / -shm sidecar files that WAL mode leaves on disk,
    # which can confuse network drives and backup tools.
    con.execute("PRAGMA journal_mode=DELETE")
    # If a concurrent connection holds a write lock, SQLite retries internally for up
    # to 5 000 ms before raising OperationalError("database is locked").
    con.execute("PRAGMA busy_timeout=5000")
    con.row_factory = sqlite3.Row
    return con


def _safe_filename_part(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value)


def _iter_windows_removable_drives() -> list:
    """Return drive roots like 'E:\\' for removable volumes on Windows."""
    if sys.platform != "win32":
        return []

    try:
        import ctypes

        drive_mask = ctypes.windll.kernel32.GetLogicalDrives()
        get_drive_type = ctypes.windll.kernel32.GetDriveTypeW
        removable_roots = []
        for letter in string.ascii_uppercase:
            bit = 1 << (ord(letter) - ord("A"))
            if not drive_mask & bit:
                continue
            root = f"{letter}:\\"
            if get_drive_type(root) == 2:
                removable_roots.append(root)
        return removable_roots
    except Exception as exc:  # noqa: BLE001
        logger.warning("Removable drive detection failed: %s", exc)
        return []


def _iter_windows_usb_drives() -> list:
    """Return drive roots for USB-backed disks on Windows.

    This catches external USB hard drives that report as fixed disks.
    """
    if sys.platform != "win32":
        return []

    powershell_script = (
        "$drives = Get-CimInstance Win32_DiskDrive | "
        "Where-Object { $_.InterfaceType -eq 'USB' } | "
        "ForEach-Object { "
        "Get-CimAssociatedInstance -InputObject $_ -ResultClassName Win32_DiskPartition | "
        "ForEach-Object { "
        "Get-CimAssociatedInstance -InputObject $_ -ResultClassName Win32_LogicalDisk | "
        "Select-Object -ExpandProperty DeviceID } }; "
        "$drives | Sort-Object -Unique"
    )

    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", powershell_script],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            if stderr:
                logger.warning("USB drive detection failed: %s", stderr)
            return []

        roots = []
        for line in completed.stdout.splitlines():
            drive = line.strip()
            if len(drive) == 2 and drive[1] == ":":
                roots.append(f"{drive}\\")
        return sorted(set(roots))
    except Exception as exc:  # noqa: BLE001
        logger.warning("USB drive detection failed: %s", exc)
        return []


def _discover_backup_dirs() -> list:
    """Return one or more backup directories.

    Priority:
    1. Explicit MAC_DB_BACKUP_DIR env var.
    2. Auto-detected external drives on Windows, using AUTO_BACKUP_SUBDIR.
    """
    configured_dir = os.getenv(BACKUP_DIR_ENV_VAR)
    if configured_dir:
        return [configured_dir]

    if sys.platform != "win32":
        return []

    drive_roots = set(_iter_windows_removable_drives())
    drive_roots.update(_iter_windows_usb_drives())
    return [os.path.join(root, AUTO_BACKUP_SUBDIR) for root in sorted(drive_roots)]


def _maybe_backup_db(serial: str, mac: str, verified_at: str) -> bool:
    """Copy the SQLite DB to configured or auto-detected external backup targets.

    Backup is best-effort: failures are logged but never abort provisioning.
    """
    backup_dirs = _discover_backup_dirs()
    if not backup_dirs:
        return False

    timestamp_part = _safe_filename_part(verified_at)
    serial_part = _safe_filename_part(serial)
    mac_part = _safe_filename_part(mac)
    backup_created = False

    for backup_dir in backup_dirs:
        try:
            os.makedirs(backup_dir, exist_ok=True)
            latest_path = os.path.join(backup_dir, "mac_addresses_latest.db")
            archive_path = os.path.join(
                backup_dir,
                f"mac_addresses_{timestamp_part}_{serial_part}_{mac_part}.db",
            )

            shutil.copy2(DB_PATH, latest_path)
            shutil.copy2(DB_PATH, archive_path)
            logger.info(
                "MAC DB backup created: latest='%s', archive='%s'",
                latest_path,
                archive_path,
            )
            backup_created = True
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "MAC DB backup skipped; could not copy '%s' to '%s': %s",
                DB_PATH,
                backup_dir,
                exc,
            )

    return backup_created


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create tables if they don't exist."""
    con = _get_connection()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS mac_range (
            id             INTEGER PRIMARY KEY CHECK (id = 1),
            start_mac      TEXT NOT NULL,
            end_mac        TEXT NOT NULL,
            next_mac       TEXT NOT NULL,
            warn_threshold INTEGER NOT NULL DEFAULT 20
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS provisioning_log (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            serial         TEXT NOT NULL,
            mac            TEXT NOT NULL,
            workstation_id TEXT,
            reserved_at    TEXT,
            written_at     TEXT,
            verified_at    TEXT,
            status         TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS golden_samples (
            serial   TEXT PRIMARY KEY,
            added_at TEXT NOT NULL,
            note     TEXT
        )
    """)

    con.commit()
    con.close()


# ---------------------------------------------------------------------------
# Range management
# ---------------------------------------------------------------------------

def set_mac_range(start_mac: str, end_mac: str, warn_threshold: int = DEFAULT_WARN_THRESHOLD) -> None:
    """Define the MAC address range for provisioning.

    MACs are handed out sequentially from start_mac to end_mac.
    A warning is issued when the remaining count drops to warn_threshold.

    Args:
        start_mac:       First MAC in the range, e.g. "02:AB:CD:00:00:00".
        end_mac:         Last MAC in the range (inclusive).
        warn_threshold:  Warn when remaining MACs <= this value.

    Raises:
        ValueError: If MACs are invalid or start > end.
    """
    start_mac = _normalise_mac(start_mac)
    end_mac = _normalise_mac(end_mac)
    _validate_mac(start_mac)
    _validate_mac(end_mac)

    if _mac_to_int(start_mac) > _mac_to_int(end_mac):
        raise ValueError(f"start_mac ({start_mac}) must be <= end_mac ({end_mac})")

    con = _get_connection()
    cur = con.cursor()
    # id=1 is the singleton row — ON CONFLICT turns this into an upsert:
    # insert on first call, update on all subsequent calls.
    cur.execute(
        """INSERT INTO mac_range (id, start_mac, end_mac, next_mac, warn_threshold)
           VALUES (1, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
               start_mac      = excluded.start_mac,      -- new lower boundary
               end_mac        = excluded.end_mac,         -- new upper boundary
               next_mac       = excluded.next_mac,        -- always reset to start_mac
               warn_threshold = excluded.warn_threshold""",  # low-pool alert level
        (start_mac, end_mac, start_mac, warn_threshold)
        # next_mac is always reset to start_mac — not preserved from the previous range.
        # Calling set_mac_range() after provisioning has started reuses addresses from the top.
    )
    con.commit()
    con.close()


def get_mac_range() -> dict:
    """Return the current MAC range configuration, or None if not set."""
    con = _get_connection()
    cur = con.cursor()
    cur.execute("SELECT * FROM mac_range WHERE id = 1")
    row = cur.fetchone()
    con.close()
    return dict(row) if row else None


def get_pool_status() -> dict:
    """Return remaining / assigned / reserved MAC counts.

    Returns:
        {
          "range_set": bool,
          "start_mac": str, "end_mac": str, "next_mac": str,
          "total": int, "assigned": int, "reserved": int,
          "remaining": int,   -- MACs not yet handed out
          "low_pool": bool
        }
    """
    con = _get_connection()
    cur = con.cursor()
    cur.execute("SELECT * FROM mac_range WHERE id = 1")
    row = cur.fetchone()
    if row is None:
        con.close()
        return {"range_set": False}

    end_int = _mac_to_int(row["end_mac"])
    next_int = _mac_to_int(row["next_mac"])
    total = end_int - _mac_to_int(row["start_mac"]) + 1
    remaining = max(0, end_int - next_int + 1)

    cur.execute("SELECT COUNT(*) FROM provisioning_log WHERE status = 'verified'")
    assigned = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM provisioning_log WHERE status IN ('reserved', 'written')")
    reserved = cur.fetchone()[0]
    con.close()

    return {
        "range_set": True,
        "start_mac": row["start_mac"],
        "end_mac": row["end_mac"],
        "next_mac": row["next_mac"],
        "warn_threshold": row["warn_threshold"],
        "total": total,
        "assigned": assigned,
        "reserved": reserved,
        "remaining": remaining,
        "low_pool": remaining <= row["warn_threshold"],
    }


# ---------------------------------------------------------------------------
# Provisioning workflow
# ---------------------------------------------------------------------------

def get_assigned_mac(serial: str):
    """Return the verified MAC for a serial number, or None (for re-test detection).

    Returns:
        MAC address string or None.
    """
    con = _get_connection()
    cur = con.cursor()
    cur.execute(
        # Only 'verified' entries are canonical. 'reserved'/'written' entries that never
        # reached 'verified' are treated as incomplete provisioning attempts and ignored.
        "SELECT mac FROM provisioning_log WHERE serial = ? AND status = 'verified'"
        " ORDER BY id DESC LIMIT 1",  # newest record wins — handles rare manual DB repairs
        (serial,)
    )
    row = cur.fetchone()
    con.close()
    return row["mac"] if row else None


def is_golden_sample(serial: str) -> bool:
    """Return True if the serial is registered as a golden sample."""
    con = _get_connection()
    cur = con.cursor()
    # SELECT 1 is the conventional existence check — fetches no column data.
    cur.execute("SELECT 1 FROM golden_samples WHERE serial = ?", (serial,))
    result = cur.fetchone() is not None  # None → not a golden sample
    con.close()
    return result


def reserve_mac(serial: str, workstation_id: str = None):
    """Take the next MAC from the range and advance the pointer.

    Returns:
        (mac, low_pool) tuple, or (None, False) if the range is exhausted.
        A rolled-back MAC is NOT re-used — the pointer always moves forward.
    """
    con = _get_connection()
    cur = con.cursor()
    cur.execute("SELECT * FROM mac_range WHERE id = 1")
    row = cur.fetchone()
    if row is None:
        con.close()
        return None, False

    next_int = _mac_to_int(row["next_mac"])
    end_int = _mac_to_int(row["end_mac"])

    if next_int > end_int:
        con.close()
        return None, False

    mac = row["next_mac"]     # the MAC address handed out in this call
    ts = _now()               # UTC timestamp written to reserved_at

    # Advance the pool pointer before inserting the log entry. Both updates run
    # inside the same DB transaction, so a crash between them cannot leave the
    # pool in an inconsistent state (SQLite atomicity guarantee).
    new_next = _int_to_mac(next_int + 1)  # one past end_mac when the last MAC is taken
    cur.execute("UPDATE mac_range SET next_mac = ? WHERE id = 1", (new_next,))

    # Insert with status='reserved'. The address is now committed to this serial —
    # it will not be issued to another device even if provisioning later fails.
    cur.execute(
        """INSERT INTO provisioning_log (serial, mac, workstation_id, reserved_at, status)
           VALUES (?, ?, ?, ?, 'reserved')""",
        (serial, mac, workstation_id, ts)
    )

    remaining_after = max(0, end_int - next_int)
    low_pool = remaining_after <= row["warn_threshold"]

    con.commit()
    con.close()
    return mac, low_pool


def confirm_mac_written(serial: str, mac: str, workstation_id: str = None) -> bool:
    """Record that the MAC was successfully written to the device."""
    con = _get_connection()
    cur = con.cursor()
    cur.execute(
        """UPDATE provisioning_log
           SET written_at = ?, status = 'written',
               -- COALESCE keeps the workstation_id from reserve_mac if already set.
               workstation_id = COALESCE(?, workstation_id)
           -- Guard: only advance from 'reserved'. Prevents double-confirm on retry.
           WHERE serial = ? AND mac = ? AND status = 'reserved'""",
        (_now(), workstation_id, serial, mac)
    )
    updated = cur.rowcount > 0  # False → entry was already advanced or rolled back
    con.commit()
    con.close()
    return updated


def confirm_mac_verified(serial: str, mac: str, workstation_id: str = None) -> bool:
    """Finalise provisioning after successful read-back verification."""
    verified_at = _now()
    con = _get_connection()
    cur = con.cursor()
    cur.execute(
        """UPDATE provisioning_log
           SET verified_at = ?, status = 'verified',
               workstation_id = COALESCE(?, workstation_id)
           -- Guard: only advance from 'written'. Prevents double-verify on retry.
           WHERE serial = ? AND mac = ? AND status = 'written'""",
        (verified_at, workstation_id, serial, mac)
    )
    success = cur.rowcount > 0  # False → entry was already verified or rolled back
    con.commit()
    con.close()
    if success:
        _maybe_backup_db(serial=serial, mac=mac, verified_at=verified_at)
    return success


def rollback_mac(serial: str, mac: str, reason: str = None) -> bool:
    """Mark a reserved/written MAC as rolled_back.

    The MAC is NOT returned to the range — it is permanently skipped.
    This wastes one MAC per failure, which is acceptable in production.

    Returns:
        True if a log entry was updated, False otherwise.
    """
    con = _get_connection()
    cur = con.cursor()
    cur.execute(
        """UPDATE provisioning_log
           SET status = 'rolled_back'
           -- Guard: never overwrite a 'verified' entry — it is the canonical record.
           WHERE serial = ? AND mac = ? AND status IN ('reserved', 'written')""",
        (serial, mac)
    )
    updated = cur.rowcount > 0  # False → entry not found or already verified/rolled_back
    con.commit()
    con.close()
    return updated


# ---------------------------------------------------------------------------
# Golden sample management
# ---------------------------------------------------------------------------

def add_golden_sample(serial: str, note: str = None) -> bool:
    """Register a serial number as a golden sample (protected from provisioning).

    Returns:
        True if added, False if already registered.
    """
    con = _get_connection()
    cur = con.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO golden_samples (serial, added_at, note) VALUES (?, ?, ?)",
        (serial, _now(), note)
    )
    added = cur.rowcount > 0
    con.commit()
    con.close()
    return added


# ---------------------------------------------------------------------------
# Audit / reporting
# ---------------------------------------------------------------------------

def get_provisioning_log(serial: str = None) -> list:
    """Return provisioning log entries, optionally filtered by serial number."""
    con = _get_connection()
    cur = con.cursor()
    if serial:
        # Filtered — used by export_mac_log --serial and test helpers.
        cur.execute(
            "SELECT * FROM provisioning_log WHERE serial = ? ORDER BY id",
            (serial,)
        )
    else:
        # Full table dump — default export and pool diagnostics.
        cur.execute("SELECT * FROM provisioning_log ORDER BY id")
    rows = [dict(r) for r in cur.fetchall()]
    con.close()
    return rows
