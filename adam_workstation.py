"""
adam_workstation.py

ADAM Audio Production Workstation CLI
------------------------------------------------

Author: Thilo Rode
Company: ADAM Audio GmbH
Version: 0.1
Date: 2025-10-22

Features:
- Command-line interface for device control, hardware management, and measurement processing
- Modular command dispatch for production and OCA device operations
- Lazy hardware manager initialization for SwitchBox and scanner devices
- Service communication via TCP/IP with auto-discovery support
- Measurement file parsing and validation (multi-channel CSV)
- Biquad filter coefficient calculation and device configuration
- Serial number scanning and trial management
- Logging to daily log files for traceability
- Extensible CLI: add new commands easily via command_map and argparse

This script provides a flexible CLI tool for ADAM Audio production workflows, hardware integration, and device configuration tasks.
It is designed for extensibility and automation in manufacturing environments.
"""

# Standard library imports
import socket  # For network communication
import json    # For encoding/decoding messages
import sys     # For system exit and argument handling
import logging # For event and error logging
import argparse # For command-line argument parsing
import os      # For file and directory operations
from datetime import datetime # For timestamps
import csv     # For parsing measurement files
import math
import numpy as np

# External module imports
#from oca.oca_manager import OCAManager # OCA device manager
from oca.oca_device import OCADevice

# Set up logging directory and file for workstation events
log_dir = "logs/adam_audio"
os.makedirs(log_dir, exist_ok=True)  # Ensure log directory exists

today = datetime.now().strftime("%Y-%m-%d")
log_filename = f"{log_dir}/adam_workstation_log_{today}.log"

# Configure logging to file only (no console output for Audio Precision calls)
logging.basicConfig(
    filename=log_filename,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(name)s] - %(message)s"
)

# Create a named logger for the workstation
WORKSTATION_LOGGER = logging.getLogger("AdamWorkstation")

# Log workstation startup
logging.info("----------------------------------- ADAM Audio Workstation started")


class AdamWorkstation:
    """
    Main class for ADAM Audio Production Workstation.

    Provides a modular CLI for device control, hardware management, measurement processing, and service communication.
    Features:
    - Lazy initialization of hardware managers (SwitchBox, Scanner)
    - Command dispatch via command_map for extensibility
    - Robust error handling and logging for traceability
    - Service auto-discovery and TCP/IP communication
    - Detailed measurement file parsing and validation
    - OCA device configuration and querying
    """

    def __init__(self, host=None, port=65432, service_name="ADAMService", scanner_type="honeywell"):
        """
        Initialize the ADAM Audio Workstation instance.

        Args:
            host (str, optional): Service IP address. If None, auto-discovery is used.
            port (int, optional): Service port number. Default is 65432.
            service_name (str, optional): Name of ADAM service to connect to.
            scanner_type (str, optional): Type of scanner hardware. Default is "honeywell".

        Sets up hardware managers, OCA manager, command dispatch map, and CLI argument parser.
        """
        # Store connection parameters for service communication
        self.port = port
        self.service_name = service_name
        self.host = host

        # Get workstation ID for logging (uses system hostname)
        self.workstation_id = socket.gethostname()

        # Initialize hardware managers as None for lazy loading
        self._switchbox_manager = None  # Will be created when needed
        self._scanner_manager = None    # Will be created when needed
        self._scanner_type = scanner_type  # Store scanner type for later initialization

        

        # Map command names to their corresponding methods for CLI dispatch
        self.command_map = {
            # OCA-Funktionen
            "discover": self.discover,
            "get_gain_calibration": self.get_gain_calibration,
            "set_gain_calibration": self.set_gain_calibration,
            "get_mode": self.get_mode,
            "set_mode": self.set_mode,
            "get_audio_input": self.get_audio_input,
            "set_audio_input": self.set_audio_input,
            # Produktions-/Hardware-/Service-Funktionen (NICHT entfernen!)
            "generate_timestamp_extension": self.generate_timestamp_extension,
            "construct_path": self.construct_path,
            "get_timestamp_subpath": self.get_timestamp_subpath,
            "generate_file_prefix": self.generate_file_prefix,
            "set_channel": self.set_channel,
            "open_box": self.open_box,
            "scan_serial": self.scan_serial,
            "get_biquad_coefficients": self.get_biquad_coefficients,
            "check_measurement_trials": self.check_measurement_trials,
            "process_measurement": self.process_measurement,
            # ...und alle weiteren, die du brauchst...
        }

        # Set up argument parser for CLI usage
        self.setup_arg_parser()

    # NEU: Properties für Lazy Loading
    @property
    def switchbox_manager(self):
        """
        Returns the SwitchBox manager instance, initializing it on first access.

        Handles communication with SwitchBox hardware for channel selection and box control.
        Uses lazy loading to avoid unnecessary hardware initialization until required.
        Logs initialization event for traceability.
        """
        # Check if the manager is already initialized
        if self._switchbox_manager is None:
            WORKSTATION_LOGGER.info("Initializing SwitchBox hardware on first use")
            from serial_managers import SwitchBoxManager
            # Create the manager instance
            self._switchbox_manager = SwitchBoxManager(self.workstation_id)
        # Return the manager instance
        return self._switchbox_manager

    @property
    def scanner_manager(self):
        """
        Returns the Scanner manager instance, initializing it on first access.

        Handles communication with scanner hardware for reading device serial numbers.
        Uses lazy loading and logs initialization for traceability.
        """
        # Check if the manager is already initialized
        if self._scanner_manager is None:
            WORKSTATION_LOGGER.info("Initializing %s Scanner hardware on first use", self._scanner_type)
            from serial_managers import ScannerManager
            # Create the manager instance
            self._scanner_manager = ScannerManager(self.workstation_id, self._scanner_type)
        # Return the manager instance
        return self._scanner_manager

    def _discover_service(self):
        """
        Attempts to discover the ADAM service IP address using AdamConnector.
        Uses lazy import to avoid dependency errors if connector is unavailable.

        Returns:
            str or None: Service IP address if found, else None. Logs errors and warnings.
        """
        try:
            # Import AdamConnector only when needed
            from adam_connector import AdamConnector
            WORKSTATION_LOGGER.info("Auto-discovering ADAM service...")
            # Create connector instance with current port and service name
            connector = AdamConnector(
                default_port=self.port,
                service_name=self.service_name,
                setup_logging=False  # Use workstation logging
            )
            # Attempt to find the service IP with a timeout
            service_ip = connector.find_service_ip(discovery_timeout=3)
            if service_ip:
                WORKSTATION_LOGGER.info("ADAM service discovered at: %s:%d", service_ip, self.port)
                return service_ip
            else:
                WORKSTATION_LOGGER.warning("No ADAM service found via discovery")
                return None
        except ImportError:
            # AdamConnector not available
            WORKSTATION_LOGGER.error("adam_connector.py not found - auto-discovery disabled")
            return None
        except (socket.error, json.JSONDecodeError) as e:
            # Log any other errors during discovery
            WORKSTATION_LOGGER.error("Service discovery failed: %s", e)
            return None

    def _ensure_host_available(self):
        """
        Ensures a valid host IP address is available for service communication.
        Uses auto-discovery if host was not specified during initialization.

        Returns:
            bool: True if host is available, False otherwise. Logs errors if unavailable.
        """
        # If host is already set, use it directly
        if self.host:
            return True
        # Otherwise, try to discover the host
        discovered_host = self._discover_service()
        if discovered_host:
            self.host = discovered_host
            return True
        else:
            WORKSTATION_LOGGER.error("No ADAM service host available and discovery failed")
            return False

    def send_command(self, command, wait_for_response=True):
        """
        Sends a command to the ADAM service over TCP/IP and optionally waits for a response.

        Args:
            command (dict): Command dictionary to send to the service.
            wait_for_response (bool, optional): If True, waits for and returns service response.

        Returns:
            str or None: Service response if wait_for_response is True, else None.

        Handles connection errors, JSON decode errors, and logs all events for traceability.
        """
        # Ensure we have a valid host before sending any command
        if not self._ensure_host_available():
            error_msg = "Error: No ADAM service available. Use --host to specify manually."
            WORKSTATION_LOGGER.error(error_msg)
            return error_msg

        try:
            # Log connection attempt
            WORKSTATION_LOGGER.info("Connecting to ADAM service at %s:%s...", self.host, self.port)
            # Create a TCP socket for communication
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
                # Connect to the ADAM service
                client_socket.connect((self.host, self.port))
                WORKSTATION_LOGGER.info("Connected to ADAM service. Sending command: %s", command.get("action", "unknown"))

                # Serialize the command as JSON and send it
                command_json = json.dumps(command).encode("utf-8")
                client_socket.send(command_json)

                if wait_for_response:
                    # Read response in chunks until complete JSON is received
                    response_data = b""
                    while True:
                        chunk = client_socket.recv(8192)  # Read up to 8KB at a time
                        if not chunk:
                            break
                        response_data += chunk
                        # Try to decode and parse JSON to check completeness
                        try:
                            response_str = response_data.decode("utf-8")
                            json.loads(response_str)
                            break  # Complete JSON received
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            continue  # Need more data

                    # Decode the response and log its size
                    response = response_data.decode("utf-8")
                    WORKSTATION_LOGGER.info("Received response from ADAM service (%d bytes)", len(response))
                    return response
                else:
                    # No response expected for this command
                    WORKSTATION_LOGGER.info("No response expected for this command.")
                    return None
        except socket.error as e:
            # Log socket errors
            WORKSTATION_LOGGER.error("Socket error: %s", e)
            return f"Error: {e}"
        except json.JSONDecodeError as e:
            # Log JSON decode errors
            WORKSTATION_LOGGER.error("JSON decode error: %s", e)
            return f"Error: {e}"

    # BEREINIGTE Command methods - Audio Precision Commands entfernt

    def generate_timestamp_extension(self, args):
        """
        Requests the service to generate a timestamp extension string.
        Used for file naming and traceability in production workflows.

        Args:
            args: CLI arguments (not used).

        Prints the service response.
        """
        # Log the command execution
        WORKSTATION_LOGGER.info("Executing 'generate_timestamp_extension' command.")
        # Build the command dictionary
        command = {"action": "generate_timestamp_extension"}
        # Send the command and print the response
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def construct_path(self, args):
        """
        Requests the service to construct a filesystem path from provided components.
        Useful for organizing measurement and log files in production.

        Args:
            args: CLI arguments containing 'paths' (list of path components).

        Prints the constructed path from the service response.
        """
        # Log the command execution and arguments
        WORKSTATION_LOGGER.info("Executing 'construct_path' command with paths: %s", args.paths)
        # Build the command dictionary
        command = {"action": "construct_path", "paths": args.paths}
        # Send the command and print the response
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def get_timestamp_subpath(self, args):
        """
        Requests the service to generate a timestamp-based subpath for organizing files.
        Useful for date/time-based file management.

        Args:
            args: CLI arguments (not used).

        Prints the generated subpath from the service response.
        """
        # Log the command execution
        WORKSTATION_LOGGER.info("Executing 'get_timestamp_subpath' command.")
        # Build the command dictionary
        command = {"action": "get_timestamp_subpath"}
        # Send the command and print the response
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def generate_file_prefix(self, args):
        """
        Requests the service to generate a file prefix from provided strings.
        Used for consistent file naming conventions in production.

        Args:
            args: CLI arguments containing 'strings' (list of prefix components).

        Prints the generated prefix from the service response.
        """
        # Log the command execution and arguments
        WORKSTATION_LOGGER.info("Executing 'generate_file_prefix' command with strings: %s", args.strings)
        # Build the command dictionary
        command = {"action": "generate_file_prefix", "strings": args.strings}
        # Send the command and print the response
        response = self.send_command(command, wait_for_response=True)
        print(response)

    # Hardware-Commands verwenden Properties (Lazy Loading)
    def set_channel(self, args):
        """
        Sets the output channel on local SwitchBox hardware.
        Used to select the correct output channel for device testing.

        Args:
            args: CLI arguments containing 'channel' (int).

        Prints the result or error and exits on failure.
        """
        try:
            # Call the SwitchBox manager to set the channel
            result_channel = self.switchbox_manager.set_channel(
                channel=args.channel,
                service_host=self.host,
                service_port=self.port
            )
            # Print the result to the user
            print(f"Channel set to {result_channel}")
        except (ValueError, FileNotFoundError, json.JSONDecodeError) as e:
            # Print error and exit
            print(f"Error: {e}")
            sys.exit(1)

    def open_box(self, args):
        """
        Opens the physical test box using local SwitchBox hardware.
        Used for device insertion/removal during production.

        Args:
            args: CLI arguments (not used).

        Prints the box status or error and exits on failure.
        """
        try:
            # Call the SwitchBox manager to open the box
            box_status = self.switchbox_manager.open_box(
                service_host=self.host,
                service_port=self.port
            )
            # Print the box status
            print(f"Box status: {box_status}")
        except (ValueError, FileNotFoundError, json.JSONDecodeError, socket.error) as e:
            # Print error and exit
            print(f"Error: {e}")
            sys.exit(1)

    def scan_serial(self, args):
        """
        Scans a device serial number using configured scanner hardware.
        Used to read serial numbers during production.

        Args:
            args: CLI arguments (not used).

        Prints the scanned serial number or error and exits on failure.
        """
        try:
            # Call the scanner manager to scan the serial number
            serial_number = self.scanner_manager.scan_serial(
                service_host=self.host,
                service_port=self.port
            )
            # Print the scanned serial number
            print(serial_number)
        except (ValueError, FileNotFoundError, json.JSONDecodeError, socket.error) as e:
            # Print error and exit
            print(f"Error: {e}")
            sys.exit(1)

    # OCA Device Commands
    def get_biquad_coefficients(self, args):
        """
        Requests the service to calculate biquad filter coefficients for DSP configuration.
        Used for configuring device DSP filters in OCA devices.

        Args:
            args: CLI arguments with filter parameters (type, gain, freq, Q, sample_rate).

        Prints the calculated coefficients from the service response.
        """
        # Log the command execution and arguments
        WORKSTATION_LOGGER.info("Executing 'get_biquad_coefficients' with: type=%s, gain=%s, peak_freq=%s, Q=%s, sample_rate=%s",
                 args.filter_type, args.gain, args.peak_freq, args.Q, args.sample_rate)
        # Build the command dictionary
        command = {
            "action": "get_biquad_coefficients",
            "filter_type": args.filter_type,
            "gain": args.gain,
            "peak_freq": args.peak_freq,
            "Q": args.Q,
            "sample_rate": args.sample_rate,
            "wait_for_response": True
        }
        # Send the command and print the response
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def _get_oca_device(self, args):
        return OCADevice(
            target=args.
            target, 
            port=args.port, 
            workstation_id=self.workstation_id, 
            service_host=self.host
            )

    # OCA-spezifische Methoden (nur die, die in OCADevice existieren)
    def discover(self, args):
        device = OCADevice(
        target=args.target,
        port=args.port,
        workstation_id=self.workstation_id,
        service_host=self.host
        )
        result = device.discover(timeout=2)
        print(result)

    def get_gain_calibration(self, args):
        device = self._get_oca_device(args)
        print(device.get_gain_calibration())

    def set_gain_calibration(self, args):
        device = self._get_oca_device(args)
        print(device.set_gain_calibration(args.value))

    def get_mode(self, args):
        device = self._get_oca_device(args)
        print(device.get_mode())

    def set_mode(self, args):
        device = self._get_oca_device(args)
        print(device.set_mode(args.position))

    def get_audio_input(self, args):
        device = self._get_oca_device(args)
        print(device.get_audio_input())

    def set_audio_input(self, args):
        device = self._get_oca_device(args)
        print(device.set_audio_input(args.position))


    def check_measurement_trials(self, args):
        """
        Checks the allowed measurement trials for a given serial number using a CSV file.

        Args:
            args: CLI arguments with 'serial_number', 'csv_path', and 'max_trials'.

        Prints the service response.
        """
        WORKSTATION_LOGGER.info("Sending check_measurement_trials: serial=%s, csv=%s, max=%d", args.serial_number, args.csv_path, args.max_trials)
        command = {
            "action": "check_measurement_trials",
            "serial_number": args.serial_number,
            "csv_path": args.csv_path,
            "max_trials": args.max_trials,
            "wait_for_response": True
        }
        response = self.send_command(command, wait_for_response=True)
        WORKSTATION_LOGGER.info("ADAM service response: %s", response)
        print(response)

    def _parse_measurement_csv(self, file_path: str):
        """
        Parses a measurement CSV file with dynamic channel count and returns structured data.

        Expected CSV structure:
            - Header lines: titles, channel names, X/Y labels, units (Hz, dBSPL, ...)
            - Data lines: numeric values (frequency, level pairs per channel)

        Args:
            file_path (str): Path to the measurement CSV file.

        Returns:
            dict: {
                'channels': {
                    'Ch1': {'frequencies': [...], 'levels': [...], 'unit': 'dBSPL'},
                    'Ch2': {...}, ...
                },
                'data_points': int
            }

        Raises:
            ValueError: If header or data format is invalid.
        """
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = [l.strip() for l in f if l.strip()]

        # Finde die Indexe der Zeile mit Einheiten (enthält 'Hz' und 'dB')
        units_idx = None
        for i, line in enumerate(lines):
            if "Hz" in line and "dB" in line:
                units_idx = i
                break
        if units_idx is None:
            raise ValueError("Kein Einheiten-Header (Hz,dB...) gefunden")

        # Die Units-Spalten extrahieren (z.B. Hz,dBSPL,Hz,dBSPL)
        units_tokens = [t for t in lines[units_idx].split(",") if t]
        # Daten beginnen nach dieser Zeile
        data_lines = lines[units_idx + 1:]

        # CSV parsing der Datenzeilen
        rows = []
        reader = csv.reader(data_lines)
        for row in reader:
            # Filter leere am Ende
            row = [c.strip() for c in row if c.strip() != ""]
            if not row:
                continue
            rows.append(row)

        if not rows:
            raise ValueError("Keine Datenzeilen gefunden")

        # Spaltenanzahl bestimmen
        col_count = len(rows[0])
        if any(len(r) != col_count for r in rows):
            # Tolerant: nur Zeilen gleicher Länge übernehmen
            rows = [r for r in rows if len(r) == col_count]

        if col_count % 2 != 0:
            raise ValueError(f"Erwarte gerade Spaltenanzahl (Frequenz+Level pro Kanal). Gefunden: {col_count}")

        channel_count = col_count // 2

        # Units pro Kanal (falls weniger Tokens -> fallback)
        # Einheit = erstes dB/ dBSPL Token je Paar (Standard dBSPL)
        def _unit_for_pair(pair_index):
            try:
                # units_tokens Beispiel: ['Hz','dBSPL','Hz','dBSPL']
                return units_tokens[pair_index * 2 + 1]
            except IndexError:
                return "dB"

        channels = {}


        cols_numeric = []
        for r in rows:
            numeric = []
            for c in r:
                try:
                    numeric.append(float(c))
                except ValueError:
                    numeric.append(math.nan)
            cols_numeric.append(numeric)


        arr = np.array(cols_numeric, dtype=float)  # shape (rows, cols)
        # Zeilen mit NaN verwerfen (optional streng)
        mask_valid = ~np.isnan(arr).any(axis=1)
        arr = arr[mask_valid]

        for ch_index in range(channel_count):
            freq_col = arr[:, 2 * ch_index]
            level_col = arr[:, 2 * ch_index + 1]
            ch_name = f"Ch{ch_index + 1}"
            channels[ch_name] = {
                "frequencies": freq_col.tolist(),
                "levels": level_col.tolist(),
                "unit": _unit_for_pair(ch_index),
                "data_points": int(len(freq_col))
            }

        return {
            "channels": channels,
            "data_points": int(arr.shape[0])
        }

    def process_measurement(self, args):
        """
        Processes a local measurement file (variable channel count) and sends parsed data to the service.

        Args:
            args: CLI arguments with 'measurement_path', 'serial_number', and 'json_directory'.

        Prints transfer status or error. Logs all events for traceability.
        """
        WORKSTATION_LOGGER.info("Processing measurement file: %s", args.measurement_path)
        try:
            if not os.path.exists(args.measurement_path):
                msg = f"Measurement file not found: {args.measurement_path}"
                WORKSTATION_LOGGER.error(msg)
                print(f"ERROR {msg}")
                return

            parsed = self._parse_measurement_csv(args.measurement_path)
            channels = parsed["channels"]
            filename = os.path.basename(args.measurement_path)
            serial_number = args.serial_number

            WORKSTATION_LOGGER.info(
                "Parsed measurement: serial=%s file=%s channels=%d points=%d",
                serial_number, filename, len(channels), parsed["data_points"]
            )

            measurement_data = {
                "device_serial": serial_number,
                "timestamp": datetime.now().isoformat(),
                "workstation_id": self.workstation_id,
                "measurement_file": filename,
                "channels": channels
            }

            command = {
                "action": "add_measurement",
                "json_directory": args.json_directory,
                "measurement_data": measurement_data,
                "wait_for_response": True
            }

            WORKSTATION_LOGGER.info("Sending measurement to service host=%s port=%s", self.host, self.port)
            response = self.send_command(command, wait_for_response=True)
            if not response:
                WORKSTATION_LOGGER.error("Empty response from service")
                print("ERROR empty response from service")
                return

            try:
                result = json.loads(response)
            except json.JSONDecodeError as e:
                WORKSTATION_LOGGER.error("Invalid JSON response: %s | raw=%s", e, response[:200])
                print("ERROR invalid service response")
                return

            if "error" in result:
                WORKSTATION_LOGGER.error("Service reported error: %s", result["error"])
                print(f"ERROR {result['error']}")
            else:
                WORKSTATION_LOGGER.info("Measurement stored: id=%s total=%s",
                                        result.get("measurement_id"), result.get("measurement_count"))
                # Nur noch diese Ausgabe bei Erfolg:
                print("Data successfully transferred.")
        except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as e:
            WORKSTATION_LOGGER.exception("Unhandled exception in process_measurement")
            print(f"ERROR {e}")

    def setup_arg_parser(self):
        parser = argparse.ArgumentParser(
            description="ADAM Audio Production Workstation",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )

        # Globale Parameter
        parser.add_argument("--host", "--service-host", dest="service_host",
                           help="ADAM service IP address (auto-discovered if not specified)")
        parser.add_argument("--port", "--service-port", dest="service_port", type=int, default=65432,
                           help="ADAM service port (default: 65432)")
        parser.add_argument("--service-name", default="ADAMService",
                           help="Name of ADAM service to connect to (default: ADAMService)")
        parser.add_argument("--scanner-type", choices=["honeywell"], default="honeywell",
                           help="Type of scanner to use (default: honeywell)")

        subparsers = parser.add_subparsers(dest="command", required=True)

        # OCA-Kommandos (nur die, die in OCADevice existieren)
        subparsers.add_parser("discover", help="Discover OCA devices")

        get_gain_parser = subparsers.add_parser("get_gain_calibration", help="Get gain calibration from OCA device")
        get_gain_parser.add_argument("target", type=str, help="OCA device name or IP address")
        get_gain_parser.add_argument("port", type=int, nargs="?", default=None, help="OCA device port (optional for device name)")

        set_gain_parser = subparsers.add_parser("set_gain_calibration", help="Set gain calibration on OCA device")
        set_gain_parser.add_argument("value", type=float, help="Gain calibration value")
        set_gain_parser.add_argument("target", type=str, help="OCA device name or IP address")
        set_gain_parser.add_argument("port", type=int, nargs="?", default=None, help="OCA device port (optional for device name)")

        get_mode_parser = subparsers.add_parser("get_mode", help="Get mode from OCA device")
        get_mode_parser.add_argument("target", type=str, help="OCA device name or IP address")
        get_mode_parser.add_argument("port", type=int, nargs="?", default=None, help="OCA device port (optional for device name)")

        set_mode_parser = subparsers.add_parser("set_mode", help="Set mode on OCA device")
        set_mode_parser.add_argument("position", type=str, help="Mode to set (e.g. 'internal-dsp', 'backplate')")
        set_mode_parser.add_argument("target", type=str, help="OCA device name or IP address")
        set_mode_parser.add_argument("port", type=int, nargs="?", default=None, help="OCA device port (optional for device name)")

        get_audio_input_parser = subparsers.add_parser("get_audio_input", help="Get audio input mode from OCA device")
        get_audio_input_parser.add_argument("target", type=str, help="OCA device name or IP address")
        get_audio_input_parser.add_argument("port", type=int, nargs="?", default=None, help="OCA device port (optional for device name)")

        set_audio_input_parser = subparsers.add_parser("set_audio_input", help="Set audio input mode on OCA device")
        set_audio_input_parser.add_argument("position", type=str, help="Audio input position to set (e.g. 'aes3', 'analogue-xlr')")
        set_audio_input_parser.add_argument("target", type=str, help="OCA device name or IP address")
        set_audio_input_parser.add_argument("port", type=int, nargs="?", default=None, help="OCA device port (optional for device name)")

        # Produktions-/Hardware-/Service-Kommandos (NICHT entfernen!)
        subparsers.add_parser("generate_timestamp_extension", help="Generate a timestamp extension.")
        parser_construct_path = subparsers.add_parser("construct_path", help="Construct a path.")
        parser_construct_path.add_argument("paths", type=str, nargs="+", help="List of paths to join.")
        subparsers.add_parser("get_timestamp_subpath", help="Get a timestamp subpath.")
        parser_generate_file_prefix = subparsers.add_parser("generate_file_prefix", help="Generate a file prefix.")
        parser_generate_file_prefix.add_argument("strings", type=str, nargs="+", help="List of strings to combine.")
        parser_set_channel = subparsers.add_parser("set_channel", help="Set the channel (1 or 2).")
        parser_set_channel.add_argument("channel", type=int, choices=[1, 2], help="Channel to set (1 or 2).")
        subparsers.add_parser("open_box", help="Open the box.")
        subparsers.add_parser("scan_serial", help="Scan the serial number.")
        biquad_parser = subparsers.add_parser("get_biquad_coefficients", help="Get biquad filter coefficients")
        biquad_parser.add_argument("filter_type", choices=["bell", "high_shelf", "low_shelf"], help="Type of biquad filter")
        biquad_parser.add_argument("gain", type=float, help="Gain in dB")
        biquad_parser.add_argument("peak_freq", type=float, help="Peak frequency in Hz")
        biquad_parser.add_argument("Q", type=float, help="Quality factor")
        biquad_parser.add_argument("sample_rate", type=int, help="Sample rate in Hz")
        set_biquad_parser = subparsers.add_parser("set_device_biquad", help="Set biquad filter on OCA device")
        set_biquad_parser.add_argument("index", type=int, help="Biquad index")
        set_biquad_parser.add_argument("coefficients", type=str, help="Koeffizienten-Liste als JSON-String")
        set_biquad_parser.add_argument("target", type=str, help="OCA device name or IP address")
        set_biquad_parser.add_argument("port", type=int, help="OCA device port")
        get_device_biquad_parser = subparsers.add_parser("get_device_biquad", help="Get biquad coefficients from OCA device")
        get_device_biquad_parser.add_argument("index", type=int, help="Biquad index")
        get_device_biquad_parser.add_argument("target", type=str, help="OCA device name or IP address")
        get_device_biquad_parser.add_argument("port", type=int, help="OCA device port")
        check_trials_parser = subparsers.add_parser("check_measurement_trials", help="Check allowed measurement trials for a serial number")
        check_trials_parser.add_argument("serial_number", type=str, help="Serial number to check")
        check_trials_parser.add_argument("csv_path", type=str, help="Path to the CSV file")
        check_trials_parser.add_argument("max_trials", type=int, help="Maximum allowed trials")
        process_measurement_parser = subparsers.add_parser("process_measurement", help="Process measurement data and send to service")
        process_measurement_parser.add_argument("measurement_path", type=str, help="Path to measurement file")
        process_measurement_parser.add_argument("--serial-number", "-s", dest="serial_number", required=True, help="Explicit device serial number")
        process_measurement_parser.add_argument("--json-directory", type=str, default="measurements", help="JSON directory on service")

        self.parser = parser

    def parse_and_execute(self):
        """
        Parses command-line arguments and executes the appropriate command function.

        Handles global connection parameters, updates instance state, and dispatches commands via command_map.
        Logs all command execution events for traceability.
        """
        # Parse arguments from the command line
        args = self.parser.parse_args()

        # Handle global connection parameters
        if args.service_host:
            self.host = args.service_host
            WORKSTATION_LOGGER.info("Using specified ADAM service host: %s", self.host)

        if args.service_port != 65432:
            self.port = args.service_port
            WORKSTATION_LOGGER.info("Using specified ADAM service port: %d", self.port)

        if args.service_name != "ADAMService":
            self.service_name = args.service_name
            WORKSTATION_LOGGER.info("Using specified ADAM service name: %s", self.service_name)

        # Execute command
        command = args.command
        WORKSTATION_LOGGER.info("Executing command: %s on ADAM service", command)

        if command in self.command_map:
            self.command_map[command](args)
        else:
            WORKSTATION_LOGGER.error("Unknown command: %s", command)
            sys.exit(1)



# Entry point for command-line usage
if __name__ == "__main__":
    # Main entry point for the ADAM Audio Production Workstation CLI.
    #
    # Parses scanner configuration from command-line arguments, initializes the workstation,
    # and executes the requested CLI command. Ensures hardware configuration is set before full parsing.
    # Parse scanner type from command-line arguments before full parsing
    temp_parser = argparse.ArgumentParser(add_help=False)
    temp_parser.add_argument("--scanner-type", choices=["honeywell"], default="honeywell")
    temp_args, _ = temp_parser.parse_known_args()

    # Create workstation instance with scanner config
    workstation = AdamWorkstation(scanner_type=temp_args.scanner_type)
    workstation.parse_and_execute()
