import logging
import os
from datetime import datetime

# Unterverzeichnis "logs" erstellen, falls es noch nicht existiert
log_dir = "logs/server"
os.makedirs(log_dir, exist_ok=True)

# Heutiges Datum im Format JJJJ-MM-TT
today = datetime.now().strftime("%Y-%m-%d")
log_filename = f"{log_dir}/ap_server_log_{today}.log"

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[
        logging.FileHandler(log_filename, encoding="utf-8"),
        logging.StreamHandler()  # Das ist für die Ausgabe im Terminal
    ]
)

import socket
import threading
import json
import time
from biquad_tools.biquad_designer import Biquad_Filter  # <-- Add this import
from oca_tools.oca_utilities import OCP1ToolWrapper

from ap_utils import Utilities, SwitchBox, HoneywellScanner  # Import utility and device classes


logging.info("----------------------------------- APServer started")

class APServer:
    """
    A server class to manage communication with clients and control devices.

    This server handles commands from clients, interacts with the Audio Precision API,
    and manages the SwitchBox and HoneywellScanner devices.
    """

    def __init__(self, host="127.0.0.1", port=65432):
        """
        Initialize the APServer.

        Args:
            host (str): The server's hostname or IP address. Default is "127.0.0.1".
            port (int): The server's port number. Default is 65432.
        """
        self.host = host
        self.port = port
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((self.host, self.port))
        self.server.listen(5)  # Allow up to 5 simultaneous connections
        self.running = True

        # Device connection states
        self.switchbox_connected = False
        self.scanner_connected = False

        # Locks for thread-safe access to devices
        self.scanner_lock = threading.Lock()
        self.switchbox_lock = threading.Lock()

        # Initialize the SwitchBox and HoneywellScanner
        self.switch_box = SwitchBox(on_connect=self.switchbox_on_connect, on_disconnect=self.switchbox_on_disconnect)
        self.scanner = HoneywellScanner(on_connect=self.scanner_on_connect, on_disconnect=self.scanner_on_disconnect)

        self.logger = logging.getLogger("APServer")
        self.logger.info("Server started")

    # --- Device Connection Callbacks ---

    def scanner_on_connect(self):
        """Callback for when the scanner connects."""
        with self.scanner_lock:
            if self.scanner_connected:
                self.logger.info("Scanner already connected.")
                return
            self.scanner_connected = True
            self.logger.info("Scanner connected.")

    def scanner_on_disconnect(self):
        """Callback for when the scanner disconnects."""
        with self.scanner_lock:
            if not self.scanner_connected:
                self.logger.info("Scanner already disconnected.")
                return
            self.scanner_connected = False
            self.logger.info("Scanner disconnected.")

    def switchbox_on_connect(self):
        """Callback for when the switchbox connects."""
        with self.switchbox_lock:
            if self.switchbox_connected:
                self.logger.info("SwitchBox already connected.")
                return
            self.switchbox_connected = True
            self.logger.info("SwitchBox connected.")

    def switchbox_on_disconnect(self):
        """Callback for when the switchbox disconnects."""
        with self.switchbox_lock:
            if not self.switchbox_connected:
                self.logger.info("SwitchBox already disconnected.")
                return
            self.switchbox_connected = False
            self.logger.info("SwitchBox disconnected.")

    # --- Client Handling ---

    def handle_client(self, client_socket):
        """
        Handle communication with a connected client.

        Args:
            client_socket (socket.socket): The socket object for the connected client.
        """
        try:
            while True:
                data = client_socket.recv(1024).decode("utf-8")
                if not data:
                    break
                self.logger.info(f"Received: {data}")
                try:
                    command = json.loads(data)
                    response = self.process_command(command)

                    # Check if the client expects a response
                    if command.get("wait_for_response", True):  # Default to True if not specified
                        client_socket.send(response.encode("utf-8"))
                        self.logger.info(f"Sent response: {response}")
                    else:
                        self.logger.info("No response sent.")
                except json.JSONDecodeError:
                    self.logger.error("Invalid JSON received.")
                    client_socket.send(b"Error: Invalid JSON format.")
                except Exception as e:
                    self.logger.error(f"Error processing command: {e}")
                    client_socket.send(f"Error: {e}".encode("utf-8"))
        except (socket.error, Exception) as e:
            self.logger.error(f"Connection error: {e}")
        finally:
            client_socket.close()
            self.logger.info("Client connection closed.")

    # --- Command Processing ---

    def process_command(self, command):
        """
        Process a command and return a response.

        Args:
            command (dict): The command received from the client.

        Returns:
            str: The response to the command.
        """
        if not isinstance(command, dict) or "action" not in command:
            return "Error: Invalid command format."

        action = command["action"]
        command_map = {
            "generate_timestamp_extension": Utilities.generate_timestamp_extension,
            "construct_path": lambda: self._construct_path(command),
            "get_timestamp_subpath": Utilities.generate_timestamp_subpath,
            "generate_file_prefix": lambda: self._generate_file_prefix(command),
            "set_channel": lambda: self._set_channel(command),
            "open_box": self._open_box,
            "scan_serial": self._scan_serial,
            "get_biquad_coefficients": lambda: self._get_biquad_coefficients(command),  # <-- Add this line
            "set_device_biquad": lambda: self._set_device_biquad(command),
        }

        if action in command_map:
            try:
                return command_map[action]()
            except Exception as e:
                self.logger.error(f"Error processing action '{action}': {e}")
                return f"Error: {e}"
        else:
            self.logger.error(f"Unknown action: {action}")
            return "Error: Unknown action."

    # Methods for Commands ---

    def _construct_path(self, command):
        paths = command.get("paths")
        if not paths or not isinstance(paths, list):
            return "Error: 'paths' must be a non-empty list of strings."
        if not all(isinstance(p, str) for p in paths):
            return "Error: All elements in 'paths' must be strings."
        self.logger.info("Constructing path from: %s", paths)
        return Utilities.construct_path(paths)

    def _generate_file_prefix(self, command):
        strings = command.get("strings")
        if not strings or not isinstance(strings, list):
            return "Error: 'strings' must be a non-empty list of strings."
        if not all(isinstance(s, str) for s in strings):
            return "Error: All elements in 'strings' must be strings."
        self.logger.info(f"Generating file prefix from: {strings}")
        return Utilities.generate_file_prefix(strings)

    def _set_channel(self, command):
        if not self.switchbox_connected:
            self.logger.error("SwitchBox not connected.")
            return "Error: SwitchBox not connected."
        channel = command.get("channel")
        if channel in [1, 2]:
            with self.switchbox_lock:
                try:
                    self.switch_box.serial_connection.reset_input_buffer()
                    self.switch_box.serial_connection.reset_output_buffer()
                    self.switch_box.start_listener()
                    self.switch_box.get_status()

                    channel = self.switch_box.switch_to_channel(channel)
                    self.logger.info(f"Channel set to {channel}")
                    self.switch_box.stop_listener()
                    return f"Channel set to {channel}"
                except Exception as e:
                    self.logger.error(f"Failed to set channel: {e}")
                    self.switch_box.stop_listener()
                    return f"Error: Failed to set channel ({e})"
        else:
            self.logger.error(f"Invalid channel: {channel}")
            return "Error: Invalid channel"

    def _open_box(self):
        if not self.switchbox_connected:
            self.logger.error("SwitchBox not connected.")
            return "Error: SwitchBox not connected."
        self.switch_box.serial_connection.reset_input_buffer()
        self.switch_box.serial_connection.reset_output_buffer()
        self.switch_box.start_listener()
        self.switch_box.get_status()

        self.switch_box.open_box()
        self.logger.info("Box opened.")
        self.switch_box.stop_listener()
        return "Box opened."

    def _scan_serial(self):
        with self.scanner_lock:
            if not self.scanner_connected:
                self.logger.error("Scanner not connected.")
                return "Error: Scanner not connected."
            serial_number = self.scanner.trigger_scan()
            if serial_number:
                self.logger.info(f"Serial number scanned: {serial_number}")
                return serial_number
            else:
                self.logger.error("Failed to scan serial number.")
                return "Error: Failed to scan serial number."

    def _get_biquad_coefficients(self, command):
        """
        Create a Biquad_Filter instance and return coefficients as a list.
        """
        try:
            filter_type = command.get("filter_type")
            gain = float(command.get("gain", 0.0))
            peak_freq = float(command.get("peak_freq", 1000.0))
            Q = float(command.get("Q", 1.0))
            sample_rate = int(command.get("sample_rate", 48000))

            biquad = Biquad_Filter(
                filter_type=filter_type,
                gain=gain,
                peak_freq=peak_freq,
                Q=Q,
                sample_rate=sample_rate
            )
            coeffs_dict = biquad.coefficients
            coeffs = [
                coeffs_dict["a1"],
                coeffs_dict["a2"],
                coeffs_dict["b0"],
                coeffs_dict["b1"],
                coeffs_dict["b2"]
            ]
            self.logger.info(f"Biquad coefficients generated: {coeffs}")
            return json.dumps(coeffs)
        except Exception as e:
            self.logger.error(f"Failed to generate biquad coefficients: {e}")
            return f"Error: Failed to generate biquad coefficients ({e})"

    def _set_device_biquad(self, command):
        """
        Calculate biquad coefficients and set them on the OCA device.
        """
        try:
            index = int(command.get("index"))
            filter_type = command.get("filter_type")
            gain = float(command.get("gain", 0.0))
            peak_freq = float(command.get("peak_freq", 1000.0))
            Q = float(command.get("Q", 1.0))
            sample_rate = int(command.get("sample_rate", 48000))
            target_ip = command.get("target_ip")
            port = int(command.get("port"))

            biquad = Biquad_Filter(
                filter_type=filter_type,
                gain=gain,
                peak_freq=peak_freq,
                Q=Q,
                sample_rate=sample_rate
            )
            coeffs_dict = biquad.coefficients
            coeffs = [
                coeffs_dict["a1"],
                coeffs_dict["a2"],
                coeffs_dict["b0"],
                coeffs_dict["b1"],
                coeffs_dict["b2"]
            ]

            wrapper = OCP1ToolWrapper(target_ip=target_ip, port=port)
            result = wrapper.set_biquad(index=index, coefficients=coeffs)
            self.logger.info(f"Set biquad on device: {result}")
            return result
        except Exception as e:
            self.logger.error(f"Failed to set device biquad: {e}")
            return f"Error: Failed to set device biquad ({e})"

    # --- Server Management ---

    def start(self):
        """Start the server and manage client connections."""
        self.logger.info("Server is running...")
        self.logger.info("Waiting for connections...")
        while self.running:
            client_socket, addr = self.server.accept()
            self.logger.info(f"Connection from {addr}")
            threading.Thread(target=self.handle_client, args=(client_socket,)).start()

    def stop(self):
        """Stop the server."""
        self.running = False
        self.server.close()
        self.switch_box.disconnect()
        self.logger.info("Server stopped.")

if __name__ == "__main__":
    server = APServer()
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()