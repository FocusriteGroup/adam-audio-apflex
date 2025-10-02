"""
Honeywell Scanner Control

Specialized control for Honeywell barcode scanners used in 
Audio Precision production line for serial number scanning.
"""
from .serial_device import SerialDevice
import time
import logging

SCANNER_LOGGER = logging.getLogger("HoneywellScanner")

class HoneywellScanner(SerialDevice):
    """Class for managing a Honeywell scanner device."""

    def __init__(self, baudrate=9600, product_id=0x0B6A, vendor_id=0x0C2E, timeout=10, retry_interval=2, on_connect=None, on_disconnect=None):
        """
        Initialize the HoneywellScanner.

        Args:
            baudrate (int): The baud rate for the serial communication (default: 9600).
            product_id (int): The Product ID of the scanner in hexadecimal.
            vendor_id (int): The Vendor ID of the scanner in hexadecimal.
            timeout (float): Timeout for reading from the serial port in seconds.
            retry_interval (int): Time in seconds to wait before retrying connection.
            on_connect (callable): Callback function for successful connection.
            on_disconnect (callable): Callback function for disconnection.
        """
        super().__init__(baudrate, product_id, vendor_id, timeout, retry_interval, on_connect, on_disconnect)
        self.serial_number = None  # Property to store the scanned serial number

    def trigger_scan(self):
        """
        Trigger a scan and store the scanned serial number.

        Returns:
            str: The scanned serial number, or None if the scan fails.
        """
        with self._lock:  # Protect shared resources
            if not self.connected or not self.serial_connected or not self.serial_connection or not self.serial_connection.is_open:
                SCANNER_LOGGER.warning("trigger_scan: Scanner not connected.")
                return None
            try:
                self.serial_connection.reset_input_buffer()
                self.serial_connection.write(bytes([0x16, ord('T'), 0x0D]))  # SYN T CR
                time.sleep(0.5)
                response = self.serial_connection.readline()
                if response:
                    self.serial_number = response.decode(errors='ignore').strip()
                    SCANNER_LOGGER.info(f"Scanned serial number: {self.serial_number}")
                    return self.serial_number
            except Exception as e:
                SCANNER_LOGGER.error(f"Error during scan: {e}")
                self.serial_connected = False
            return None