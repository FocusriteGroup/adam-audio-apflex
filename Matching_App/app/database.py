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
