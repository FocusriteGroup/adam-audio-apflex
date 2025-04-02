import serial
import serial.tools.list_ports
import logging
import threading
import time

# Configure logging to write to a file named 'sandbox.log'
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("sandbox.log"),  # Log to a file named 'sandbox.log'
        logging.StreamHandler()             # Also log to the console
    ]
)

class SwitchBox:
    def __init__(self, vid=0x2E8A, pid=0x000A, baudrate=9600, timeout=3):
        """
        Initialize the SwitchBox controller.

        Args:
            vid (int): Vendor ID of the switch box (default: 0x2E8A for Pico).
            pid (int): Product ID of the switch box (default: 0x000A for Pico).
            baudrate (int): The baud rate for the serial communication (default: 9600).
            timeout (float): Timeout for reading from the serial port in seconds.
        """
        self.vid = vid
        self.pid = pid
        self.baudrate = baudrate
        self.timeout = timeout
        self.port = None
        self.serial_connection = None
        self.box_status = "Closed"  # Default box status
        self.channel = "One"       # Default channel
        self.lock = threading.Lock()  # Lock for thread-safe updates
        self.listener_thread = None
        self.running = False

        # Detect the port during initialization
        self.detect_port()

    def detect_port(self):
        """Detect the COM port based on VID and PID."""
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if port.vid == self.vid and port.pid == self.pid:
                self.port = port.device
                return
        raise Exception(f"Device with VID: {hex(self.vid)} and PID: {hex(self.pid)} not found.")

    def connect(self):
        """Connect to the switch box."""
        if not self.port:
            raise ConnectionError("Port not detected. Cannot connect to the switch box.")
        try:
            self.serial_connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            self.running = True
            self.start_listener()

            # Send a GET_STATUS command to initialize the status
            self.send_command("GET_STATUS")
            time.sleep(0.1)  # Allow some time for the listener to process the response
        except serial.SerialException as e:
            raise ConnectionError(f"Failed to connect to {self.port}: {e}")

    def disconnect(self):
        """Disconnect from the switch box."""
        self.running = False
        if self.listener_thread and self.listener_thread.is_alive():
            self.listener_thread.join()
        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.close()

    def send_command(self, command):
        """
        Send a command to the switch box.

        Args:
            command (str): The command to send.
        """
        if not self.serial_connection or not self.serial_connection.is_open:
            raise ConnectionError("Serial connection is not open.")

        try:
            # Send the command
            self.serial_connection.write(command.encode('utf-8') + b'\n')
        except Exception as e:
            raise RuntimeError(f"Error sending command: {e}")

    def start_listener(self):
        """Start the listener thread to process incoming messages."""
        self.listener_thread = threading.Thread(target=self.listen_for_messages, daemon=True)
        self.listener_thread.start()

    def listen_for_messages(self):
        """Continuously listen for incoming serial messages."""
        while self.running:
            try:
                if self.serial_connection.in_waiting > 0:
                    message = self.serial_connection.read_until(b'\n').decode('utf-8').strip()
                    self.update_status(message)
            except Exception as e:
                logging.error(f"Error reading from serial: {e}")

    def update_status(self, message):
        """
        Update the box status and channel based on the incoming message.

        Args:
            message (str): The 2-bit status message (e.g., "00", "01", "10", "11").
        """
        # Ensure the message is 2 bits by padding with leading zeros if necessary
        if len(message) == 1:
            message = message.zfill(2)  # Pad with leading zeros to make it 2 characters

        if len(message) == 2 and all(bit in "01" for bit in message):
            print(f"Received status message: {message}")
            with self.lock:
                # Decode the first bit (channel)
                self.channel = "Two" if message[0] == "1" else "One"
                # Decode the second bit (box status)
                self.box_status = "Open" if message[1] == "1" else "Closed"
                logging.info(f"Updated status: Channel={self.channel}, Box={self.box_status}")
        else:
            logging.warning(f"Invalid status message received: {message}")

    def switch_to_channel_1(self):
        """Switch to Channel 1."""
        self.send_command("SET_CHANNEL_1")

    def switch_to_channel_2(self):
        """Switch to Channel 2."""
        self.send_command("SET_CHANNEL_2")

    def open_box(self):
        """Open the box."""
        self.send_command("OPEN_BOX")

    def get_status(self):
        """
        Get the current status.

        Returns:
            dict: A dictionary with the current status:
                - "channel": "One" or "Two"
                - "box_status": "Open" or "Closed"
        """
        with self.lock:
            return {"channel": self.channel, "box_status": self.box_status}


def main():
    logging.info("Initializing SwitchBox...")

    try:
        # Initialize the SwitchBox with default VID, PID, and baud rate
        switch_box = SwitchBox()

        # Connect to the switch box
        switch_box.connect()
        logging.info(f"Connected to the switch box on {switch_box.port} at {switch_box.baudrate} baud.")

        # Example: Switch to Channel 1
        logging.info("Switching to Channel 1...")
        switch_box.switch_to_channel_1()

        time.sleep(1)  # Wait for a moment to allow the listener to process messages

        # Example: Switch to Channel 2
        logging.info("Switching to Channel 2...")
        switch_box.switch_to_channel_2()

        time.sleep(1)  # Wait for a moment to allow the listener to process messages

        # Example: Switch to Channel 1
        logging.info("Switching to Channel 1...")
        switch_box.switch_to_channel_1()

        time.sleep(1)  # Wait for a moment to allow the listener to process messages

        # Example: Open the box
        logging.info("Opening the box...")
        switch_box.open_box()

        # Wait for a few seconds to allow the listener to process messages
        time.sleep(5)

        # Example: Get the current status
        status = switch_box.get_status()
        logging.info(f"Current Status: Channel={status['channel']}, Box={status['box_status']}")

    except Exception as e:
        logging.error(f"An error occurred: {e}")
    finally:
        # Disconnect from the switch box
        switch_box.disconnect()
        logging.info("Disconnected from the switch box.")


if __name__ == "__main__":
    main()
