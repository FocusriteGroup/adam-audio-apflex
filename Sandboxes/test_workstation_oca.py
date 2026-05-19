"""
test_workstation_oca.py

Smoke-test for OCA commands routed through adam_workstation.py CLI.

Usage:
    python Sandboxes/test_workstation_oca.py --target <device name or IP>

Each test invokes adam_workstation.py as a subprocess (exactly as Audio Precision
project scripts do) and checks the exit code + stdout.
"""

import argparse
import re
import subprocess
import sys
import os

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
WORKSTATION = os.path.join(REPO_ROOT, "adam_workstation.py")
PYTHON = sys.executable

# ── ANSI colour helpers ────────────────────────────────────────────────────────
_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_GREEN  = "\033[32m"
_RED    = "\033[31m"
_YELLOW = "\033[33m"
_CYAN   = "\033[36m"
_DIM    = "\033[2m"

def _c(text, *codes):
    return "".join(codes) + str(text) + _RESET

def section(title):
    print(f"\n{_c(f'── {title} ', _BOLD, _CYAN)}{_c('─' * (44 - len(title)), _DIM)}")

def run(label, *cmd_args):
    """Run adam_workstation.py with cmd_args, print coloured output, return (ok, stdout)."""
    cmd = [PYTHON, WORKSTATION] + list(str(a) for a in cmd_args)
    cmd_display = "adam_workstation.py " + " ".join(str(a) for a in cmd_args)

    print(f"\n  {_c('CMD', _BOLD)}  {_c(cmd_display, _DIM)}")

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()

        if proc.returncode == 0:
            print(f"  {_c('[ PASS ]', _BOLD, _GREEN)}  {label}")
            if stdout:
                print(f"  {_c('result', _DIM)}  {stdout}")
            return True, stdout
        else:
            print(f"  {_c('[ FAIL ]', _BOLD, _RED)}  {label}")
            if stdout:
                print(f"  {_c('stdout', _DIM)}  {stdout}")
            if stderr:
                # Only show the first meaningful error line from stderr
                first_err = next((l for l in stderr.splitlines() if l.strip() and not l.startswith("ERROR:")), stderr.splitlines()[0] if stderr else "")
                print(f"  {_c('stderr', _DIM)}  {_c(first_err, _RED)}")
            return False, None
    except Exception as exc:
        print(f"  {_c('[ FAIL ]', _BOLD, _RED)}  {label}")
        print(f"  {_c('error ', _DIM)}  {_c(exc, _RED)}")
        return False, None


def to_cli_string(s):
    return str(s).lower().replace(" ", "-")


def check_value(label, raw, validator=None):
    """Validate that the raw output is a non-empty value.
    Optionally run validator(value) -> bool for range/format checks.
    """
    value = (raw or "").strip()
    if not value or value == "None":
        print(f"  {_c('[WARN]', _YELLOW, _BOLD)}  {label}: empty or None value")
        return False
    if validator and not validator(value):
        print(f"  {_c('[WARN]', _YELLOW, _BOLD)}  {label}: value '{value}' failed validation")
        return False
    print(f"  {_c('[VAL ]', _BOLD, _GREEN)}  {label}: {value}")
    return True


def readback(label, expected, *get_cmd_args):
    """Run a get command silently and verify the returned value matches expected."""
    cmd = [PYTHON, WORKSTATION] + list(str(a) for a in get_cmd_args)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
        actual = proc.stdout.strip()
    except Exception as exc:
        print(f"  {_c('[FAIL]', _BOLD, _RED)}  readback {label}: {exc}")
        return False
    if not actual:
        print(f"  {_c('[FAIL]', _BOLD, _RED)}  readback {label}: empty response")
        return False
    try:
        match = float(actual) == float(str(expected))
    except (ValueError, TypeError):
        match = str(actual) == str(expected)
    if match:
        print(f"  {_c('[RDBK]', _BOLD, _GREEN)}  {label}: {actual}")
        return True
    print(f"  {_c('[FAIL]', _BOLD, _RED)}  readback {label}: expected '{expected}', got '{actual}'")
    return False


def main():
    parser = argparse.ArgumentParser(description="Workstation OCA smoke test")
    parser.add_argument("--target", required=True, help="OCA device name or IP address")
    args = parser.parse_args()
    target = args.target

    print(_c(f"\nOCA Workstation Smoke Test  —  target: {target}", _BOLD))

    results = {}

    # ── Discovery ──────────────────────────────────────────────────────────────
    section("Discovery")
    ok, _ = run("discover", "discover")
    results["discover"] = ok

    # ── Gain Calibration ───────────────────────────────────────────────────────
    section("Gain Calibration")
    ok, raw = run("get_gain_calibration", "get_gain_calibration", target)
    results["get_gain_calibration"] = ok

    ok, _ = run("set_gain_calibration(0)", "set_gain_calibration", 0, target)
    results["set_gain_calibration"] = ok
    if ok:
        results["set_gain_calibration_verify"] = readback(
            "gain_calibration=0", 0,
            "get_gain_calibration", target
        )

    # ── Mode ───────────────────────────────────────────────────────────────────
    section("Mode")
    ok, raw = run("get_mode", "get_mode", target)
    results["get_mode"] = ok
    current_mode = to_cli_string(raw) if raw else "backplate"
    results["get_mode_value"] = check_value("mode value", raw)

    ok, _ = run(f"set_mode('{current_mode}')", "set_mode", current_mode, target)
    results["set_mode"] = ok
    if ok:
        results["set_mode_verify"] = readback(
            f"mode='{current_mode}'", current_mode,
            "get_mode", target
        )

    # ── Audio Input ────────────────────────────────────────────────────────────
    section("Audio Input")
    ok, raw = run("get_audio_input", "get_audio_input", target)
    results["get_audio_input"] = ok
    original_input = to_cli_string(raw) if raw else "analogue-xlr"
    results["get_audio_input_value"] = check_value("input_mode value", raw)

    for mode in ("aes3", "analogue-xlr"):
        ok, _ = run(f"set_audio_input('{mode}')", "set_audio_input", mode, target)
        results[f"set_audio_input_{mode}"] = ok
        if ok:
            results[f"set_audio_input_{mode}_verify"] = readback(
                f"audio_input='{mode}'", mode,
                "get_audio_input", target
            )

    run("set_audio_input(restore)", "set_audio_input", original_input, target)

    # ── Bass Management ────────────────────────────────────────────────────────
    section("Bass Management")
    ok, raw = run("get_bass_management", "get_bass_management", target)
    results["get_bass_management"] = ok
    original_bm = to_cli_string(raw) if raw else "wide"
    results["get_bass_management_value"] = check_value("bass_management_mode value", raw)

    for position in ("stereo", "wide", "lfe"):
        ok, _ = run(f"set_bass_management('{position}')", "set_bass_management", position, target)
        results[f"set_bass_management_{position}"] = ok
        if ok:
            results[f"set_bass_management_{position}_verify"] = readback(
                f"bass_management='{position}'", position,
                "get_bass_management", target
            )

    run("set_bass_management(restore)", "set_bass_management", original_bm, target)

    # ── Bass Management Bypass ───────────────────────────────────────
    section("Bass Management Bypass")
    ok, raw = run("get_bass_management_bypass", "get_bass_management_bypass", target)
    results["get_bass_management_bypass"] = ok
    original_bypass = raw if raw else None
    results["get_bass_management_bypass_value"] = check_value(
        "bypass_state value", raw,
        validator=lambda v: v in ("enabled", "disabled")
    )

    for state in ("enabled", "disabled"):
        ok, _ = run(f"set_bass_management_bypass('{state}')", "set_bass_management_bypass", state, target)
        results[f"set_bass_management_bypass_{state}"] = ok
        if ok:
            results[f"set_bass_management_bypass_{state}_verify"] = readback(
                f"bypass='{state}'", state,
                "get_bass_management_bypass", target
            )

    if original_bypass:
        run("set_bass_management_bypass(restore)", "set_bass_management_bypass", original_bypass, target)

    # ── Gain ───────────────────────────────────────────────────────────────────
    section("Gain")
    ok, raw = run("get_gain", "get_gain", target)
    results["get_gain"] = ok
    original_gain = float(raw) if raw else -12.0
    results["get_gain_value"] = check_value("gain value", raw,
        validator=lambda v: -24 <= float(v) <= 6)

    ok, _ = run("set_gain(-12)", "set_gain", -12, target)
    results["set_gain"] = ok
    if ok:
        results["set_gain_verify"] = readback(
            "gain=-12", -12,
            "get_gain", target
        )

    run("set_gain(restore)", "set_gain", original_gain, target)

    # ── Phase Delay ────────────────────────────────────────────────────────────
    section("Phase Delay")
    ok, raw = run("get_phase_delay", "get_phase_delay", target)
    results["get_phase_delay"] = ok
    results["get_phase_delay_value"] = check_value("phase_delay value", raw,
        validator=lambda v: int(v) in (0, 45, 90, 135, 180, 225, 270, 315))

    ok, _ = run("set_phase_delay('deg0')", "set_phase_delay", "deg0", target)
    results["set_phase_delay"] = ok
    if ok:
        results["set_phase_delay_verify"] = readback(
            "phase_delay=0", 0,
            "get_phase_delay", target
        )

    # ── Mute ───────────────────────────────────────────────────────────────────
    section("Mute")
    ok, raw = run("get_mute", "get_mute", target)
    results["get_mute"] = ok
    results["get_mute_value"] = check_value("mute_state value", raw,
        validator=lambda v: v in ("normal", "mute"))

    ok, _ = run("set_mute('mute')", "set_mute", "mute", target)
    results["set_mute_mute"] = ok
    if ok:
        results["set_mute_mute_verify"] = readback(
            "mute_state='mute'", "mute",
            "get_mute", target
        )

    ok, _ = run("set_mute('normal')", "set_mute", "normal", target)
    results["set_mute_normal"] = ok
    if ok:
        results["set_mute_normal_verify"] = readback(
            "mute_state='normal'", "normal",
            "get_mute", target
        )

    # ── MAC Address ────────────────────────────────────────────────────────────
    section("MAC Address")
    ok, raw = run("get_mac_address", "get_mac_address", target)
    results["get_mac_address"] = ok
    original_mac = raw if re.match(r"^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$", raw or "") else None
    results["get_mac_address_value"] = check_value("mac value", raw,
        validator=lambda v: bool(re.match(r"^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$", v)))

    if original_mac:
        ok, _ = run(f"set_mac_address('{original_mac}')", "set_mac_address", original_mac, target)
        results["set_mac_address"] = ok
        if ok:
            results["set_mac_address_verify"] = readback(
                f"mac='{original_mac}'", original_mac,
                "get_mac_address", target
            )
    else:
        print(f"  {_c('[SKIP]', _YELLOW, _BOLD)}  set_mac_address — could not parse MAC from get response")
        results["set_mac_address"] = False

    # ── Serial Number ──────────────────────────────────────────────────────────
    section("Serial Number")
    ok, raw = run("get_serial_number", "get_serial_number", target)
    results["get_serial_number"] = ok
    original_serial = raw if raw else None
    results["get_serial_number_value"] = check_value("serial value", raw,
        validator=lambda v: len(v) > 0)

    if original_serial:
        ok, _ = run(f"set_serial_number('{original_serial}')", "set_serial_number", original_serial, target)
        results["set_serial_number"] = ok
        if ok:
            results["set_serial_number_verify"] = readback(
                f"serial='{original_serial}'", original_serial,
                "get_serial_number", target
            )
    else:
        print(f"  {_c('[SKIP]', _YELLOW, _BOLD)}  set_serial_number — could not parse serial from get response")
        results["set_serial_number"] = False

    # ── Model Description ──────────────────────────────────────────────────────
    section("Model Description")
    ok, raw = run("get_model_description", "get_model_description", target)
    results["get_model_description"] = ok
    results["get_model_description_model"] = check_value("model", raw)

    # ── Summary ────────────────────────────────────────────────────────────────
    passed = sum(v for v in results.values())
    total  = len(results)
    bar    = "═" * 50
    print(f"\n  {_c(bar, _BOLD)}")
    print(f"  {_c('SUMMARY', _BOLD)}")
    print(f"  {bar}")
    for name, ok in results.items():
        tag   = _c("  PASS", _GREEN, _BOLD) if ok else _c("  FAIL", _RED, _BOLD)
        label = _c(name, _DIM) if ok else _c(name, _RED)
        print(f"  {tag}  {label}")
    print(f"  {bar}")
    colour = _GREEN if passed == total else _RED
    print(f"  {_c(f'{passed}/{total} checks passed', _BOLD, colour)}")
    print(f"  {_c(bar, _BOLD)}\n")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
