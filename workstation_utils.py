"""
ADAM Audio Workstation Utilities

Shared utilities for the ADAM Audio Workstation.
"""

import socket
import threading
import json
import logging
from datetime import datetime
from ap_utils import SwitchBox, HoneywellScanner
import time

# Spezifische Logger für jede Komponente
WORKSTATION_LOGGER = logging.getLogger("ADAMLogger")
SCANNER_LOGGER = logging.getLogger("ADAMScanner")
SWITCHBOX_LOGGER = logging.getLogger("ADAMSwitchBox")

class WorkstationLogger:
    """Centralized logging utilities for workstation features."""
    
    @staticmethod
    def send_log_to_service(workstation_id, log_data, service_host, service_port=65432):
        """
        Send log data to ADAM service for central logging.
        
        Args:
            workstation_id (str): Workstation identifier
            log_data (dict): Log data to send to service
            service_host (str): Service host
            service_port (int): Service port
            
        Returns:
            bool: True if logging successful, False otherwise
        """
        if not service_host:
            WORKSTATION_LOGGER.warning("No service host available for logging")
            return False
            
        try:
            log_command = {
                "action": "log_workstation_task",
                "workstation_id": workstation_id,
                **log_data
            }
            
            WORKSTATION_LOGGER.info("Sending log to service: %s", log_command)
            
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
                client_socket.settimeout(5.0)
                client_socket.connect((service_host, service_port))
                client_socket.send(json.dumps(log_command).encode("utf-8"))
                response = client_socket.recv(1024).decode("utf-8")
                
                if response and "logged" in response:
                    WORKSTATION_LOGGER.info("Log successfully sent to service")
                    return True
                else:
                    WORKSTATION_LOGGER.warning("Service logging failed: %s", response)
                    return False
                    
        except Exception as e:
            WORKSTATION_LOGGER.error("Error sending log to service: %s", e)
            return False

class ScannerManager:
    """Manages local scanner operations - supports different scanner types."""
    
    def __init__(self, workstation_id, scanner_type="honeywell"):
        """
        Initialize scanner manager.
        
        Args:
            workstation_id (str): Workstation identifier
            scanner_type (str): Type of scanner to use. Default is "honeywell".
        """
        self.workstation_id = workstation_id
        self.scanner_type = scanner_type.lower()
        
        # Scanner-Initialisierung basierend auf Typ
        if self.scanner_type == "honeywell":
            self._init_honeywell_scanner()
        else:
            raise ValueError(f"Unknown scanner type: {scanner_type}. Currently supported: honeywell")

    def _init_honeywell_scanner(self):
        """Initialize HoneywellScanner hardware with connection retry."""
        self.scanner_lock = threading.Lock()
        self.scanner = HoneywellScanner(
            on_connect=self._on_connect, 
            on_disconnect=self._on_disconnect
        )
        
        # NEU: Warten bis Scanner bereit ist
        self._wait_for_scanner_ready()
        SCANNER_LOGGER.info("Local HoneywellScanner hardware initialized")

    def _wait_for_scanner_ready(self, timeout=5.0, retry_interval=0.1):
        """
        Wait for scanner to be ready with timeout.
        
        Args:
            timeout (float): Maximum time to wait in seconds
            retry_interval (float): Time between connection checks
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                if self.scanner.connected:
                    SCANNER_LOGGER.info("HoneywellScanner connection confirmed after %.1f seconds", time.time() - start_time)
                    return
                time.sleep(retry_interval)
            except Exception as e:
                SCANNER_LOGGER.debug("Scanner connection check failed: %s", e)
                time.sleep(retry_interval)
        
        SCANNER_LOGGER.warning("Scanner not ready after %.1f seconds - proceeding anyway", timeout)

    def _on_connect(self):
        """Callback executed when the Scanner is connected."""
        with self.scanner_lock:
            SCANNER_LOGGER.info("HoneywellScanner connection event received")  # ← SCANNER_LOGGER

    def _on_disconnect(self):
        """Callback executed when the Scanner is disconnected."""
        with self.scanner_lock:
            SCANNER_LOGGER.info("HoneywellScanner disconnection event received")  # ← SCANNER_LOGGER

    def scan_serial(self, service_host=None, service_port=65432):
        """Scan serial number using configured scanner hardware with retry logic."""
        if self.scanner_type == "honeywell":
            return self._scan_serial_honeywell_with_retry(service_host, service_port)
        else:
            raise ValueError(f"Scan method not implemented for scanner type: {self.scanner_type}")

    def _scan_serial_honeywell_with_retry(self, service_host=None, service_port=65432, max_retries=2, retry_delay=0.5):
        """
        Scan serial number using local HoneywellScanner hardware with retry logic.
        
        Args:
            service_host (str): Service host for logging
            service_port (int): Service port for logging
            max_retries (int): Maximum number of retry attempts
            retry_delay (float): Delay between retries in seconds
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    SCANNER_LOGGER.info("Scanner retry attempt %d/%d after %.1f second delay", attempt, max_retries, retry_delay)
                    time.sleep(retry_delay)
                
                return self._scan_serial_honeywell(service_host, service_port, attempt)
                
            except Exception as e:
                last_exception = e
                if attempt < max_retries:
                    SCANNER_LOGGER.warning("Scanner attempt %d/%d failed: %s", attempt + 1, max_retries + 1, e)
                    # Versuche Scanner-Reset zwischen Versuchen
                    self._reset_scanner_connection()
                else:
                    SCANNER_LOGGER.error("All scanner attempts failed. Last error: %s", e)
        
        # Alle Versuche fehlgeschlagen
        raise last_exception

    def _reset_scanner_connection(self):
        """Reset scanner connection between retry attempts."""
        try:
            SCANNER_LOGGER.debug("Attempting scanner connection reset")
            with self.scanner_lock:
                try:
                    self.scanner.serial_disconnect()
                except Exception as disconnect_error:
                    SCANNER_LOGGER.debug("Disconnect during reset failed (expected): %s", disconnect_error)
                
                # Kurze Pause für Hardware-Reset
                time.sleep(0.2)
                
                # Scanner wird automatisch reconnected durch HoneywellScanner-Logik
                
        except Exception as reset_error:
            SCANNER_LOGGER.debug("Scanner reset failed: %s", reset_error)

    def _scan_serial_honeywell(self, service_host=None, service_port=65432, attempt=0):
        """Scan serial number using local HoneywellScanner hardware."""
        start_time = datetime.now()
        
        try:
            if attempt == 0:
                SCANNER_LOGGER.info("Executing local HoneywellScanner scan_serial (automatic)")
            else:
                SCANNER_LOGGER.info("Executing local HoneywellScanner scan_serial (automatic) - attempt %d", attempt + 1)
            
            # NEU: Verbindung mit erweiterten Checks prüfen
            if not self._ensure_scanner_connected():
                raise Exception("HoneywellScanner not connected after connection checks")
            
            with self.scanner_lock:
                try:
                    # NEU: Kurze Pause vor serieller Verbindung
                    time.sleep(0.1)
                    
                    self.scanner.serial_connect()
                    serial_number = self.scanner.trigger_scan()
                    
                    if not serial_number:
                        raise Exception("Failed to scan serial number")
                    
                    end_time = datetime.now()
                    response_time = (end_time - start_time).total_seconds()
                    
                    # Log to service using centralized logger
                    log_data = {
                        "task_type": "scanner",
                        "scanner_type": "honeywell",
                        "operation": "scan_serial",
                        "result": "success",
                        "task_data": {
                            "serial_number": serial_number,
                            "response_time": response_time,
                            "scan_method": "automatic",
                            "local_execution": True,
                            "attempt": attempt + 1  # ← NEU: Attempt-Info hinzufügen
                        },
                        "timestamp": start_time.isoformat()
                    }
                    
                    WorkstationLogger.send_log_to_service(
                        self.workstation_id, log_data, service_host, service_port
                    )
                    
                    if attempt == 0:
                        SCANNER_LOGGER.info("Local HoneywellScanner scan completed successfully: serial=%s, time=%.3fs", serial_number, response_time)
                    else:
                        SCANNER_LOGGER.info("Local HoneywellScanner scan completed successfully on attempt %d: serial=%s, time=%.3fs", attempt + 1, serial_number, response_time)
                    
                    return serial_number
                    
                finally:
                    try:
                        self.scanner.serial_disconnect()
                    except Exception as disconnect_error:
                        SCANNER_LOGGER.debug("Error during scanner disconnect: %s", disconnect_error)
        
        except Exception as e:
            error_msg = f"Local HoneywellScanner error: {e}"
            SCANNER_LOGGER.debug(error_msg)  # ← Debug statt error (wird in retry-logic gehandelt)
            
            # Log error to service nur bei letztem Versuch (wird von caller gehandelt)
            raise Exception(str(e))  # ← Vereinfacht für retry-logic

    def _ensure_scanner_connected(self, max_checks=3, check_delay=0.1):
        """
        Ensure scanner is connected with multiple checks.
        
        Args:
            max_checks (int): Maximum number of connection checks
            check_delay (float): Delay between checks in seconds
            
        Returns:
            bool: True if scanner is connected, False otherwise
        """
        for check in range(max_checks):
            try:
                if self.scanner.connected:
                    SCANNER_LOGGER.debug("Scanner connection confirmed on check %d/%d", check + 1, max_checks)
                    return True
                
                if check < max_checks - 1:
                    SCANNER_LOGGER.debug("Scanner connection check %d/%d failed, retrying...", check + 1, max_checks)
                    time.sleep(check_delay)
                    
            except Exception as e:
                SCANNER_LOGGER.debug("Connection check %d/%d failed with exception: %s", check + 1, max_checks, e)
                if check < max_checks - 1:
                    time.sleep(check_delay)
        
        SCANNER_LOGGER.warning("Scanner connection could not be confirmed after %d checks", max_checks)
        return False

class SwitchBoxManager:
    """Manages local SwitchBox operations."""
    
    def __init__(self, workstation_id):
        self.workstation_id = workstation_id
        
        # SwitchBox-Initialisierung
        self.switchbox_lock = threading.Lock()
        self.switch_box = SwitchBox(
            on_connect=self._on_connect, 
            on_disconnect=self._on_disconnect
        )
        SWITCHBOX_LOGGER.info("Local SwitchBox hardware initialized")  # ← SWITCHBOX_LOGGER

    def _on_connect(self):
        """Callback executed when the SwitchBox is connected."""
        with self.switchbox_lock:
            SWITCHBOX_LOGGER.info("SwitchBox connection event received")  # ← SWITCHBOX_LOGGER

    def _on_disconnect(self):
        """Callback executed when the SwitchBox is disconnected."""
        with self.switchbox_lock:
            SWITCHBOX_LOGGER.info("SwitchBox disconnection event received")  # ← SWITCHBOX_LOGGER

    def set_channel(self, channel, service_host=None, service_port=65432):
        """Set channel on local SwitchBox hardware."""
        start_time = datetime.now()
        
        try:
            SWITCHBOX_LOGGER.info("Executing local SwitchBox set_channel: %d", channel)  # ← SWITCHBOX_LOGGER
            
            if not self.switch_box.connected:
                raise Exception("SwitchBox not connected")
            
            if channel not in [1, 2]:
                raise Exception(f"Invalid channel: {channel}")
            
            with self.switchbox_lock:
                try:
                    self.switch_box.serial_connect()
                    self.switch_box.start_listening()
                    self.switch_box.get_status()
                    result_channel = self.switch_box.switch_to_channel(channel)
                    
                    end_time = datetime.now()
                    response_time = (end_time - start_time).total_seconds()
                    
                    # Log to service using centralized logger
                    log_data = {
                        "task_type": "switchbox",
                        "operation": "set_channel",
                        "result": "success",
                        "task_data": {
                            "channel": result_channel,
                            "response_time": response_time,
                            "local_execution": True
                        },
                        "timestamp": start_time.isoformat()
                    }
                    
                    WorkstationLogger.send_log_to_service(
                        self.workstation_id, log_data, service_host, service_port
                    )
                    
                    SWITCHBOX_LOGGER.info("Local set_channel completed successfully: channel=%s, time=%.3fs", result_channel, response_time)  # ← SWITCHBOX_LOGGER
                    return result_channel
                    
                finally:
                    self.switch_box.stop_listening()
                    self.switch_box.serial_disconnect()
        
        except Exception as e:
            error_msg = f"Local SwitchBox error: {e}"
            SWITCHBOX_LOGGER.error(error_msg)  # ← SWITCHBOX_LOGGER
            
            # Log error to service using centralized logger
            log_data = {
                "task_type": "switchbox",
                "operation": "set_channel",
                "result": "error",
                "task_data": {
                    "channel": channel,
                    "error": str(e),
                    "local_execution": True
                },
                "timestamp": start_time.isoformat()
            }
            
            WorkstationLogger.send_log_to_service(
                self.workstation_id, log_data, service_host, service_port
            )
            raise Exception(error_msg)

    def open_box(self, service_host=None, service_port=65432):
        """Open box on local SwitchBox hardware."""
        start_time = datetime.now()
        
        try:
            SWITCHBOX_LOGGER.info("Executing local SwitchBox open_box")  # ← SWITCHBOX_LOGGER
            
            if not self.switch_box.connected:
                raise Exception("SwitchBox not connected")
            
            with self.switchbox_lock:
                try:
                    self.switch_box.serial_connect()
                    self.switch_box.start_listening()
                    self.switch_box.get_status()
                    self.switch_box.open_box()
                    
                    end_time = datetime.now()
                    duration = (end_time - start_time).total_seconds()
                    
                    # Log to service using centralized logger
                    log_data = {
                        "task_type": "switchbox",
                        "operation": "open_box",
                        "result": "success",
                        "task_data": {
                            "duration": duration,
                            "local_execution": True,
                            "box_status": self.switch_box.box_status
                        },
                        "timestamp": start_time.isoformat()
                    }
                    
                    WorkstationLogger.send_log_to_service(
                        self.workstation_id, log_data, service_host, service_port
                    )
                    
                    SWITCHBOX_LOGGER.info("Local open_box completed successfully: duration=%.3fs, status=%s", duration, self.switch_box.box_status)  # ← SWITCHBOX_LOGGER
                    return self.switch_box.box_status
                    
                finally:
                    self.switch_box.stop_listening()
                    self.switch_box.serial_disconnect()
        
        except Exception as e:
            error_msg = f"Local SwitchBox error: {e}"
            SWITCHBOX_LOGGER.error(error_msg)  # ← SWITCHBOX_LOGGER
            
            # Log error to service using centralized logger
            log_data = {
                "task_type": "switchbox",
                "operation": "open_box",
                "result": "error",
                "task_data": {
                    "error": str(e),
                    "local_execution": True
                },
                "timestamp": start_time.isoformat()
            }
            
            WorkstationLogger.send_log_to_service(
                self.workstation_id, log_data, service_host, service_port
            )
            raise Exception(error_msg)