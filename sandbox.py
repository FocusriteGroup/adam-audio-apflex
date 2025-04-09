import serial
import serial.tools.list_ports
import threading
import time
import logging


class SerialDevice:
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
                        print(f"[INFO] Device connected on {found.device}")
                        if self.on_connect:
                            self.on_connect()
                    except serial.SerialException as e:
                        print(f"[WARN] Failed to open device port: {e}")
                        self.serial_connection = None
                        self.connected = False

                elif not found and self.connected:
                    # Device was disconnected
                    print("[INFO] Device disconnected.")
                    self.connected = False
                    self._current_port = None
                    if self.serial_connection:
                        try:
                            self.serial_connection.close()
                        except:
                            pass
                        self.serial_connection = None
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
                except:
                    pass
            self.connected = False
            print("[INFO] Device disconnected.")

    def connect(self):
        """Start or restart the connection loop."""
        if not self._stop:
            print("[INFO] Scanning is already running.")
            return
        self._stop = False
        self._connection_thread = threading.Thread(target=self._connection_loop, daemon=True)
        self._connection_thread.start()
        print("[INFO] Scanning started.")


class HoneywellScanner(SerialDevice):
    def __init__(self, baudrate=115200, product_id=None, vendor_id=None, timeout=10, retry_interval=2, on_connect=None, on_disconnect=None):
        """
        Initialize the HoneywellScanner.

        Args:
            baudrate (int): The baud rate for the serial communication (default: 115200).
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
                print("[WARN] Scanner not connected.")
                return None
            try:
                self.serial_connection.reset_input_buffer()
                self.serial_connection.write(bytes([0x16, ord('T'), 0x0D]))  # SYN T CR
                print("[INFO] Scan triggered. Waiting for data...")
                time.sleep(0.5)
                response = self.serial_connection.readline()
                if response:
                    self.serial_number = response.decode(errors='ignore').strip()
                    print(f"[INFO] Scanned serial number: {self.serial_number}")
                    return self.serial_number
            except Exception as e:
                print(f"[ERROR] During scan: {e}")
                self.connected = False
            return None


class SwitchBox(SerialDevice):
    def __init__(self, vid=0x2E8A, pid=0x000A, baudrate=9600, timeout=3, retry_interval=5, on_connect=None, on_disconnect=None):
        def wrapped_on_connect():
            if on_connect:
                on_connect()
            self.start_listener()

        super().__init__(baudrate, product_id=pid, vendor_id=vid, timeout=timeout, retry_interval=retry_interval, on_connect=wrapped_on_connect, on_disconnect=on_disconnect)
        self.box_status = "Closed"
        self.channel = 1
        self.listener_thread = None
        self.status_updated_event = threading.Event()

        while not self.connected:
            time.sleep(0.1)

        self.get_status()

    def start_listener(self):
        if not self.listener_thread or not self.listener_thread.is_alive():
            self.listener_thread = threading.Thread(target=self.listen_for_messages, daemon=True)
            self.listener_thread.start()

    def listen_for_messages(self):
        while not self._stop:
            try:
                if self.serial_connection and self.serial_connection.is_open:
                    if self.serial_connection.in_waiting > 0:
                        message = self.serial_connection.read_until(b'\n').decode('utf-8').strip()
                        print(f"[DEBUG] Received message: {message}")
                        self.update_status(message)
                else:
                    break
            except Exception as e:
                logging.error(f"Error in listener: {e}")
                break

    def update_status(self, message):
        if len(message) == 1:
            message = message.zfill(2)

        if len(message) == 2 and all(bit in "01" for bit in message):
            with self.lock:
                self.channel = 2 if message[0] == "1" else 1
                self.box_status = "Open" if message[1] == "1" else "Closed"
                self.status_updated_event.set()

    def send_command(self, command):
        with self.lock:  # Protect access to self.serial_connection
            if not self.connected:
                raise ConnectionError("SwitchBox is not connected.")
            if not self.serial_connection or not self.serial_connection.is_open:
                raise ConnectionError("Serial connection is not open.")
            try:
                self.serial_connection.write(command.encode('utf-8') + b'\n')
            except serial.SerialException as e:
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
            raise ValueError("Invalid channel. Only channel 1 or 2 is supported.")

        with self.lock:  # Protect access to self.channel
            if self.channel == target_channel:
                print(f"[INFO] Already on Channel {target_channel}.")
                return self.channel

        command = "SET_CHANNEL_1" if target_channel == 1 else "SET_CHANNEL_2"
        self.send_command(command)

        while True:
            with self.lock:
                if self.channel == target_channel:
                    break
            time.sleep(0.1)

        return self.channel

    def open_box(self):
        with self.lock:  # Protect access to self.box_status
            if self.box_status == "Open":
                print("[INFO] Box is already open.")
                return self.box_status

        self.send_command("OPEN_BOX")
        while True:
            with self.lock:
                if self.box_status == "Open":
                    break
            time.sleep(0.1)
        return self.box_status

    def get_status(self):
        self.status_updated_event.clear()  # Clear the event before sending the command
        self.send_command("GET_STATUS")
        if not self.status_updated_event.wait(timeout=2):  # Wait for the status to be updated
            logging.warning("Timeout waiting for status update.")
        with self.lock:
            return {"channel": self.channel, "box_status": self.box_status}


def on_switchbox_connected():
    print("✅ SwitchBox connected!")

def on_switchbox_disconnected():
    print("❌ SwitchBox disconnected!")

# Create a SwitchBox instance
switchbox = SwitchBox(
    vid=0x2E8A,
    pid=0x000A,
    baudrate=9600,
    timeout=3,
    retry_interval=5,
    on_connect=on_switchbox_connected,
    on_disconnect=on_switchbox_disconnected
)

time.sleep(5)  # Allow some time for the connection to establish

try:
    while True:
        if switchbox.connected:
            print("🔄 SwitchBox is connected. Testing features...")

            # Get the current status
            status = switchbox.get_status()
            print(f"📦 Current Status: {status}")

            # Switch to Channel 1
            print("🔀 Switching to Channel 1...")
            channel = switchbox.switch_to_channel(1)
            print(f"✅ Switched to Channel: {channel}")
            print(f"channel: {switchbox.channel}")

            # Wait for a few seconds
            time.sleep(2)

            # Switch to Channel 2
            print("🔀 Switching to Channel 2...")
            channel = switchbox.switch_to_channel(2)
            print(f"✅ Switched to Channel: {channel}")
            print(f"channel: {switchbox.channel}")

            # Wait for a few seconds
            time.sleep(2)

            # Open the box
            print("🔓 Opening the box...")
            switchbox.open_box()
            print(f"📦 Box Status After Opening: {switchbox.get_status()}")

            # Wait for a few seconds
            time.sleep(5)
        else:
            print("📴 Waiting for SwitchBox...")
        time.sleep(5)
except KeyboardInterrupt:
    print("\n[EXIT] Stopping...")
finally:
    switchbox.disconnect()