"""
Base Serial Device Control

Provides the foundation for all serial communication devices
in the ADAM Audio production environment.
"""
import os
import datetime
import serial
import serial.tools.list_ports
import threading
import time
import logging

SERIALDEVICE_LOGGER = logging.getLogger("SerialDevice")

class SerialDevice:
    """Base class for serial devices with connection management."""

    def __init__(self, baudrate=9600, product_id=None, vendor_id=None, timeout=3, retry_interval=2, on_connect=None, on_disconnect=None):
        """
        Initialize the SerialDevice.

        Args:
            baudrate (int): The baud rate for the serial communication (default: 9600).
            product_id (int): The Product ID of the device in hexadecimal (e.g., 0x0B6A).
            vendor_id (int): The Vendor ID of the device in hexadecimal (e.g., 0x0C2E).
            timeout (float): Timeout for reading from the serial port in seconds.
            retry_interval (int): Time in seconds to wait before retrying connection.
            on_connect (callable): Callback function for successful connection.
            on_disconnect (callable): Callback function for disconnection.
        """
        self.baudrate = baudrate
        self.product_id = product_id
        self.vendor_id = vendor_id
        self.timeout = timeout
        self.retry_interval = retry_interval
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect

        self.connected = False  # Indicates if the device is physically connected
        self.serial_connected = False  # Indicates if the serial connection is established
        self.serial_connection = None  # Serial connection object

        self._stop = True  # Flag to control the monitoring thread
        self._current_port = None  # Stores the current port of the device

        # Thread for monitoring device connection
        self._monitor_thread = None

        self._lock = threading.Lock()  # Lock to prevent race conditions

        # Start monitoring automatically upon initialization
        self.start_monitoring()

    def _monitor_device(self):
        """
        Monitor the connection status of the device.

        This method runs in a separate thread and continuously checks if the device
        is physically connected. It triggers the `on_connect` and `on_disconnect`
        callbacks when the connection status changes.
        """
        while not self._stop:
            with self._lock:
                # Check if the device is physically connected
                device_found = self._check_device_connection()
                if device_found and not self.connected:
                    self.connected = True
                    SERIALDEVICE_LOGGER.info("Device physically connected.")
                    if self.on_connect:
                        self.on_connect()
                elif not device_found and self.connected:
                    self.connected = False
                    SERIALDEVICE_LOGGER.info("Device physically disconnected.")
                    if self.on_disconnect:
                        self.on_disconnect()

                # Ensure serial_connected is reset if the device is disconnected
                if not self.connected and self.serial_connected:
                    self.serial_connected = False
                    SERIALDEVICE_LOGGER.info("Serial connection reset due to physical disconnection.")

            time.sleep(self.retry_interval)

    def _check_device_connection(self):
        """
        Check if the device with the specified vendor_id and product_id is connected.

        Returns:
            bool: True if the device is found, False otherwise.
        """
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if port.vid == self.vendor_id and port.pid == self.product_id:
                self._current_port = port.device
                return True
        self._current_port = None
        return False

    def start_monitoring(self):
        """
        Start the device monitoring thread.

        This thread continuously checks if the device is physically connected.
        """
        if self._monitor_thread is None or not self._monitor_thread.is_alive():
            self._stop = False
            self._monitor_thread = threading.Thread(target=self._monitor_device, daemon=True)
            self._monitor_thread.start()

    def stop_monitoring(self):
        """
        Stop the device monitoring thread.

        This stops the thread that checks the physical connection status of the device.
        """
        self._stop = True
        if self._monitor_thread:
            self._monitor_thread.join()

    def serial_connect(self):
        """
        Attempt to establish a serial connection to the device.

        Returns:
            bool: True if the connection is successfully established, False otherwise.
        """
        with self._lock:
            if not self.connected:
                SERIALDEVICE_LOGGER.warning("Device is not physically connected. Cannot establish serial connection.")
                return False

            try:
                self.serial_connection = serial.Serial(
                    port=self._current_port,
                    baudrate=self.baudrate,
                    timeout=self.timeout
                )
                self.serial_connected = True
                SERIALDEVICE_LOGGER.info(f"Serial connection established on port {self._current_port}.")
                return True
            except serial.SerialException as e:
                SERIALDEVICE_LOGGER.error(f"Failed to establish serial connection: {e}")
                self.serial_connection = None
                self.serial_connected = False
                return False

    def serial_disconnect(self):
        """
        Disconnect the serial connection if established.

        This method closes the serial connection and resets the `serial_connected` flag.
        """
        with self._lock:
            if self.serial_connection and self.serial_connection.is_open:
                self.serial_connection.close()
                self.serial_connected = False
                SERIALDEVICE_LOGGER.info("Serial connection closed.")
            else:
                SERIALDEVICE_LOGGER.warning("No active serial connection to disconnect.")