"""
test_mac_stress.py

Stress test for the SubPro MAC address provisioning write → read-back verification.

What is tested:
  - Many provisioning cycles in sequence
  - Variable ARP_FLUSH_DELAY (0 s … 3 s) to find the minimum viable delay
  - OCA communication reliability under rapid successive calls
  - Read-back consistency: every provisioned MAC is confirmed via RETEST_OK

Each parametrized case runs CYCLES_PER_DELAY independent provisioning cycles
at a fixed delay, measures timing, and reports:
  - Success rate
  - VERIFY_FAILED count (read-back didn't match written MAC)
  - OCA error count
  - Average / min / max cycle time
  - Per-delay pass/fail verdict

Run from workspace root:
    $pytest = ".venv\\Scripts\\pytest.exe"
    & $pytest SubProMACAddresses/test_mac_stress.py -v `
        --html=logs/mac_stress/report.html `
        --self-contained-html `
        --junitxml=logs/mac_stress/junit.xml

Requirements:
    pip install pytest pytest-html
"""

import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HERE          = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_ROOT = os.path.dirname(_HERE)
WORKSTATION    = os.path.join(WORKSPACE_ROOT, "adam_workstation.py")
DB_PATH        = os.path.join(_HERE, "db", "mac_addresses.db")
LOG_DIR        = os.path.join(WORKSPACE_ROOT, "logs", "mac_stress")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TARGET          = "ASubsDV1"

# Large range — enough for all stress cycles without exhaustion
MAC_RANGE_START = "02:FE:ED:01:00:00"
MAC_RANGE_END   = "02:FE:ED:01:FF:FF"   # 65 536 MACs
WARN_THRESHOLD  = 100

# ARP delays to test (seconds).
# 0.0 = maximum stress; 3.0 = production default.
DELAYS = [0.0, 0.5, 1.0, 2.0, 3.0]

# Number of full provision → verify cycles per delay value
CYCLES_PER_DELAY = 5

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


def db_exec(sql, params=()):
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA journal_mode=DELETE")
    con.execute(sql, params)
    con.commit()
    con.close()


def db_query(sql, params=()):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute(sql, params).fetchall()]
    con.close()
    return rows


# ---------------------------------------------------------------------------
# Session fixture — runs setup / teardown exactly once for all stress tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def stress_state():
    """
    One-time setup: init DB, configure MAC range, read device serial + MAC.
    Teardown: restore device to its initial MAC.
    """
    os.makedirs(LOG_DIR, exist_ok=True)

    run("init_mac_db")
    db_exec("DELETE FROM mac_range")
    db_exec("DELETE FROM provisioning_log")
    run("set_mac_range", MAC_RANGE_START, MAC_RANGE_END,
        f"--warn-threshold={WARN_THRESHOLD}")

    serial      = str(run("get_serial_number", TARGET)).strip()
    initial_mac = str(run("get_mac_address",   TARGET)).strip()

    state = {
        "serial":      serial,
        "initial_mac": initial_mac,
        "default_mac": initial_mac,
    }

    yield state

    # Restore device to initial MAC after all stress tests
    run("set_mac_address", state["initial_mac"], TARGET)


# ---------------------------------------------------------------------------
# Parametrized stress test
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("arp_delay", DELAYS)
def test_readback_stress(stress_state, arp_delay, cycles, record_property):
    """
    Run CYCLES_PER_DELAY provisioning cycles at the given arp_delay.

    Each cycle:
      1. Reset device to default_mac
      2. provision_mac  → expect 'success'  (MAC written + read-back verified)
      3. provision_mac  → expect 'retest_ok' (confirms device holds the MAC)
      4. Clean up DB entry (keep next_mac pointer advancing — WAI)
    """
    s = stress_state
    delay_label = f"{arp_delay:.1f}s"

    cycle_stats = []

    for i in range(cycles):
        # Unique synthetic serial per cycle — avoids duplicate_sn across runs
        cycle_serial = f"SN-STRESS-D{int(arp_delay * 10):02d}-{i:04d}"

        # --- Reset device to default MAC ---
        run("set_mac_address", s["default_mac"], TARGET)

        # --- Provision ---
        t0     = time.monotonic()
        result = run("provision_mac", TARGET, cycle_serial, s["default_mac"],
                     f"--arp-delay={arp_delay}")
        elapsed = round(time.monotonic() - t0, 3)

        status = "success" if result == "successful" else "error"
        reason = result if result != "successful" else ""
        mac    = ""

        stat = {
            "cycle":        i,
            "serial":       cycle_serial,
            "delay_s":      arp_delay,
            "elapsed_s":    elapsed,
            "status":       status,
            "reason":       reason,
            "mac":          mac,
            "retest_status": "",
        }

        # --- Verify read-back via RETEST_OK ---
        if status == "success":
            retest = run("provision_mac", TARGET, cycle_serial, s["default_mac"],
                         f"--arp-delay={arp_delay}")
            stat["retest_status"] = "retest_ok" if retest == "successful" else "error"

        cycle_stats.append(stat)
        print(
            f"  [{delay_label}] cycle {i:02d}: {status}"
            + (f" → retest={stat['retest_status']}" if status == "success" else f" ({reason})")
            + f"  ({elapsed:.2f}s)"
        )

        # Clean up DB entry (MAC pointer stays advanced — this is intentional)
        db_exec("DELETE FROM provisioning_log WHERE serial=?", (cycle_serial,))

    # -----------------------------------------------------------------------
    # Statistics
    # -----------------------------------------------------------------------
    n               = len(cycle_stats)
    n_success       = sum(1 for r in cycle_stats if r["status"] == "success")
    n_verify_failed = sum(1 for r in cycle_stats if "verification failed" in r["reason"])
    n_oca_error     = sum(1 for r in cycle_stats if "OCA communication" in r["reason"])
    n_retest_ok     = sum(1 for r in cycle_stats if r["retest_status"] == "retest_ok")
    times           = [r["elapsed_s"] for r in cycle_stats]
    avg_t           = round(sum(times) / n, 3)
    min_t           = round(min(times), 3)
    max_t           = round(max(times), 3)

    # Attach stats to pytest-html report
    record_property("arp_delay_s",    arp_delay)
    record_property("cycles",         n)
    record_property("success",        n_success)
    record_property("verify_failed",  n_verify_failed)
    record_property("oca_errors",     n_oca_error)
    record_property("retest_ok",      n_retest_ok)
    record_property("avg_time_s",     avg_t)
    record_property("min_time_s",     min_t)
    record_property("max_time_s",     max_t)

    summary = (
        f"\n{'─'*60}\n"
        f"  delay={delay_label}  cycles={n}\n"
        f"  success={n_success}  verify_failed={n_verify_failed}  oca_errors={n_oca_error}\n"
        f"  retest_ok={n_retest_ok}\n"
        f"  time: avg={avg_t}s  min={min_t}s  max={max_t}s\n"
        f"{'─'*60}"
    )
    print(summary)

    # Write per-delay CSV
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(LOG_DIR, f"stress_delay{int(arp_delay*10):02d}_{ts}.csv")
    import csv
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(cycle_stats[0].keys()))
        writer.writeheader()
        writer.writerows(cycle_stats)

    # -----------------------------------------------------------------------
    # Assertions
    # -----------------------------------------------------------------------
    assert n_success == n, (
        f"delay={delay_label}: only {n_success}/{n} cycles succeeded "
        f"(verify_failed={n_verify_failed}, oca_errors={n_oca_error})"
    )
    assert n_retest_ok == n_success, (
        f"delay={delay_label}: RETEST_OK mismatch — "
        f"{n_retest_ok}/{n_success} passed read-back confirmation"
    )


# ---------------------------------------------------------------------------
# MAC arithmetic helpers
# ---------------------------------------------------------------------------

def _mac_int(mac_str: str) -> int:
    """Convert 'AA:BB:CC:DD:EE:FF' to integer."""
    return int(mac_str.replace(":", ""), 16)


def _int_mac(n: int) -> str:
    """Convert integer to 'AA:BB:CC:DD:EE:FF' string."""
    h = f"{n:012X}"
    return ":".join(h[i:i + 2] for i in range(0, 12, 2))


# ---------------------------------------------------------------------------
# Exhaustion test
# ---------------------------------------------------------------------------

# Start of the dedicated exhaustion MAC range (separate from stress range)
EXHAUST_START = "02:FE:ED:03:00:00"


def test_exhaustion_and_beyond(stress_state, mac_count, record_property):
    """
    Fill the MAC pool to capacity, then attempt one more provisioning.

    Flow:
      1. Re-configure the DB with a pool of exactly mac_count MACs.
      2. Provision mac_count devices (unique synthetic serials) — all must succeed.
      3. Attempt one more provisioning — must return 'pool_exhausted' error.

    Controls:
      --mac-count N   size of the pool (default: 10)

    The ARP delay is set to 0 s for speed; OCA write reliability was already
    validated by test_readback_stress.
    """
    s = stress_state
    exhaust_end = _int_mac(_mac_int(EXHAUST_START) + mac_count - 1)

    # Re-configure DB: dedicated range of exactly mac_count MACs
    db_exec("DELETE FROM mac_range")
    db_exec("DELETE FROM provisioning_log")
    run("set_mac_range", EXHAUST_START, exhaust_end, "--warn-threshold=1")

    print(
        f"\n  Exhaustion test: pool = {mac_count} MACs "
        f"({EXHAUST_START} \u2192 {exhaust_end})"
    )

    # --- Provision all mac_count MACs ---
    success_count = 0
    for i in range(mac_count):
        cycle_serial = f"SN-EXHAUST-{i:04d}"
        run("set_mac_address", s["default_mac"], TARGET)
        result = run("provision_mac", TARGET, cycle_serial, s["default_mac"],
                     "--arp-delay=0.0")
        if result == "successful":
            success_count += 1
            print(f"  [{i+1:>{len(str(mac_count))}}/{mac_count}] {cycle_serial}: successful")
        else:
            pytest.fail(f"Cycle {i} failed unexpectedly before pool exhaustion: {result!r}")

    assert success_count == mac_count, \
        f"Expected {mac_count} successes, got {success_count}"

    pool = run("get_mac_pool_status")
    print(f"\n  Pool status after full provisioning: {pool}")
    assert pool.get("remaining", -1) == 0, \
        f"Pool should report 0 remaining after exhaustion, got: {pool}"

    # --- One beyond the limit ---
    run("set_mac_address", s["default_mac"], TARGET)
    beyond = run("provision_mac", TARGET, "SN-EXHAUST-BEYOND", s["default_mac"],
                 "--arp-delay=0.0")

    assert isinstance(beyond, str), f"Expected error string, got: {beyond!r}"
    assert "pool exhausted" in beyond.lower(), \
        f"Expected pool_exhausted error, got: {beyond!r}"
    print(f"\n  Beyond-exhaustion correctly returned: {beyond!r}")

    record_property("mac_count",          mac_count)
    record_property("success_count",      success_count)
    record_property("beyond_result",      beyond)
    record_property("exhaustion_verified", True)
