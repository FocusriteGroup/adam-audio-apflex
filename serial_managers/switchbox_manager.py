"""
Serial SwitchBox Manager

High-level switchbox management with retry logic and service integration.
Specialized for audio routing switch boxes via serial communication.
"""

import threading
import time
from datetime import datetime
from .base_serial_manager import BaseSerialManager
from hardware import SwitchBox

class SwitchBoxManager(BaseSerialManager):
    """Manages serial switchbox operations with retry logic."""
    
    def __init__(self, workstation_id):
        """
        Initialize serial switchbox manager.
        
        Args:
            workstation_id (str): Workstation identifier
        """
        super().__init__(workstation_id, "SwitchBox")
        
        # SwitchBox-Initialisierung
        self.switchbox_lock = threading.Lock()
        self.switch_box = SwitchBox(
            on_connect=self._on_connect, 
            on_disconnect=self._on_disconnect
        )
        
        # Warten bis Serial SwitchBox bereit ist
        self._wait_for_serial_device_ready(self.switch_box, "SwitchBox")
        self.logger.info("SwitchBox serial hardware initialized")

    def _on_connect(self):
        """Callback executed when the serial SwitchBox is connected."""
        with self.switchbox_lock:
            self.logger.info("SwitchBox serial connection event received")

    def _on_disconnect(self):
        """Callback executed when the serial SwitchBox is disconnected."""
        with self.switchbox_lock:
            self.logger.info("SwitchBox serial disconnection event received")

    def _reset_serial_connection(self):
        """Reset switchbox serial connection between retry attempts."""
        try:
            self.logger.debug("Attempting SwitchBox serial connection reset")
            with self.switchbox_lock:
                try:
                    self.switch_box.serial_disconnect()
                except Exception as disconnect_error:
                    self.logger.debug("Serial disconnect during reset failed (expected): %s", disconnect_error)
                
                # Kurze Pause für Serial Hardware-Reset
                time.sleep(0.2)
                
        except Exception as reset_error:
            self.logger.debug("SwitchBox serial reset failed: %s", reset_error)

    def set_channel(self, channel, service_host=None, service_port=65432):
        """Set channel on serial SwitchBox hardware with retry logic."""
        return self.execute_with_retry(
            self._set_channel_switchbox, 
            "set_channel", 
            channel=channel, 
            service_host=service_host, 
            service_port=service_port
        )

    def _set_channel_switchbox(self, attempt, channel, service_host=None, service_port=65432):
        """Set channel on local SwitchBox serial hardware."""
        start_time = datetime.now()
        
        try:
            if attempt == 0:
                self.logger.info("Executing local SwitchBox set_channel: %d", channel)
            else:
                self.logger.info("Executing local SwitchBox set_channel: %d - attempt %d", channel, attempt + 1)
            
            # Serial-Verbindung mit erweiterten Checks prüfen
            if not self._ensure_serial_device_connected(self.switch_box, "SwitchBox"):
                raise Exception("SwitchBox not connected after connection checks")
            
            if channel not in [1, 2]:
                raise Exception(f"Invalid channel: {channel}")
            
            with self.switchbox_lock:
                try:
                    # Kurze Pause vor serieller Verbindung
                    time.sleep(0.1)
                    
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
                            "local_execution": True,
                            "attempt": attempt + 1
                        },
                        "timestamp": start_time.isoformat()
                    }
                    
                    self._log_to_service(log_data, service_host, service_port)
                    
                    if attempt == 0:
                        self.logger.info("Local set_channel completed successfully: channel=%s, time=%.3fs", result_channel, response_time)
                    else:
                        self.logger.info("Local set_channel completed successfully on attempt %d: channel=%s, time=%.3fs", attempt + 1, result_channel, response_time)
                    
                    return result_channel
                    
                finally:
                    try:
                        self.switch_box.stop_listening()
                        self.switch_box.serial_disconnect()
                    except Exception as disconnect_error:
                        self.logger.debug("Error during switchbox serial disconnect: %s", disconnect_error)
        
        except Exception as e:
            self.logger.debug(f"Local SwitchBox serial error: {e}")
            raise Exception(str(e))

    def open_box(self, service_host=None, service_port=65432):
        """Open box on serial SwitchBox hardware with retry logic."""
        return self.execute_with_retry(
            self._open_box_switchbox, 
            "open_box", 
            service_host=service_host, 
            service_port=service_port
        )

    def _open_box_switchbox(self, attempt, service_host=None, service_port=65432):
        """Open box on local SwitchBox serial hardware."""
        start_time = datetime.now()
        
        try:
            if attempt == 0:
                self.logger.info("Executing local SwitchBox open_box")
            else:
                self.logger.info("Executing local SwitchBox open_box - attempt %d", attempt + 1)
            
            # Serial-Verbindung mit erweiterten Checks prüfen
            if not self._ensure_serial_device_connected(self.switch_box, "SwitchBox"):
                raise Exception("SwitchBox not connected after connection checks")
            
            with self.switchbox_lock:
                try:
                    # Kurze Pause vor serieller Verbindung
                    time.sleep(0.1)
                    
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
                            "box_status": self.switch_box.box_status,
                            "attempt": attempt + 1
                        },
                        "timestamp": start_time.isoformat()
                    }
                    
                    self._log_to_service(log_data, service_host, service_port)
                    
                    if attempt == 0:
                        self.logger.info("Local open_box completed successfully: duration=%.3fs, status=%s", duration, self.switch_box.box_status)
                    else:
                        self.logger.info("Local open_box completed successfully on attempt %d: duration=%.3fs, status=%s", attempt + 1, duration, self.switch_box.box_status)
                    
                    return self.switch_box.box_status
                    
                finally:
                    try:
                        self.switch_box.stop_listening()
                        self.switch_box.serial_disconnect()
                    except Exception as disconnect_error:
                        self.logger.debug("Error during switchbox serial disconnect: %s", disconnect_error)
        
        except Exception as e:
            self.logger.debug(f"Local SwitchBox serial error: {e}")
            raise Exception(str(e))