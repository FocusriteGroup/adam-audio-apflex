from ap_utils import HoneywellScanner, SwitchBox
import time

# Helper function to wait for the connection
def wait_for_connection(device, timeout=10):
    """
    Wait for the device to connect.

    Args:
        device: The serial device instance (e.g., HoneywellScanner or SwitchBox).
        timeout (int): Maximum time to wait for the connection in seconds.

    Raises:
        TimeoutError: If the device fails to connect within the timeout period.
    """
    start_time = time.time()
    while not device.connected:
        if time.time() - start_time > timeout:
            raise TimeoutError("Device failed to connect within the timeout period.")
        print("[INFO] Waiting for device to connect...")
        time.sleep(0.5)  # Check connection status every 0.5 seconds
    print("[INFO] Device connected!")

# Test HoneywellScanner
def test_honeywell_scanner():
    scanner = HoneywellScanner(
        timeout=10,
        retry_interval=2
    )
    wait_for_connection(scanner)  # Wait for the scanner to connect
    print("Triggering scan...")
    serial_number = scanner.trigger_scan()
    if serial_number:
        print(f"[INFO] Scanned Serial Number: {serial_number}")
    else:
        print("[WARN] No serial number scanned.")

# Test SwitchBox
def test_switchbox():
    switchbox = SwitchBox(
        timeout=3,
        retry_interval=5
    )
    wait_for_connection(switchbox)  # Wait for the SwitchBox to connect

    print("Switching to Channel 1...")
    switchbox.switch_to_channel(1)
    time.sleep(1)  # Delay to allow the command to take effect

    print("Switching to Channel 2...")
    switchbox.switch_to_channel(2)
    time.sleep(1)  # Delay to allow the command to take effect

    print("Opening the box...")
    switchbox.open_box()
    time.sleep(1)  # Delay to allow the command to take effect

    print("Getting status...")
    status = switchbox.get_status()
    print(f"Status: {status}")

if __name__ == "__main__":
    try:
        print("Testing Honeywell Scanner...")
        test_honeywell_scanner()
        print("\nTesting SwitchBox...")
        test_switchbox()
    except TimeoutError as e:
        print(f"[ERROR] {e}")
    except Exception as e:
        print(f"[ERROR] An unexpected error occurred: {e}")