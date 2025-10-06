import socket
import json
import sys
import logging
import argparse
import os
import time  # NEU HINZUFÜGEN
from datetime import datetime
from oca.oca_manager import OCAManager
import csv

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

        # NEU: OCA Manager hinzufügen (VORSICHTIG eingefügt)
        self.oca_manager = OCAManager(
            workstation_id=self.workstation_id,
            service_client=self  # Workstation fungiert als Service-Client für Logging
        )

        # Map of commands to their corresponding methods - BEREINIGT
        self.command_map = {
            "generate_timestamp_extension": self.generate_timestamp_extension,
            "construct_path": self.construct_path,
            "get_timestamp_subpath": self.get_timestamp_subpath,
            "generate_file_prefix": self.generate_file_prefix,
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
            # NEU HINZUFÜGEN:
            "process_measurement": self.process_measurement,
        }

        self.setup_arg_parser()

    # NEU: Properties für Lazy Loading
    @property
    def switchbox_manager(self):
        """Lazy-loaded SwitchBox manager."""
        if self._switchbox_manager is None:
            WORKSTATION_LOGGER.info("Initializing SwitchBox hardware on first use")
            from serial_managers import SwitchBoxManager
            self._switchbox_manager = SwitchBoxManager(self.workstation_id)
        return self._switchbox_manager

    @property
    def scanner_manager(self):
        """Lazy-loaded Scanner manager."""
        if self._scanner_manager is None:
            WORKSTATION_LOGGER.info("Initializing %s Scanner hardware on first use", self._scanner_type)
            from serial_managers import ScannerManager
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
                WORKSTATION_LOGGER.info("Connected to ADAM service. Sending command: %s", command.get("action", "unknown"))
                
                # Send command as JSON
                command_json = json.dumps(command).encode("utf-8")
                client_socket.send(command_json)

                if wait_for_response:
                    # FIX: Größere Buffer und schrittweise Response lesen
                    response_data = b""
                    while True:
                        chunk = client_socket.recv(8192)  # Größere Chunks
                        if not chunk:
                            break
                        response_data += chunk
                        
                        # Prüfen ob komplettes JSON empfangen
                        try:
                            response_str = response_data.decode("utf-8")
                            json.loads(response_str)  # Test ob valid JSON
                            break  # Komplettes JSON empfangen
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            continue  # Mehr Daten benötigt
                
                    response = response_data.decode("utf-8")
                    WORKSTATION_LOGGER.info("Received response from ADAM service (%d bytes)", len(response))
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

    # BEREINIGTE Command methods - Audio Precision Commands entfernt

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

    # Hardware-Commands verwenden Properties (Lazy Loading)
    def set_channel(self, args):
        """Set channel on local SwitchBox hardware only."""
        try:
            result_channel = self.switchbox_manager.set_channel(
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
            box_status = self.switchbox_manager.open_box(
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
            serial_number = self.scanner_manager.scan_serial(
                service_host=self.host,
                service_port=self.port
            )
            print(serial_number)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

    # OCA Device Commands
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



    def get_serial_number(self, args):
        """Get serial number from OCA device (LOCAL)."""
        WORKSTATION_LOGGER.info("Executing 'get_serial_number' on OCA device %s:%d", args.target_ip, args.port)
        try:
            result = self.oca_manager.get_serial_number(args.target_ip, args.port)
            print(result)
        except Exception as e:
            error_msg = f"Error getting serial number: {e}"
            print(error_msg)
            WORKSTATION_LOGGER.error(error_msg)

    def set_mute(self, args):
        """Set mute state on OCA device (LOCAL)."""
        WORKSTATION_LOGGER.info("Executing 'set_mute' to %s on OCA device %s:%d", args.state, args.target_ip, args.port)
        try:
            result = self.oca_manager.set_mute(args.state, args.target_ip, args.port)
            print(result)
        except Exception as e:
            error_msg = f"Error setting mute: {e}"
            print(error_msg)
            WORKSTATION_LOGGER.error(error_msg)

    def get_mute(self, args):
        """Get mute state from OCA device (LOCAL)."""
        WORKSTATION_LOGGER.info("Executing 'get_mute' on OCA device %s:%d", args.target_ip, args.port)
        try:
            result = self.oca_manager.get_mute(args.target_ip, args.port)
            print(result)
        except Exception as e:
            error_msg = f"Error getting mute state: {e}"
            print(error_msg)
            WORKSTATION_LOGGER.error(error_msg)

    def set_gain(self, args):
        """Set gain on OCA device (LOCAL)."""
        WORKSTATION_LOGGER.info("Executing 'set_gain' to %s on OCA device %s:%d", args.value, args.target_ip, args.port)
        try:
            result = self.oca_manager.set_gain(args.value, args.target_ip, args.port)
            print(result)
        except Exception as e:
            error_msg = f"Error setting gain: {e}"
            print(error_msg)
            WORKSTATION_LOGGER.error(error_msg)

    def get_gain(self, args):
        """Get gain from OCA device (LOCAL)."""
        WORKSTATION_LOGGER.info("Executing 'get_gain' on OCA device %s:%d", args.target_ip, args.port)
        try:
            result = self.oca_manager.get_gain(args.target_ip, args.port)
            print(result)
        except Exception as e:
            error_msg = f"Error getting gain: {e}"
            print(error_msg)
            WORKSTATION_LOGGER.error(error_msg)

    def get_model_description(self, args):
        """Get model description from OCA device (LOCAL)."""
        WORKSTATION_LOGGER.info("Executing 'get_model_description' on OCA device %s:%d", args.target_ip, args.port)
        try:
            result = self.oca_manager.get_model_description(args.target_ip, args.port)
            print(result)
        except Exception as e:
            error_msg = f"Error getting model description: {e}"
            print(error_msg)
            WORKSTATION_LOGGER.error(error_msg)

    def get_firmware_version(self, args):
        """Get firmware version from OCA device (LOCAL)."""
        WORKSTATION_LOGGER.info("Executing 'get_firmware_version' on OCA device %s:%d", args.target_ip, args.port)
        try:
            result = self.oca_manager.get_firmware_version(args.target_ip, args.port)
            print(result)
        except Exception as e:
            error_msg = f"Error getting firmware version: {e}"
            print(error_msg)
            WORKSTATION_LOGGER.error(error_msg)

    def get_audio_input(self, args):
        """Get audio input from OCA device (LOCAL)."""
        WORKSTATION_LOGGER.info("Executing 'get_audio_input' on OCA device %s:%d", args.target_ip, args.port)
        try:
            result = self.oca_manager.get_audio_input(args.target_ip, args.port)
            print(result)
        except Exception as e:
            error_msg = f"Error getting audio input: {e}"
            print(error_msg)
            WORKSTATION_LOGGER.error(error_msg)

    def set_audio_input(self, args):
        """Set audio input on OCA device (LOCAL)."""
        WORKSTATION_LOGGER.info("Executing 'set_audio_input' to %s on OCA device %s:%d", args.position, args.target_ip, args.port)
        try:
            result = self.oca_manager.set_audio_input(args.position, args.target_ip, args.port)
            print(result)
        except Exception as e:
            error_msg = f"Error setting audio input: {e}"
            print(error_msg)
            WORKSTATION_LOGGER.error(error_msg)

    def get_mode(self, args):
        """Get mode from OCA device (LOCAL)."""
        WORKSTATION_LOGGER.info("Executing 'get_mode' on OCA device %s:%d", args.target_ip, args.port)
        try:
            result = self.oca_manager.get_mode(args.target_ip, args.port)
            print(result)
        except Exception as e:
            error_msg = f"Error getting mode: {e}"
            print(error_msg)
            WORKSTATION_LOGGER.error(error_msg)

    def set_mode(self, args):
        """Set mode on OCA device (LOCAL)."""
        WORKSTATION_LOGGER.info("Executing 'set_mode' to %s on OCA device %s:%d", args.position, args.target_ip, args.port)
        try:
            result = self.oca_manager.set_mode(args.position, args.target_ip, args.port)
            print(result)
        except Exception as e:
            error_msg = f"Error setting mode: {e}"
            print(error_msg)
            WORKSTATION_LOGGER.error(error_msg)

    def get_phase_delay(self, args):
        """Get phase delay from OCA device (LOCAL)."""
        WORKSTATION_LOGGER.info("Executing 'get_phase_delay' on OCA device %s:%d", args.target_ip, args.port)
        try:
            result = self.oca_manager.get_phase_delay(args.target_ip, args.port)
            print(result)
        except Exception as e:
            error_msg = f"Error getting phase delay: {e}"
            print(error_msg)
            WORKSTATION_LOGGER.error(error_msg)

    def set_phase_delay(self, args):
        """Set phase delay on OCA device (LOCAL)."""
        WORKSTATION_LOGGER.info("Executing 'set_phase_delay' to %s on OCA device %s:%d", args.position, args.target_ip, args.port)
        try:
            result = self.oca_manager.set_phase_delay(args.position, args.target_ip, args.port)
            print(result)
        except Exception as e:
            error_msg = f"Error setting phase delay: {e}"
            print(error_msg)
            WORKSTATION_LOGGER.error(error_msg)

    def get_device_biquad(self, args):
        """Get device biquad from OCA device (LOCAL)."""
        WORKSTATION_LOGGER.info("Executing 'get_device_biquad' index %d on OCA device %s:%d", args.index, args.target_ip, args.port)
        try:
            result = self.oca_manager.get_device_biquad(args.index, args.target_ip, args.port)
            print(result)
        except Exception as e:
            error_msg = f"Error getting device biquad: {e}"
            print(error_msg)
            WORKSTATION_LOGGER.error(error_msg)
    

    def set_device_biquad(self, args):
        """Set device biquad on OCA device (LOCAL)."""
        WORKSTATION_LOGGER.info("Executing 'set_device_biquad' index %d with coefficients %s on OCA device %s:%d", 
                       args.index, args.coefficients, args.target_ip, args.port)
        try:
            coeffs = json.loads(args.coefficients)
            result = self.oca_manager.set_device_biquad(args.index, coeffs, args.target_ip, args.port)
            print(result)
        except json.JSONDecodeError as e:
            error_msg = f"Error parsing coefficients: {e}"
            print(error_msg)
            WORKSTATION_LOGGER.error(error_msg)
        except Exception as e:
            error_msg = f"Error setting device biquad: {e}"
            print(error_msg)
            WORKSTATION_LOGGER.error(error_msg)


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

    def _parse_measurement_csv(self, file_path: str):
        """
        Dynamisch: erkennt 1..n Kanäle (je Kanal: Frequenz + Pegel Spalte).
        Erwartete Struktur:
            Zeilen mit Titel / Kanalnamen / X,Y Zeile / Units (Hz,dBSPL,...)
            Danach reine Zahlenzeilen.
        Rückgabe:
            {
              'channels': {
                  'Ch1': {'frequencies': [...], 'levels': [...], 'unit': 'dBSPL'},
                  'Ch2': {...},
                  ...
              },
              'data_points': N
            }
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
            except:
                return "dB"

        channels = {}
        import math
        import numpy as np

        cols_numeric = []
        for r in rows:
            numeric = []
            for c in r:
                try:
                    numeric.append(float(c))
                except:
                    numeric.append(math.nan)
            cols_numeric.append(numeric)

        import numpy as np
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
        """Process local measurement file (variable channel count) and send to service."""
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
        except Exception as e:
            WORKSTATION_LOGGER.exception("Unhandled exception in process_measurement")
            print(f"ERROR {e}")

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

        # BEREINIGT: Nur noch Production/OCA Commands

        # Helper Commands
        subparsers.add_parser("generate_timestamp_extension", help="Generate a timestamp extension.")

        parser_construct_path = subparsers.add_parser("construct_path", help="Construct a path.")
        parser_construct_path.add_argument("paths", type=str, nargs="+", help="List of paths to join.")

        subparsers.add_parser("get_timestamp_subpath", help="Get a timestamp subpath.")

        parser_generate_file_prefix = subparsers.add_parser("generate_file_prefix", help="Generate a file prefix.")
        parser_generate_file_prefix.add_argument("strings", type=str, nargs="+", help="List of strings to combine.")

        # Hardware Commands
        parser_set_channel = subparsers.add_parser("set_channel", help="Set the channel (1 or 2).")
        parser_set_channel.add_argument("channel", type=int, choices=[1, 2], help="Channel to set (1 or 2).")

        subparsers.add_parser("open_box", help="Open the box.")

        subparsers.add_parser("scan_serial", help="Scan the serial number.")

        # Biquad Commands
        biquad_parser = subparsers.add_parser("get_biquad_coefficients", help="Get biquad filter coefficients")
        biquad_parser.add_argument("filter_type", choices=["bell", "high_shelf", "low_shelf"], help="Type of biquad filter")
        biquad_parser.add_argument("gain", type=float, help="Gain in dB")
        biquad_parser.add_argument("peak_freq", type=float, help="Peak frequency in Hz")
        biquad_parser.add_argument("Q", type=float, help="Quality factor")
        biquad_parser.add_argument("sample_rate", type=int, help="Sample rate in Hz")

        set_biquad_parser = subparsers.add_parser("set_device_biquad", help="Set biquad filter on OCA device")
        set_biquad_parser.add_argument("index", type=int, help="Biquad index")
        set_biquad_parser.add_argument("coefficients", type=str, help="Koeffizienten-Liste als JSON-String")
        set_biquad_parser.add_argument("target_ip", type=str, help="OCA device IP address")
        set_biquad_parser.add_argument("port", type=int, help="OCA device port")

        get_device_biquad_parser = subparsers.add_parser("get_device_biquad", help="Get biquad coefficients from OCA device")
        get_device_biquad_parser.add_argument("index", type=int, help="Biquad index")
        get_device_biquad_parser.add_argument("target_ip", type=str, help="OCA device IP address")
        get_device_biquad_parser.add_argument("port", type=int, help="OCA device port")

        # OCA Device Commands
        get_serial_parser = subparsers.add_parser("get_serial_number", help="Get serial number from OCA device")
        get_serial_parser.add_argument("target_ip", type=str, help="OCA device IP address")
        get_serial_parser.add_argument("port", type=int, help="OCA device port")

        get_gain_parser = subparsers.add_parser("get_gain", help="Get gain from OCA device")
        get_gain_parser.add_argument("target_ip", type=str, help="OCA device IP address")
        get_gain_parser.add_argument("port", type=int, help="OCA device port")

        set_gain_parser = subparsers.add_parser("set_gain", help="Set gain on OCA device")
        set_gain_parser.add_argument("value", type=float, help="Gain value")
        set_gain_parser.add_argument("target_ip", type=str, help="OCA device IP address")
        set_gain_parser.add_argument("port", type=int, help="OCA device port")

        get_model_parser = subparsers.add_parser("get_model_description", help="Get model description from OCA device")
        get_model_parser.add_argument("target_ip", type=str, help="OCA device IP address")
        get_model_parser.add_argument("port", type=int, help="OCA device port")

        get_firmware_parser = subparsers.add_parser("get_firmware_version", help="Get firmware version from OCA device")
        get_firmware_parser.add_argument("target_ip", type=str, help="OCA device IP address")
        get_firmware_parser.add_argument("port", type=int, help="OCA device port")

        get_audio_input_parser = subparsers.add_parser("get_audio_input", help="Get audio input mode from OCA device")
        get_audio_input_parser.add_argument("target_ip", type=str, help="OCA device IP address")
        get_audio_input_parser.add_argument("port", type=int, help="OCA device port")

        set_audio_input_parser = subparsers.add_parser("set_audio_input", help="Set audio input mode on OCA device")
        set_audio_input_parser.add_argument("position", type=str, help="Audio input position (e.g. 'aes3', 'analogue')")
        set_audio_input_parser.add_argument("target_ip", type=str, help="OCA device IP address")
        set_audio_input_parser.add_argument("port", type=int, help="OCA device port")

        get_mute_parser = subparsers.add_parser("get_mute", help="Get mute state from OCA device")
        get_mute_parser.add_argument("target_ip", type=str, help="OCA device IP address")
        get_mute_parser.add_argument("port", type=int, help="OCA device port")

        set_mute_parser = subparsers.add_parser("set_mute", help="Set mute state on OCA device")
        set_mute_parser.add_argument("state", type=str, choices=["muted", "unmuted"], help="Mute state ('muted' or 'unmuted')")
        set_mute_parser.add_argument("target_ip", type=str, help="OCA device IP address")
        set_mute_parser.add_argument("port", type=int, help="OCA device port")

        get_mode_parser = subparsers.add_parser("get_mode", help="Get control mode from OCA device")
        get_mode_parser.add_argument("target_ip", type=str, help="OCA device IP address")
        get_mode_parser.add_argument("port", type=int, help="OCA device port")

        set_mode_parser = subparsers.add_parser("set_mode", help="Set control mode on OCA device")
        set_mode_parser.add_argument("position", type=str, help="Control mode to set")
        set_mode_parser.add_argument("target_ip", type=str, help="OCA device IP address")
        set_mode_parser.add_argument("port", type=int, help="OCA device port")

        get_phase_delay_parser = subparsers.add_parser("get_phase_delay", help="Get phase delay from OCA device")
        get_phase_delay_parser.add_argument("target_ip", type=str, help="OCA device IP address")
        get_phase_delay_parser.add_argument("port", type=int, help="OCA device port")

        set_phase_delay_parser = subparsers.add_parser("set_phase_delay", help="Set phase delay on OCA device")
        set_phase_delay_parser.add_argument("position", type=str, help="Phase delay value (e.g. 'deg0', 'deg45', ...)")
        set_phase_delay_parser.add_argument("target_ip", type=str, help="OCA device IP address")
        set_phase_delay_parser.add_argument("port", type=int, help="OCA device port")

        check_trials_parser = subparsers.add_parser("check_measurement_trials", help="Check allowed measurement trials for a serial number")
        check_trials_parser.add_argument("serial_number", type=str, help="Serial number to check")
        check_trials_parser.add_argument("csv_path", type=str, help="Path to the CSV file")
        check_trials_parser.add_argument("max_trials", type=int, help="Maximum allowed trials")

        # NEU HINZUFÜGEN:
        process_measurement_parser = subparsers.add_parser("process_measurement", help="Process measurement data and send to service")
        process_measurement_parser.add_argument("measurement_path", type=str, help="Path to measurement file")
        process_measurement_parser.add_argument("--serial-number", "-s", dest="serial_number", required=True, help="Explicit device serial number")
        process_measurement_parser.add_argument("--json-directory", type=str, default="measurements", help="JSON directory on service")

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
