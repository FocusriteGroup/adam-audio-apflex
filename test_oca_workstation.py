import subprocess

def run(cmd):
    print(f"\n>>> {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)

DEVICE_NAME = "ASubsEV2"
DEVICE_IP = "169.254.42.86"
PORT = "50001"
SERVICE_HOST = "192.168.14.91"

# Discover
run(f"python adam_workstation.py --host {SERVICE_HOST} discover")

# Get mode
run(f"python adam_workstation.py --host {SERVICE_HOST} get_mode {DEVICE_NAME}")
run(f"python adam_workstation.py --host {SERVICE_HOST} get_mode {DEVICE_NAME} {PORT}")
#run(f"python adam_workstation.py --host {SERVICE_HOST} get_mode {DEVICE_IP} {PORT}")

# Set mode
run(f"python adam_workstation.py --host {SERVICE_HOST} set_mode internal-dsp {DEVICE_NAME}")
run(f"python adam_workstation.py --host {SERVICE_HOST} set_mode internal-dsp {DEVICE_NAME} {PORT}")
#run(f"python adam_workstation.py --host {SERVICE_HOST} set_mode internal-dsp {DEVICE_IP} {PORT}")

run(f"python adam_workstation.py --host {SERVICE_HOST} set_mode backplate {DEVICE_NAME}")
run(f"python adam_workstation.py --host {SERVICE_HOST} set_mode backplate {DEVICE_NAME} {PORT}")
#run(f"python adam_workstation.py --host {SERVICE_HOST} set_mode backplate {DEVICE_IP} {PORT}")

# Get gain calibration
run(f"python adam_workstation.py --host {SERVICE_HOST} get_gain_calibration {DEVICE_NAME}")
run(f"python adam_workstation.py --host {SERVICE_HOST} get_gain_calibration {DEVICE_NAME} {PORT}")
#run(f"python adam_workstation.py --host {SERVICE_HOST} get_gain_calibration {DEVICE_IP} {PORT}")

# Set gain calibration
run(f"python adam_workstation.py --host {SERVICE_HOST} set_gain_calibration 2.0 {DEVICE_NAME}")
run(f"python adam_workstation.py --host {SERVICE_HOST} set_gain_calibration 2.0 {DEVICE_NAME} {PORT}")
#run(f"python adam_workstation.py --host {SERVICE_HOST} set_gain_calibration 2.0 {DEVICE_IP} {PORT}")

# Get audio input
run(f"python adam_workstation.py --host {SERVICE_HOST} get_audio_input {DEVICE_NAME}")
run(f"python adam_workstation.py --host {SERVICE_HOST} get_audio_input {DEVICE_NAME} {PORT}")
#run(f"python adam_workstation.py --host {SERVICE_HOST} get_audio_input {DEVICE_IP} {PORT}")

# Set audio input
run(f"python adam_workstation.py --host {SERVICE_HOST} set_audio_input aes3 {DEVICE_NAME}")
run(f"python adam_workstation.py --host {SERVICE_HOST} set_audio_input aes3 {DEVICE_NAME} {PORT}")
#run(f"python adam_workstation.py --host {SERVICE_HOST} set_audio_input aes3 {DEVICE_IP} {PORT}")

run(f"python adam_workstation.py --host {SERVICE_HOST} set_audio_input analogue-xlr {DEVICE_NAME}")
run(f"python adam_workstation.py --host {SERVICE_HOST} set_audio_input analogue-xlr {DEVICE_NAME} {PORT}")
#run(f"python adam_workstation.py --host {SERVICE_HOST} set_audio_input analogue-xlr {DEVICE_IP} {PORT}")

# Test bass management in internal-dsp mode
print("\n=== Testing bass management in internal-dsp mode ===")
run(f"python adam_workstation.py --host {SERVICE_HOST} set_mode internal-dsp {DEVICE_NAME}")
run(f"python adam_workstation.py --host {SERVICE_HOST} get_mode {DEVICE_NAME}")

# Get bass management
run(f"python adam_workstation.py --host {SERVICE_HOST} get_bass_management {DEVICE_NAME}")
run(f"python adam_workstation.py --host {SERVICE_HOST} get_bass_management {DEVICE_NAME} {PORT}")

# Set bass management - cycle through all modes in internal-dsp
bass_modes = ["stereo-bass", "stereo", "wide", "lfe"]
for mode in bass_modes:
    run(f"python adam_workstation.py --host {SERVICE_HOST} set_bass_management {mode} {DEVICE_NAME}")
    run(f"python adam_workstation.py --host {SERVICE_HOST} get_bass_management {DEVICE_NAME}")

# Verify bass management is not settable in backplate mode
print("\n=== Verifying bass management in backplate mode ===")
run(f"python adam_workstation.py --host {SERVICE_HOST} set_mode backplate {DEVICE_NAME}")
run(f"python adam_workstation.py --host {SERVICE_HOST} get_mode {DEVICE_NAME}")

# Should still be able to get bass management state
run(f"python adam_workstation.py --host {SERVICE_HOST} get_bass_management {DEVICE_NAME}")

# Return to internal-dsp mode at the end
run(f"python adam_workstation.py --host {SERVICE_HOST} set_mode internal-dsp {DEVICE_NAME}")