"""
MAC address provisioning logic for SubPro EOL production.

Called after a device has passed the APx500 EOL test.

Flow
----
1. Read current MAC from device via OCA.
2a. current_mac == DEFAULT_MAC  → First-test path
    - Check DB: SN already assigned?  →  DUPLICATE SN  →  HALT
    - Pool empty?                      →  POOL EXHAUSTED →  HALT
    - reserve_mac → set_mac_address → confirm_mac_written
    - ARP flush + sleep → get_mac_address → compare
      - Match   → confirm_mac_verified → SUCCESS
      - Mismatch → rollback_mac        → VERIFY FAILED
2b. current_mac != DEFAULT_MAC  → Re-test path
    - DB has no entry for this SN     → UNKNOWN DEVICE   → HALT
    - DB entry matches current_mac    → Re-test OK        → SUCCESS
    - DB entry differs from device MAC → MAC MISMATCH     → HALT

Return value
------------
All public functions return a dict with at least:
    {"status": "success" | "retest_ok" | "error", ...}

Error dicts additionally contain a "reason" key:
    "duplicate_sn"     – SN already in DB but device still has Default MAC
    "pool_exhausted"   – No MACs available in pool
    "verify_failed"    – Written MAC could not be read back correctly
    "unknown_device"   – Device has unique MAC but SN is not in DB
    "mac_mismatch"     – Re-test: device MAC differs from DB record
    "oca_error"        – OCA communication failure
"""

import logging
import subprocess
import sys
import time

from SubProMACAddresses.mac_database import (
    confirm_mac_verified,
    confirm_mac_written,
    get_assigned_mac,
    get_pool_status,
    reserve_mac,
    rollback_mac,
)

logger = logging.getLogger(__name__)

# Seconds to wait after flushing the ARP cache so the device can
# re-announce itself with the new MAC via mDNS.
ARP_FLUSH_DELAY = 3.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _flush_arp_cache() -> None:
    """Delete all ARP table entries so the OS forgets the device's old MAC."""
    try:
        if sys.platform == "win32":
            # Requires elevated privileges on Windows
            subprocess.run(["arp", "-d", "*"], check=False, capture_output=True)
        else:
            # Linux / macOS
            subprocess.run(["ip", "neigh", "flush", "all"], check=False, capture_output=True)
        logger.debug("ARP cache flushed.")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not flush ARP cache: %s", exc)


def _normalise_mac(mac: str) -> str:
    """Return MAC in upper-case colon-separated format, e.g. 'AA:BB:CC:DD:EE:FF'."""
    return mac.strip().upper()


def _read_mac(device):
    """Read MAC from device via OCA. Returns normalised string or None on error."""
    try:
        result = device.get_mac_address()
        # OCA wrapper returns a dict or string depending on implementation;
        # adapt extraction to whatever get_mac_address() returns.
        if isinstance(result, dict):
            mac = result.get("value") or result.get("mac") or result.get("result")
        else:
            mac = str(result)
        return _normalise_mac(mac) if mac else None
    except Exception as exc:  # noqa: BLE001
        logger.error("OCA get_mac_address failed: %s", exc)
        return None


def _write_mac(device, mac: str) -> bool:
    """Write MAC to device via OCA. Returns True on success."""
    try:
        device.set_mac_address(mac)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("OCA set_mac_address failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def provision_mac(
    device,
    serial: str,
    workstation_id: str,
    default_mac: str,
) -> dict:
    """Assign a unique MAC address to a device that has passed EOL testing.

    Args:
        device:          OCADevice instance, already connected to the target.
        serial:          Device serial number (already read at test start).
        workstation_id:  ID string of the test station (for audit log).
        default_mac:     The factory default MAC address used before provisioning,
                         e.g. "02:00:00:00:00:00".

    Returns:
        dict with keys:
            status       "success" | "retest_ok" | "error"
            reason       (only on error) see module docstring for values
            mac          assigned/verified MAC address (on success / retest_ok)
            low_pool     True if fewer than LOW_POOL_WARN MACs remain (on success)
            available    number of available MACs remaining (on success)
    """
    default_mac = _normalise_mac(default_mac)

    # ------------------------------------------------------------------
    # Step 1: Read current MAC from device
    # ------------------------------------------------------------------
    current_mac = _read_mac(device)
    if current_mac is None:
        logger.error("[%s] OCA MAC read failed.", serial)
        return {"status": "error", "reason": "oca_error", "detail": "get_mac_address returned nothing"}

    logger.info("[%s] Current device MAC: %s", serial, current_mac)

    # ------------------------------------------------------------------
    # Step 2a: Device still has Default MAC → First-test path
    # ------------------------------------------------------------------
    if current_mac == default_mac:
        return _provision_first_test(device, serial, workstation_id)

    # ------------------------------------------------------------------
    # Step 2b: Device has a unique MAC → Re-test path
    # ------------------------------------------------------------------
    return _provision_retest(serial, current_mac)


# ---------------------------------------------------------------------------
# Internal provisioning paths
# ---------------------------------------------------------------------------

def _provision_first_test(device, serial: str, workstation_id: str) -> dict:
    """Handle a device arriving with the Default MAC (first test or clean re-test)."""

    # Guard: SN already in DB means a second physical device with the same SN
    db_mac = get_assigned_mac(serial)
    if db_mac is not None:
        logger.error(
            "[%s] DUPLICATE SN — DB already has MAC %s assigned for this serial.", serial, db_mac
        )
        return {
            "status": "error",
            "reason": "duplicate_sn",
            "db_mac": db_mac,
            "detail": (
                f"Serial {serial!r} is already assigned to MAC {db_mac}. "
                "Two devices may share the same serial number."
            ),
        }

    # Reserve next MAC from range
    mac, low_pool = reserve_mac(serial, workstation_id)
    if mac is None:
        logger.error("[%s] MAC range exhausted — no MACs available.", serial)
        return {"status": "error", "reason": "pool_exhausted", "detail": "MAC range is exhausted."}

    logger.info("[%s] Reserved MAC: %s", serial, mac)

    # Write MAC to device via OCA
    if not _write_mac(device, mac):
        rollback_mac(serial, mac, reason="OCA write failed")
        return {
            "status": "error",
            "reason": "oca_error",
            "detail": "set_mac_address call failed; MAC rolled back to pool.",
        }

    confirm_mac_written(serial, mac, workstation_id)
    logger.info("[%s] MAC written: %s", serial, mac)

    # Flush ARP cache and wait for device to re-announce via mDNS
    _flush_arp_cache()
    logger.debug("[%s] Waiting %.1f s after ARP flush…", serial, ARP_FLUSH_DELAY)
    time.sleep(ARP_FLUSH_DELAY)

    # Read back MAC from device to verify
    read_back = _read_mac(device)
    if read_back is None:
        rollback_mac(serial, mac, reason="OCA read-back failed after write")
        return {
            "status": "error",
            "reason": "oca_error",
            "detail": "get_mac_address returned nothing after write; MAC rolled back.",
        }

    if read_back != mac:
        rollback_mac(serial, mac, reason=f"verify failed: read back {read_back!r}")
        logger.error("[%s] Verify FAILED — wrote %s, read back %s", serial, mac, read_back)
        return {
            "status": "error",
            "reason": "verify_failed",
            "written": mac,
            "read_back": read_back,
            "detail": "Device MAC after write does not match expected value; MAC rolled back.",
        }

    # Finalise in DB
    confirm_mac_verified(serial, mac, workstation_id)
    logger.info("[%s] Provisioning SUCCESS — MAC %s verified.", serial, mac)

    pool = get_pool_status()
    return {
        "status": "success",
        "mac": mac,
        "low_pool": low_pool,
        "remaining": pool.get("remaining", 0),
    }


def _provision_retest(serial: str, current_mac: str) -> dict:
    """Handle a device that already has a unique MAC (re-test path)."""

    db_mac = get_assigned_mac(serial)

    if db_mac is None:
        # Unique MAC on device but nothing in DB → unknown provenance
        logger.error(
            "[%s] UNKNOWN DEVICE — has MAC %s but SN not found in DB.", serial, current_mac
        )
        return {
            "status": "error",
            "reason": "unknown_device",
            "current_mac": current_mac,
            "detail": (
                f"Device has MAC {current_mac!r} but serial {serial!r} has no DB record. "
                "Manual investigation required."
            ),
        }

    if current_mac != db_mac:
        logger.error(
            "[%s] MAC MISMATCH — DB has %s, device reports %s.", serial, db_mac, current_mac
        )
        return {
            "status": "error",
            "reason": "mac_mismatch",
            "db_mac": db_mac,
            "device_mac": current_mac,
            "detail": "Device MAC differs from DB record. Manual investigation required.",
        }

    logger.info("[%s] Re-test OK — MAC %s matches DB record.", serial, db_mac)
    return {"status": "retest_ok", "mac": db_mac}
