import os
import datetime
import serial
import serial.tools.list_ports
import threading
import time
import logging

class Utilities:
    """Utility class for various helper functions."""

    @staticmethod
    def generate_timestamp_extension():
        """Generate a file extension using the current time in the format 'year_month_day_hour_minute_second'."""
        now = datetime.datetime.now()
        extension = now.strftime("%Y_%m_%d_%H_%M_%S")
        logging.info(f"Generated timestamp extension: {extension}")
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
            logging.error("construct_path: 'paths' must be a non-empty list of strings.")
            raise ValueError("'paths' must be a non-empty list of strings.")
        if not all(isinstance(p, str) for p in paths):
            logging.error("construct_path: All elements in 'paths' must be strings.")
            raise ValueError("All elements in 'paths' must be strings.")
        result = os.path.normpath(os.path.join(*paths))
        logging.info(f"Constructed path: {result}")
        return result

    @staticmethod
    def generate_timestamp_subpath():
        """Generate a timestamp subpath formatted as 'YYYY/MM/DD/HH_MM_SS'."""
        now = datetime.datetime.now()
        subpath = now.strftime("%Y/%m_%d")
        subpath_norm = os.path.normpath(subpath)
        logging.info(f"Generated timestamp subpath: {subpath_norm}")
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
            logging.error("generate_file_prefix: 'strings' must be a non-empty list of strings.")
            raise ValueError("'strings' must be a non-empty list of strings.")
        if not all(isinstance(s, str) for s in strings):
            logging.error("generate_file_prefix: All elements in 'strings' must be strings.")
            raise ValueError("All elements in 'strings' must be strings.")
        result = "_".join(strings)
        logging.info(f"Generated file prefix: {result}")
        return result


class SerialDevice:
    """Base class for serial devices with connection management."""

    def __init__(self, baudrate=9600, product_id=None, vendor_id=None, timeout=3, retry_interval=5, on_connect=None, on_disconnect=None):
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

        self.serial_connection = None
        self.connected = False
        self._stop = True  # Initially stopped
        self._current_port = None
        self.lock = threading.Lock()  # Lock for thread safety

        # Automatically start the connection loop
        self.connect()

    def _connection_loop(self):
        """Continuously check and maintain the connection to the device."""
        while not self._stop:
            ports = serial.tools.list_ports.comports()
            found = None

            for port in ports:
                vid = port.vid
                pid = port.pid
                if (self.vendor_id is None or vid == self.vendor_id) and (self.product_id is None or pid == self.product_id):
                    found = port
                    break

            with self.lock:  # Protect shared resources
                if found and not self.connected:
                    try:
                        self.serial_connection = serial.Serial(found.device, self.baudrate, timeout=self.timeout)
                        self._current_port = found.device
                        self.connected = True
                        logging.info(f"Connected to serial device on {found.device}")
                        if self.on_connect:
                            self.on_connect()
                    except serial.SerialException as e:
                        logging.error(f"Serial connection failed: {e}")
                        self.serial_connection = None
                        self.connected = False

                elif not found and self.connected:
                    # Device was disconnected
                    self.connected = False
                    self._current_port = None
                    if self.serial_connection:
                        try:
                            self.serial_connection.close()
                        except Exception:
                            pass
                        self.serial_connection = None
                    logging.info("Serial device disconnected.")
                    if self.on_disconnect:
                        self.on_disconnect()

            time.sleep(self.retry_interval)

    def disconnect(self):
        """Disconnect from the device."""
        with self.lock:  # Protect shared resources
            self._stop = True
            if self.serial_connection and self.serial_connection.is_open:
                try:
                    self.serial_connection.close()
                except Exception:
                    pass
            self.connected = False
            logging.info("Serial device connection closed.")

    def connect(self):
        """Start or restart the connection loop."""
        if not self._stop:
            return
        self._stop = False
        self._connection_thread = threading.Thread(target=self._connection_loop, daemon=True)
        self._connection_thread.start()


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
        with self.lock:  # Protect shared resources
            if not self.connected or not self.serial_connection or not self.serial_connection.is_open:
                logging.warning("trigger_scan: Scanner not connected.")
                return None
            try:
                self.serial_connection.reset_input_buffer()
                self.serial_connection.write(bytes([0x16, ord('T'), 0x0D]))  # SYN T CR
                time.sleep(0.5)
                response = self.serial_connection.readline()
                if response:
                    self.serial_number = response.decode(errors='ignore').strip()
                    logging.info(f"Scanned serial number: {self.serial_number}")
                    return self.serial_number
            except Exception as e:
                logging.error(f"Error during scan: {e}")
                self.connected = False
            return None


class SwitchBox(SerialDevice):
    """Class for managing a SwitchBox device."""

    def __init__(self, vid=0x2E8A, pid=0x000A, baudrate=9600, timeout=3, retry_interval=5, on_connect=None, on_disconnect=None):
        """
        Initialize the SwitchBox.

        Args:
            vid (int): Vendor ID of the SwitchBox.
            pid (int): Product ID of the SwitchBox.
            baudrate (int): Baud rate for communication.
            timeout (float): Timeout for serial communication.
            retry_interval (int): Retry interval for connection attempts.
            on_connect (callable): Callback for successful connection.
            on_disconnect (callable): Callback for disconnection.
        """
        def wrapped_on_connect():
            if on_connect:
                on_connect()
            #.start_listener()

        super().__init__(baudrate, product_id=pid, vendor_id=vid, timeout=timeout, retry_interval=retry_interval, on_connect=wrapped_on_connect, on_disconnect=on_disconnect)
        self.box_status = "Closed"
        self.channel = 1
        self.listener_thread = None
        self.status_updated_event = threading.Event()
        self._stop_listener = False  # Separate flag for stopping the listener

        while not self.connected:
            time.sleep(0.1)

        self.get_status()

    def start_listener(self):
        """Start a listener thread to monitor incoming messages."""
        if not self.listener_thread or not self.listener_thread.is_alive():
            self._stop_listener = False  # Reset the listener stop flag
            self.listener_thread = threading.Thread(target=self.listen_for_messages, daemon=True)
            self.listener_thread.start()
            logging.info("SwitchBox listener thread started.")

    def listen_for_messages(self):
        """Listen for messages from the SwitchBox and update its status."""
        while not self._stop_listener:  # Use the separate flag for stopping the listener
            try:
                if self.serial_connection and self.serial_connection.is_open:
                    if self.serial_connection.in_waiting > 0:
                        message = self.serial_connection.read_until(b'\n').decode('utf-8').strip()
                        self.update_status(message)
                else:
                    break
            except Exception as e:
                logging.error(f"Error in SwitchBox listener: {e}")
                break

    def stop_listener(self):
        """Stop the listener thread."""
        self._stop_listener = True  # Set the listener stop flag to True
        if self.listener_thread and self.listener_thread.is_alive():
            self.listener_thread.join()  # Wait for the thread to finish
            logging.info("SwitchBox listener thread stopped.")

    def update_status(self, message):
        """Update the status of the SwitchBox based on a received message."""
        if len(message) == 1:
            message = message.zfill(2)

        if len(message) == 2 and all(bit in "01" for bit in message):
            with self.lock:
                self.channel = 2 if message[0] == "1" else 1
                self.box_status = "Open" if message[1] == "1" else "Closed"
                self.status_updated_event.set()
                logging.info(f"SwitchBox status updated: channel={self.channel}, box_status={self.box_status}")

    def send_command(self, command):
        """Send a command to the SwitchBox."""
        with self.lock:  # Protect access to self.serial_connection
            if not self.connected:
                logging.error("send_command: SwitchBox is not connected.")
                raise ConnectionError("SwitchBox is not connected.")
            if not self.serial_connection or not self.serial_connection.is_open:
                logging.error("send_command: Serial connection is not open.")
                raise ConnectionError("Serial connection is not open.")
            try:
                self.serial_connection.write(command.encode('utf-8') + b'\n')
                logging.info(f"Sent command to SwitchBox: {command}")
            except serial.SerialException as e:
                logging.error(f"Failed to send command: {e}")
                raise ConnectionError(f"Failed to send command: {e}")

    def switch_to_channel(self, target_channel):
        """
        Switch to the specified channel.

        Args:
            target_channel (int): The target channel (1 or 2).

        Returns:
            int: The current channel after switching.
        """
        if target_channel not in [1, 2]:
            logging.error("switch_to_channel: Invalid channel. Only channel 1 or 2 is supported.")
            raise ValueError("Invalid channel. Only channel 1 or 2 is supported.")

        with self.lock:  # Protect access to self.channel
            if self.channel == target_channel:
                logging.info(f"SwitchBox already on channel {target_channel}")
                return self.channel

        command = "SET_CHANNEL_1" if target_channel == 1 else "SET_CHANNEL_2"
        self.send_command(command)

        while True:
            with self.lock:
                if self.channel == target_channel:
                    break
            time.sleep(0.1)

        logging.info(f"SwitchBox switched to channel {target_channel}")
        return self.channel

    def open_box(self):
        """Open the SwitchBox."""
        with self.lock:  # Protect access to self.box_status
            if self.box_status == "Open":
                logging.info("SwitchBox already open.")
                return self.box_status

        self.send_command("OPEN_BOX")
        while True:
            with self.lock:
                if self.box_status == "Open":
                    break
            time.sleep(0.1)
        logging.info("SwitchBox opened.")
        return self.box_status

    def get_status(self):
        """Get the current status of the SwitchBox."""
        self.status_updated_event.clear()  # Clear the event before sending the command
        self.send_command("GET_STATUS")
        self.status_updated_event.wait(timeout=2)  # Wait for the status to be updated
        with self.lock:
            logging.info(f"SwitchBox status: channel={self.channel}, box_status={self.box_status}")
            return {"channel": self.channel, "box_status": self.box_status}