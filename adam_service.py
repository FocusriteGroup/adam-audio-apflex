"""
adam_service.py

ADAM Audio Production Service
------------------------------------------------

Author: Thilo Rode
Company: ADAM Audio GmbH
Version: 0.1
Date: 2025-10-22

Features:
- Network service for ADAM Audio speaker testing, production line control, and quality assurance
- Handles device communication, production equipment control, and automated testing workflows
- UDP broadcast-based service discovery for workstation auto-configuration
- Modular command processing for helper functions, biquad calculations, measurement trial tracking, and logging
- Robust error handling and detailed logging to daily log files
- Extensible architecture for new production features and workstation support

This script provides a robust backend service for ADAM Audio production environments, enabling automated device management, measurement tracking, and workstation integration.
"""
import logging
import os
from datetime import datetime
import csv
from pathlib import Path  # sicherstellen, dass vorhanden

# Unterverzeichnis "logs" für ADAM Audio Service erstellen
log_dir = "logs/adam_audio"
os.makedirs(log_dir, exist_ok=True)

# Heutiges Datum im Format JJJJ-MM-TT
today = datetime.now().strftime("%Y-%m-%d")
log_filename = f"{log_dir}/adam_service_log_{today}.log"

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

# ÄNDERUNG 1: Import von helpers statt ap_utils
from helpers import generate_timestamp_extension, construct_path, generate_timestamp_subpath, generate_file_prefix

logging.info("----------------------------------- ADAM Audio Service started")

class AdamService:
    """
    ADAM Audio Production Service.

    Provides a network service for ADAM Audio speaker testing, production line control,
    and quality assurance. Handles device communication, production equipment control,
    automated testing workflows, and workstation integration.

    Features:
    - TCP/IP server for workstation connections
    - UDP broadcast-based service discovery
    - Modular command processing for production, measurement, and helper functions
    - Detailed logging and error handling
    """

    def __init__(self, host="0.0.0.0", port=65432, service_name="ADAMService"):
        """
        Initialize the ADAM Audio Service instance.

        Args:
            host (str, optional): Hostname or IP address to bind the service. Default is "0.0.0.0" (all interfaces).
            port (int, optional): TCP port for workstation connections. Default is 65432.
            service_name (str, optional): Name of this service instance. Default is "ADAMService".

        Sets up TCP server, UDP discovery, logging, and service metadata.
        """
        self.host = host
        self.port = port
        self.service_name = service_name
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((self.host, self.port))
        self.server.listen(5)
        self.running = True

        # Discovery service configuration
        self.discovery_port = 65433
        self.discovery_running = False
        self.discovery_thread = None
        self.discovery_interval = 2  # Sekunden zwischen Broadcasts

        self.logger = logging.getLogger("ADAMService")
 
        # Display service information and start discovery
        self._display_service_info()
        self._start_discovery()

        self.logger.info("ADAM Audio Service started")

    def _display_service_info(self):
        """
        Display ADAM Audio service connection information at startup.

        Logs service metadata, network configuration, and usage examples for workstations.
        Handles errors in network info retrieval gracefully.
        """
        try:
            hostname = socket.gethostname()
            
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                primary_ip = s.getsockname()[0]
            
            self.logger.info("=== ADAM AUDIO SERVICE INFO ===")
            self.logger.info("Company: ADAM Audio")
            self.logger.info("Service: Production Support Service")
            self.logger.info("Service Name: %s", self.service_name)
            self.logger.info("Hostname: %s", hostname)
            self.logger.info("Service Port: %d", self.port)
            self.logger.info("Discovery Port: %d", self.discovery_port)
            self.logger.info("Discovery Interval: %d seconds", self.discovery_interval)
            self.logger.info("Primary IP: %s", primary_ip)
            self.logger.info("Host binding: %s (0.0.0.0 = all interfaces)", self.host)
            self.logger.info("Discovery service: ENABLED")
            self.logger.info("Note: OCA device communication handled locally by workstations")
            self.logger.info("Workstation usage examples:")
            self.logger.info("  Helper functions: python adam_workstation.py --host %s generate_timestamp_extension", primary_ip)
            self.logger.info("  Biquad calculation: python adam_workstation.py --host %s get_biquad_coefficients bell 3.0 1000 1.4 48000", primary_ip)
            # OCA-BEISPIELE ENTFERNT:
            # self.logger.info("  OCA commands: python adam_workstation.py --host %s get_serial_number 192.168.10.20 50001", primary_ip)
            self.logger.info("  Auto-discovery: python adam_connector.py --find --service-name %s", self.service_name)
            self.logger.info("================================")

        except (socket.error, OSError) as e:
            self.logger.error("Could not determine service connection info: %s", e)

    def _start_discovery(self):
        """
        Start the UDP broadcast-based discovery service for workstation auto-configuration.

        Launches a background thread for periodic service announcements.
        """
        self.discovery_running = True
        self.discovery_thread = threading.Thread(target=self._discovery_broadcast_loop, daemon=True)
        self.discovery_thread.start()
        self.logger.info("Discovery service started on port %d (interval: %ds)", 
                        self.discovery_port, self.discovery_interval)

    def _discovery_broadcast_loop(self):
        """
        Main loop for UDP service discovery broadcasts.

        Periodically announces service metadata for workstation auto-discovery.
        Uses adaptive intervals: fast announcements on startup, then normal intervals.
        Handles broadcast errors and retries gracefully.
        """
        initial_interval = 1  # Schnelle Announcements beim Start (1 Sekunde)
        normal_interval = self.discovery_interval  # Normal interval (2 Sekunden)
        fast_announcements = 5  # Anzahl schneller Announcements beim Start

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            try:
                # Socket für Broadcast konfigurieren
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                announcement_count = 0

                self.logger.info("Starting discovery broadcast loop...")

                while self.discovery_running:
                    try:
                        # Service-Informationen für Broadcast sammeln
                        broadcast_data = self._get_discovery_data()
                        broadcast_data["sequence"] = announcement_count

                        # JSON-Nachricht erstellen
                        message = json.dumps(broadcast_data)

                        # Broadcast senden
                        sock.sendto(message.encode('utf-8'), ('<broadcast>', self.discovery_port))

                        # Logging basierend auf Phase
                        if announcement_count < fast_announcements:
                            current_interval = initial_interval
                            self.logger.debug("Fast discovery broadcast #%d sent: %s:%d", 
                                           announcement_count + 1, broadcast_data["ip"], self.port)
                        else:
                            current_interval = normal_interval
                            self.logger.debug("Discovery broadcast sent: %s:%d", 
                                           broadcast_data["ip"], self.port)

                        announcement_count += 1

                        # Warten bis zum nächsten Broadcast
                        time.sleep(current_interval)

                    except (socket.error, json.JSONDecodeError) as e:
                        if self.discovery_running:  # Nur loggen wenn Service noch aktiv sein soll
                            self.logger.error("Discovery broadcast error: %s", e)
                        # Kurze Pause vor Retry
                        time.sleep(1)

            except (socket.error, OSError) as e:
                self.logger.error("Failed to create discovery broadcast socket: %s", e)

    def _get_discovery_data(self):
        """
        Collect service information for UDP discovery broadcasts.

        Returns:
            dict: Service metadata for broadcast (IP, port, hostname, capabilities, status, etc.)
        Handles errors in IP retrieval and provides fallback data.
        """
        try:
            hostname = socket.gethostname()

            # Primäre IP ermitteln (die Route zum Internet verwendet)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]

            return {
                "service": self.service_name,
                "company": "ADAM Audio",
                "ip": ip,
                "port": self.port,
                "hostname": hostname,
                "timestamp": time.time(),
                "version": "1.0",
                "capabilities": [
                    "BiquadFilters", 
                    "MeasurementTrials",
                    "ProductionLogging",
                    "HelperFunctions",
                    "WorkstationSupport"
                    # "OCA" ENTFERNT - wird jetzt lokal von Workstations gehandhabt
                ],
                "discovery_port": self.discovery_port,
                "status": "running",
                "note": "OCA communication handled locally by workstations"
            }

        except (FileNotFoundError, PermissionError, json.JSONDecodeError, KeyError, ValueError) as e:
            self.logger.error("Error collecting discovery data: %s", e)
            # Fallback-Daten wenn IP-Ermittlung fehlschlägt
            return {
                "service": self.service_name,
                "company": "ADAM Audio",
                "ip": "unknown",
                "port": self.port,
                "hostname": socket.gethostname(),
                "timestamp": time.time(),
                "version": "1.0",
                "status": "running",
                "error": str(e)
            }

    def _send_goodbye_broadcast(self):
        """
        Send a goodbye UDP broadcast when the service shuts down.

        Announces service unavailability for reliable workstation detection (mDNS pattern).
        Retries broadcast for robustness.
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

                # Goodbye-Daten sammeln
                goodbye_data = self._get_discovery_data()
                goodbye_data["status"] = "goodbye"
                goodbye_data["message"] = "ADAM Audio Service shutting down"

                goodbye_message = json.dumps(goodbye_data)

                # Goodbye-Nachricht mehrfach senden für Zuverlässigkeit
                for i in range(3):
                    sock.sendto(goodbye_message.encode('utf-8'), ('<broadcast>', self.discovery_port))
                    if i < 2:  # Nicht nach dem letzten Versuch warten
                        time.sleep(0.1)

                self.logger.info("Goodbye discovery broadcast sent (3x)")

        except (FileNotFoundError, PermissionError, json.JSONDecodeError, KeyError, ValueError) as e:
            self.logger.error("Failed to send goodbye broadcast: %s", e)

    # --- Workstation Handling ---

    def handle_workstation(self, workstation_socket):
        """
        Handle communication with a connected workstation client.

        Receives command data, processes the command, and sends a response if requested.
        Handles large JSON payloads, connection errors, and logs all events.
        Closes the connection after processing.
        """
        client_address = workstation_socket.getpeername()
        try:
            # FIX: Größere Buffer für große JSON-Daten
            data_buffer = b""
            while True:
                chunk = workstation_socket.recv(8192)  # Größere Chunks
                if not chunk:
                    break
                data_buffer += chunk

                # Prüfen ob komplette Nachricht empfangen
                try:
                    command_str = data_buffer.decode("utf-8")
                    command = json.loads(command_str)
                    break  # Komplette Nachricht empfangen
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue  # Mehr Daten benötigt

            if not data_buffer:
                return

            self.logger.info("Received command from %s: %s", client_address, command.get("action", "unknown"))
            response = self.process_command(command)

            # Response senden
            if response and command.get("wait_for_response", True):
                response_bytes = response.encode("utf-8")
                workstation_socket.send(response_bytes)
                self.logger.info("Sent response to %s (%d bytes)", client_address, len(response_bytes))
            else:
                self.logger.info("No response sent to %s", client_address)

        except (socket.error, json.JSONDecodeError, UnicodeDecodeError) as e:
            self.logger.error("Error handling workstation %s: %s", client_address, e)
        finally:
            workstation_socket.close()
            self.logger.info("Workstation connection closed: %s", client_address)

    # --- Command Processing ---

    def process_command(self, command):
        """
        Process a command received from a workstation and return a response string.

        Args:
            command (dict): Command dictionary with 'action' and parameters.

        Returns:
            str: Response string (JSON or error message).
        Handles unknown actions and logs errors.
        """
        if not isinstance(command, dict) or "action" not in command:
            return "Error: Invalid command format."

        action = command["action"]
        command_map = {
            # Helper Functions
            "generate_timestamp_extension": generate_timestamp_extension,
            "construct_path": lambda: self._construct_path(command),
            "get_timestamp_subpath": generate_timestamp_subpath,
            "generate_file_prefix": lambda: self._generate_file_prefix(command),

            # Biquad Calculations
            "get_biquad_coefficients": lambda: self._get_biquad_coefficients(command),

            # Measurement Trial Tracking
            "check_measurement_trials": lambda: self._check_measurement_trials(command),

            # Workstation Logging
            "log_workstation_task": lambda: self._log_workstation_task(command),

            # NEU: Vereinfachtes Measurement Management
            "add_measurement": lambda: self._add_measurement(command),
        }

        if action in command_map:
            try:
                return command_map[action]()
            except (FileNotFoundError, PermissionError, json.JSONDecodeError, KeyError, ValueError) as e:
                self.logger.error("Error processing action '%s': %s", action, e)
                return f"Error: {e}"
        else:
            self.logger.error("Unknown action: %s", action)
            return "Error: Unknown action."

    # --- Methods for Commands ---

    def _construct_path(self, command):
        """
        Construct a file path from a list of strings provided in the command.

        Args:
            command (dict): Command with 'paths' (list of strings).

        Returns:
            str: Constructed path or error message.
        """
        paths = command.get("paths")
        if not paths or not isinstance(paths, list):
            return "Error: 'paths' must be a non-empty list of strings."
        if not all(isinstance(p, str) for p in paths):
            return "Error: All elements in 'paths' must be strings."
        self.logger.info("Constructing path from: %s", paths)
        # ÄNDERUNG 3: Direkte Funktion statt Utilities-Klasse
        return construct_path(paths)

    def _generate_file_prefix(self, command):
        """
        Generate a file prefix from a list of strings provided in the command.

        Args:
            command (dict): Command with 'strings' (list of strings).

        Returns:
            str: Generated prefix or error message.
        """
        strings = command.get("strings")
        if not strings or not isinstance(strings, list):
            return "Error: 'strings' must be a non-empty list of strings."
        if not all(isinstance(s, str) for s in strings):
            return "Error: All elements in 'strings' must be strings."
        self.logger.info("Generating file prefix from: %s", strings)
        # ÄNDERUNG 4: Direkte Funktion statt Utilities-Klasse
        return generate_file_prefix(strings)

    def _get_biquad_coefficients(self, command):
        """
        Calculate biquad filter coefficients using Biquad_Filter.

        Args:
            command (dict): Command with filter parameters (type, gain, freq, Q, sample_rate).

        Returns:
            str: JSON-encoded list of coefficients or error message.
        Handles ValueError and KeyError.
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

    def _check_measurement_trials(self, command):
        """
        Check how many times a serial number appears in a CSV file with Status='Failed'.
        Compares to max_trials and creates the CSV file if it doesn't exist.

        Args:
            command (dict): Command with 'serial_number', 'csv_path', and 'max_trials'.

        Returns:
            str: Permission message or error message.
        Handles file creation, CSV parsing, and logs all events.
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

        except (FileNotFoundError, PermissionError, json.JSONDecodeError, KeyError, ValueError) as e:
            self.logger.error("Error checking measurement trials: %s", e)
            return f"Error: {e}"

    # --- Workstation Logging ---

    def _log_workstation_task(self, command):
        """
        Log any workstation task (generic method for all hardware operations).

        Args:
            command (dict): Command with workstation/task metadata.

        Returns:
            str: JSON-encoded status or error message.
        Logs all details for traceability.
        """
        try:
            workstation_id = command.get("workstation_id", "UNKNOWN")
            task_type = command.get("task_type", "UNKNOWN")  # "switchbox", "scanner", etc.
            operation = command.get("operation", "UNKNOWN")  # "set_channel", "scan_serial", etc.
            result = command.get("result", "UNKNOWN")
            timestamp = command.get("timestamp", datetime.now().isoformat())

            # Optional task-specific data
            task_data = command.get("task_data", {})

            # Generic logging mit allen Details
            self.logger.info("WORKSTATION[%s] %s.%s result=%s at %s - Data: %s", 
                            workstation_id, task_type.upper(), operation, result, timestamp, task_data)

            return json.dumps({
                "status": "logged", 
                "task_type": task_type,
                "operation": operation, 
                "result": result
            })

        except (KeyError, ValueError, TypeError) as e:
            error_msg = f"Error logging workstation task: {e}"
            self.logger.error(error_msg)
            return json.dumps({"error": error_msg})

    # NEUE Methode für das Hinzufügen von Messungen
    def _add_measurement(self, command):
        """
        Add a measurement to the global JSON file, using a shared frequency vector.

        Args:
            command (dict): Command with 'json_directory' and 'measurement_data'.

        Returns:
            str: JSON-encoded status, measurement ID, and metadata, or error message.
        Handles frequency vector adoption, validation, and robust file management.
        """
        try:
            requested_dir = command.get("json_directory", "measurements")
            measurement_data = command.get("measurement_data")
            if not measurement_data:
                return json.dumps({"error": "No measurement_data provided"})

            target_dir = self._resolve_json_directory(requested_dir)
            target_dir.mkdir(parents=True, exist_ok=True)
            json_file = target_dir / "all_measurements.json"

            # JSON laden oder Grundstruktur
            if json_file.exists():
                with json_file.open("r", encoding="utf-8") as f:
                    json_data = json.load(f)
            else:
                json_data = {
                    "metadata": {
                        "created": datetime.now().isoformat(),
                        "last_updated": datetime.now().isoformat(),
                        "total_measurements": 0
                    },
                    "measurements": {}
                }

            # Prüfen ob globaler Frequenzvektor existiert
            global_freq = json_data.get("frequency_vector", None)

            # Frequenzvektor aus erster Messung übernehmen falls noch nicht vorhanden
            if global_freq is None:
                # Erste Channel mit Frequenzliste suchen
                adopted = False
                for ch_name, ch_data in measurement_data.get("channels", {}).items():
                    freqs = ch_data.get("frequencies")
                    if freqs and isinstance(freqs, list) and len(freqs) > 0:
                        json_data["frequency_vector"] = freqs
                        json_data["metadata"]["frequency_points"] = len(freqs)
                        global_freq = freqs
                        self.logger.info("Global frequency vector adopted from channel %s (%d points)", ch_name, len(freqs))
                        adopted = True
                        break
                if not adopted:
                    return json.dumps({"error": "No frequency vector found in first measurement"})
            else:
                # Validierung eingehender Frequenzlisten (falls gesendet)
                for ch_name, ch_data in measurement_data.get("channels", {}).items():
                    incoming = ch_data.get("frequencies")
                    if incoming:
                        if len(incoming) != len(global_freq):
                            self.logger.warning(
                                "Incoming frequency length mismatch (ch=%s expected=%d got=%d) -> ignoring incoming frequencies",
                                ch_name, len(global_freq), len(incoming)
                            )
                        else:
                            # Schneller Vergleich (erstes, mittleres, letztes Element)
                            if not (incoming[0] == global_freq[0] and
                                    incoming[len(incoming)//2] == global_freq[len(global_freq)//2] and
                                    incoming[-1] == global_freq[-1]):
                                self.logger.warning(
                                    "Incoming frequency values differ (ch=%s) -> ignoring incoming frequencies",
                                    ch_name
                                )
                        # Frequenzen werden in jedem Fall ignoriert (globales Modell)

            # Frequenzlisten aus den Kanal-Daten entfernen, nur Levels behalten
            for ch_name, ch_data in measurement_data.get("channels", {}).items():
                if "frequencies" in ch_data:
                    del ch_data["frequencies"]
                # data_points ggf. aktualisieren
                if "levels" in ch_data and isinstance(ch_data["levels"], list):
                    ch_data["data_points"] = len(ch_data["levels"])

            device_serial = measurement_data.get("device_serial", "UNKNOWN")
            measurement_id = f"{device_serial}_{int(time.time())}"

            json_data["measurements"][measurement_id] = measurement_data
            json_data["metadata"]["last_updated"] = datetime.now().isoformat()
            json_data["metadata"]["total_measurements"] = len(json_data["measurements"])

            with json_file.open("w", encoding="utf-8") as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)

            return json.dumps({
                "status": "success",
                "measurement_id": measurement_id,
                "measurement_count": len(json_data["measurements"]),
                "frequency_points": len(json_data.get("frequency_vector", [])),
                "json_file": str(json_file),
                "base_dir_mode": "user_home",
                "base_dir": str(self._get_user_home())
            })
        except (FileNotFoundError, PermissionError, json.JSONDecodeError, KeyError, ValueError) as e:
            self.logger.error("Error adding measurement: %s", e)
            return json.dumps({"error": str(e)})


    # --- Service Management ---

    def start(self):
        """
        Start the ADAM Audio service and manage workstation connections.

        Listens for incoming workstation connections and spawns handler threads.
        Logs all connection events and errors.
        """
        self.logger.info("ADAM Audio Service is running...")
        self.logger.info("Waiting for workstation connections...")
        while self.running:
            workstation_socket, addr = self.server.accept()
            self.logger.info("Workstation connection from %s", addr)
            threading.Thread(target=self.handle_workstation, args=(workstation_socket,)).start()

    def stop(self):
        """
        Stop the ADAM Audio service and UDP discovery service.

        Sends goodbye broadcast, stops threads, closes sockets, and logs shutdown events.
        """
        self.logger.info("Stopping ADAM Audio Service...")

        # Discovery Service stoppen
        self.discovery_running = False

        # Goodbye-Broadcast senden
        try:
            self._send_goodbye_broadcast()
        except (socket.error, OSError, json.JSONDecodeError) as e:
            self.logger.error("Error sending goodbye broadcast: %s", e)

        # Auf Discovery-Thread warten
        if self.discovery_thread and self.discovery_thread.is_alive():
            self.discovery_thread.join(timeout=2)
            if self.discovery_thread.is_alive():
                self.logger.warning("Discovery thread did not stop within timeout")

        # Hauptservice stoppen
        self.running = False

        # Geräte-Verbindungen schließen
        try:
            self.server.close()
        except Exception as e:
            self.logger.error("Error closing service socket: %s", e)

        self.logger.info("ADAM Audio Service and discovery service stopped.")

    def _get_user_home(self) -> Path:
        """
        Determine the base directory for measurement storage.
    
        Priority:
            1. Environment variable ADAM_SERVICE_HOME (if set)
            2. User home directory (platform-independent)
    
        Returns:
            Path: Base directory for storage.
        """
        env_override = os.getenv("ADAM_SERVICE_HOME")
        if env_override:
            p = Path(env_override).expanduser()
            try:
                p.mkdir(parents=True, exist_ok=True)
            except (PermissionError, FileNotFoundError, OSError):
                pass
            return p
        return Path.home()

    def _resolve_json_directory(self, requested: str) -> Path:
        """
        Resolve a workstation-provided (relative) folder name to a safe path under the service host's user home.

        Removes absolute roots and '..' for security.

        Args:
            requested (str): Requested directory name.

        Returns:
            Path: Safe, resolved directory path.
        """
        base = self._get_user_home()
        req = requested or "measurements"
        p = Path(req)
        if p.is_absolute():
            # absolute Teile abschneiden
            p = Path(*p.parts[1:])
        safe_parts = [part for part in p.parts if part not in ("..", ".", "")]
        if not safe_parts:
            safe_parts = ["measurements"]
        return base.joinpath(*safe_parts)

# --- Command Line Interface ---

def main():
    """
    Main entry point for ADAM Audio Service.

    Parses command-line arguments, initializes the service, and starts the main loop.
    Handles graceful shutdown on KeyboardInterrupt.
    """
    import argparse

    parser = argparse.ArgumentParser(description="ADAM Audio Production Service")
    parser.add_argument("--service-name", default="ADAMService",
                       help="Name of this service instance (default: ADAMService)")
    parser.add_argument("--service-port", type=int, default=65432,
                       help="Service port (default: 65432)")
    parser.add_argument("--host", default="0.0.0.0",
                       help="Host binding (default: 0.0.0.0 for all interfaces)")

    args = parser.parse_args()

    service = AdamService(
        host=args.host,
        port=args.service_port,
        service_name=args.service_name
    )

    try:
        service.start()
    except KeyboardInterrupt:
        service.stop()

if __name__ == "__main__":
    main()
