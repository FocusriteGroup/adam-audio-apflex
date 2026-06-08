"""
test_mac_provisioning.py

Pytest integration test suite for the SubPro MAC address provisioning flow.

Tests all paths in the SubPro EOL flow diagram using adam_workstation.py provision_mac.

Paths covered:
  test_1_success        — First test, MAC written and verified
  test_2_retest_ok      — Device already has provisioned MAC matching DB record
  test_3_duplicate_sn   — Device shows default MAC but SN already in DB
  test_4_mac_mismatch   — Device has unknown MAC that doesn't match DB record
  test_5_unknown_device — Device has unique MAC but SN not found in DB at all
  test_6_pool_exhausted — MAC range fully consumed, no MACs available
  test_7_export_log     — Export of provisioning log to CSV

Run from workspace root:
    pytest SubProMACAddresses/test_mac_provisioning.py -v \\
        --html=logs/mac_provisioning_test/report.html \\
        --self-contained-html \\
        --junitxml=logs/mac_provisioning_test/junit.xml

Requirements:
    pip install pytest pytest-html
"""

import csv
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HERE           = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_ROOT  = os.path.dirname(_HERE)
WORKSTATION     = os.path.join(WORKSPACE_ROOT, "adam_workstation.py")
DB_PATH         = os.path.join(_HERE, "db", "mac_addresses.db")
LOG_DIR         = os.path.join(WORKSPACE_ROOT, "logs", "mac_provisioning_test")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TARGET          = "169.254.27.208"
TARGET_PORT     = 50001
MAC_RANGE_START = "02:FE:ED:00:00:00"
MAC_RANGE_END   = "02:FE:ED:00:00:09"   # 10 MACs total
WARN_THRESHOLD  = 3
ALTERNATE_MAC   = "02:FE:ED:FF:FF:01"   # Used for MAC_MISMATCH / UNKNOWN_DEVICE

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(*args):
    """Call adam_workstation.py from workspace root. Returns parsed JSON or raw string."""
    cmd = [sys.executable, WORKSTATION] + [str(a) for a in args]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=WORKSPACE_ROOT)
    out = result.stdout.strip()
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return out


def run_oca(command, *args):
    """Call an OCA command with TARGET + PORT appended automatically."""
    return run(command, TARGET, *args, TARGET_PORT)


def db_exec(sql, params=()):
    """Execute a write statement directly on the MAC DB."""
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA journal_mode=DELETE")
    con.execute(sql, params)
    con.commit()
    con.close()


def db_query(sql, params=()):
    """Execute a read statement and return rows as list of dicts."""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute(sql, params).fetchall()]
    con.close()
    return rows


# ---------------------------------------------------------------------------
# Fixture — module-scoped shared device state
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def device_state():
    """
    Setup: initialise DB, configure MAC range, read device serial + current MAC.
    Teardown: restore device to its original MAC address.

    Yields a mutable dict so tests can share state (e.g. provisioned_mac).
    """
    os.makedirs(LOG_DIR, exist_ok=True)

    # --- Setup ---
    run("init_mac_db")
    db_exec("DELETE FROM mac_range")
    db_exec("DELETE FROM provisioning_log")
    run("set_mac_range", MAC_RANGE_START, MAC_RANGE_END,
        f"--warn-threshold={WARN_THRESHOLD}")

    serial      = str(run("get_serial_number", TARGET, TARGET_PORT)).strip()
    initial_mac = str(run("get_mac_address",   TARGET, TARGET_PORT)).strip()

    state = {
        "serial":          serial,
        "initial_mac":     initial_mac,
        "default_mac":     initial_mac,  # whatever the device currently has = test default
        "provisioned_mac": None,         # populated by test_1_success
    }

    yield state

    # --- Teardown ---
    run("set_mac_address", state["initial_mac"], TARGET, TARGET_PORT)


# ---------------------------------------------------------------------------
# Tests  (number prefixes guarantee alphabetical / execution order)
# ---------------------------------------------------------------------------

def test_1_success(device_state):
    """
    First-test path: device has default MAC, SN not in DB.

    Flow: default_mac == current_mac → SN not in DB → reserve → write → verify
    Expected: status='success', MAC assigned from range, DB entry 'verified'.
    """
    s = device_state
    result = run("provision_mac", TARGET, s["serial"], s["default_mac"], TARGET_PORT)

    assert result == "successful", f"Expected 'successful', got: {result!r}"

    # Get the assigned MAC from DB — result string no longer carries it
    rows = db_query(
        "SELECT * FROM provisioning_log WHERE serial=? AND status='verified'",
        (s["serial"],),
    )
    assert len(rows) == 1, f"Expected 1 verified DB entry, got: {rows}"
    mac = rows[0]["mac"]
    assert mac.upper().startswith("02:FE:ED"), \
        f"Assigned MAC not from test range: {mac}"

    s["provisioned_mac"] = mac  # pass to subsequent tests


def test_2_retest_ok(device_state):
    """
    Re-test path: device already holds its provisioned MAC, SN in DB with matching entry.

    Flow: current_mac != default_mac → SN in DB → MAC matches → RETEST_OK
    Expected: status='retest_ok', same MAC confirmed.
    """
    s = device_state
    assert s["provisioned_mac"], "provisioned_mac not set — test_1 must run first"

    current = str(run("get_mac_address", TARGET, TARGET_PORT)).strip()
    assert current == s["provisioned_mac"], \
        f"Device should hold provisioned MAC {s['provisioned_mac']}, got {current}"

    result = run("provision_mac", TARGET, s["serial"], s["default_mac"], TARGET_PORT)

    assert result == "successful", f"Expected 'successful', got: {result!r}"


def test_3_export_log(device_state):
    """
    Export provisioning log while the DB holds a real verified entry (from test_1).

    Validates:
      - Full export contains the real device serial, MAC, and populated timestamps
      - --status verified filter includes real device, excludes 'reserved' rows
      - --serial filter returns exactly one row matching the queried serial
    Also validates filter behaviour with two synthetic rows inserted and removed
    within this test.
    """
    s  = device_state
    assert s["provisioned_mac"], "provisioned_mac not set — test_1 must run first"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Insert two synthetic rows so filter tests have predictable additional content
    db_exec(
        "INSERT OR IGNORE INTO provisioning_log (serial, mac, status, workstation_id) "
        "VALUES (?, ?, 'verified', 'test-station')",
        ("TEST-EXPORT-V", "02:FE:ED:00:FF:01"),
    )
    db_exec(
        "INSERT OR IGNORE INTO provisioning_log (serial, mac, status, workstation_id) "
        "VALUES (?, ?, 'reserved', 'test-station')",
        ("TEST-EXPORT-R", "02:FE:ED:00:FF:02"),
    )

    try:
        # --- Export ALL ---
        export_all = os.path.join(LOG_DIR, f"export_all_{ts}.csv")
        r = run("export_mac_log", export_all)
        assert isinstance(r, dict),        f"Unexpected result: {r!r}"
        assert r["status"] == "ok",        f"Export failed: {r}"
        assert os.path.isfile(export_all),  f"Export file not created: {export_all}"
        assert r["exported"] >= 3,         f"Expected ≥3 rows (real + 2 synthetic), got {r['exported']}"

        with open(export_all, encoding="utf-8", newline="") as f:
            rows_all = list(csv.DictReader(f))
        assert any(row["serial"] == s["serial"] for row in rows_all), \
            f"Real device serial {s['serial']!r} missing from full export"
        assert any(row["mac"] == s["provisioned_mac"] for row in rows_all), \
            f"Provisioned MAC {s['provisioned_mac']!r} missing from full export"
        assert any(row["serial"] == "TEST-EXPORT-V" for row in rows_all), \
            "Synthetic verified row missing from full export"
        assert any(row["serial"] == "TEST-EXPORT-R" for row in rows_all), \
            "Synthetic reserved row missing from full export"
        assert all(
            "mac" in row and "serial" in row and "status" in row for row in rows_all
        ), "CSV row missing required columns"

        # --- Export filtered by --status verified ---
        export_verified = os.path.join(LOG_DIR, f"export_verified_{ts}.csv")
        r_v = run("export_mac_log", export_verified, "--status", "verified")
        assert r_v["status"] == "ok",      f"Filtered export (verified) failed: {r_v}"
        with open(export_verified, encoding="utf-8", newline="") as f:
            rows_v = list(csv.DictReader(f))
        assert all(row["status"] == "verified" for row in rows_v), \
            f"Non-verified row in --status verified export: {rows_v}"
        assert any(row["serial"] == s["serial"] for row in rows_v), \
            "Real device serial missing from verified export"
        assert any(row["serial"] == "TEST-EXPORT-V" for row in rows_v), \
            "Synthetic verified row missing from verified export"
        assert all(row["serial"] != "TEST-EXPORT-R" for row in rows_v), \
            "Reserved synthetic row leaked into verified export"

        # --- Export filtered by --serial (real device) ---
        export_serial = os.path.join(LOG_DIR, f"export_serial_{ts}.csv")
        r_s = run("export_mac_log", export_serial, "--serial", s["serial"])
        assert r_s["status"] == "ok",      f"Filtered export (serial) failed: {r_s}"
        with open(export_serial, encoding="utf-8", newline="") as f:
            rows_s = list(csv.DictReader(f))
        assert len(rows_s) == 1,            f"Expected exactly 1 row for {s['serial']!r}, got: {rows_s}"
        assert rows_s[0]["serial"] == s["serial"]
        assert rows_s[0]["mac"]    == s["provisioned_mac"]
        assert rows_s[0]["status"] == "verified"
        assert rows_s[0]["reserved_at"], "reserved_at timestamp missing for real device"
        assert rows_s[0]["verified_at"], "verified_at timestamp missing for real device"

    finally:
        db_exec(
            "DELETE FROM provisioning_log "
            "WHERE serial IN ('TEST-EXPORT-V', 'TEST-EXPORT-R')"
        )


def test_4_duplicate_sn(device_state):
    """
    Duplicate SN path: device is reset to default MAC, SN already verified in DB.

    Flow: current_mac == default_mac → SN already in DB → DUPLICATE_SN
    Expected: status='error', reason='duplicate_sn'.
    """
    s = device_state

    run("set_mac_address", s["default_mac"], TARGET, TARGET_PORT)
    current = str(run("get_mac_address", TARGET, TARGET_PORT)).strip()
    assert current == s["default_mac"], \
        f"Failed to reset device to default MAC: {current}"

    result = run("provision_mac", TARGET, s["serial"], s["default_mac"], TARGET_PORT)

    assert isinstance(result, str), f"Expected error string, got: {result!r}"
    assert "duplicate serial number" in result, f"Wrong error: {result!r}"
    assert s["provisioned_mac"] in result, f"DB MAC missing from error: {result!r}"


def test_5_mac_mismatch(device_state):
    """
    MAC mismatch path: device has a unique MAC that differs from the DB record.

    Flow: current_mac != default_mac → SN in DB → MAC differs from DB → MAC_MISMATCH
    Expected: status='error', reason='mac_mismatch'.
    """
    s = device_state

    run("set_mac_address", ALTERNATE_MAC, TARGET, TARGET_PORT)
    current = str(run("get_mac_address", TARGET, TARGET_PORT)).strip()
    assert current == ALTERNATE_MAC, \
        f"Failed to write ALTERNATE_MAC to device: {current}"

    result = run("provision_mac", TARGET, s["serial"], s["default_mac"], TARGET_PORT)

    assert isinstance(result, str), f"Expected error string, got: {result!r}"
    assert "MAC mismatch" in result, f"Wrong error: {result!r}"
    assert s["provisioned_mac"] in result, f"DB MAC missing from error: {result!r}"
    assert ALTERNATE_MAC in result, f"Device MAC missing from error: {result!r}"


def test_6_unknown_device(device_state):
    """
    Unknown device path: device has a unique MAC but SN has no DB record.

    Flow: current_mac != default_mac → SN not in DB → UNKNOWN_DEVICE
    Expected: status='error', reason='unknown_device'.
    """
    s = device_state

    db_exec("DELETE FROM provisioning_log WHERE serial=?", (s["serial"],))

    current = str(run("get_mac_address", TARGET, TARGET_PORT)).strip()
    assert current == ALTERNATE_MAC, \
        f"Device should still hold ALTERNATE_MAC from test_4: {current}"

    rows = db_query("SELECT * FROM provisioning_log WHERE serial=?", (s["serial"],))
    assert rows == [], f"DB should be empty for this SN, got: {rows}"

    result = run("provision_mac", TARGET, s["serial"], s["default_mac"], TARGET_PORT)

    assert isinstance(result, str), f"Expected error string, got: {result!r}"
    assert "unknown device" in result, f"Wrong error: {result!r}"
    assert ALTERNATE_MAC in result, f"Device MAC missing from error: {result!r}"


def test_7_pool_exhausted(device_state):
    """
    Pool exhausted path: MAC range fully consumed, next_mac past end_mac.

    Flow: current_mac == default_mac → SN not in DB → reserve_mac → pool empty → POOL_EXHAUSTED
    Expected: status='error', reason='pool_exhausted'.
    """
    s = device_state

    # Advance pointer past end of range
    db_exec("UPDATE mac_range SET next_mac = 'FF:FF:FF:FF:FF:FF' WHERE id = 1")

    pool = run("get_mac_pool_status")
    assert pool["remaining"] == 0, f"Pool should be exhausted, got: {pool}"

    # Device must show default MAC for first-test path; SN deleted in test_5
    run("set_mac_address", s["default_mac"], TARGET, TARGET_PORT)
    current = str(run("get_mac_address", TARGET, TARGET_PORT)).strip()
    assert current == s["default_mac"], \
        f"Failed to reset device MAC: {current}"

    result = run("provision_mac", TARGET, s["serial"], s["default_mac"], TARGET_PORT)

    assert isinstance(result, str), f"Expected error string, got: {result!r}"
    assert "pool exhausted" in result.lower(), f"Wrong error: {result!r}"


def _test_export_log_legacy(device_state):
    """
    Superseded by test_3_export_log — kept for reference only, not collected by pytest.
    Verify export_mac_log produces a valid CSV file and that --status / --serial
    filters work correctly.

    Inserts two known rows directly into the DB, exports with various options,
    validates CSV content, then cleans up.
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Insert two known rows so the export always has predictable content
    db_exec(
        "INSERT OR IGNORE INTO provisioning_log (serial, mac, status, workstation_id) "
        "VALUES (?, ?, 'verified', 'test-station')",
        ("TEST-EXPORT-V", "02:FE:ED:00:FF:01"),
    )
    db_exec(
        "INSERT OR IGNORE INTO provisioning_log (serial, mac, status, workstation_id) "
        "VALUES (?, ?, 'reserved', 'test-station')",
        ("TEST-EXPORT-R", "02:FE:ED:00:FF:02"),
    )

    try:
        # --- Export ALL ---
        export_all = os.path.join(LOG_DIR, f"export_all_{ts}.csv")
        r = run("export_mac_log", export_all)
        assert isinstance(r, dict),      f"Unexpected result: {r!r}"
        assert r["status"] == "ok",      f"Export failed: {r}"
        assert os.path.isfile(export_all), f"Export file not created: {export_all}"
        assert r["exported"] >= 2,       f"Expected ≥2 rows, got {r['exported']}"

        with open(export_all, encoding="utf-8", newline="") as f:
            rows_all = list(csv.DictReader(f))
        assert any(r["serial"] == "TEST-EXPORT-V" for r in rows_all), \
            "TEST-EXPORT-V missing from full export"
        assert any(r["serial"] == "TEST-EXPORT-R" for r in rows_all), \
            "TEST-EXPORT-R missing from full export"
        assert all("mac" in r and "serial" in r and "status" in r for r in rows_all), \
            "CSV row missing required columns"

        # --- Export filtered by --status verified ---
        export_verified = os.path.join(LOG_DIR, f"export_verified_{ts}.csv")
        r_v = run("export_mac_log", export_verified, "--status", "verified")
        assert r_v["status"] == "ok",    f"Filtered export (verified) failed: {r_v}"
        with open(export_verified, encoding="utf-8", newline="") as f:
            rows_v = list(csv.DictReader(f))
        assert all(row["status"] == "verified" for row in rows_v), \
            f"Non-verified row in --status verified export: {rows_v}"
        assert any(row["serial"] == "TEST-EXPORT-V" for row in rows_v), \
            "TEST-EXPORT-V not in verified export"
        assert all(row["serial"] != "TEST-EXPORT-R" for row in rows_v), \
            "TEST-EXPORT-R (reserved) leaked into verified export"

        # --- Export filtered by --serial ---
        export_serial = os.path.join(LOG_DIR, f"export_serial_{ts}.csv")
        r_s = run("export_mac_log", export_serial, "--serial", "TEST-EXPORT-R")
        assert r_s["status"] == "ok",    f"Filtered export (serial) failed: {r_s}"
        with open(export_serial, encoding="utf-8", newline="") as f:
            rows_s = list(csv.DictReader(f))
        assert len(rows_s) == 1,         f"Expected exactly 1 row for TEST-EXPORT-R, got: {rows_s}"
        assert rows_s[0]["serial"] == "TEST-EXPORT-R"
        assert rows_s[0]["mac"]    == "02:FE:ED:00:FF:02"
        assert rows_s[0]["status"] == "reserved"

    finally:
        db_exec(
            "DELETE FROM provisioning_log WHERE serial IN ('TEST-EXPORT-V', 'TEST-EXPORT-R')"
        )
