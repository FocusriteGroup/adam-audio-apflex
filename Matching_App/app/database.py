import json
import os
import sqlite3
from datetime import datetime

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Data")
_DB_DIR = os.path.join(_DATA_DIR, "db")
DB_PATH = os.path.join(_DB_DIR, "matcher.db")
_SETTINGS_PATH = os.path.join(_DB_DIR, "settings.json")

_DEFAULT_SETTINGS = {
    "rmse_threshold": 1.0,
    "freq_min": 200,
    "freq_max": 8000,
    "pin": "1234",
    "max_module_age_days": 14,
}


def load_settings():
    """Load settings from JSON file, returning defaults for missing keys."""
    settings = dict(_DEFAULT_SETTINGS)
    if os.path.isfile(_SETTINGS_PATH):
        with open(_SETTINGS_PATH, "r") as f:
            stored = json.load(f)
        settings.update(stored)
    return settings


def save_settings(settings):
    """Persist settings dict to JSON file."""
    os.makedirs(_DB_DIR, exist_ok=True)
    with open(_SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)


def _get_connection():
    os.makedirs(_DB_DIR, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA journal_mode=WAL")
    return con


def init_db():
    """Create tables if they don't exist."""
    con = _get_connection()
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS frequency_vector (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            frequencies TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS drivers (
            serial      TEXT PRIMARY KEY,
            side        TEXT NOT NULL,
            levels      TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'unmatched',
            partner     TEXT,
            loaded_at   TEXT NOT NULL,
            matched_at  TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS system_builds (
            system_serial TEXT PRIMARY KEY,
            module_1      TEXT NOT NULL,
            module_2      TEXT NOT NULL,
            built_at      TEXT NOT NULL
        )
    """)
    con.commit()
    con.close()


def load_json_into_db(json_path):
    """Parse a measurement JSON file and insert new drivers into the database.

    Drivers whose serial number already exists are skipped.
    Returns the number of newly inserted drivers.
    """
    with open(json_path, "r") as f:
        data = json.load(f)

    con = _get_connection()
    cur = con.cursor()

    # Store frequency vector (only once, first time)
    if data.get("frequency_vector"):
        cur.execute("SELECT id FROM frequency_vector WHERE id = 1")
        if cur.fetchone() is None:
            cur.execute(
                "INSERT INTO frequency_vector (id, frequencies) VALUES (1, ?)",
                (json.dumps(data["frequency_vector"]),),
            )

    now = datetime.now().isoformat()
    inserted = 0

    for key, m in data.get("measurements", {}).items():
        serial = m.get("serial_number") or m.get("device_serial")
        if not serial:
            continue

        # Only accept IA (left) and IB (right) prefixes
        if serial.startswith("IA"):
            side = "left"
        elif serial.startswith("IB"):
            side = "right"
        else:
            continue

        # Skip if this serial already exists
        cur.execute("SELECT serial FROM drivers WHERE serial = ?", (serial,))
        if cur.fetchone() is not None:
            continue

        levels = m["channels"]["Ch1"]["levels"]
        cur.execute(
            "INSERT INTO drivers (serial, side, levels, status, loaded_at) VALUES (?, ?, ?, 'unmatched', ?)",
            (serial, side, json.dumps(levels), now),
        )
        inserted += 1

    con.commit()
    con.close()
    return inserted


def get_pool_counts():
    """Return (unmatched, matched, paired) counts."""
    con = _get_connection()
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM drivers WHERE status = 'unmatched'")
    unmatched = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM drivers WHERE status = 'matched'")
    matched = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM drivers WHERE status = 'paired'")
    paired = cur.fetchone()[0]
    con.close()
    return unmatched, matched, paired


def get_status_count(status):
    """Return count of drivers in the requested status."""
    con = _get_connection()
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM drivers WHERE status = ?", (status,))
    count = cur.fetchone()[0]
    con.close()
    return count


def get_data_signature():
    """Return a small signature used to detect new/updated measurement rows."""
    con = _get_connection()
    cur = con.cursor()
    cur.execute("SELECT COUNT(*), COALESCE(MAX(loaded_at), '') FROM drivers")
    count, max_loaded_at = cur.fetchone()
    con.close()
    return count, max_loaded_at


def get_unmatched_drivers():
    """Return (left_drivers, right_drivers) as lists of (serial, levels_json) tuples."""
    con = _get_connection()
    cur = con.cursor()
    cur.execute(
        "SELECT serial, levels FROM drivers WHERE status = 'unmatched' AND side = 'left'"
    )
    left = cur.fetchall()
    cur.execute(
        "SELECT serial, levels FROM drivers WHERE status = 'unmatched' AND side = 'right'"
    )
    right = cur.fetchall()
    con.close()
    return left, right


def get_frequency_vector():
    """Return the stored frequency vector as a list of floats, or None."""
    con = _get_connection()
    cur = con.cursor()
    cur.execute("SELECT frequencies FROM frequency_vector WHERE id = 1")
    row = cur.fetchone()
    con.close()
    if row is None:
        return None
    return json.loads(row[0])


def get_pool_serials():
    """Return (left_serials, right_serials) lists of unmatched driver serial numbers."""
    con = _get_connection()
    cur = con.cursor()
    cur.execute(
        "SELECT serial FROM drivers WHERE status = 'unmatched' AND side = 'left' ORDER BY serial"
    )
    left = [row[0] for row in cur.fetchall()]
    cur.execute(
        "SELECT serial FROM drivers WHERE status = 'unmatched' AND side = 'right' ORDER BY serial"
    )
    right = [row[0] for row in cur.fetchall()]
    con.close()
    return left, right


def get_status_serials(status):
    """Return sorted serial list for a given status."""
    con = _get_connection()
    cur = con.cursor()
    if status != "matched":
        cur.execute(
            "SELECT serial FROM drivers WHERE status = ? ORDER BY side, serial",
            (status,),
        )
        rows = [row[0] for row in cur.fetchall()]
        con.close()
        return rows

    # For matched status, return serials in pair-adjacent order: left, right.
    cur.execute(
        "SELECT serial, partner, side FROM drivers WHERE status = 'matched'"
    )
    matched_rows = cur.fetchall()
    con.close()

    by_serial = {serial: (partner, side) for serial, partner, side in matched_rows}
    ordered = []
    seen = set()

    # Start from left side to create stable pair ordering.
    left_serials = sorted(
        [serial for serial, (_partner, side) in by_serial.items() if side == "left"]
    )
    for left in left_serials:
        if left in seen:
            continue
        partner, _ = by_serial[left]
        ordered.append(left)
        seen.add(left)
        if partner in by_serial and partner not in seen:
            ordered.append(partner)
            seen.add(partner)

    # Append any remaining rows (defensive for inconsistent data).
    for serial in sorted(by_serial.keys()):
        if serial not in seen:
            ordered.append(serial)
            seen.add(serial)

    return ordered


def get_matched_pairs():
    """Return matched pairs as list of (left_serial, right_serial)."""
    con = _get_connection()
    cur = con.cursor()
    cur.execute(
        """
        SELECT serial, partner FROM drivers
        WHERE status = 'matched' AND side = 'left'
        ORDER BY serial
        """
    )
    rows = cur.fetchall()
    con.close()
    return [(left, right) for left, right in rows if right]


def get_all_drivers(include_levels=False):
    """Return all driver rows as dicts for reporting/export."""
    con = _get_connection()
    cur = con.cursor()
    if include_levels:
        cur.execute(
            """
            SELECT serial, side, status, partner, loaded_at, matched_at, levels
            FROM drivers
            ORDER BY status, side, serial
            """
        )
    else:
        cur.execute(
            """
            SELECT serial, side, status, partner, loaded_at, matched_at
            FROM drivers
            ORDER BY status, side, serial
            """
        )
    rows = cur.fetchall()
    con.close()
    if include_levels:
        return [
            {
                "serial": r[0],
                "side": r[1],
                "status": r[2],
                "partner": r[3],
                "loaded_at": r[4],
                "matched_at": r[5],
                "levels": json.loads(r[6]) if r[6] else [],
            }
            for r in rows
        ]
    return [
        {
            "serial": r[0],
            "side": r[1],
            "status": r[2],
            "partner": r[3],
            "loaded_at": r[4],
            "matched_at": r[5],
        }
        for r in rows
    ]


def store_pairs(pairs):
    """Store matched pairs in the database.

    Args:
        pairs: list of (left_serial, right_serial, rmse) tuples.
    """
    con = _get_connection()
    cur = con.cursor()
    now = datetime.now().isoformat()
    for left_serial, right_serial, rmse in pairs:
        cur.execute(
            "UPDATE drivers SET status='matched', partner=?, matched_at=? WHERE serial=?",
            (right_serial, now, left_serial),
        )
        cur.execute(
            "UPDATE drivers SET status='matched', partner=?, matched_at=? WHERE serial=?",
            (left_serial, now, right_serial),
        )
    con.commit()
    con.close()


def lookup_driver(serial):
    """Look up a driver by serial number.

    Returns a dict with keys (serial, side, status, partner) or None.
    """
    con = _get_connection()
    cur = con.cursor()
    cur.execute(
        "SELECT serial, side, status, partner FROM drivers WHERE serial = ?",
        (serial,),
    )
    row = cur.fetchone()
    con.close()
    if row is None:
        return None
    return {"serial": row[0], "side": row[1], "status": row[2], "partner": row[3]}


def confirm_pair(serial_a, serial_b):
    """Mark two matched drivers as paired.

    Returns True if successful, False if they aren't valid matched partners.
    """
    con = _get_connection()
    cur = con.cursor()
    cur.execute(
        "SELECT partner, status FROM drivers WHERE serial = ?", (serial_a,)
    )
    row = cur.fetchone()
    if row is None or row[0] != serial_b or row[1] != 'matched':
        con.close()
        return False
    now = datetime.now().isoformat()
    cur.execute(
        "UPDATE drivers SET status='paired', matched_at=? WHERE serial IN (?, ?)",
        (now, serial_a, serial_b),
    )
    con.commit()
    con.close()
    return True


def reset_matched_drivers():
    """Reset all 'matched' drivers back to 'unmatched'.

    Only affects matched drivers — paired drivers are left untouched.
    Returns the number of drivers reset.
    """
    con = _get_connection()
    cur = con.cursor()
    cur.execute(
        "UPDATE drivers SET status='unmatched', partner=NULL, matched_at=NULL "
        "WHERE status='matched'"
    )
    count = cur.rowcount
    con.commit()
    con.close()
    return count


def get_paired_list():
    """Return list of (left_serial, right_serial, matched_at) for all paired drivers."""
    con = _get_connection()
    cur = con.cursor()
    cur.execute(
        "SELECT serial, partner, matched_at FROM drivers "
        "WHERE status = 'paired' AND side = 'left' ORDER BY matched_at DESC"
    )
    rows = cur.fetchall()
    con.close()
    return [(r[0], r[1], r[2]) for r in rows]


def find_paired_by_serial(serial):
    """Return (left_serial, right_serial) if serial is in a paired set, else None."""
    con = _get_connection()
    cur = con.cursor()
    cur.execute(
        "SELECT serial, partner, side FROM drivers WHERE serial = ? AND status = 'paired'",
        (serial,),
    )
    row = cur.fetchone()
    con.close()
    if row is None:
        return None
    s, partner, side = row
    if not partner:
        return None
    if side == "left":
        return s, partner
    return partner, s


def unpair(left_serial, right_serial):
    """Reset a paired pair back to unmatched.

    Returns True if successful.
    """
    con = _get_connection()
    cur = con.cursor()
    cur.execute(
        "UPDATE drivers SET status='unmatched', partner=NULL, matched_at=NULL "
        "WHERE serial IN (?, ?) AND status='paired'",
        (left_serial, right_serial),
    )
    count = cur.rowcount
    con.commit()
    con.close()
    return count > 0


def unpair_by_serial(serial):
    """Unpair by one serial; returns (ok, left_serial, right_serial)."""
    pair = find_paired_by_serial(serial)
    if not pair:
        return False, None, None
    left_serial, right_serial = pair
    ok = unpair(left_serial, right_serial)
    return ok, left_serial, right_serial


def delete_driver(serial):
    """Delete a driver from the database.

    If the driver has a matched partner, that partner is reset to unmatched.
    Returns True if the driver was deleted.
    """
    con = _get_connection()
    cur = con.cursor()
    # Check if driver has a partner that needs resetting
    cur.execute("SELECT partner, status FROM drivers WHERE serial = ?", (serial,))
    row = cur.fetchone()
    if row is None:
        con.close()
        return False
    partner, status = row
    if partner and status == 'matched':
        cur.execute(
            "UPDATE drivers SET status='unmatched', partner=NULL, matched_at=NULL "
            "WHERE serial = ?",
            (partner,),
        )
    cur.execute("DELETE FROM drivers WHERE serial = ?", (serial,))
    con.commit()
    con.close()
    return True


def restore_from_quarantine(serial):
    """Move a quarantined driver back to pool (unmatched status).
    
    Returns True if the driver was restored.
    """
    con = _get_connection()
    cur = con.cursor()
    cur.execute("SELECT status FROM drivers WHERE serial = ?", (serial,))
    row = cur.fetchone()
    if row is None or row[0] != 'quarantined':
        con.close()
        return False
    cur.execute(
        "UPDATE drivers SET status='unmatched', partner=NULL, matched_at=NULL "
        "WHERE serial = ?",
        (serial,),
    )
    con.commit()
    con.close()
    return True


def quarantine_old_modules(max_age_days):
    """Move old pool modules (unmatched/matched) to quarantined; returns count."""
    try:
        days = int(max_age_days)
    except (TypeError, ValueError):
        days = 0
    if days <= 0:
        return 0

    con = _get_connection()
    cur = con.cursor()
    cur.execute(
        """
        SELECT serial, partner, status FROM drivers
        WHERE status IN ('unmatched', 'matched')
          AND loaded_at <= datetime('now', '-' || ? || ' days')
        """,
        (str(days),),
    )
    rows = cur.fetchall()
    if not rows:
        con.close()
        return 0

    serials_to_quarantine = {r[0] for r in rows}
    affected_partners = set()
    for serial, partner, status in rows:
        if status == 'matched' and partner and partner not in serials_to_quarantine:
            affected_partners.add(partner)

    if affected_partners:
        cur.executemany(
            "UPDATE drivers SET status='unmatched', partner=NULL, matched_at=NULL WHERE serial = ?",
            [(s,) for s in affected_partners],
        )

    cur.executemany(
        "UPDATE drivers SET status='quarantined', partner=NULL, matched_at=NULL WHERE serial = ?",
        [(s,) for s in serials_to_quarantine],
    )
    count = len(serials_to_quarantine)
    con.commit()
    con.close()
    return count


def verify_and_link_system(system_sn, sn1, sn2, db_path=None):
    """Verify two modules are a valid matched/paired pair and link them to a system.

    Returns (success: bool, reason: str).

    Pass/Fail conditions:
    - FAIL if either serial does not exist.
    - FAIL if either module is not in 'matched' or 'paired' status.
    - FAIL if modules are not matched/paired to each other.
    - FAIL if either module is already paired to a different partner.
    - PASS if modules are matched to each other (auto-pairs if needed).
    - PASS if modules are already paired to each other.
    On success, the system_sn is linked in system_builds.
    """
    try:
        if db_path:
            import os as _os
            _os.makedirs(_os.path.dirname(_os.path.abspath(db_path)), exist_ok=True)
            con = sqlite3.connect(db_path)
            con.execute("PRAGMA journal_mode=WAL")
        else:
            con = _get_connection()

        # Ensure system_builds table exists (for callers using a custom db_path)
        con.execute("""
            CREATE TABLE IF NOT EXISTS system_builds (
                system_serial TEXT PRIMARY KEY,
                module_1      TEXT NOT NULL,
                module_2      TEXT NOT NULL,
                built_at      TEXT NOT NULL
            )
        """)
        con.commit()

        cur = con.cursor()

        # 1. Check both serials exist
        cur.execute("SELECT serial, status, partner FROM drivers WHERE serial = ?", (sn1,))
        row1 = cur.fetchone()
        cur.execute("SELECT serial, status, partner FROM drivers WHERE serial = ?", (sn2,))
        row2 = cur.fetchone()

        if row1 is None:
            con.close()
            return False, f"Module {sn1} not found in database"
        if row2 is None:
            con.close()
            return False, f"Module {sn2} not found in database"

        _, status1, partner1 = row1
        _, status2, partner2 = row2

        # 2. Check modules are in an acceptable status
        valid_statuses = {'matched', 'paired'}
        if status1 not in valid_statuses:
            con.close()
            return False, f"Module {sn1} is not matched or paired (status: {status1})"
        if status2 not in valid_statuses:
            con.close()
            return False, f"Module {sn2} is not matched or paired (status: {status2})"

        # 3. Check they are matched/paired to each other (not to different partners)
        if partner1 != sn2:
            if partner1:
                con.close()
                return False, f"Module {sn1} is matched/paired to a different module: {partner1}"
            else:
                con.close()
                return False, f"Module {sn1} has no partner"
        if partner2 != sn1:
            if partner2:
                con.close()
                return False, f"Module {sn2} is matched/paired to a different module: {partner2}"
            else:
                con.close()
                return False, f"Module {sn2} has no partner"

        # 4. Auto-pair if matched but not yet paired
        now = datetime.now().isoformat()
        action = "already paired"
        if status1 == 'matched' or status2 == 'matched':
            cur.execute(
                "UPDATE drivers SET status='paired', matched_at=? WHERE serial IN (?, ?)",
                (now, sn1, sn2),
            )
            action = "auto-paired"

        # 5. Unlink any existing system_builds entries that reference these modules
        cur.execute(
            "DELETE FROM system_builds WHERE module_1 IN (?, ?) OR module_2 IN (?, ?)",
            (sn1, sn2, sn1, sn2),
        )

        # 6. Link system_sn → the two modules
        cur.execute(
            "INSERT OR REPLACE INTO system_builds (system_serial, module_1, module_2, built_at) "
            "VALUES (?, ?, ?, ?)",
            (system_sn, sn1, sn2, now),
        )

        con.commit()
        con.close()
        return True, f"System {system_sn} linked to {sn1} and {sn2} ({action})"

    except Exception as e:
        return False, f"Database error: {str(e)}"


def get_driver_levels(serial):
    """Return (frequency_vector, levels) for a driver, or (None, None)."""
    con = _get_connection()
    cur = con.cursor()
    cur.execute("SELECT frequencies FROM frequency_vector WHERE id = 1")
    fv_row = cur.fetchone()
    cur.execute("SELECT levels FROM drivers WHERE serial = ?", (serial,))
    lv_row = cur.fetchone()
    con.close()
    if fv_row is None or lv_row is None:
        return None, None
    freqs = json.loads(fv_row[0])
    levels = json.loads(lv_row[0])
    return freqs, levels
