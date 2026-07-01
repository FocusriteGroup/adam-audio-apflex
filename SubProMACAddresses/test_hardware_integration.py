"""
test_hardware_integration.py

Hardware integration test: full MAC provisioning cycle with real OCA device,
using the test databases so production data is never touched.
Also fills the SN/FW test DB so DataTools shows the provisioned unit.

Requirements
------------
- SubPro device reachable at DEVICE_HOST:DEVICE_PORT
- Test DBs present (created by fresh DB script or previous test runs):
    SubProMACAddresses/db/mac_addresses_test.db
    SubPro_SN_FW_Workstation/Data/subpro_workstation_test.db
- DataTools settings pointing at the test DBs (for visual verification)

Run
---
    pytest SubProMACAddresses/test_hardware_integration.py -v -s

The -s flag shows print() output so you can see device state changes live.
"""

import os
import sys
import time
from pathlib import Path

import pytest

_HERE = Path(__file__).parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT))

from oca.oca_device import OCADevice
import SubProMACAddresses.mac_database as mac_db
from SubProMACAddresses.mac_database import set_mac_range
from SubProMACAddresses.mac_provisioner import provision_mac
from SubPro_SN_FW_Workstation.app.db.database import Database

# ---------------------------------------------------------------------------
# Configuration — adjust here if device IP or paths differ
# ---------------------------------------------------------------------------

DEVICE_HOST = "169.254.13.134"
DEVICE_PORT = 50001

DEFAULT_MAC  = "DE:AD:BE:EF:00:00"   # factory-default before provisioning
TEST_SERIALS = ["CI0000012", "CI0000013", "CI0000014", "CI0000015"]
WS_ID        = "HW_Integration_Test"

# A fresh sub-range within the test pool (won't collide with existing entries)
MAC_RANGE_START = "02:00:00:01:00:00"
MAC_RANGE_END   = "02:00:00:01:00:0F"   # 16 addresses
MAC_RANGE_WARN  = 3

MAC_DB_PATH  = str(_HERE / "db" / "mac_addresses_test.db")
SNFW_DB_PATH = str(_ROOT / "SubPro_SN_FW_Workstation" / "Data" / "subpro_workstation_test.db")

# Seconds to wait after a MAC write for device to reboot + re-announce mDNS
REBOOT_WAIT_S = 8


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wait_for_device(host: str, port: int, timeout: int = 30) -> bool:
    """Poll until OCA responds or timeout is reached. Returns True if online."""
    deadline = time.time() + timeout
    dev = OCADevice(host, port)
    while time.time() < deadline:
        try:
            result = dev.get_serial_number()
            if result and "error" not in str(result).lower():
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def _set_device_state(dev: OCADevice, serial: str, mac: str, label: str) -> None:
    """Write SN + MAC to device and wait for it to come back online."""
    print(f"\n[{label}] Setting SN={serial}, MAC={mac} …")
    dev.set_serial_number(serial)
    dev.set_mac_address(mac)
    print(f"[{label}] Waiting {REBOOT_WAIT_S}s for device reboot …")
    time.sleep(REBOOT_WAIT_S)
    if not _wait_for_device(DEVICE_HOST, DEVICE_PORT):
        raise RuntimeError("Device did not come back online after MAC change")
    print(f"[{label}] Device online.")


# ---------------------------------------------------------------------------
# Class-scoped parametrized fixture
# ---------------------------------------------------------------------------

@pytest.fixture(params=TEST_SERIALS, scope="class")
def hw_state(request):
    """
    Class-scoped, parametrized fixture — runs once per serial in TEST_SERIALS.
    All 5 tests in TestProvisioning share one fixture instance per serial,
    so state (provisioned_mac, unit_id) flows between tests naturally.

    Teardown restores device to its original SN + MAC after each serial.
    """
    test_serial = request.param

    # ── Skip guard ─────────────────────────────────────────────────────────
    if not _wait_for_device(DEVICE_HOST, DEVICE_PORT, timeout=5):
        pytest.skip(f"Hardware not reachable at {DEVICE_HOST}:{DEVICE_PORT}")

    dev = OCADevice(DEVICE_HOST, DEVICE_PORT)

    # Capture original state
    initial_sn  = dev.get_serial_number().get("value", "")
    initial_mac = dev.get_mac_address().get("value", "")
    print(f"\n[setup-{test_serial}] Device: SN={initial_sn}, MAC={initial_mac}")

    # Put device into test state
    _set_device_state(dev, test_serial, DEFAULT_MAC, f"setup-{test_serial}")

    # Switch mac_database to test DB + configure a fresh MAC range
    original_db_path = mac_db.DB_PATH
    mac_db.DB_PATH = MAC_DB_PATH
    set_mac_range(MAC_RANGE_START, MAC_RANGE_END, MAC_RANGE_WARN)

    # Remove any leftover provisioning entry for this serial from previous runs
    import sqlite3 as _sqlite3
    con = _sqlite3.connect(MAC_DB_PATH)
    con.execute("DELETE FROM provisioning_log WHERE serial=?", (test_serial,))
    con.commit()
    con.close()
    print(f"[setup-{test_serial}] MAC DB: {MAC_DB_PATH}")
    print(f"[setup-{test_serial}] MAC range: {MAC_RANGE_START} – {MAC_RANGE_END}")

    # Open SN/FW test DB
    snfw_db = Database(Path(SNFW_DB_PATH))
    print(f"[setup-{test_serial}] SN/FW DB: {SNFW_DB_PATH}")

    state = {
        "dev":             dev,
        "snfw_db":         snfw_db,
        "serial":          test_serial,
        "initial_sn":      initial_sn,
        "initial_mac":     initial_mac,
        "provisioned_mac": None,
        "unit_id":         None,
    }

    yield state

    # ── Teardown ────────────────────────────────────────────────────────────
    snfw_db._conn.close()
    mac_db.DB_PATH = original_db_path

    print(f"\n[teardown-{test_serial}] Restoring SN={initial_sn}, MAC={initial_mac} …")
    try:
        _set_device_state(dev, initial_sn, initial_mac, f"teardown-{test_serial}")
    except Exception as exc:
        print(f"[teardown-{test_serial}] WARNING: restore failed — {exc}")


# ---------------------------------------------------------------------------
# Tests  (grouped in a class so the class-scoped fixture covers all of them)
# ---------------------------------------------------------------------------

class TestProvisioning:

    def test_1_device_in_default_state(self, hw_state):
        """Sanity check: device reports the test SN and default MAC before provisioning."""
        s   = hw_state
        dev = s["dev"]
        sn  = dev.get_serial_number().get("value", "")
        mac = dev.get_mac_address().get("value", "")

        assert sn.upper() == s["serial"].upper(), f"Expected SN={s['serial']}, got {sn!r}"
        assert mac.upper() == DEFAULT_MAC.upper(), f"Expected MAC={DEFAULT_MAC}, got {mac!r}"
        print(f"\n[test_1-{s['serial']}] Device OK: SN={sn}, MAC={mac}")

    def test_2_provision_mac(self, hw_state):
        """
        First-test path: device with default MAC receives a MAC from the test pool.
        Verifies:
          - provision_mac returns status='success'
          - assigned MAC is from the configured test range
          - provisioning_log entry with status='verified' exists in test DB
        """
        s = hw_state

        pool_before = mac_db.get_pool_status()

        result = provision_mac(
            device=s["dev"],
            serial=s["serial"],
            workstation_id=WS_ID,
            default_mac=DEFAULT_MAC,
            arp_delay=5.0,
        )

        print(f"\n[test_2-{s['serial']}] provision_mac result: {result}")
        assert result["status"] == "success", f"Provisioning failed: {result}"

        assigned = result["mac"]
        assert assigned.upper().startswith(MAC_RANGE_START[:11].upper()), (
            f"Assigned MAC {assigned!r} not from test range {MAC_RANGE_START!r}"
        )

        db_mac = mac_db.get_assigned_mac(s["serial"])
        assert db_mac is not None
        assert db_mac.upper() == assigned.upper()

        pool_after = mac_db.get_pool_status()
        assert pool_after["assigned"] == pool_before["assigned"] + 1

        s["provisioned_mac"] = assigned
        print(f"[test_2-{s['serial']}] Provisioned: {assigned}  Pool remaining: {pool_after['remaining']}")

    def test_3_fill_snfw_db(self, hw_state):
        """
        Insert a complete unit record into the SN/FW test DB so DataTools
        shows the provisioned unit in the Tristar Databases view.
        """
        s = hw_state
        assert s["provisioned_mac"], "Needs test_2 to run first"

        db = s["snfw_db"]
        unit_id = db.create_unit(s["serial"], "A10S")
        db.update_unit_fw(unit_id, fw_found="2.0.0", fw_flashed=True, fw_final="2.0.0")

        parts = db.get_parts_config()
        for i, part in enumerate(parts):
            part_sn = f"{part['prefix_a10s']}{str(100 + i).zfill(7)}"
            db.add_part_scan(unit_id, part["name"], part_sn)
            print(f"[test_3-{s['serial']}] Part: {part['name']} = {part_sn}")

        db.complete_unit(unit_id, "PASS")
        s["unit_id"] = unit_id

        units = db.get_units(product_sn_filter=s["serial"])
        assert len(units) >= 1
        unit = next(u for u in units if u["id"] == unit_id)
        assert unit["result"] == "PASS"
        assert len(db.get_parts_for_unit(unit_id)) == len(parts)
        print(f"[test_3-{s['serial']}] SN/FW DB: unit_id={unit_id}, result=PASS")

    def test_4_retest_ok(self, hw_state):
        """Re-test path: device already has its provisioned MAC → retest_ok, no new MAC consumed."""
        s = hw_state
        assert s["provisioned_mac"], "Needs test_2 to run first"

        pool_before = mac_db.get_pool_status()

        result = provision_mac(
            device=s["dev"],
            serial=s["serial"],
            workstation_id=WS_ID,
            default_mac=DEFAULT_MAC,
            arp_delay=0,
        )

        print(f"\n[test_4-{s['serial']}] retest result: {result}")
        assert result["status"] == "retest_ok", f"Expected retest_ok, got: {result}"
        assert result["mac"].upper() == s["provisioned_mac"].upper()
        assert mac_db.get_pool_status()["assigned"] == pool_before["assigned"]

    def test_5_duplicate_sn_rejected(self, hw_state):
        """Guard: resetting MAC to default and re-provisioning the same SN is rejected."""
        s = hw_state

        dev = s["dev"]
        dev.set_mac_address(DEFAULT_MAC)
        time.sleep(REBOOT_WAIT_S)
        _wait_for_device(DEVICE_HOST, DEVICE_PORT)

        result = provision_mac(
            device=dev,
            serial=s["serial"],
            workstation_id=WS_ID,
            default_mac=DEFAULT_MAC,
            arp_delay=0,
        )

        print(f"\n[test_5-{s['serial']}] duplicate_sn result: {result}")
        assert result["status"] == "error"
        assert result["reason"] == "duplicate_sn"
        assert result["db_mac"].upper().startswith(MAC_RANGE_START[:11].upper())
