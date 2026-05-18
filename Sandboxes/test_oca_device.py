"""
test_oca_device.py

Manual smoke-test for all OCADevice methods.

Usage:
    python Sandboxes/test_oca_device.py --target <IP or device name>

The script runs every get/set command in sequence and prints PASS / FAIL for each one.
Set commands restore the original value where possible.
"""

import argparse
import logging
import sys
import os

# Make sure the repo root is on sys.path regardless of where the script is run from
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from oca.oca_device import OCADevice

logging.basicConfig(level=logging.WARNING)  # suppress verbose library output

PASS = "PASS"
FAIL = "FAIL"


def check(label, fn, *args, **kwargs):
    """Call fn(*args, **kwargs), print PASS/FAIL, return (ok, result)."""
    try:
        result = fn(*args, **kwargs)
        print(f"  [{PASS}] {label}")
        print(f"         result: {result}")
        return True, result
    except Exception as exc:
        print(f"  [{FAIL}] {label}")
        print(f"         error : {exc}")
        return False, None


# ── Helpers to extract CLI-compatible scalar values from result dicts ──────────

def _to_cli_string(s):
    """Convert a human-readable string like 'Analogue XLR' to 'analogue-xlr'."""
    return str(s).lower().replace(" ", "-")


def extract_gain_calibration(result):
    if isinstance(result, dict) and "calibration_values" in result:
        return result["calibration_values"][0]
    return result


def extract_mode(result):
    if isinstance(result, dict) and "mode" in result:
        return _to_cli_string(result["mode"])
    return result


def extract_audio_input(result):
    if isinstance(result, dict) and "input_mode" in result:
        return _to_cli_string(result["input_mode"])
    return result


def extract_bass_management(result):
    if isinstance(result, dict) and "bass_management_mode" in result:
        return _to_cli_string(result["bass_management_mode"])
    return result


def extract_gain(result):
    if isinstance(result, dict) and "gain" in result:
        return result["gain"]
    return result


def extract_phase_delay(result):
    """Phase delay get returns None currently; fall back to 'deg0'."""
    if isinstance(result, dict) and "phase_delay" in result:
        return _to_cli_string(result["phase_delay"])
    return "deg0"


def main():
    parser = argparse.ArgumentParser(description="OCADevice smoke test")
    parser.add_argument(
        "--target",
        required=True,
        help="IP address or device name of the OCA device under test",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=50001,
        help="OCA port (default: 50001)",
    )
    args = parser.parse_args()

    device = OCADevice(target=args.target, port=args.port)

    results = {}

    # ── Discovery ──────────────────────────────────────────────────────────────
    print("\n[Discovery]")
    ok, _ = check("discover()", device.discover)
    results["discover"] = ok

    # ── Gain Calibration ───────────────────────────────────────────────────────
    print("\n[Gain Calibration]")
    ok, raw = check("get_gain_calibration()", device.get_gain_calibration)
    results["get_gain_calibration"] = ok
    original_gain_cal = extract_gain_calibration(raw)

    ok, _ = check("set_gain_calibration(0)", device.set_gain_calibration, 0)
    results["set_gain_calibration"] = ok

    if original_gain_cal is not None:
        check("set_gain_calibration(restore)", device.set_gain_calibration, original_gain_cal)

    # ── Mode ───────────────────────────────────────────────────────────────────
    print("\n[Mode]")
    ok, raw = check("get_mode()", device.get_mode)
    results["get_mode"] = ok
    original_mode = extract_mode(raw)

    ok, _ = check(f"set_mode('{original_mode}')", device.set_mode, original_mode or "backplate")
    results["set_mode"] = ok

    # ── Audio Input ────────────────────────────────────────────────────────────
    print("\n[Audio Input]")
    ok, raw = check("get_audio_input()", device.get_audio_input)
    results["get_audio_input"] = ok
    original_input = extract_audio_input(raw)

    for position in ("aes3", "analogue-xlr"):
        ok, _ = check(f"set_audio_input('{position}')", device.set_audio_input, position)
        results[f"set_audio_input_{position}"] = ok

    if original_input is not None:
        check("set_audio_input(restore)", device.set_audio_input, original_input)

    # ── Bass Management ────────────────────────────────────────────────────────
    print("\n[Bass Management]")
    ok, raw = check("get_bass_management()", device.get_bass_management)
    results["get_bass_management"] = ok
    original_bm = extract_bass_management(raw)

    for position in ("stereo-bass", "stereo", "wide"):
        ok, _ = check(f"set_bass_management('{position}')", device.set_bass_management, position)
        results[f"set_bass_management_{position}"] = ok

    if original_bm is not None:
        check("set_bass_management(restore)", device.set_bass_management, original_bm)

    # ── Gain ───────────────────────────────────────────────────────────────────
    print("\n[Gain]")
    ok, raw = check("get_gain()", device.get_gain)
    results["get_gain"] = ok
    original_gain = extract_gain(raw)

    ok, _ = check("set_gain(-12)", device.set_gain, -12)
    results["set_gain"] = ok

    if original_gain is not None:
        check("set_gain(restore)", device.set_gain, original_gain)

    # ── Phase Delay ────────────────────────────────────────────────────────────
    print("\n[Phase Delay]")
    ok, raw = check("get_phase_delay()", device.get_phase_delay)
    results["get_phase_delay"] = ok
    original_phase = extract_phase_delay(raw)

    ok, _ = check(f"set_phase_delay('{original_phase}')", device.set_phase_delay, original_phase)
    results["set_phase_delay"] = ok

    # ── Mute ───────────────────────────────────────────────────────────────────
    print("\n[Mute]")
    ok, raw = check("get_mute()", device.get_mute)
    results["get_mute"] = ok
    original_mute = raw  # mute get currently returns raw; pass through as-is

    ok, _ = check("set_mute('true')", device.set_mute, "true")
    results["set_mute_true"] = ok

    ok, _ = check("set_mute('false')", device.set_mute, "false")
    results["set_mute_false"] = ok

    if original_mute is not None:
        check("set_mute(restore)", device.set_mute, original_mute)

    # ── Summary ────────────────────────────────────────────────────────────────
    passed = sum(v for v in results.values())
    total = len(results)
    print(f"\n{'='*50}")
    print(f"Result: {passed}/{total} checks passed")
    if passed < total:
        failed = [k for k, v in results.items() if not v]
        print(f"Failed : {', '.join(failed)}")
    print("="*50)

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
