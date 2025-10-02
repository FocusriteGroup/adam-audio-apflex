"""
Serial Scanner Manager

High-level scanner management with retry logic and service integration.
Supports multiple serial scanner types with unified interface.
"""

import threading
import time
from datetime import datetime
from .base_serial_manager import BaseSerialManager
from hardware import HoneywellScanner

class ScannerManager(BaseSerialManager):
    """Manages serial scanner operations with retry logic."""
    
    def __init__(self, workstation_id, scanner_type="honeywell"):
        """
        Initialize serial scanner manager.
        
        Args:
            workstation_id (str): Workstation identifier
            scanner_type (str): Type of scanner to use. Default is "honeywell".
        """
        super().__init__(workstation_id, "Scanner")
        self.scanner_type = scanner_type.lower()
        
        # Scanner-Initialisierung basierend auf Typ
        if self.scanner_type == "honeywell":
            self._init_honeywell_scanner()
        else:
            raise ValueError(f"Unknown scanner type: {scanner_type}. Currently supported: honeywell")

    def _init_honeywell_scanner(self):
        """Initialize HoneywellScanner serial hardware."""
        self.scanner_lock = threading.Lock()
        self.scanner = HoneywellScanner(
            on_connect=self._on_connect, 
            on_disconnect=self._on_disconnect
        )
        
        # Warten bis Serial Scanner bereit ist
        self._wait_for_serial_device_ready(self.scanner, "HoneywellScanner")
        self.logger.info("HoneywellScanner serial hardware initialized")

    def _on_connect(self):
        """Callback executed when the serial scanner is connected."""
        with self.scanner_lock:
            self.logger.info("HoneywellScanner serial connection event received")

    def _on_disconnect(self):
        """Callback executed when the serial scanner is disconnected."""
        with self.scanner_lock:
            self.logger.info("HoneywellScanner serial disconnection event received")

    def _reset_serial_connection(self):
        """Reset scanner serial connection between retry attempts."""
        try:
            self.logger.debug("Attempting scanner serial connection reset")
            with self.scanner_lock:
                try:
                    self.scanner.serial_disconnect()
                except Exception as disconnect_error:
                    self.logger.debug("Serial disconnect during reset failed (expected): %s", disconnect_error)
                
                # Kurze Pause für Serial Hardware-Reset
                time.sleep(0.2)
                
        except Exception as reset_error:
            self.logger.debug("Scanner serial reset failed: %s", reset_error)

    def scan_serial(self, service_host=None, service_port=65432):
        """Scan serial number using configured scanner hardware with retry logic."""
        if self.scanner_type == "honeywell":
            return self.execute_with_retry(
                self._scan_serial_honeywell, 
                "scan_serial", 
                service_host=service_host, 
                service_port=service_port
            )
        else:
            raise ValueError(f"Scan method not implemented for scanner type: {self.scanner_type}")

    def _scan_serial_honeywell(self, attempt, service_host=None, service_port=65432):
        """Scan serial number using local HoneywellScanner serial hardware."""
        start_time = datetime.now()
        
        if attempt == 0:
            self.logger.info("Executing local HoneywellScanner scan_serial (automatic)")
        else:
            self.logger.info("Executing local HoneywellScanner scan_serial (automatic) - attempt %d", attempt + 1)
        
        # Serial-Verbindung mit erweiterten Checks prüfen
        if not self._ensure_serial_device_connected(self.scanner, "HoneywellScanner"):
            raise Exception("HoneywellScanner not connected after connection checks")
        
        with self.scanner_lock:
            try:
                # Kurze Pause vor serieller Verbindung
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
                        "attempt": attempt + 1
                    },
                    "timestamp": start_time.isoformat()
                }
                
                self._log_to_service(log_data, service_host, service_port)
                
                if attempt == 0:
                    self.logger.info("Local HoneywellScanner scan completed successfully: serial=%s, time=%.3fs", 
                                   serial_number, response_time)
                else:
                    self.logger.info("Local HoneywellScanner scan completed successfully on attempt %d: serial=%s, time=%.3fs", 
                                   attempt + 1, serial_number, response_time)
                
                return serial_number
                
            finally:
                try:
                    self.scanner.serial_disconnect()
                except Exception as disconnect_error:
                    self.logger.debug("Error during scanner serial disconnect: %s", disconnect_error)