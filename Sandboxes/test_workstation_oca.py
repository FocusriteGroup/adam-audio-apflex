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

    # ── Mode ───────────────────────────────────────────────────────────────────
    section("Mode")
    ok, raw = run("get_mode", "get_mode", target)
    results["get_mode"] = ok
    mode_match = re.search(r"'mode':\s*'([^']+)'", raw or "")
    current_mode = to_cli_string(mode_match.group(1)) if mode_match else "backplate"

    ok, _ = run(f"set_mode('{current_mode}')", "set_mode", current_mode, target)
    results["set_mode"] = ok

    # ── Audio Input ────────────────────────────────────────────────────────────
    section("Audio Input")
    ok, raw = run("get_audio_input", "get_audio_input", target)
    results["get_audio_input"] = ok
    input_match = re.search(r"'input_mode':\s*'([^']+)'", raw or "")
    original_input = to_cli_string(input_match.group(1)) if input_match else "analogue-xlr"

    for mode in ("aes3", "analogue-xlr"):
        ok, _ = run(f"set_audio_input('{mode}')", "set_audio_input", mode, target)
        results[f"set_audio_input_{mode}"] = ok

    run("set_audio_input(restore)", "set_audio_input", original_input, target)

    # ── Bass Management ────────────────────────────────────────────────────────
    section("Bass Management")
    ok, raw = run("get_bass_management", "get_bass_management", target)
    results["get_bass_management"] = ok
    bm_match = re.search(r"'bass_management_mode':\s*'([^']+)'", raw or "")
    original_bm = to_cli_string(bm_match.group(1)) if bm_match else "wide"

    for position in ("stereo-bass", "stereo", "wide"):
        ok, _ = run(f"set_bass_management('{position}')", "set_bass_management", position, target)
        results[f"set_bass_management_{position}"] = ok

    run("set_bass_management(restore)", "set_bass_management", original_bm, target)

    # ── Gain ───────────────────────────────────────────────────────────────────
    section("Gain")
    ok, raw = run("get_gain", "get_gain", target)
    results["get_gain"] = ok
    gain_match = re.search(r"'gain':\s*([-\d.]+)", raw or "")
    original_gain = float(gain_match.group(1)) if gain_match else -12.0

    ok, _ = run("set_gain(-12)", "set_gain", -12, target)
    results["set_gain"] = ok

    run("set_gain(restore)", "set_gain", original_gain, target)

    # ── Phase Delay ────────────────────────────────────────────────────────────
    section("Phase Delay")
    ok, raw = run("get_phase_delay", "get_phase_delay", target)
    results["get_phase_delay"] = ok

    ok, _ = run("set_phase_delay('deg0')", "set_phase_delay", "deg0", target)
    results["set_phase_delay"] = ok

    # ── Mute ───────────────────────────────────────────────────────────────────
    section("Mute")
    ok, _ = run("get_mute", "get_mute", target)
    results["get_mute"] = ok

    ok, _ = run("set_mute('mute')", "set_mute", "mute", target)
    results["set_mute_mute"] = ok

    ok, _ = run("set_mute('normal')", "set_mute", "normal", target)
    results["set_mute_normal"] = ok

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
