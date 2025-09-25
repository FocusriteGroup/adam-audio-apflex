import logging
import os
from datetime import datetime
import csv

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
        logging.StreamHandler()
    ]
)

import socket
import threading
import json
import time
from biquad_tools.biquad_designer import Biquad_Filter
from oca_tools.oca_utilities import OCP1ToolWrapper

from ap_utils import Utilities, SwitchBox, HoneywellScanner

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
        self.server.listen(5)
        self.running = True

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
        """
        Callback executed when the scanner is connected.
        """
        with self.scanner_lock:
            self.logger.info("Scanner physically connected.")

    def scanner_on_disconnect(self):
        """
        Callback executed when the scanner is disconnected.
        """
        with self.scanner_lock:
            self.logger.info("Scanner physically disconnected.")

    def switchbox_on_connect(self):
        """
        Callback executed when the SwitchBox is connected.
        """
        with self.switchbox_lock:
            self.logger.info("SwitchBox physically connected.")

    def switchbox_on_disconnect(self):
        """
        Callback executed when the SwitchBox is disconnected.
        """
        with self.switchbox_lock:
            self.logger.info("SwitchBox physically disconnected.")

    # --- Client Handling ---

    def handle_client(self, client_socket):
        """
        Handle communication with a connected client.

        Args:
            client_socket (socket.socket): The client socket.
        """
        try:
            while True:
                data = client_socket.recv(1024).decode("utf-8")
                if not data:
                    break
                self.logger.info("Received: %s", data)
                try:
                    command = json.loads(data)
                    response = self.process_command(command)
                    if command.get("wait_for_response", True):
                        client_socket.send(response.encode("utf-8"))
                        self.logger.info("Sent response: %s", response)
                    else:
                        self.logger.info("No response sent.")
                except json.JSONDecodeError:
                    self.logger.error("Invalid JSON received.")
                    client_socket.send(b"Error: Invalid JSON format.")
                except (OSError, socket.error) as e:
                    self.logger.error("Error processing command: %s", e)
                    client_socket.send(f"Error: {e}".encode("utf-8"))
        except (socket.error, OSError) as e:
            self.logger.error("Connection error: %s", e)
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
            "get_biquad_coefficients": lambda: self._get_biquad_coefficients(command),
            "set_device_biquad": lambda: self._set_device_biquad(command),
            "get_serial_number": lambda: self._get_serial_number(command),
            "get_gain": lambda: self._get_gain(command),
            "get_device_biquad": lambda: self._get_device_biquad(command),
            "set_gain": lambda: self._set_gain(command),
            "get_model_description": lambda: self._get_model_description(command),
            "get_firmware_version": lambda: self._get_firmware_version(command),
            "get_audio_input": lambda: self._get_audio_input(command),
            "set_audio_input": lambda: self._set_audio_input(command),
            "get_mute": lambda: self._get_mute(command),
            "set_mute": lambda: self._set_mute(command),
            "get_mode": lambda: self._get_mode(command),
            "set_mode": lambda: self._set_mode(command),
            "get_phase_delay": lambda: self._get_phase_delay(command),
            "set_phase_delay": lambda: self._set_phase_delay(command),
            "check_measurement_trials": lambda: self._check_measurement_trials(command),
        }

        if action in command_map:
            try:
                return command_map[action]()
            except Exception as e:
                self.logger.error("Error processing action '%s': %s", action, e)
                return f"Error: {e}"
        else:
            self.logger.error("Unknown action: %s", action)
            return "Error: Unknown action."

    # --- Methods for Commands ---

    def _construct_path(self, command):
        """
        Construct a file path from a list of strings.
        """
        paths = command.get("paths")
        if not paths or not isinstance(paths, list):
            return "Error: 'paths' must be a non-empty list of strings."
        if not all(isinstance(p, str) for p in paths):
            return "Error: All elements in 'paths' must be strings."
        self.logger.info("Constructing path from: %s", paths)
        return Utilities.construct_path(paths)

    def _generate_file_prefix(self, command):
        """
        Generate a file prefix from a list of strings.
        """
        strings = command.get("strings")
        if not strings or not isinstance(strings, list):
            return "Error: 'strings' must be a non-empty list of strings."
        if not all(isinstance(s, str) for s in strings):
            return "Error: All elements in 'strings' must be strings."
        self.logger.info("Generating file prefix from: %s", strings)
        return Utilities.generate_file_prefix(strings)

    def _set_channel(self, command):
        """
        Set the channel on the SwitchBox.
        """
        if not self.switch_box.connected:
            self.logger.error("SwitchBox not connected.")
            return "Error: SwitchBox not connected."
        channel = command.get("channel")
        if channel in [1, 2]:
            with self.switchbox_lock:
                try:
                    self.switch_box.serial_connect()
                    self.switch_box.start_listening()
                    self.switch_box.get_status()
                    channel = self.switch_box.switch_to_channel(channel)
                    self.logger.info("Channel set to %s", channel)
                    return f"Channel set to {channel}"
                except Exception as e:
                    self.logger.error("Failed to set channel: %s", e)
                    return f"Error: Failed to set channel ({e})"
                finally:
                    self.switch_box.stop_listening()
                    self.switch_box.serial_disconnect()
        else:
            self.logger.error("Invalid channel: %s", channel)
            return "Error: Invalid channel"

    def _open_box(self):
        """
        Open the SwitchBox.
        """
        if not self.switch_box.connected:
            self.logger.error("SwitchBox not connected.")
            return "Error: SwitchBox not connected."
        with self.switchbox_lock:
            try:
                self.switch_box.serial_connect()
                self.switch_box.start_listening()
                self.switch_box.get_status()
                self.switch_box.open_box()
                self.logger.info("Box opened.")
                return f"Box status: {self.switch_box.box_status}"
            except Exception as e:
                self.logger.error("Failed to open box: %s", e)
                return f"Error: Failed to open box ({e})"
            finally:
                self.switch_box.stop_listening()
                self.switch_box.serial_disconnect()

    def _scan_serial(self):
        """
        Scan a serial number using the HoneywellScanner.
        """
        if not self.scanner.connected:
            self.logger.error("Scanner not connected.")
            return "Error: Scanner not connected."
        with self.scanner_lock:
            try:
                self.scanner.serial_connect()
                serial_number = self.scanner.trigger_scan()
                if serial_number:
                    self.logger.info("Serial number scanned: %s", serial_number)
                    return serial_number
                else:
                    self.logger.error("Failed to scan serial number.")
                    return "Error: Failed to scan serial number."
            except Exception as e:
                self.logger.error("Failed to scan serial number: %s", e)
                return f"Error: Failed to scan serial number ({e})"
            finally:
                self.scanner.serial_disconnect()

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
            self.logger.info("Biquad coefficients generated: %s", coeffs)
            return json.dumps(coeffs)
        except (ValueError, KeyError) as e:
            self.logger.error("Failed to generate biquad coefficients: %s", e)
            return f"Error: Failed to generate biquad coefficients ({e})"

    def _set_device_biquad(self, command):
        """
        Calculate biquad coefficients and set them on the OCA device.
        """
        try:
            index = int(command.get("index"))
            coefficients = command.get("coefficients")
            target_ip = command.get("target_ip")
            port = int(command.get("port"))
            wrapper = OCP1ToolWrapper(target_ip=target_ip, port=port)
            result = wrapper.set_biquad(index=index, coefficients=coefficients)
            self.logger.info("Set biquad on device: %s", result)
            return result
        except (ValueError, KeyError, TypeError) as e:
            self.logger.error("Failed to set device biquad: %s", e)
            return f"Error: Failed to set device biquad ({e})"

    def _get_device_biquad(self, command):
        """
        Get the biquad coefficients from the OCA device.
        """
        try:
            index = int(command.get("index"))
            target_ip = command.get("target_ip")
            port = int(command.get("port"))
            wrapper = OCP1ToolWrapper(target_ip=target_ip, port=port)
            result = wrapper.get_biquad(index=index)
            self.logger.info("Biquad coefficients received: %s", result)
            return result
        except Exception as e:
            self.logger.error("Failed to get device biquad: %s", e)
            return f"Error: Failed to get device biquad ({e})"

    def _get_serial_number(self, command):
        """
        Get the serial number from the OCA device.
        """
        try:
            target_ip = command.get("target_ip")
            port = int(command.get("port"))
            wrapper = OCP1ToolWrapper(target_ip=target_ip, port=port)
            serial = wrapper.get_serial_number()
            self.logger.info("Serial number received: %s", serial)
            return serial
        except Exception as e:
            self.logger.error("Failed to get serial number: %s", e)
            return f"Error: Failed to get serial number ({e})"

    def _get_gain(self, command):
        """
        Get the gain from the OCA device.
        """
        try:
            target_ip = command.get("target_ip")
            port = int(command.get("port"))
            wrapper = OCP1ToolWrapper(target_ip=target_ip, port=port)
            gain = wrapper.get_gain()
            self.logger.info("Gain received: %s", gain)
            return gain
        except Exception as e:
            self.logger.error("Failed to get gain: %s", e)
            return f"Error: Failed to get gain ({e})"

    def _set_gain(self, command):
        """
        Set the gain on the OCA device.
        """
        try:
            value = float(command.get("value"))
            target_ip = command.get("target_ip")
            port = int(command.get("port"))
            wrapper = OCP1ToolWrapper(target_ip=target_ip, port=port)
            result = wrapper.set_gain(value)
            self.logger.info("Set gain result: %s", result)
            return result
        except Exception as e:
            self.logger.error("Failed to set gain: %s", e)
            return f"Error: Failed to set gain ({e})"

    def _get_model_description(self, command):
        """
        Get the model description from the OCA device.
        """
        try:
            target_ip = command.get("target_ip")
            port = int(command.get("port"))
            wrapper = OCP1ToolWrapper(target_ip=target_ip, port=port)
            desc = wrapper.get_model_description()
            self.logger.info("Model description received: %s", desc)
            return desc
        except Exception as e:
            self.logger.error("Failed to get model description: %s", e)
            return f"Error: Failed to get model description ({e})"

    def _get_firmware_version(self, command):
        """
        Get the firmware version from the OCA device.
        """
        try:
            target_ip = command.get("target_ip")
            port = int(command.get("port"))
            wrapper = OCP1ToolWrapper(target_ip=target_ip, port=port)
            version = wrapper.get_firmware_version()
            self.logger.info("Firmware version received: %s", version)
            return version
        except Exception as e:
            self.logger.error("Failed to get firmware version: %s", e)
            return f"Error: Failed to get firmware version ({e})"

    def _get_audio_input(self, command):
        """
        Get the audio input mode from the OCA device.
        """
        try:
            target_ip = command.get("target_ip")
            port = int(command.get("port"))
            wrapper = OCP1ToolWrapper(target_ip=target_ip, port=port)
            audio_input = wrapper.get_audio_input()
            self.logger.info("Audio input received: %s", audio_input)
            return audio_input
        except Exception as e:
            self.logger.error("Failed to get audio input: %s", e)
            return f"Error: Failed to get audio input ({e})"

    def _set_audio_input(self, command):
        """
        Set the audio input mode on the OCA device.
        """
        try:
            position = command.get("position")
            target_ip = command.get("target_ip")
            port = int(command.get("port"))
            wrapper = OCP1ToolWrapper(target_ip=target_ip, port=port)
            result = wrapper.set_audio_input(position)
            self.logger.info("Set audio input result: %s", result)
            return result
        except Exception as e:
            self.logger.error("Failed to set audio input: %s", e)
            return f"Error: Failed to set audio input ({e})"

    def _get_mute(self, command):
        """
        Get the mute state from the OCA device.
        """
        try:
            target_ip = command.get("target_ip")
            port = int(command.get("port"))
            wrapper = OCP1ToolWrapper(target_ip=target_ip, port=port)
            mute = wrapper.get_mute()
            self.logger.info("Mute state received: %s", mute)
            return mute
        except Exception as e:
            self.logger.error("Failed to get mute state: %s", e)
            return f"Error: Failed to get mute state ({e})"

    def _set_mute(self, command):
        """
        Set the mute state on the OCA device.
        """
        try:
            state = command.get("state")
            target_ip = command.get("target_ip")
            port = int(command.get("port"))
            wrapper = OCP1ToolWrapper(target_ip=target_ip, port=port)
            result = wrapper.set_mute(state)
            self.logger.info("Set mute result: %s", result)
            return result
        except Exception as e:
            self.logger.error("Failed to set mute state: %s", e)
            return f"Error: Failed to set mute state ({e})"

    def _get_mode(self, command):
        """
        Get the control mode from the OCA device.
        """
        try:
            target_ip = command.get("target_ip")
            port = int(command.get("port"))
            wrapper = OCP1ToolWrapper(target_ip=target_ip, port=port)
            mode = wrapper.get_mode()
            self.logger.info("Mode received: %s", mode)
            return mode
        except Exception as e:
            self.logger.error("Failed to get mode: %s", e)
            return f"Error: Failed to get mode ({e})"

    def _set_mode(self, command):
        """
        Set the control mode on the OCA device.
        """
        try:
            position = command.get("position")
            target_ip = command.get("target_ip")
            port = int(command.get("port"))
            wrapper = OCP1ToolWrapper(target_ip=target_ip, port=port)
            result = wrapper.set_mode(position)
            self.logger.info("Set mode result: %s", result)
            return result
        except Exception as e:
            self.logger.error("Failed to set mode: %s", e)
            return f"Error: Failed to set mode ({e})"

    def _get_phase_delay(self, command):
        """
        Get the phase delay from the OCA device.
        """
        try:
            target_ip = command.get("target_ip")
            port = int(command.get("port"))
            wrapper = OCP1ToolWrapper(target_ip=target_ip, port=port)
            delay = wrapper.get_phase_delay()
            self.logger.info("Phase delay received: %s", delay)
            return delay
        except Exception as e:
            self.logger.error("Failed to get phase delay: %s", e)
            return f"Error: Failed to get phase delay ({e})"

    def _set_phase_delay(self, command):
        """
        Set the phase delay on the OCA device.
        """
        try:
            position = command.get("position")
            target_ip = command.get("target_ip")
            port = int(command.get("port"))
            wrapper = OCP1ToolWrapper(target_ip=target_ip, port=port)
            result = wrapper.set_phase_delay(position)
            self.logger.info("Set phase delay result: %s", result)
            return result
        except Exception as e:
            self.logger.error("Failed to set phase delay: %s", e)
            return f"Error: Failed to set phase delay ({e})"

    def _check_measurement_trials(self, command):
        """
        Check how many times a serial number appears in a CSV file with Status='Failed' and compare to max_trials.
        Creates the CSV file if it doesn't exist.
        Returns only "Measurement permitted" or "Maximum number of permitted measurements reached."
        """
        serial_number = command.get("serial_number")
        csv_path = command.get("csv_path")
        max_trials = int(command.get("max_trials"))
        self.logger.info("Checking measurement trials for serial: %s, file: %s, max: %d", serial_number, csv_path, max_trials)
        
        try:
            # Check if CSV file exists, create it if not
            if not os.path.exists(csv_path):
                self.logger.info("CSV file does not exist, creating: %s", csv_path)
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(csv_path), exist_ok=True)
                # Create CSV file with header
                with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(["Date", "Time", "Status", "ResultsPath", "SerialNumber", "FilePrefix"])
                msg = "Measurement permitted."
                self.logger.info("%s (CSV file created, serial=%s)", msg, serial_number)
                return msg
            
            # File exists, count Failed entries
            count = 0
            with open(csv_path, newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile, delimiter=",", skipinitialspace=True)
                for row in reader:
                    self.logger.debug("CSV row: %s", row)
                    if row.get("SerialNumber") == serial_number and row.get("Status") == "Failed":
                        count += 1
            
            self.logger.info("Serial %s found %d times with Failed status in %s", serial_number, count, csv_path)
            if count >= max_trials:
                msg = f"Maximum number of permitted failed measurements reached for serial number {serial_number}."
                self.logger.warning("%s (serial=%s, failed_count=%d, max=%d)", msg, serial_number, count, max_trials)
                return msg
            else:
                msg = "Measurement permitted."
                self.logger.info("%s (serial=%s, failed_count=%d, max=%d)", msg, serial_number, count, max_trials)
                return msg
                
        except Exception as e:
            self.logger.error("Error checking measurement trials: %s", e)
            return f"Error: {e}"

    # --- Server Management ---

    def start(self):
        """
        Start the server and manage client connections.
        """
        self.logger.info("Server is running...")
        self.logger.info("Waiting for connections...")
        while self.running:
            client_socket, addr = self.server.accept()
            self.logger.info("Connection from %s", addr)
            threading.Thread(target=self.handle_client, args=(client_socket,)).start()

    def stop(self):
        """
        Stop the server.
        """
        self.running = False
        self.server.close()
        self.switch_box.serial_disconnect()
        self.scanner.serial_disconnect()
        self.logger.info("Server stopped.")

if __name__ == "__main__":
    server = APServer()
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()