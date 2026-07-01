"""
test_provisioner_unit.py

Unit tests for SubProMACAddresses.mac_provisioner.provision_mac.

All paths in the provisioning flow are covered without a real OCA device.
A fresh SQLite database is created for each test via the `isolated_db` fixture.

Paths covered
-------------
test_success            — Default MAC → MAC written and read-back matches  → success
test_duplicate_sn       — Default MAC but SN already verified in DB        → error/duplicate_sn
test_pool_exhausted     — Default MAC but MAC range fully consumed          → error/pool_exhausted
test_verify_failed      — MAC written but read-back returns wrong value     → error/verify_failed
test_mac_written        — Verifies set_mac_address is called with pool MAC
test_retest_ok          — Device already has its provisioned MAC            → retest_ok
test_unknown_device     — Unique MAC on device, SN not in DB               → error/unknown_device
test_mac_mismatch       — Unique MAC on device, differs from DB record     → error/mac_mismatch
test_db_path_propagation — provision_mac uses whichever DB_PATH is active  → isolation test

Run:
    pytest SubProMACAddresses/test_provisioner_unit.py -v
"""

import os
import sqlite3
import sys
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

import SubProMACAddresses.mac_database as mac_db
from SubProMACAddresses.mac_database import set_mac_range
from SubProMACAddresses.mac_provisioner import provision_mac

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MAC  = "DE:AD:BE:EF:00:00"
WS_ID        = "unit_test_workstation"
RANGE_START  = "02:AA:00:00:00:00"
RANGE_END    = "02:AA:00:00:00:09"   # 10 MACs
RANGE_WARN   = 3

_SCHEMA = """
CREATE TABLE mac_range (
    id INTEGER PRIMARY KEY CHECK (id=1),
    start_mac TEXT NOT NULL,
    end_mac TEXT NOT NULL,
    next_mac TEXT NOT NULL,
    warn_threshold INTEGER NOT NULL
);
CREATE TABLE provisioning_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    serial TEXT NOT NULL,
    mac TEXT NOT NULL,
    workstation_id TEXT,
    reserved_at TEXT,
    written_at TEXT,
    verified_at TEXT,
    status TEXT NOT NULL
);
CREATE TABLE golden_samples (
    serial TEXT PRIMARY KEY,
    added_at TEXT NOT NULL,
    note TEXT
);
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_db(path: str) -> None:
    """Initialise a fresh provisioning DB at *path*."""
    con = sqlite3.connect(path)
    con.executescript(_SCHEMA)
    con.commit()
    con.close()


def _seed_range(start=RANGE_START, end=RANGE_END, warn=RANGE_WARN) -> None:
    """Insert a MAC range into the currently active DB."""
    set_mac_range(start, end, warn)


def _insert_verified(serial: str, mac: str) -> None:
    """Directly insert a 'verified' provisioning record into the active DB."""
    con = sqlite3.connect(mac_db.DB_PATH)
    con.execute(
        "INSERT INTO provisioning_log "
        "(serial, mac, status, reserved_at, written_at, verified_at) "
        "VALUES (?, ?, 'verified', 'x', 'x', 'x')",
        (serial, mac),
    )
    con.commit()
    con.close()


def _advance_next_mac(new_next: str) -> None:
    """Move next_mac pointer in the active DB without going through reserve_mac."""
    con = sqlite3.connect(mac_db.DB_PATH)
    con.execute("UPDATE mac_range SET next_mac=?", (new_next,))
    con.commit()
    con.close()


def _make_device(current_mac: str, readback_mac: str = None) -> MagicMock:
    """
    Build a MagicMock OCADevice.

    get_mac_address() → current_mac initially; after set_mac_address() it returns
    readback_mac (if given) or the value that was written.
    discover() returns an empty list so retarget logic is bypassed.
    """
    state = {"mac": current_mac}

    def _get():
        return {"value": state["mac"]}

    def _set(m):
        state["mac"] = readback_mac if readback_mac is not None else m

    dev = MagicMock()
    dev.get_mac_address.side_effect = _get
    dev.set_mac_address.side_effect = _set
    dev.discover.return_value = {"devices": []}
    dev.unlock_factory_settings.return_value = {"value": "Done"}
    return dev


# ---------------------------------------------------------------------------
# Fixture — isolated DB per test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    """
    Create a fresh SQLite DB for each test and patch mac_database.DB_PATH
    so that all mac_database functions operate on the temp DB.
    """
    db_path = str(tmp_path / "mac_test.db")
    _create_db(db_path)
    monkeypatch.setattr(mac_db, "DB_PATH", db_path)
    monkeypatch.setattr(mac_db, "_DB_DIR", str(tmp_path))
    yield db_path


# ---------------------------------------------------------------------------
# First-test path (device has default MAC)
# ---------------------------------------------------------------------------

class TestFirstTestPath:
    def test_success(self):
        """Happy path: default MAC → MAC assigned, written, verified."""
        _seed_range()
        dev = _make_device(DEFAULT_MAC)

        result = provision_mac(dev, "CI0000001", WS_ID, DEFAULT_MAC, arp_delay=0)

        assert result["status"] == "success"
        assert result["mac"] == RANGE_START
        pool = mac_db.get_pool_status()
        assert pool["assigned"] == 1
        assert pool["remaining"] == 9

    def test_mac_written_to_device(self):
        """Verifies set_mac_address is called with the first pool MAC."""
        _seed_range()
        dev = _make_device(DEFAULT_MAC)

        provision_mac(dev, "CI0000001", WS_ID, DEFAULT_MAC, arp_delay=0)

        dev.set_mac_address.assert_called_once_with(RANGE_START)

    def test_duplicate_sn(self):
        """SN already verified in DB → duplicate_sn error, no new MAC consumed."""
        _seed_range()
        _insert_verified("CI0000001", RANGE_START)
        _advance_next_mac("02:AA:00:00:00:01")

        dev = _make_device(DEFAULT_MAC)
        result = provision_mac(dev, "CI0000001", WS_ID, DEFAULT_MAC, arp_delay=0)

        assert result["status"] == "error"
        assert result["reason"] == "duplicate_sn"
        assert result["db_mac"] == RANGE_START
        # No additional MAC consumed
        pool = mac_db.get_pool_status()
        assert pool["next_mac"] == "02:AA:00:00:00:01"

    def test_pool_exhausted(self):
        """All MACs handed out → pool_exhausted error."""
        _seed_range(end="02:AA:00:00:00:00")       # 1-MAC range
        _advance_next_mac("02:AA:00:00:00:01")      # pointer past end

        dev = _make_device(DEFAULT_MAC)
        result = provision_mac(dev, "CI0000001", WS_ID, DEFAULT_MAC, arp_delay=0)

        assert result["status"] == "error"
        assert result["reason"] == "pool_exhausted"

    def test_verify_failed(self):
        """Device returns wrong MAC on read-back → verify_failed, MAC rolled back."""
        _seed_range()
        dev = _make_device(DEFAULT_MAC, readback_mac="FF:FF:FF:FF:FF:FF")

        result = provision_mac(dev, "CI0000001", WS_ID, DEFAULT_MAC, arp_delay=0)

        assert result["status"] == "error"
        assert result["reason"] == "verify_failed"
        assert result["written"] == RANGE_START
        # Pool pointer advanced but no 'verified' record
        pool = mac_db.get_pool_status()
        assert pool["assigned"] == 0


# ---------------------------------------------------------------------------
# Re-test path (device already has a unique MAC)
# ---------------------------------------------------------------------------

class TestRetestPath:
    def test_retest_ok(self):
        """Device MAC matches DB record → retest_ok, no new MAC consumed."""
        _seed_range()
        _insert_verified("CI0000001", RANGE_START)
        _advance_next_mac("02:AA:00:00:00:01")

        dev = _make_device(RANGE_START)
        result = provision_mac(dev, "CI0000001", WS_ID, DEFAULT_MAC, arp_delay=0)

        assert result["status"] == "retest_ok"
        assert result["mac"] == RANGE_START
        # No additional MAC consumed
        pool = mac_db.get_pool_status()
        assert pool["next_mac"] == "02:AA:00:00:00:01"

    def test_unknown_device(self):
        """Unique MAC on device, SN not in DB → unknown_device error."""
        _seed_range()
        unique_mac = "02:AA:00:00:00:05"

        dev = _make_device(unique_mac)
        result = provision_mac(dev, "CI0000001", WS_ID, DEFAULT_MAC, arp_delay=0)

        assert result["status"] == "error"
        assert result["reason"] == "unknown_device"
        assert result["current_mac"] == unique_mac

    def test_mac_mismatch(self):
        """Device MAC differs from DB record → mac_mismatch error."""
        _seed_range()
        db_mac     = RANGE_START          # "02:AA:00:00:00:00"
        device_mac = "02:AA:00:00:00:01"  # different
        _insert_verified("CI0000001", db_mac)
        _advance_next_mac("02:AA:00:00:00:02")

        dev = _make_device(device_mac)
        result = provision_mac(dev, "CI0000001", WS_ID, DEFAULT_MAC, arp_delay=0)

        assert result["status"] == "error"
        assert result["reason"] == "mac_mismatch"
        assert result["db_mac"] == db_mac
        assert result["device_mac"] == device_mac


# ---------------------------------------------------------------------------
# DB path isolation (regression for DataTools mac_db_path bug)
# ---------------------------------------------------------------------------

class TestDbPathPropagation:
    def test_provision_uses_active_db_path(self, tmp_path):
        """
        provision_mac must operate on whatever mac_database.DB_PATH points to
        at call time.  Two isolated DBs: only the active one gets the record.
        """
        # DB A — has a 'verified' record for CI0000001
        db_a = str(tmp_path / "a.db")
        _create_db(db_a)
        mac_db.DB_PATH = db_a
        mac_db._DB_DIR  = str(tmp_path)
        _seed_range("02:AA:00:00:00:00", "02:AA:00:00:00:09")
        _insert_verified("CI0000001", "02:AA:00:00:00:00")
        _advance_next_mac("02:AA:00:00:00:01")

        # DB B — fresh, SN CI0000001 unknown, different pool
        db_b = str(tmp_path / "b.db")
        _create_db(db_b)
        mac_db.DB_PATH = db_b
        mac_db._DB_DIR  = str(tmp_path)
        _seed_range("02:BB:00:00:00:00", "02:BB:00:00:00:09")

        # Provision with DB B active → should succeed (SN not in DB B)
        dev = _make_device(DEFAULT_MAC)
        result = provision_mac(dev, "CI0000001", WS_ID, DEFAULT_MAC, arp_delay=0)

        assert result["status"] == "success", (
            "provision_mac used the wrong DB — expected success from fresh DB B, "
            f"got: {result}"
        )
        assert result["mac"].startswith("02:BB:"), (
            f"Expected a MAC from pool B (02:BB:...), got {result['mac']!r}"
        )

        # DB A must be untouched
        mac_db.DB_PATH = db_a
        assert mac_db.get_pool_status()["assigned"] == 1   # only the pre-seeded record
        assert mac_db.get_pool_status()["next_mac"] == "02:AA:00:00:00:01"
