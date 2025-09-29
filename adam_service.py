import logging
import os
from datetime import datetime
import csv

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
from oca_tools.oca_utilities import OCP1ToolWrapper

from ap_utils import Utilities, SwitchBox, HoneywellScanner

logging.info("----------------------------------- ADAM Audio Service started")

class AdamService:
    """
    ADAM Audio Production Service.

    Network service for ADAM Audio speaker testing, production line control,
    and quality assurance processes. Handles device communication, production
    equipment control, and automated testing workflows.
    """

    def __init__(self, host="0.0.0.0", port=65432, service_name="AdamAudio"):
        """
        Initialize the ADAM Audio Service.

        Args:
            host (str): The service's hostname or IP address. Default is "0.0.0.0" for network access.
            port (int): The service's port number. Default is 65432.
            service_name (str): Name of this service instance. Default is "AdamAudio".
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

        # Locks for thread-safe access to devices
        self.scanner_lock = threading.Lock()
        self.switchbox_lock = threading.Lock()

        # Initialize the SwitchBox and HoneywellScanner
        self.switch_box = SwitchBox(on_connect=self.switchbox_on_connect, on_disconnect=self.switchbox_on_disconnect)
        self.scanner = HoneywellScanner(on_connect=self.scanner_on_connect, on_disconnect=self.scanner_on_disconnect)

        self.logger = logging.getLogger("AdamAudio")
        
        # Display service information and start discovery
        self._display_service_info()
        self._start_discovery()
        
        self.logger.info("ADAM Audio Service started")

    def _display_service_info(self):
        """Display ADAM Audio service connection information at startup."""
        try:
            hostname = socket.gethostname()
            
            # Ermittle die primäre IP-Adresse (die Route zum Internet verwendet)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                primary_ip = s.getsockname()[0]
            
            self.logger.info("=== ADAM AUDIO SERVICE INFO ===")
            self.logger.info("Company: ADAM Audio")
            self.logger.info("Service: Production & Testing Service")
            self.logger.info("Service Name: %s", self.service_name)
            self.logger.info("Hostname: %s", hostname)
            self.logger.info("Service Port: %d", self.port)
            self.logger.info("Discovery Port: %d", self.discovery_port)
            self.logger.info("Discovery Interval: %d seconds", self.discovery_interval)
            self.logger.info("Primary IP: %s", primary_ip)
            self.logger.info("Host binding: %s (0.0.0.0 = all interfaces)", self.host)
            self.logger.info("Discovery service: ENABLED")
            self.logger.info("Workstation usage examples:")
            self.logger.info("  Auto-discovery: python adam_connector.py --find --service-name %s", self.service_name)
            self.logger.info("  Production workstation: python adam_workstation.py --service %s --eol-workflow --auto-discover", self.service_name)
            self.logger.info("  Manual command: python adam_workstation.py --service %s --command get_serial_number --host %s", self.service_name, primary_ip)
            self.logger.info("================================")
            
        except Exception as e:
            self.logger.error("Could not determine service connection info: %s", e)

    def _start_discovery(self):
        """Start the discovery broadcast service."""
        self.discovery_running = True
        self.discovery_thread = threading.Thread(target=self._discovery_broadcast_loop, daemon=True)
        self.discovery_thread.start()
        self.logger.info("Discovery service started on port %d (interval: %ds)", 
                        self.discovery_port, self.discovery_interval)

    def _discovery_broadcast_loop(self):
        """
        Main discovery broadcast loop.
        
        Broadcasts service information periodically using UDP broadcasts.
        Uses adaptive intervals: fast announcements on startup, then normal intervals.
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
                        
                    except Exception as e:
                        if self.discovery_running:  # Nur loggen wenn Service noch aktiv sein soll
                            self.logger.error("Discovery broadcast error: %s", e)
                        # Kurze Pause vor Retry
                        time.sleep(1)
                        
            except Exception as e:
                self.logger.error("Failed to create discovery broadcast socket: %s", e)

    def _get_discovery_data(self):
        """
        Collect service information for discovery broadcasts.
        
        Returns:
            dict: Service information for broadcast
        """
        try:
            hostname = socket.gethostname()
            
            # Primäre IP ermitteln (die Route zum Internet verwendet)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
            
            return {
                "service": self.service_name,  # Jetzt konfigurierbar
                "company": "ADAM Audio",
                "ip": ip,
                "port": self.port,
                "hostname": hostname,
                "timestamp": time.time(),
                "version": "1.0",
                "capabilities": [
                    "OCA", 
                    "SwitchBox", 
                    "Scanner", 
                    "BiquadFilters", 
                    "MeasurementTrials",
                    "ProductionControl",
                    "EOLTesting",
                    "QualityAssurance"
                ],
                "discovery_port": self.discovery_port,
                "status": "running"
            }
            
        except Exception as e:
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
        Send goodbye message when service shuts down.
        
        This follows the mDNS pattern of announcing service unavailability.
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
                
        except Exception as e:
            self.logger.error("Failed to send goodbye broadcast: %s", e)

    # --- Device Connection Callbacks ---

    def scanner_on_connect(self):
        """
        Callback executed when the scanner is connected.
        """
        with self.scanner_lock:
            self.logger.info("HoneywellScanner physically connected.")

    def scanner_on_disconnect(self):
        """
        Callback executed when the scanner is disconnected.
        """
        with self.scanner_lock:
            self.logger.info("HoneywellScanner physically disconnected.")

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
        Handle communication with a connected workstation/client.

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
            self.logger.info("Workstation connection closed.")

    # --- Command Processing ---

    def process_command(self, command):
        """
        Process a command and return a response.

        Args:
            command (dict): The command received from the workstation.

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

    # --- Service Management ---

    def start(self):
        """
        Start the ADAM Audio service and manage workstation connections.
        """
        self.logger.info("ADAM Audio Service is running...")
        self.logger.info("Waiting for workstation connections...")
        while self.running:
            client_socket, addr = self.server.accept()
            self.logger.info("Workstation connection from %s", addr)
            threading.Thread(target=self.handle_client, args=(client_socket,)).start()

    def stop(self):
        """
        Stop the ADAM Audio service and discovery service.
        """
        self.logger.info("Stopping ADAM Audio Service...")
        
        # Discovery Service stoppen
        self.discovery_running = False
        
        # Goodbye-Broadcast senden
        try:
            self._send_goodbye_broadcast()
        except Exception as e:
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
            
        self.switch_box.serial_disconnect()
        self.scanner.serial_disconnect()
        
        self.logger.info("ADAM Audio Service and discovery service stopped.")

# --- Command Line Interface ---

def main():
    """Main entry point for ADAM Audio Service."""
    import argparse
    
    parser = argparse.ArgumentParser(description="ADAM Audio Production Service")
    parser.add_argument("--service-name", default="AdamAudio",
                       help="Name of this service instance (default: AdamAudio)")
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