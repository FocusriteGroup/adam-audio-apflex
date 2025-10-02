import socket
import json
import sys
import logging
import argparse
import os
from datetime import datetime

# ADAM Audio Workstation Logging - angleichen an Utils-Struktur
log_dir = "logs/adam_audio"
os.makedirs(log_dir, exist_ok=True)

today = datetime.now().strftime("%Y-%m-%d")
log_filename = f"{log_dir}/adam_workstation_log_{today}.log"

# Configure logging nur File - KEIN Console Output für Audio Precision calls
logging.basicConfig(
    filename=log_filename,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(name)s] - %(message)s"
)

# Workstation-Logger
WORKSTATION_LOGGER = logging.getLogger("AdamWorkstation")

logging.info("----------------------------------- ADAM Audio Workstation started")

class AdamWorkstation:
    """
    ADAM Audio Production Workstation.

    Complete workstation software for ADAM Audio device control,
    production line operations, EOL testing, and quality assurance.
    
    Integrates with ADAM Audio services to provide a comprehensive
    production environment for speaker manufacturing and testing.
    """

    def __init__(self, host=None, port=65432, service_name="ADAMService", scanner_type="honeywell"):
        """
        Initialize the ADAM Audio Workstation.

        Args:
            host (str): Service IP address (auto-discovered if None)
            port (int): Service port number. Default is 65432.
            service_name (str): Name of ADAM service to connect to
            scanner_type (str): Type of scanner to use. Default is "honeywell".
        """
        self.port = port
        self.service_name = service_name
        self.host = host
        
        # Workstation-ID für Logging
        self.workstation_id = socket.gethostname()
        
        # NEU: Lazy Loading - Hardware-Manager werden nur bei Bedarf initialisiert
        self._switchbox_manager = None
        self._scanner_manager = None
        self._scanner_type = scanner_type  # Scanner-Type für spätere Initialisierung speichern

        # Map of commands to their corresponding methods
        self.command_map = {
            "wake_up": self.wake_up,
            "generate_timestamp_extension": self.generate_timestamp_extension,
            "construct_path": self.construct_path,
            "get_timestamp_subpath": self.get_timestamp_subpath,
            "generate_file_prefix": self.generate_file_prefix,
            "activate_measurement": self.activate_measurement,
            "set_average": self.set_average,
            "set_channel": self.set_channel,
            "open_box": self.open_box,
            "scan_serial": self.scan_serial,
            "get_biquad_coefficients": self.get_biquad_coefficients,
            "set_device_biquad": self.set_device_biquad,
            "get_serial_number": self.get_serial_number,
            "get_gain": self.get_gain,
            "get_device_biquad": self.get_device_biquad,
            "set_gain": self.set_gain,
            "get_model_description": self.get_model_description,
            "get_firmware_version": self.get_firmware_version,
            "get_audio_input": self.get_audio_input,
            "set_audio_input": self.set_audio_input,
            "get_mute": self.get_mute,
            "set_mute": self.set_mute,
            "get_mode": self.get_mode,
            "set_mode": self.set_mode,
            "get_phase_delay": self.get_phase_delay,
            "set_phase_delay": self.set_phase_delay,
            "check_measurement_trials": self.check_measurement_trials,
        }

        self.setup_arg_parser()

    # NEU: Properties für Lazy Loading
    @property
    def switchbox_manager(self):
        """Lazy-loaded SwitchBox manager."""
        if self._switchbox_manager is None:
            WORKSTATION_LOGGER.info("Initializing SwitchBox hardware on first use")
            from workstation_utils import SwitchBoxManager
            self._switchbox_manager = SwitchBoxManager(self.workstation_id)
        return self._switchbox_manager

    @property
    def scanner_manager(self):
        """Lazy-loaded Scanner manager."""
        if self._scanner_manager is None:
            WORKSTATION_LOGGER.info("Initializing %s Scanner hardware on first use", self._scanner_type)
            from workstation_utils import ScannerManager
            self._scanner_manager = ScannerManager(self.workstation_id, self._scanner_type)
        return self._scanner_manager

    def _discover_service(self):
        """
        Discover ADAM service using connector (lazy import).
        
        Returns:
            str: Service IP address or None if not found
        """
        try:
            # Lazy import to avoid import errors if connector not available
            from adam_connector import AdamConnector
            
            WORKSTATION_LOGGER.info("Auto-discovering ADAM service...")
            connector = AdamConnector(
                default_port=self.port,
                service_name=self.service_name,
                setup_logging=False  # Use workstation logging
            )
            
            service_ip = connector.find_service_ip(discovery_timeout=3)
            if service_ip:
                WORKSTATION_LOGGER.info("ADAM service discovered at: %s:%d", service_ip, self.port)
                return service_ip
            else:
                WORKSTATION_LOGGER.warning("No ADAM service found via discovery")
                return None
        except ImportError:
            WORKSTATION_LOGGER.error("adam_connector.py not found - auto-discovery disabled")
            return None
        except Exception as e:
            WORKSTATION_LOGGER.error("Service discovery failed: %s", e)
            return None

    def _ensure_host_available(self):
        """
        Ensure that a valid host is available.
        Uses discovery only if no host was specified.
        
        Returns:
            bool: True if host is available, False otherwise
        """
        if self.host:
            # Host already specified - direkte Verwendung
            return True
            
        # Kein Host - versuche Auto-Discovery
        discovered_host = self._discover_service()
        if discovered_host:
            self.host = discovered_host
            return True
        else:
            WORKSTATION_LOGGER.error("No ADAM service host available and discovery failed")
            return False

    def send_command(self, command, wait_for_response=True):
        """
        Send a command to the ADAM service and optionally wait for a response.

        Args:
            command (dict): The command to send to the service.
            wait_for_response (bool): Whether to wait for a response from the service.

        Returns:
            str: The service's response if wait_for_response is True, otherwise None.
        """
        # Ensure we have a valid host
        if not self._ensure_host_available():
            error_msg = "Error: No ADAM service available. Use --host to specify manually."
            WORKSTATION_LOGGER.error(error_msg)
            return error_msg

        try:
            WORKSTATION_LOGGER.info("Connecting to ADAM service at %s:%s...", self.host, self.port)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
                client_socket.connect((self.host, self.port))  # Connect to the service
                WORKSTATION_LOGGER.info("Connected to ADAM service. Sending command: %s", command)
                client_socket.send(json.dumps(command).encode("utf-8"))  # Send the command as JSON

                if wait_for_response:
                    response = client_socket.recv(1024).decode("utf-8")  # Receive and decode the service's response
                    WORKSTATION_LOGGER.info("Received response from ADAM service: %s", response)
                    return response
                else:
                    WORKSTATION_LOGGER.info("No response expected for this command.")
                    return None
        except socket.error as e:
            WORKSTATION_LOGGER.error("Socket error: %s", e)
            return f"Error: {e}"
        except json.JSONDecodeError as e:
            WORKSTATION_LOGGER.error("JSON decode error: %s", e)
            return f"Error: {e}"

    # Command methods
    def wake_up(self, args):
        """Send a command to wake up the service."""
        WORKSTATION_LOGGER.info("Executing 'wake_up' command.")
        command = {"action": "wake_up", "wait_for_response": False}
        self.send_command(command, wait_for_response=False)

    def generate_timestamp_extension(self, args):
        """Request the service to generate a timestamp extension."""
        WORKSTATION_LOGGER.info("Executing 'generate_timestamp_extension' command.")
        command = {"action": "generate_timestamp_extension"}
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def construct_path(self, args):
        """Request the service to construct a path from the provided components."""
        WORKSTATION_LOGGER.info("Executing 'construct_path' command with paths: %s", args.paths)
        command = {"action": "construct_path", "paths": args.paths}
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def get_timestamp_subpath(self, args):
        """Request the service to generate a timestamp subpath."""
        WORKSTATION_LOGGER.info("Executing 'get_timestamp_subpath' command.")
        command = {"action": "get_timestamp_subpath"}
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def generate_file_prefix(self, args):
        """Request the service to generate a file prefix from the provided strings."""
        WORKSTATION_LOGGER.info("Executing 'generate_file_prefix' command with strings: %s", args.strings)
        command = {"action": "generate_file_prefix", "strings": args.strings}
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def activate_measurement(self, args):
        """Request the service to activate a specific measurement."""
        WORKSTATION_LOGGER.info("Executing 'activate_measurement' command for measurement: %s", args.measurement_name)
        command = {"action": "activate_measurement", "measurement_name": args.measurement_name, "wait_for_response": False}
        self.send_command(command, wait_for_response=False)

    def set_average(self, args):
        """Request the service to set the number of averages."""
        if args.averages <= 0:
            WORKSTATION_LOGGER.error("'averages' must be a positive integer.")
            sys.exit(1)
        WORKSTATION_LOGGER.info("Executing 'set_average' command with averages: %d", args.averages)
        command = {"action": "set_average", "averages": args.averages, "wait_for_response": False}
        self.send_command(command, wait_for_response=False)

    # NEU: Hardware-Commands verwenden Properties (Lazy Loading)
    def set_channel(self, args):
        """Set channel on local SwitchBox hardware only."""
        try:
            result_channel = self.switchbox_manager.set_channel(  # ← Property-Zugriff
                channel=args.channel,
                service_host=self.host,
                service_port=self.port
            )
            print(f"Channel set to {result_channel}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

    def open_box(self, args):
        """Open box on local SwitchBox hardware only."""
        try:
            box_status = self.switchbox_manager.open_box(  # ← Property-Zugriff
                service_host=self.host,
                service_port=self.port
            )
            print(f"Box status: {box_status}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

    def scan_serial(self, args):
        """Scan serial number using configured scanner hardware."""
        try:
            serial_number = self.scanner_manager.scan_serial(  # ← Property-Zugriff
                service_host=self.host,
                service_port=self.port
            )
            print(serial_number)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

    def get_biquad_coefficients(self, args):
        """Request the service to calculate biquad filter coefficients."""
        WORKSTATION_LOGGER.info("Executing 'get_biquad_coefficients' with: type=%s, gain=%s, peak_freq=%s, Q=%s, sample_rate=%s", 
                 args.filter_type, args.gain, args.peak_freq, args.Q, args.sample_rate)
        command = {
            "action": "get_biquad_coefficients",
            "filter_type": args.filter_type,
            "gain": args.gain,
            "peak_freq": args.peak_freq,
            "Q": args.Q,
            "sample_rate": args.sample_rate,
            "wait_for_response": True
        }
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def set_device_biquad(self, args):
        """Send coefficients to the service to set them on the OCA device."""
        try:
            coeffs = json.loads(args.coefficients)
        except Exception as e:
            print("Fehler beim Parsen der Koeffizienten:", e)
            return
        command = {
            "action": "set_device_biquad",
            "index": args.index,
            "coefficients": coeffs,
            "target_ip": args.target_ip,
            "port": args.port,
            "wait_for_response": True
        }
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def get_serial_number(self, args):
        """Request the service to get the serial number from the OCA device."""
        WORKSTATION_LOGGER.info("Executing 'get_serial_number' for %s:%d", args.target_ip, args.port)
        command = {
            "action": "get_serial_number",
            "target_ip": args.target_ip,
            "port": args.port,
            "wait_for_response": True
        }
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def get_gain(self, args):
        """Request the service to get the gain from the OCA device."""
        WORKSTATION_LOGGER.info("Executing 'get_gain' for %s:%d", args.target_ip, args.port)
        command = {
            "action": "get_gain",
            "target_ip": args.target_ip,
            "port": args.port,
            "wait_for_response": True
        }
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def get_device_biquad(self, args):
        """Request the service to get biquad coefficients from the OCA device."""
        WORKSTATION_LOGGER.info("Executing 'get_device_biquad' for index=%d %s:%d", args.index, args.target_ip, args.port)
        command = {
            "action": "get_device_biquad",
            "index": args.index,
            "target_ip": args.target_ip,
            "port": args.port,
            "wait_for_response": True
        }
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def set_gain(self, args):
        """Request the service to set the gain on the OCA device."""
        WORKSTATION_LOGGER.info("Executing 'set_gain' to %s for %s:%d", args.value, args.target_ip, args.port)
        command = {
            "action": "set_gain",
            "value": args.value,
            "target_ip": args.target_ip,
            "port": args.port,
            "wait_for_response": True
        }
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def get_model_description(self, args):
        """Request the service to get the model description from the OCA device."""
        WORKSTATION_LOGGER.info("Executing 'get_model_description' for %s:%d", args.target_ip, args.port)
        command = {
            "action": "get_model_description",
            "target_ip": args.target_ip,
            "port": args.port,
            "wait_for_response": True
        }
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def get_firmware_version(self, args):
        """Request the service to get the firmware version from the OCA device."""
        WORKSTATION_LOGGER.info("Executing 'get_firmware_version' for %s:%d", args.target_ip, args.port)
        command = {
            "action": "get_firmware_version",
            "target_ip": args.target_ip,
            "port": args.port,
            "wait_for_response": True
        }
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def get_audio_input(self, args):
        """Request the service to get the audio input mode from the OCA device."""
        WORKSTATION_LOGGER.info("Executing 'get_audio_input' for %s:%d", args.target_ip, args.port)
        command = {
            "action": "get_audio_input",
            "target_ip": args.target_ip,
            "port": args.port,
            "wait_for_response": True
        }
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def set_audio_input(self, args):
        """Request the service to set the audio input mode on the OCA device."""
        WORKSTATION_LOGGER.info("Executing 'set_audio_input' to %s for %s:%d", args.position, args.target_ip, args.port)
        command = {
            "action": "set_audio_input",
            "position": args.position,
            "target_ip": args.target_ip,
            "port": args.port,
            "wait_for_response": True
        }
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def get_mute(self, args):
        """Request the service to get the mute state from the OCA device."""
        WORKSTATION_LOGGER.info("Executing 'get_mute' for %s:%d", args.target_ip, args.port)
        command = {
            "action": "get_mute",
            "target_ip": args.target_ip,
            "port": args.port,
            "wait_for_response": True
        }
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def set_mute(self, args):
        """Request the service to set the mute state on the OCA device."""
        WORKSTATION_LOGGER.info("Executing 'set_mute' to %s for %s:%d", args.state, args.target_ip, args.port)
        command = {
            "action": "set_mute",
            "state": args.state,
            "target_ip": args.target_ip,
            "port": args.port,
            "wait_for_response": True
        }
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def get_mode(self, args):
        """Request the service to get the control mode from the OCA device."""
        WORKSTATION_LOGGER.info("Executing 'get_mode' for %s:%d", args.target_ip, args.port)
        command = {
            "action": "get_mode",
            "target_ip": args.target_ip,
            "port": args.port,
            "wait_for_response": True
        }
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def set_mode(self, args):
        """Request the service to set the control mode on the OCA device."""
        WORKSTATION_LOGGER.info("Executing 'set_mode' to %s for %s:%d", args.position, args.target_ip, args.port)
        command = {
            "action": "set_mode",
            "position": args.position,
            "target_ip": args.target_ip,
            "port": args.port,
            "wait_for_response": True
        }
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def get_phase_delay(self, args):
        """Request the service to get the phase delay from the OCA device."""
        WORKSTATION_LOGGER.info("Executing 'get_phase_delay' for %s:%d", args.target_ip, args.port)
        command = {
            "action": "get_phase_delay",
            "target_ip": args.target_ip,
            "port": args.port,
            "wait_for_response": True
        }
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def set_phase_delay(self, args):
        """Request the service to set the phase delay on the OCA device."""
        WORKSTATION_LOGGER.info("Executing 'set_phase_delay' to %s for %s:%d", args.position, args.target_ip, args.port)
        command = {
            "action": "set_phase_delay",
            "position": args.position,
            "target_ip": args.target_ip,
            "port": args.port,
            "wait_for_response": True
        }
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def check_measurement_trials(self, args):
        """Check the allowed measurement trials for a serial number."""
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

    def setup_arg_parser(self):
        """Set up the argument parser for command-line arguments."""
        parser = argparse.ArgumentParser(
            description="ADAM Audio Production Workstation",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Connection Examples:
  # Fast: Direct connection (für häufige Verwendung)
  python adam_workstation.py --host 192.168.1.166 get_serial_number 192.168.1.100 7000
  
  # Auto-discovery (wenn Service-IP unbekannt)
  python adam_workstation.py get_serial_number 192.168.1.100 7000
  
  # Different scanner type (future)
  python adam_workstation.py --scanner-type manual scan_serial
            """
        )
        
        # Global connection parameters
        parser.add_argument("--host", "--service-host", dest="service_host",
                           help="ADAM service IP address (auto-discovered if not specified)")
        parser.add_argument("--port", "--service-port", dest="service_port", type=int, default=65432,
                           help="ADAM service port (default: 65432)")
        parser.add_argument("--service-name", default="ADAMService",
                           help="Name of ADAM service to connect to (default: ADAMService)")
        
        # Scanner configuration
        parser.add_argument("--scanner-type", choices=["honeywell"], default="honeywell",
                           help="Type of scanner to use (default: honeywell)")
        
        # Subcommands
        subparsers = parser.add_subparsers(dest="command", required=True)

        # Subparser for "wake_up" command
        subparsers.add_parser("wake_up", help="Wake up the service.")

        # Subparser for "generate_timestamp_extension" command
        subparsers.add_parser("generate_timestamp_extension", help="Generate a timestamp extension.")

        # Subparser for "construct_path" command
        parser_construct_path = subparsers.add_parser("construct_path", help="Construct a path.")
        parser_construct_path.add_argument("paths", type=str, nargs="+", help="List of paths to join.")

        # Subparser for "get_timestamp_subpath" command
        subparsers.add_parser("get_timestamp_subpath", help="Get a timestamp subpath.")

        # Subparser for "generate_file_prefix" command
        parser_generate_file_prefix = subparsers.add_parser("generate_file_prefix", help="Generate a file prefix.")
        parser_generate_file_prefix.add_argument("strings", type=str, nargs="+", help="List of strings to combine.")

        # Subparser for "activate_measurement" command
        parser_activate_measurement = subparsers.add_parser("activate_measurement", help="Activate a measurement.")
        parser_activate_measurement.add_argument("measurement_name", type=str, help="Name of the measurement to activate.")

        # Subparser for "set_average" command
        parser_set_average = subparsers.add_parser("set_average", help="Set the number of averages.")
        parser_set_average.add_argument("averages", type=int, help="Number of averages to set.")

        # Subparser for "set_channel" command
        parser_set_channel = subparsers.add_parser("set_channel", help="Set the channel (1 or 2).")
        parser_set_channel.add_argument("channel", type=int, choices=[1, 2], help="Channel to set (1 or 2).")

        # Subparser for "open_box" command
        subparsers.add_parser("open_box", help="Open the box.")

        # Subparser for "scan_serial" command
        subparsers.add_parser("scan_serial", help="Scan the serial number.")

        # Add biquad coefficients command
        biquad_parser = subparsers.add_parser("get_biquad_coefficients", help="Get biquad filter coefficients")
        biquad_parser.add_argument("filter_type", choices=["bell", "high_shelf", "low_shelf"], help="Type of biquad filter")
        biquad_parser.add_argument("gain", type=float, help="Gain in dB")
        biquad_parser.add_argument("peak_freq", type=float, help="Peak frequency in Hz")
        biquad_parser.add_argument("Q", type=float, help="Quality factor")
        biquad_parser.add_argument("sample_rate", type=int, help="Sample rate in Hz")

        # Subparser for "set_device_biquad" command
        set_biquad_parser = subparsers.add_parser("set_device_biquad", help="Set biquad filter on OCA device")
        set_biquad_parser.add_argument("index", type=int, help="Biquad index")
        set_biquad_parser.add_argument("coefficients", type=str, help="Koeffizienten-Liste als JSON-String")
        set_biquad_parser.add_argument("target_ip", type=str, help="OCA device IP address")
        set_biquad_parser.add_argument("port", type=int, help="OCA device port")

        # Subparser for "get_serial_number" command
        get_serial_parser = subparsers.add_parser("get_serial_number", help="Get serial number from OCA device")
        get_serial_parser.add_argument("target_ip", type=str, help="OCA device IP address")
        get_serial_parser.add_argument("port", type=int, help="OCA device port")

        # Subparser for "get_gain" command
        get_gain_parser = subparsers.add_parser("get_gain", help="Get gain from OCA device")
        get_gain_parser.add_argument("target_ip", type=str, help="OCA device IP address")
        get_gain_parser.add_argument("port", type=int, help="OCA device port")

        # Subparser for "set_gain" command
        set_gain_parser = subparsers.add_parser("set_gain", help="Set gain on OCA device")
        set_gain_parser.add_argument("value", type=float, help="Gain value")
        set_gain_parser.add_argument("target_ip", type=str, help="OCA device IP address")
        set_gain_parser.add_argument("port", type=int, help="OCA device port")

        # Subparser for "get_device_biquad" command
        get_device_biquad_parser = subparsers.add_parser("get_device_biquad", help="Get biquad coefficients from OCA device")
        get_device_biquad_parser.add_argument("index", type=int, help="Biquad index")
        get_device_biquad_parser.add_argument("target_ip", type=str, help="OCA device IP address")
        get_device_biquad_parser.add_argument("port", type=int, help="OCA device port")

        # Subparser for "get_model_description" command
        get_model_parser = subparsers.add_parser("get_model_description", help="Get model description from OCA device")
        get_model_parser.add_argument("target_ip", type=str, help="OCA device IP address")
        get_model_parser.add_argument("port", type=int, help="OCA device port")

        # Subparser for "get_firmware_version" command
        get_firmware_parser = subparsers.add_parser("get_firmware_version", help="Get firmware version from OCA device")
        get_firmware_parser.add_argument("target_ip", type=str, help="OCA device IP address")
        get_firmware_parser.add_argument("port", type=int, help="OCA device port")

        # Subparser for "get_audio_input" command
        get_audio_input_parser = subparsers.add_parser("get_audio_input", help="Get audio input mode from OCA device")
        get_audio_input_parser.add_argument("target_ip", type=str, help="OCA device IP address")
        get_audio_input_parser.add_argument("port", type=int, help="OCA device port")

        # Subparser for "set_audio_input" command
        set_audio_input_parser = subparsers.add_parser("set_audio_input", help="Set audio input mode on OCA device")
        set_audio_input_parser.add_argument("position", type=str, help="Audio input position (e.g. 'aes3', 'analogue')")
        set_audio_input_parser.add_argument("target_ip", type=str, help="OCA device IP address")
        set_audio_input_parser.add_argument("port", type=int, help="OCA device port")

        # Subparser for "get_mute" command
        get_mute_parser = subparsers.add_parser("get_mute", help="Get mute state from OCA device")
        get_mute_parser.add_argument("target_ip", type=str, help="OCA device IP address")
        get_mute_parser.add_argument("port", type=int, help="OCA device port")

        # Subparser for "set_mute" command
        set_mute_parser = subparsers.add_parser("set_mute", help="Set mute state on OCA device")
        set_mute_parser.add_argument("state", type=str, choices=["muted", "unmuted"], help="Mute state ('muted' or 'unmuted')")
        set_mute_parser.add_argument("target_ip", type=str, help="OCA device IP address")
        set_mute_parser.add_argument("port", type=int, help="OCA device port")

        # Subparser for "get_mode" command
        get_mode_parser = subparsers.add_parser("get_mode", help="Get control mode from OCA device")
        get_mode_parser.add_argument("target_ip", type=str, help="OCA device IP address")
        get_mode_parser.add_argument("port", type=int, help="OCA device port")

        # Subparser for "set_mode" command
        set_mode_parser = subparsers.add_parser("set_mode", help="Set control mode on OCA device")
        set_mode_parser.add_argument("position", type=str, help="Control mode to set")
        set_mode_parser.add_argument("target_ip", type=str, help="OCA device IP address")
        set_mode_parser.add_argument("port", type=int, help="OCA device port")

        # Subparser für "get_phase_delay"
        get_phase_delay_parser = subparsers.add_parser("get_phase_delay", help="Get phase delay from OCA device")
        get_phase_delay_parser.add_argument("target_ip", type=str, help="OCA device IP address")
        get_phase_delay_parser.add_argument("port", type=int, help="OCA device port")

        # Subparser für "set_phase_delay"
        set_phase_delay_parser = subparsers.add_parser("set_phase_delay", help="Set phase delay on OCA device")
        set_phase_delay_parser.add_argument("position", type=str, help="Phase delay value (e.g. 'deg0', 'deg45', ...)")
        set_phase_delay_parser.add_argument("target_ip", type=str, help="OCA device IP address")
        set_phase_delay_parser.add_argument("port", type=int, help="OCA device port")

        # Subparser für "check_measurement_trials"
        check_trials_parser = subparsers.add_parser("check_measurement_trials", help="Check allowed measurement trials for a serial number")
        check_trials_parser.add_argument("serial_number", type=str, help="Serial number to check")
        check_trials_parser.add_argument("csv_path", type=str, help="Path to the CSV file")
        check_trials_parser.add_argument("max_trials", type=int, help="Maximum allowed trials")

        self.parser = parser

    def parse_and_execute(self):
        """Parse command-line arguments and execute the appropriate function."""
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


if __name__ == "__main__":
    # Parse args first to get scanner config
    temp_parser = argparse.ArgumentParser(add_help=False)
    temp_parser.add_argument("--scanner-type", choices=["honeywell"], default="honeywell")
    temp_args, _ = temp_parser.parse_known_args()
    
    # Create workstation with scanner config
    workstation = AdamWorkstation(scanner_type=temp_args.scanner_type)
    workstation.parse_and_execute()
