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
import shutil  # For copying files and directories

# External module imports
#from oca.oca_manager import OCAManager # OCA device manager
from oca.oca_device import OCADevice
from analysis import MeasurementParser, MeasurementUpload, GainCalibration
from analysis.csv_processing import extract_csv_columns as extract_csv_columns_local
from analysis.csv_processing import split_ap_distortion_csv as split_ap_distortion_csv_local
from analysis.csv_processing import octave_smooth_ap_csv as octave_smooth_ap_csv_local
from analysis.csv_processing import merge_ap_distortion_csvs as merge_ap_distortion_csvs_local
from analysis.csv_processing import filter_reference_by_limits as filter_reference_by_limits_local
from helpers import (
    generate_timestamp_extension,
    construct_path,
    generate_timestamp_subpath,
    generate_file_prefix,
)
from cli.workstation_parser import build_workstation_parser
from SubProMACAddresses import mac_database, mac_provisioner

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
            "extract_csv_columns": self.extract_csv_columns,
            "split_ap_distortion_csv": self.split_ap_distortion_csv,
            "octave_smooth_ap_csv": self.octave_smooth_ap_csv,
            "merge_ap_distortion_csvs": self.merge_ap_distortion_csvs,
            "set_channel": self.set_channel,
            "open_box": self.open_box,
            "scan_serial": self.scan_serial,
            "get_biquad_coefficients": self.get_biquad_coefficients,
            "check_measurement_trials": self.check_measurement_trials,
            "upload_measurement": self.upload_measurement,  # Changed from process_measurement
            "calibrate_gain": self.calibrate_gain,  # NEU: Gain Calibration
            "get_bass_management": self.get_bass_management,
            "set_bass_management": self.set_bass_management,
            "get_bass_management_bypass": self.get_bass_management_bypass,
            "set_bass_management_bypass": self.set_bass_management_bypass,
            "get_gain": self.get_gain,
            "set_gain": self.set_gain,
            "get_phase_delay": self.get_phase_delay,
            "set_phase_delay": self.set_phase_delay,
            "get_mute": self.get_mute,
            "set_mute": self.set_mute,
            "get_mac_address": self.get_mac_address,
            "set_mac_address": self.set_mac_address,
            "get_serial_number": self.get_serial_number,
            "set_serial_number": self.set_serial_number,
            "get_model_description": self.get_model_description,
            "get_firmware_version": self.get_firmware_version,
            "init_asub": self.init_asub,  # Add new command to map
            "setup_references": self.setup_references,  # Setup References directory
            "is_golden_sample": self.is_golden_sample,
            "is_default_serial": self.is_default_serial,
            "verify_system": self.verify_system,
            "filter_reference_by_limits": self.filter_reference_by_limits,  # Filter reference by limits
            # MAC provisioning
            "provision_mac": self.provision_mac,
            "init_mac_db": self.init_mac_db,
            "set_mac_range": self.set_mac_range,
            "get_mac_pool_status": self.get_mac_pool_status,
            "export_mac_log": self.export_mac_log,
            "register_golden_sample": self.register_golden_sample,
        }

        # Set up argument parser for CLI usage
        self.setup_arg_parser()

    def _show_error_popup(self, title, message):
        """Display a modal error dialog with an OK button. Silently skipped if tkinter is unavailable."""
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(title, message)
            root.destroy()
        except Exception:
            pass  # tkinter not available, silently skip popup

    def _show_warning_popup(self, title, message):
        """Display a modal warning dialog with an OK button. Silently skipped if tkinter is unavailable."""
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showwarning(title, message)
            root.destroy()
        except Exception:
            pass  # tkinter not available, silently skip popup

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
        if args.server:
            WORKSTATION_LOGGER.info("Executing 'generate_timestamp_extension' via service.")
            command = {"action": "generate_timestamp_extension"}
            response = self.send_command(command, wait_for_response=True)
            print(response)
            return

        # Log the command execution
        WORKSTATION_LOGGER.info("Executing 'generate_timestamp_extension' command locally.")
        # Generate the timestamp locally
        print(generate_timestamp_extension())

    def construct_path(self, args):
        """
        Requests the service to construct a filesystem path from provided components.
        Useful for organizing measurement and log files in production.

        Args:
            args: CLI arguments containing 'paths' (list of path components).

        Prints the constructed path from the service response.
        """
        if args.server:
            WORKSTATION_LOGGER.info("Executing 'construct_path' via service with paths: %s", args.paths)
            command = {"action": "construct_path", "paths": args.paths}
            response = self.send_command(command, wait_for_response=True)
            print(response)
            return

        # Log the command execution and arguments
        WORKSTATION_LOGGER.info("Executing 'construct_path' locally with paths: %s", args.paths)
        # Build and print the path locally
        print(construct_path(args.paths))

    def get_timestamp_subpath(self, args):
        """
        Requests the service to generate a timestamp-based subpath for organizing files.
        Useful for date/time-based file management.

        Args:
            args: CLI arguments (not used).

        Prints the generated subpath from the service response.
        """
        if args.server:
            WORKSTATION_LOGGER.info("Executing 'get_timestamp_subpath' via service.")
            command = {"action": "get_timestamp_subpath"}
            response = self.send_command(command, wait_for_response=True)
            print(response)
            return

        # Log the command execution
        WORKSTATION_LOGGER.info("Executing 'get_timestamp_subpath' command locally.")
        # Generate the subpath locally
        print(generate_timestamp_subpath())

    def generate_file_prefix(self, args):
        """
        Requests the service to generate a file prefix from provided strings.
        Used for consistent file naming conventions in production.

        Args:
            args: CLI arguments containing 'strings' (list of prefix components).

        Prints the generated prefix from the service response.
        """
        if args.server:
            WORKSTATION_LOGGER.info("Executing 'generate_file_prefix' via service with strings: %s", args.strings)
            command = {"action": "generate_file_prefix", "strings": args.strings}
            response = self.send_command(command, wait_for_response=True)
            print(response)
            return

        # Log the command execution and arguments
        WORKSTATION_LOGGER.info("Executing 'generate_file_prefix' locally with strings: %s", args.strings)
        # Generate and print the prefix locally
        print(generate_file_prefix(args.strings))

    def extract_csv_columns(self, args):
        """
        Extract selected CSV columns from row 2 onward into a new CSV file.

        Runs locally by default. If --server is provided, delegates to ADAM service.
        """
        if args.server:
            WORKSTATION_LOGGER.info(
                "Executing 'extract_csv_columns' via service: input=%s, columns=%s, output=%s, output_dir=%s",
                args.input_path,
                args.columns,
                args.output_filename,
                args.output_dir,
            )
            command = {
                "action": "extract_csv_columns",
                "input_path": args.input_path,
                "columns": args.columns,
                "output_filename": args.output_filename,
                "output_dir": args.output_dir,
            }
            response = self.send_command(command, wait_for_response=True)
            print(response)
            return

        WORKSTATION_LOGGER.info(
            "Executing 'extract_csv_columns' locally: input=%s, columns=%s, output=%s, output_dir=%s",
            args.input_path,
            args.columns,
            args.output_filename,
            args.output_dir,
        )
        output_path = extract_csv_columns_local(
            input_path=args.input_path,
            columns=args.columns,
            output_filename=args.output_filename,
            output_dir=args.output_dir,
        )
        print(output_path)

    def split_ap_distortion_csv(self, args):
        """
        Split an AP Level & Distortion CSV into per-metric files (F, H2, H3, Total).

        Runs locally by default. If --server is provided, delegates to ADAM service.
        """
        if args.server:
            WORKSTATION_LOGGER.info(
                "Executing 'split_ap_distortion_csv' via service: input=%s, output_dir=%s, fraction=%s, output_prefix=%s",
                args.input_path,
                args.output_dir,
                args.fraction,
                args.output_prefix,
            )
            command = {
                "action": "split_ap_distortion_csv",
                "input_path": args.input_path,
                "output_dir": args.output_dir,
                "fraction": args.fraction,
                "output_prefix": args.output_prefix,
            }
            response = self.send_command(command, wait_for_response=True)
            print(response)
            return

        WORKSTATION_LOGGER.info(
            "Executing 'split_ap_distortion_csv' locally: input=%s, output_dir=%s, fraction=%s, output_prefix=%s",
            args.input_path,
            args.output_dir,
            args.fraction,
            args.output_prefix,
        )
        results = split_ap_distortion_csv_local(
            input_path=args.input_path,
            output_dir=args.output_dir,
            fraction=args.fraction,
            output_prefix=args.output_prefix,
        )
        for metric, path in results.items():
            print(f"{metric}: {path}")

    def merge_ap_distortion_csvs(self, args):
        """
        Merge two or more AP Level & Distortion CSV files into per-metric combined files.

        Runs locally by default. If --server is provided, delegates to ADAM service.
        """
        if args.server:
            WORKSTATION_LOGGER.info(
                "Executing 'merge_ap_distortion_csvs' via service: inputs=%s, output_dir=%s, "
                "fraction=%s, output_prefix=%s",
                args.input_paths,
                args.output_dir,
                args.fraction,
                args.output_prefix,
            )
            command = {
                "action": "merge_ap_distortion_csvs",
                "input_paths": args.input_paths,
                "output_dir": args.output_dir,
                "fraction": args.fraction,
                "output_prefix": args.output_prefix,
            }
            response = self.send_command(command, wait_for_response=True)
            print(response)
            return

        WORKSTATION_LOGGER.info(
            "Executing 'merge_ap_distortion_csvs' locally: inputs=%s, output_dir=%s, "
            "fraction=%s, output_prefix=%s",
            args.input_paths,
            args.output_dir,
            args.fraction,
            args.output_prefix,
        )
        results = merge_ap_distortion_csvs_local(
            input_paths=args.input_paths,
            output_dir=args.output_dir,
            fraction=args.fraction,
            output_prefix=args.output_prefix,
        )
        for metric, path in results.items():
            print(f"{metric}: {path}")

    def octave_smooth_ap_csv(self, args):
        """
        Apply 1/n-octave smoothing to all Y columns of an AP measurement CSV.

        Runs locally by default. If --server is provided, delegates to ADAM service.
        """
        if args.server:
            WORKSTATION_LOGGER.info(
                "Executing 'octave_smooth_ap_csv' via service: input=%s, fraction=%d, output=%s, output_dir=%s",
                args.input_path, args.fraction, args.output_filename, args.output_dir,
            )
            command = {
                "action": "octave_smooth_ap_csv",
                "input_path": args.input_path,
                "fraction": args.fraction,
                "output_filename": args.output_filename,
                "output_dir": args.output_dir,
            }
            response = self.send_command(command, wait_for_response=True)
            print(response)
            return

        WORKSTATION_LOGGER.info(
            "Executing 'octave_smooth_ap_csv' locally: input=%s, fraction=%d, output=%s, output_dir=%s",
            args.input_path, args.fraction, args.output_filename, args.output_dir,
        )
        output_path = octave_smooth_ap_csv_local(
            input_path=args.input_path,
            fraction=args.fraction,
            output_filename=args.output_filename,
            output_dir=args.output_dir,
        )
        print(output_path)

    def filter_reference_by_limits(self, args):
        """
        Filter a reference measurement CSV to include only frequencies within limits ranges.

        Identifies frequency ranges covered by a limits CSV (which may have gaps) and
        creates a new reference CSV containing only frequencies that fall within those ranges.

        Runs locally (no server support).
        """
        WORKSTATION_LOGGER.info(
            "Executing 'filter_reference_by_limits': reference=%s, limits=%s, output=%s, output_dir=%s",
            args.reference_path,
            args.limits_path,
            args.output_filename,
            args.output_dir,
        )
        
        try:
            output_path = filter_reference_by_limits_local(
                reference_path=args.reference_path,
                limits_path=args.limits_path,
                output_filename=args.output_filename,
                output_dir=args.output_dir,
            )
            WORKSTATION_LOGGER.info(f"Filter operation completed successfully. Output: {output_path}")
            # Success string for AP sequence
            print("successful")
        except Exception as e:
            WORKSTATION_LOGGER.error(f"Error filtering reference by limits: {e}")
            # Specific error message for AP report
            print(str(e))
            raise

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
        except Exception as e:
            self._show_error_popup("SwitchBox Error", f"Failed to set channel.\n\n{e}")
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
        except Exception as e:
            self._show_error_popup("SwitchBox Error", f"Failed to open box.\n\n{e}")
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
        except Exception as e:
            # Scanner not available - show popup, return NaN so caller can detect the failure
            WORKSTATION_LOGGER.error("scan_serial failed: %s", e)
            self._show_error_popup("Scanner Not Found", f"No scanner connected.\n\n{e}")
            print("NaN")
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
            target=None,
            port=None,
            workstation_id=self.workstation_id,
            service_host=self.host
        )
        result = device.discover(timeout=2)
        print(result)

    def get_gain_calibration(self, args):
        device = self._get_oca_device(args)
        result = device.get_gain_calibration()
        WORKSTATION_LOGGER.debug("get_gain_calibration result: %s", result)
        values = result.get("calibration_values", [])
        print(values[0] if values else "")

    def set_gain_calibration(self, args):
        device = self._get_oca_device(args)
        print(device.set_gain_calibration(args.value)["success"])

    def get_mode(self, args):
        device = self._get_oca_device(args)
        result = device.get_mode()
        WORKSTATION_LOGGER.debug("get_mode result: %s", result)
        print(result.get("mode", ""))

    def set_mode(self, args):
        device = self._get_oca_device(args)
        print(device.set_mode(args.position)["success"])

    def get_audio_input(self, args):
        device = self._get_oca_device(args)
        result = device.get_audio_input()
        WORKSTATION_LOGGER.debug("get_audio_input result: %s", result)
        print(result.get("input_mode", ""))

    def set_audio_input(self, args):
        """Set audio input mode."""
        device = self._get_oca_device(args)
        print(device.set_audio_input(args.mode))

    def get_bass_management(self, args):
        device = self._get_oca_device(args)
        result = device.get_bass_management()
        WORKSTATION_LOGGER.debug("get_bass_management result: %s", result)
        print(result.get("bass_management_mode", ""))

    def set_bass_management(self, args):
        device = self._get_oca_device(args)
        print(device.set_bass_management(args.position)["success"])

    def get_bass_management_bypass(self, args):
        device = self._get_oca_device(args)
        result = device.get_bass_management_bypass()
        WORKSTATION_LOGGER.debug("get_bass_management_bypass result: %s", result)
        print(result.get("bypass_state", ""))

    def set_bass_management_bypass(self, args):
        device = self._get_oca_device(args)
        result = device.set_bass_management_bypass(args.position)
        print(result.get("success", result.get("bypass_state", result)))

    def get_gain(self, args):
        """Get subwoofer gain level."""
        device = self._get_oca_device(args)
        result = device.get_gain()
        WORKSTATION_LOGGER.debug("get_gain result: %s", result)
        print(result.get("gain", ""))

    def set_gain(self, args):
        """Set subwoofer gain level."""
        device = self._get_oca_device(args)
        print(device.set_gain(args.value)["success"])

    def get_phase_delay(self, args):
        """Get current phase delay setting."""
        device = self._get_oca_device(args)
        result = device.get_phase_delay()
        WORKSTATION_LOGGER.debug("get_phase_delay result: %s", result)
        print(result.get("phase_delay", ""))

    def set_phase_delay(self, args):
        device = self._get_oca_device(args)
        print(device.set_phase_delay(args.position)["success"])

    def get_mute(self, args):
        device = self._get_oca_device(args)
        result = device.get_mute()
        WORKSTATION_LOGGER.debug("get_mute result: %s", result)
        print(result.get("mute_state", ""))

    def set_mute(self, args):
        device = self._get_oca_device(args)
        print(device.set_mute(args.position)["success"])

    def get_mac_address(self, args):
        device = self._get_oca_device(args)
        result = device.get_mac_address()
        WORKSTATION_LOGGER.debug("get_mac_address result: %s", result)
        print(result.get("value", ""))

    def set_mac_address(self, args):
        device = self._get_oca_device(args)
        result = device.set_mac_address(args.value)
        print(result.get("success", result.get("value", result)))

    def provision_mac(self, args):
        # Opens a TCP/OCA connection to the device. Fails fast (timeout) if unreachable.
        device = self._get_oca_device(args)
        result = mac_provisioner.provision_mac(
            device=device,
            serial=args.serial,
            workstation_id=self.workstation_id,  # written to DB as audit trail
            default_mac=args.default_mac,
            arp_delay=args.arp_delay,             # None uses ARP_FLUSH_DELAY constant (3.0 s)
        )
        WORKSTATION_LOGGER.info("provision_mac [%s]: %s", args.serial, result)
        if result.get("low_pool"):
            # Logged as WARNING so it surfaces in AP's test report without failing the step.
            WORKSTATION_LOGGER.warning(
                "MAC pool running low — %s MACs remaining.", result.get("remaining")
            )
        status = result.get("status")
        if status in ("success", "retest_ok"):
            # AP reads the literal string "successful" as PASS for this step.
            print("successful")
        else:
            reason = result.get("reason", "error")
            # "Error:" prefix is the AP convention — any other prefix is treated as PASS.
            if reason == "duplicate_sn":
                msg = (
                    f"Error: duplicate serial number — "
                    f"SN {args.serial!r} is already assigned to MAC {result.get('db_mac', '?')}"
                )
            elif reason == "pool_exhausted":
                msg = "Error: MAC pool exhausted — no addresses available"
            elif reason == "verify_failed":
                msg = (
                    f"Error: MAC write verification failed — "
                    f"wrote {result.get('written', '?')}, read back {result.get('read_back', '?')}"
                )
            elif reason == "unknown_device":
                msg = (
                    f"Error: unknown device — "
                    f"SN {args.serial!r} has no DB record but device reports MAC {result.get('current_mac', '?')}"
                )
            elif reason == "mac_mismatch":
                msg = (
                    f"Error: MAC mismatch — "
                    f"DB has {result.get('db_mac', '?')}, device reports {result.get('device_mac', '?')}"
                )
            elif reason == "oca_error":
                msg = f"Error: OCA communication failure — {result.get('detail', 'no detail')}"
            else:
                msg = f"Error: {reason}"
            print(msg)

    def init_mac_db(self, args):
        mac_database.init_db()
        WORKSTATION_LOGGER.info("MAC database initialized.")
        print(json.dumps({"status": "ok", "detail": "MAC database initialized."}))

    def set_mac_range(self, args):
        # No OCA or provisioner involvement — pure DB operation, safe to call off-line.
        mac_database.set_mac_range(
            start_mac=args.start_mac,
            end_mac=args.end_mac,
            warn_threshold=args.warn_threshold,
        )
        WORKSTATION_LOGGER.info(
            "MAC range set: %s – %s (warn_threshold=%d)",
            args.start_mac, args.end_mac, args.warn_threshold,
        )
        # JSON output allows post-setup verification scripts to confirm the range.
        print(json.dumps({
            "status": "ok",
            "start_mac": args.start_mac,
            "end_mac": args.end_mac,
            "warn_threshold": args.warn_threshold,
        }))

    def get_mac_pool_status(self, args):
        status = mac_database.get_pool_status()
        print(json.dumps(status))

    def export_mac_log(self, args):
        # getattr guards against callers that omit the --serial flag entirely;
        # `or None` converts an empty string to None so the DB query returns all rows.
        serial_filter = getattr(args, "serial", None) or None
        rows = mac_database.get_provisioning_log(serial=serial_filter)
        if args.status:
            rows = [r for r in rows if r["status"] == args.status]
        fieldnames = ["serial", "mac", "status", "reserved_at", "written_at", "verified_at", "workstation_id"]
        with open(args.output_path, "w", newline="", encoding="utf-8") as f:
            # extrasaction="ignore" silently drops any future DB columns not in fieldnames,
            # keeping the CSV contract stable when the schema is extended.
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        WORKSTATION_LOGGER.info("export_mac_log: %d entries written to %s", len(rows), args.output_path)
        print(json.dumps({"status": "ok", "exported": len(rows), "path": args.output_path}))

    def register_golden_sample(self, args):
        # Idempotent — safe to call repeatedly (e.g. on every AP startup) without
        # creating duplicate entries or raising errors.
        already_registered = mac_database.is_golden_sample(args.serial)
        if already_registered:
            print(f"already registered: {args.serial}")
            return
        mac_database.add_golden_sample(serial=args.serial, note=args.note)
        WORKSTATION_LOGGER.info("register_golden_sample: serial='%s' note='%s'", args.serial, args.note)
        print(f"registered: {args.serial}")

    def get_serial_number(self, args):
        device = self._get_oca_device(args)
        result = device.get_serial_number()
        WORKSTATION_LOGGER.debug("get_serial_number result: %s", result)
        print(result.get("value", ""))

    def set_serial_number(self, args):
        device = self._get_oca_device(args)
        result = device.set_serial_number(args.value)
        print(result.get("success", result.get("value", result)))

    def get_model_description(self, args):
        device = self._get_oca_device(args)
        result = device.get_model_description()
        WORKSTATION_LOGGER.debug("get_model_description result: %s", result)
        print(result.get("model", result.get("raw", "")))

    def get_firmware_version(self, args):
        device = self._get_oca_device(args)
        result = device.get_firmware_version()
        WORKSTATION_LOGGER.debug("get_firmware_version result: %s", result)
        print(result.get("version", result.get("raw", "")))

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

    def upload_measurement(self, args):
        """Uploads a measurement file into local matcher DB (JSON path deprecated)."""
        try:
            upload_data = MeasurementUpload.prepare_upload(
                args.measurement_path,
                args.serial_number,
                self.workstation_id
            )

            if getattr(args, "server", False):
                WORKSTATION_LOGGER.error("upload_measurement currently supports local DB writes only")
                self._show_error_popup(
                    "Feature Not Available",
                    "upload_measurement currently supports local DB writes only.\n"
                    "Service mode is disabled for this feature."
                )
                print(False)
                return

            WORKSTATION_LOGGER.info(
                "Writing measurement to local DB: db=%s, serial=%s",
                args.db_path,
                args.serial_number,
            )
            result = MeasurementUpload.write_measurement_local_db(
                upload_data,
                args.serial_number,
                args.db_path,
            )

            if result.get("status") == "success":
                WORKSTATION_LOGGER.info("Measurement written locally: %s", result.get("db_file"))
                print(True)
            elif result.get("error") == "status_blocked":
                sn = result.get("serial_number", args.serial_number)
                current_status = result.get("current_status", "unknown")
                if current_status == "paired":
                    msg = (
                        f"DUT {sn} is currently paired.\n"
                        "Unpair in the Matching App first, then remeasure."
                    )
                else:
                    msg = (
                        f"DUT {sn} is currently '{current_status}'.\n"
                        "Please resolve this state in the Matching App before remeasurement."
                    )
                WORKSTATION_LOGGER.warning(
                    "Measurement rejected due to status: serial=%s, status=%s",
                    sn,
                    current_status,
                )
                self._show_error_popup("DUT Not In Pool", msg)
                print(False)
            else:
                WORKSTATION_LOGGER.error("Write failed: %s", result.get("error", "Unknown error"))
                print(False)

        except Exception as e:
            WORKSTATION_LOGGER.error("Measurement upload failed: %s", str(e))
            print(False)

    def calibrate_gain(self, args):
        """Calculates gain calibration between input and target measurements."""
        try:
            # Use GainCalibration class
            results = GainCalibration.calculate_gain_difference(
                args.input_file,
                args.target_file,
                args.frequencies
            )
            
            # Only print the average gain difference
            print(f"{results['average_gain_db']:.2f}")
                
        except Exception as e:
            WORKSTATION_LOGGER.error("Gain calibration failed: %s", str(e))
            print(f"ERROR: {str(e)}")

    def init_asub(self, args):
        """Initialize ASubs subwoofer with default settings."""
        try:
            
            device = self._get_oca_device(args)
            WORKSTATION_LOGGER.info("Starting ASubs initialization sequence")
            
            # Set internal DSP mode
            result = device.set_mode("internal-dsp")
            WORKSTATION_LOGGER.debug("Set mode result: %s", result)
            
            # Set gain to 0 dB
            result = device.set_gain(0)
            WORKSTATION_LOGGER.debug("Set gain result: %s", result)
            
            # Set mute to normal (unmuted)
            result = device.set_mute("normal")
            WORKSTATION_LOGGER.debug("Set mute result: %s", result)
            
            # Set phase delay to 0 degrees
            result = device.set_phase_delay("deg0")
            WORKSTATION_LOGGER.debug("Set phase delay result: %s", result)
            
            # Set gain calibration to 0 dB
            result = device.set_gain_calibration(0)
            WORKSTATION_LOGGER.debug("Set gain calibration result: %s", result)

            # Set audio input to analogue XLR
            result = device.set_audio_input("analogue-xlr")
            WORKSTATION_LOGGER.debug("Set audio input result: %s", result)

            # Set bass management to wide
            result = device.set_bass_management("wide")
            WORKSTATION_LOGGER.debug("Set bass management result: %s", result)

            # Disable bass management bypass (so bass management is active)
            result = device.set_bass_management_bypass("disabled")
            WORKSTATION_LOGGER.debug("Set bass management bypass result: %s", result)

            WORKSTATION_LOGGER.info("ASubs initialization sequence completed successfully")
            print("Initialization successful")
            return True
            
        except Exception as e:
            error_msg = f"ASubs initialization failed: {str(e)}"
            WORKSTATION_LOGGER.error(error_msg)
            print(f"Initialization failed: {str(e)}")
            return False

    def setup_references(self, args):
        """Setup References directory by copying DefaultReferences if needed."""
        try:
            target_path = os.path.abspath(args.path)
            references_dir = os.path.join(target_path, "References")

            WORKSTATION_LOGGER.info("Checking References directory at: %s", references_dir)

            # Check if References directory exists
            if os.path.exists(references_dir):
                WORKSTATION_LOGGER.info("References directory already exists")
                print("References directory already exists")
                return True

            # References doesn't exist, need to create and copy
            WORKSTATION_LOGGER.info("References directory not found, creating...")

            # Determine source directory (stereo or mono)
            use_mono = getattr(args, "mono", False)
            if use_mono:
                default_refs = os.path.join(os.getcwd(), "DefaultReferences", "Mono")
                WORKSTATION_LOGGER.info("Using mono references from: %s", default_refs)
            else:
                default_refs = os.path.join(os.getcwd(), "DefaultReferences")
                WORKSTATION_LOGGER.info("Using stereo references from: %s", default_refs)

            if not os.path.exists(default_refs):
                mono_suffix = "\\Mono" if use_mono else ""
                error_msg = f"DefaultReferences{mono_suffix} directory not found at: {default_refs}"
                WORKSTATION_LOGGER.error(error_msg)
                print(f"ERROR: {error_msg}")
                return False

            # Create References directory and copy contents
            os.makedirs(references_dir, exist_ok=True)
            WORKSTATION_LOGGER.info("Created References directory")

            # Copy all contents from source to References
            for item in os.listdir(default_refs):
                # Skip the Mono subdirectory when copying stereo references
                if not use_mono and item == "Mono":
                    continue

                src_path = os.path.join(default_refs, item)
                dst_path = os.path.join(references_dir, item)

                if os.path.isdir(src_path):
                    shutil.copytree(src_path, dst_path)
                    WORKSTATION_LOGGER.info("Copied directory: %s", item)
                else:
                    shutil.copy2(src_path, dst_path)
                    WORKSTATION_LOGGER.info("Copied file: %s", item)

            mode = "mono" if use_mono else "stereo"
            WORKSTATION_LOGGER.info("Successfully copied %s DefaultReferences to References", mode)
            print(f"References directory created and populated successfully ({mode})")
            return True

        except Exception as e:
            error_msg = f"Failed to setup References: {str(e)}"
            WORKSTATION_LOGGER.error(error_msg)
            print(f"ERROR: {error_msg}")
            return False

    def _check_serial_match(self, scanned: str, reference: str, measure_reference: bool,
                              reference_label: str, other_label: str) -> bool:
        """Shared logic for serial-match checks with warning popups.

        Returns True if scanned == reference, False otherwise.
        Shows a warning popup when the connected unit does not match what is expected.
        """
        is_match = scanned == reference

        if measure_reference and not is_match:
            msg = (
                f"The {reference_label} is expected to be measured, "
                f"but a different unit is connected.\n\n"
                f"Expected: {reference}\n"
                f"Scanned:  {scanned}"
            )
            WORKSTATION_LOGGER.warning(
                "%s expected but different unit connected: scanned='%s'", reference_label, scanned
            )
            self._show_warning_popup("Wrong Unit Connected", msg)
        elif not measure_reference and is_match:
            msg = (
                f"An {other_label} is expected to be measured, "
                f"but the {reference_label} is connected.\n\n"
                f"{reference_label}: {reference}\n"
                f"Scanned:  {scanned}"
            )
            WORKSTATION_LOGGER.warning(
                "%s expected but %s is connected: scanned='%s'", other_label, reference_label, scanned
            )
            self._show_warning_popup(f"{reference_label} Connected", msg)

        return is_match

    def is_golden_sample(self, args):
        """Checks whether the scanned serial number matches the Golden Sample serial number
        and validates whether the correct unit type is connected.

        Args:
            args: CLI arguments with 'scanned_serial', 'golden_sample_serial', and
                  'measure_golden_sample' (True = Golden Sample expected,
                  False = EOL unit expected).

        Prints 'True' if the scanned serial matches the Golden Sample, 'False' otherwise.
        Shows a warning popup on mismatch between expected and actual unit type.
        """
        scanned = args.scanned_serial.strip()
        golden = args.golden_sample_serial.strip()
        measure_golden = args.measure_golden_sample

        WORKSTATION_LOGGER.info(
            "is_golden_sample: scanned='%s', golden='%s', measure_golden=%s",
            scanned, golden, measure_golden
        )

        is_golden = self._check_serial_match(
            scanned, golden, measure_golden,
            reference_label="Golden Sample",
            other_label="EOL unit"
        )
        print(is_golden)

    def is_default_serial(self, args):
        """Checks whether the scanned serial number matches the expected default serial number
        and validates whether the correct unit type is connected.

        Args:
            args: CLI arguments with 'scanned_serial', 'default_serial', and
                  'measure_default' (True = default-serial unit expected,
                  False = production unit expected).

        Prints 'True' if the scanned serial matches the default serial, 'False' otherwise.
        Shows a warning popup on mismatch between expected and actual unit type.
        """
        scanned = args.scanned_serial.strip()
        default = args.default_serial.strip()
        measure_default = args.measure_default

        WORKSTATION_LOGGER.info(
            "is_default_serial: scanned='%s', default='%s', measure_default=%s",
            scanned, default, measure_default
        )

        is_default = self._check_serial_match(
            scanned, default, measure_default,
            reference_label="default unit",
            other_label="production unit"
        )
        print(is_default)

    def verify_system(self, args):
        """Verify two modules are a matched pair and link them to a system serial.

        Prints True if successful, or an error message string if not.
        All diagnostic output also goes to the log file and error popups.
        """
        import sqlite3 as _sqlite3
        try:
            db_path = args.db_path
            sn1 = args.module_sn_1.strip()
            sn2 = args.module_sn_2.strip()
            system_sn = args.system_sn.strip()

            WORKSTATION_LOGGER.info(
                "verify_system: system=%s, module1=%s, module2=%s, db=%s",
                system_sn, sn1, sn2, db_path,
            )

            import os as _os
            _os.makedirs(_os.path.dirname(_os.path.abspath(db_path)), exist_ok=True)
            con = _sqlite3.connect(db_path)
            con.execute("PRAGMA journal_mode=DELETE")
            con.execute("PRAGMA busy_timeout=5000")

            # Ensure system_builds table exists
            con.execute("""
                CREATE TABLE IF NOT EXISTS system_builds (
                    system_serial TEXT PRIMARY KEY,
                    module_1      TEXT NOT NULL,
                    module_2      TEXT NOT NULL,
                    built_at      TEXT NOT NULL
                )
            """)
            con.commit()
            cur = con.cursor()

            # 1. Check both serials exist
            cur.execute("SELECT serial, status, partner FROM drivers WHERE serial = ?", (sn1,))
            row1 = cur.fetchone()
            cur.execute("SELECT serial, status, partner FROM drivers WHERE serial = ?", (sn2,))
            row2 = cur.fetchone()

            if row1 is None:
                con.close()
                msg = f"Module {sn1} not found in database."
                WORKSTATION_LOGGER.warning("verify_system FAIL: module %s not found", sn1)
                self._show_error_popup("System Verification Failed", msg)
                print(msg)
                return
            if row2 is None:
                con.close()
                msg = f"Module {sn2} not found in database."
                WORKSTATION_LOGGER.warning("verify_system FAIL: module %s not found", sn2)
                self._show_error_popup("System Verification Failed", msg)
                print(msg)
                return

            _, status1, partner1 = row1
            _, status2, partner2 = row2

            # 2. Check modules are in an acceptable status
            valid_statuses = {'matched', 'paired'}
            if status1 not in valid_statuses:
                con.close()
                msg = f"Module {sn1} is not matched or paired (status: {status1})."
                WORKSTATION_LOGGER.warning("verify_system FAIL: %s", msg)
                self._show_error_popup("System Verification Failed", msg)
                print(msg)
                return
            if status2 not in valid_statuses:
                con.close()
                msg = f"Module {sn2} is not matched or paired (status: {status2})."
                WORKSTATION_LOGGER.warning("verify_system FAIL: %s", msg)
                self._show_error_popup("System Verification Failed", msg)
                print(msg)
                return

            # 3. Check they are matched/paired to each other
            if partner1 != sn2:
                con.close()
                msg = (
                    f"Module {sn1} is not matched to {sn2}. "
                    f"Its current partner is: {partner1 or 'none'}."
                )
                WORKSTATION_LOGGER.warning("verify_system FAIL: %s", msg)
                self._show_error_popup("System Verification Failed", msg)
                print(msg)
                return
            if partner2 != sn1:
                con.close()
                msg = (
                    f"Module {sn2} is not matched to {sn1}. "
                    f"Its current partner is: {partner2 or 'none'}."
                )
                WORKSTATION_LOGGER.warning("verify_system FAIL: %s", msg)
                self._show_error_popup("System Verification Failed", msg)
                print(msg)
                return

            # 4. Auto-pair if matched but not yet paired
            now = datetime.now().isoformat()
            action = "already paired"
            if status1 == 'matched' or status2 == 'matched':
                cur.execute(
                    "UPDATE drivers SET status='paired', matched_at=? WHERE serial IN (?, ?)",
                    (now, sn1, sn2),
                )
                action = "auto-paired"
                WORKSTATION_LOGGER.info("verify_system: auto-paired %s and %s", sn1, sn2)

            # 5. Unlink any existing system_builds entries referencing these modules
            cur.execute(
                "DELETE FROM system_builds WHERE module_1 IN (?, ?) OR module_2 IN (?, ?)",
                (sn1, sn2, sn1, sn2),
            )

            # 6. Link system_sn to the two modules
            cur.execute(
                "INSERT OR REPLACE INTO system_builds "
                "(system_serial, module_1, module_2, built_at) VALUES (?, ?, ?, ?)",
                (system_sn, sn1, sn2, now),
            )
            con.commit()
            con.close()

            WORKSTATION_LOGGER.info(
                "verify_system PASS: system=%s linked to %s and %s (%s)",
                system_sn, sn1, sn2, action,
            )
            print(True)

        except Exception as e:
            WORKSTATION_LOGGER.error("verify_system error: %s", str(e))
            self._show_error_popup("System Verification Error", str(e))
            print(f"Error: {e}")

    def setup_arg_parser(self):
        self.parser = build_workstation_parser()

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
            # --host implies --server for all commands that support it
            if hasattr(args, "server"):
                args.server = True

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
