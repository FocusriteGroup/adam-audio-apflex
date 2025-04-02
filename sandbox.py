import serial
import serial.tools.list_ports
import logging
import time  # Import the time module for delays

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
        except serial.SerialException as e:
            raise ConnectionError(f"Failed to connect to {self.port}: {e}")

    def disconnect(self):
        """Disconnect from the switch box."""
        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.close()

    def send_command(self, command):
        """
        Send a command to the switch box and return the response.

        Args:
            command (str): The command to send.

        Returns:
            str: The response from the switch box.
        """
        if not self.serial_connection or not self.serial_connection.is_open:
            raise ConnectionError("Serial connection is not open.")

        try:
            # Send the command
            self.serial_connection.write(command.encode('utf-8') + b'\n')

            # Read the response
            response = self.serial_connection.read_until(b'\n').decode('utf-8').strip()
            return response
        except Exception as e:
            raise RuntimeError(f"Error sending command: {e}")

    def switch_to_channel_1(self):
        """Switch to channel 1."""
        return self.send_command("channel_1")

    def switch_to_channel_2(self):
        """Switch to channel 2."""
        return self.send_command("channel_2")

    def open_box(self):
        """Open the measurement box."""
        return self.send_command("open_box")

    def check_box_status(self):
        """
        Check the status of the measurement box.

        Returns:
            str: The status of the box (e.g., "Channel is set to channel 1, Box is open!").
        """
        return self.send_command("VAL")

    def print_help(self):
        """
        Request and print the help menu from the switch box.

        Returns:
            str: The help menu text.
        """
        logging.info("Requesting help menu...")
        return self.send_command("?")  # Send the '?' command to retrieve the help menu

def main():
    logging.info("Initializing SwitchBox...")

    try:
        # Initialize the SwitchBox with default VID, PID, and baud rate
        switch_box = SwitchBox()

        # Connect to the switch box
        switch_box.connect()
        logging.info(f"Connected to the switch box on {switch_box.port} at {switch_box.baudrate} baud.")

        # Example: Switch to channel 1
        logging.info("Switching to channel 1...")
        response = switch_box.switch_to_channel_1()
        logging.info(f"Response: {response}")

        # Example: Switch to channel 2
        logging.info("Switching to channel 2...")
        response = switch_box.switch_to_channel_2()
        logging.info(f"Response: {response}")

        # Example: Open the measurement box
        logging.info("Opening the measurement box...")
        response = switch_box.open_box()
        logging.info(f"Response: {response}")

        # Example: Check the box status
        logging.info("Checking box status...")
        box_status = switch_box.check_box_status()
        logging.info(f"Box status: {box_status}")

    except Exception as e:
        logging.error(f"An error occurred: {e}")
    finally:
        # Disconnect from the switch box
        switch_box.disconnect()
        logging.info("Disconnected from the switch box.")

if __name__ == "__main__":
    main()
