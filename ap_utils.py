import os
import datetime
import serial
import serial.tools.list_ports
import threading
import time
import logging

UTILS_LOGGER = logging.getLogger("Utilities")
SERIALDEVICE_LOGGER = logging.getLogger("SerialDevice")
SCANNER_LOGGER = logging.getLogger("HoneywellScanner")
SWITCHBOX_LOGGER = logging.getLogger("SwitchBox")

class Utilities:
    """Utility class for various helper functions."""

    @staticmethod
    def generate_timestamp_extension():
        """Generate a file extension using the current time in the format 'year_month_day_hour_minute_second'."""
        now = datetime.datetime.now()
        extension = now.strftime("%Y_%m_%d_%H_%M_%S")
        UTILS_LOGGER.info(f"Generated timestamp extension: {extension}")
        return extension

    @staticmethod
    def construct_path(paths):
        """
        Construct a path by joining the list of paths.

        Args:
            paths (list): A list of strings representing path components.

        Returns:
            str: A normalized path string.

        Raises:
            ValueError: If 'paths' is not a non-empty list of strings.
        """
        if not paths or not isinstance(paths, list):
            UTILS_LOGGER.error("construct_path: 'paths' must be a non-empty list of strings.")
            raise ValueError("'paths' must be a non-empty list of strings.")
        if not all(isinstance(p, str) for p in paths):
            UTILS_LOGGER.error("construct_path: All elements in 'paths' must be strings.")
            raise ValueError("All elements in 'paths' must be strings.")
        result = os.path.normpath(os.path.join(*paths))
        UTILS_LOGGER.info(f"Constructed path: {result}")
        return result

    @staticmethod
    def generate_timestamp_subpath():
        """Generate a timestamp subpath formatted as 'YYYY/MM/DD/HH_MM_SS'."""
        now = datetime.datetime.now()
        subpath = now.strftime("%Y/%m_%d")
        subpath_norm = os.path.normpath(subpath)
        UTILS_LOGGER.info(f"Generated timestamp subpath: {subpath_norm}")
        return subpath_norm

    @staticmethod
    def generate_file_prefix(strings):
        """
        Generate a file prefix by concatenating a list of strings with an underscore.

        Args:
            strings (list): A list of strings to concatenate.

        Returns:
            str: A single string with the substrings joined by an underscore.

        Raises:
            ValueError: If 'strings' is not a non-empty list of strings.
        """
        if not strings or not isinstance(strings, list):
            UTILS_LOGGER.error("generate_file_prefix: 'strings' must be a non-empty list of strings.")
            raise ValueError("'strings' must be a non-empty list of strings.")
        if not all(isinstance(s, str) for s in strings):
            UTILS_LOGGER.error("generate_file_prefix: All elements in 'strings' must be strings.")
            raise ValueError("All elements in 'strings' must be strings.")
        result = "_".join(strings)
        UTILS_LOGGER.info(f"Generated file prefix: {result}")
        return result

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

class SwitchBox(SerialDevice):
    """Class for managing a SwitchBox device."""

    def __init__(self, baudrate=9600, product_id=0x000A, vendor_id=0x2E8A, timeout=3, retry_interval=2, on_connect=None, on_disconnect=None):
        """
        Initialize the SwitchBox.

        Args:
            baudrate (int): The baud rate for the serial communication (default: 9600).
            product_id (int): The Product ID of the SwitchBox in hexadecimal (default: 0x000A).
            vendor_id (int): The Vendor ID of the SwitchBox in hexadecimal (default: 0x2E8A).
            timeout (float): Timeout for reading from the serial port in seconds.
            retry_interval (int): Time in seconds to wait before retrying connection.
            on_connect (callable): Callback function for successful connection.
            on_disconnect (callable): Callback function for disconnection.
        """
        super().__init__(baudrate, product_id, vendor_id, timeout, retry_interval, on_connect, on_disconnect)
        self.box_status = None
        self.channel = None
        self._message_thread = None
        self._stop_message_thread = threading.Event()
        self._message_received_event = threading.Event()  # Event to signal when a message is received
        self.status_updated_event = threading.Event()
        

    def start_listening(self):
        """
        Start the thread to listen for messages from the SwitchBox.
        """
        if self._message_thread is None or not self._message_thread.is_alive():
            self._stop_message_thread.clear()
            self._message_thread = threading.Thread(target=self._listen_for_messages_thread, daemon=True)
            self._message_thread.start()
            SWITCHBOX_LOGGER.info("Started listening thread for SwitchBox messages.")

    def stop_listening(self):
        """
        Stop the thread that listens for messages from the SwitchBox.
        """
        if self._message_thread and self._message_thread.is_alive():
            self._stop_message_thread.set()
            self._message_thread.join()
            SWITCHBOX_LOGGER.info("Stopped listening thread for SwitchBox messages.")

    def wait_for_message(self, timeout=None):
        """
        Wait for a message to be received by the listener.

        Args:
            timeout (float): Maximum time to wait for a message in seconds. If None, wait indefinitely.

        Returns:
            bool: True if a message was received, False if the timeout occurred.
        """
        return self._message_received_event.wait(timeout)

    def wait_for_status_update(self, timeout=None):
        """
        Wait for the status to be updated.

        Args:
            timeout (float): Maximum time to wait for the status update in seconds. If None, wait indefinitely.

        Returns:
            bool: True if the status was updated, False if the timeout occurred.
        """
        updated = self.status_updated_event.wait(timeout)
        if updated:
            SWITCHBOX_LOGGER.info("Status update detected.")
        else:
            SWITCHBOX_LOGGER.warning("Timeout while waiting for status update.")
        
        # Reset the event for future updates
        self.status_updated_event.clear()
        return updated

    def _listen_for_messages_thread(self):
        """
        Internal method to run `listen_for_messages` in a thread.
        """
        if not self.serial_connected or not self.serial_connection or not self.serial_connection.is_open:
            SWITCHBOX_LOGGER.warning("_listen_for_messages_thread: Serial connection is not established.")
            return

        SWITCHBOX_LOGGER.info("Listening for messages from the SwitchBox...")
        try:
            while not self._stop_message_thread.is_set():
                if self.serial_connection.in_waiting > 0:
                    message = self.serial_connection.readline().decode(errors='ignore').strip()
                    SWITCHBOX_LOGGER.info(f"Received message: {message}")
                    self._message_received_event.set()  # Signal that a message was received
                    
                    self.update_status(message)

                    
                    
                time.sleep(0.1)  # Prevent CPU overuse
        except Exception as e:
            SWITCHBOX_LOGGER.error(f"Error while listening for messages: {e}")
        finally:
            SWITCHBOX_LOGGER.info("Stopped listening for messages.")

    def update_status(self, message):
        """Update the status of the SwitchBox based on a received message."""
        if len(message) == 1:
            message = message.zfill(2)

        if len(message) == 2 and all(bit in "01" for bit in message):
            with self._lock:
                self.channel = 2 if message[0] == "1" else 1
                self.box_status = "Open" if message[1] == "1" else "Closed"
                SWITCHBOX_LOGGER.info(f"SwitchBox status updated: channel={self.channel}, box_status={self.box_status}")
                
                # Set the event to signal that the status has been updated
                self.status_updated_event.set()

    def get_status(self):
        """
        Send a `GET_STATUS` message to the SwitchBox without waiting for a response.
        """
        self.send_command("GET_STATUS")
        self.wait_for_status_update(timeout=5)
        with self._lock:
            SWITCHBOX_LOGGER.info(f"SwitchBox status: channel={self.channel}, box_status={self.box_status}")
            return {"channel": self.channel, "box_status": self.box_status}

    def switch_to_channel(self, target_channel):
        """
        Switch the SwitchBox to the specified channel.
        """
        if target_channel not in [1, 2]:
            SWITCHBOX_LOGGER.error("switch_to_channel: Invalid channel. Only channel 1 or 2 is supported.")
            raise ValueError("Invalid channel. Only channel 1 or 2 is supported.")
        
        with self._lock:  # Protect access to self.channel
            if self.channel == target_channel:
                SWITCHBOX_LOGGER.info(f"SwitchBox already on channel {target_channel}")
                return self.channel
        
        command = "SET_CHANNEL_1" if target_channel == 1 else "SET_CHANNEL_2"
        
        self.send_command(command)

        SWITCHBOX_LOGGER.info(f"SwitchBox switched to channel {target_channel}")
        self.wait_for_status_update(timeout=5)

        return self.channel
    
    def open_box(self):
        """
        Open the SwitchBox.
        """
        with self._lock:  # Protect access to self.box_status
            if self.box_status == "Open":
                SWITCHBOX_LOGGER.info("SwitchBox is already open.")
                return self.box_status

        self.send_command("OPEN_BOX")

        while True:
            with self._lock:
                if self.box_status == "Open":
                    break

        SWITCHBOX_LOGGER.info("SwitchBox opened.")

        return self.box_status

    def send_command(self, command):
        """
        Send a custom command to the SwitchBox.

        Args:
            command (str): The command string to send.
        """
        with self._lock:
            if not self.serial_connected or not self.serial_connection or not self.serial_connection.is_open:
                SWITCHBOX_LOGGER.warning("send_command: Serial connection is not established.")
                return

            try:
                self.serial_connection.reset_input_buffer()
                self.serial_connection.write(command.encode() + b"\n")  # Send the custom command
                SWITCHBOX_LOGGER.info(f"Command '{command}' sent.")
                self._message_received_event.wait(timeout=5)  # Wait for a response
                if not self._message_received_event.is_set():
                    SWITCHBOX_LOGGER.warning(f"No response received for command '{command}'.")

                self._message_received_event.clear()  # Reset the event for the next message
                
            except Exception as e:
                SWITCHBOX_LOGGER.error(f"Error while sending command '{command}': {e}")