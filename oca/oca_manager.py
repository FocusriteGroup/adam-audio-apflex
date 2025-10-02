"""
ADAM Audio OCA Manager

High-level OCA device management with workstation integration.
Provides service logging and coordination for OCA operations.
"""

import logging
import socket
import json
from datetime import datetime
from .oca_device import OCADevice

class OCAManager:
    """
    OCA Device Manager.
    
    Manages OCA device communication and provides integration
    with workstation logging and service communication.
    """
    
    def __init__(self, workstation_id=None, service_client=None):
        """
        Initialize OCA Manager.
        
        Args:
            workstation_id (str): Workstation identifier for logging
            service_client: Service client for logging (optional)
        """
        self.workstation_id = workstation_id or socket.gethostname()
        self.service_client = service_client
        self.logger = logging.getLogger(f"OCAManager-{self.workstation_id}")
        
    def create_device(self, target_ip, port=50001):
        """Create OCA device instance."""
        return OCADevice(target_ip=target_ip, port=port)
    
    def _log_to_service(self, operation, result, target_ip, port, extra_data=None):
        """Log OCA operation to service if service client available."""
        if not self.service_client:
            return
            
        try:
            task_data = {
                "target_ip": target_ip,
                "port": port,
                **(extra_data or {})
            }
            
            command = {
                "action": "log_workstation_task",
                "workstation_id": self.workstation_id,
                "task_type": "oca",
                "operation": operation,
                "result": str(result),
                "task_data": task_data,
                "timestamp": datetime.now().isoformat(),
                "wait_for_response": False
            }
            
            self.service_client.send_command(command, wait_for_response=False)
            self.logger.debug("OCA operation logged to service")
            
        except Exception as e:
            self.logger.warning("Failed to log OCA operation to service: %s", e)
    
    # === High-level OCA operations with logging ===
    
    def get_serial_number(self, target_ip, port=50001):
        """Get serial number with service logging."""
        device = self.create_device(target_ip, port)
        try:
            result = device.get_serial_number()
            self._log_to_service("get_serial_number", result, target_ip, port)
            return result
        except Exception as e:
            self._log_to_service("get_serial_number", f"Error: {e}", target_ip, port)
            raise
    
    def set_mute(self, state, target_ip, port=50001):
        """Set mute state with service logging."""
        device = self.create_device(target_ip, port)
        try:
            result = device.set_mute(state)
            self._log_to_service("set_mute", result, target_ip, port, {"state": state})
            return result
        except Exception as e:
            self._log_to_service("set_mute", f"Error: {e}", target_ip, port, {"state": state})
            raise
    
    def get_mute(self, target_ip, port=50001):
        """Get mute state with service logging."""
        device = self.create_device(target_ip, port)
        try:
            result = device.get_mute()
            self._log_to_service("get_mute", result, target_ip, port)
            return result
        except Exception as e:
            self._log_to_service("get_mute", f"Error: {e}", target_ip, port)
            raise
    
    def set_gain(self, value, target_ip, port=50001):
        """Set gain with service logging."""
        device = self.create_device(target_ip, port)
        try:
            result = device.set_gain(value)
            self._log_to_service("set_gain", result, target_ip, port, {"value": value})
            return result
        except Exception as e:
            self._log_to_service("set_gain", f"Error: {e}", target_ip, port, {"value": value})
            raise
    
    def get_gain(self, target_ip, port=50001):
        """Get gain with service logging."""
        device = self.create_device(target_ip, port)
        try:
            result = device.get_gain()
            self._log_to_service("get_gain", result, target_ip, port)
            return result
        except Exception as e:
            self._log_to_service("get_gain", f"Error: {e}", target_ip, port)
            raise
    
    def get_model_description(self, target_ip, port=50001):
        """Get model description with service logging."""
        device = self.create_device(target_ip, port)
        try:
            result = device.get_model_description()
            self._log_to_service("get_model_description", result, target_ip, port)
            return result
        except Exception as e:
            self._log_to_service("get_model_description", f"Error: {e}", target_ip, port)
            raise
    
    def get_firmware_version(self, target_ip, port=50001):
        """Get firmware version with service logging."""
        device = self.create_device(target_ip, port)
        try:
            result = device.get_firmware_version()
            self._log_to_service("get_firmware_version", result, target_ip, port)
            return result
        except Exception as e:
            self._log_to_service("get_firmware_version", f"Error: {e}", target_ip, port)
            raise
    
    def get_audio_input(self, target_ip, port=50001):
        """Get audio input with service logging."""
        device = self.create_device(target_ip, port)
        try:
            result = device.get_audio_input()
            self._log_to_service("get_audio_input", result, target_ip, port)
            return result
        except Exception as e:
            self._log_to_service("get_audio_input", f"Error: {e}", target_ip, port)
            raise
    
    def set_audio_input(self, position, target_ip, port=50001):
        """Set audio input with service logging."""
        device = self.create_device(target_ip, port)
        try:
            result = device.set_audio_input(position)
            self._log_to_service("set_audio_input", result, target_ip, port, {"position": position})
            return result
        except Exception as e:
            self._log_to_service("set_audio_input", f"Error: {e}", target_ip, port, {"position": position})
            raise
    
    def get_mode(self, target_ip, port=50001):
        """Get mode with service logging."""
        device = self.create_device(target_ip, port)
        try:
            result = device.get_mode()
            self._log_to_service("get_mode", result, target_ip, port)
            return result
        except Exception as e:
            self._log_to_service("get_mode", f"Error: {e}", target_ip, port)
            raise
    
    def set_mode(self, position, target_ip, port=50001):
        """Set mode with service logging."""
        device = self.create_device(target_ip, port)
        try:
            result = device.set_mode(position)
            self._log_to_service("set_mode", result, target_ip, port, {"position": position})
            return result
        except Exception as e:
            self._log_to_service("set_mode", f"Error: {e}", target_ip, port, {"position": position})
            raise
    
    def get_phase_delay(self, target_ip, port=50001):
        """Get phase delay with service logging."""
        device = self.create_device(target_ip, port)
        try:
            result = device.get_phase_delay()
            self._log_to_service("get_phase_delay", result, target_ip, port)
            return result
        except Exception as e:
            self._log_to_service("get_phase_delay", f"Error: {e}", target_ip, port)
            raise
    
    def set_phase_delay(self, position, target_ip, port=50001):
        """Set phase delay with service logging."""
        device = self.create_device(target_ip, port)
        try:
            result = device.set_phase_delay(position)
            self._log_to_service("set_phase_delay", result, target_ip, port, {"position": position})
            return result
        except Exception as e:
            self._log_to_service("set_phase_delay", f"Error: {e}", target_ip, port, {"position": position})
            raise
    
    def get_device_biquad(self, index, target_ip, port=50001):
        """Get device biquad with service logging."""
        device = self.create_device(target_ip, port)
        try:
            result = device.get_device_biquad(index)
            self._log_to_service("get_device_biquad", result, target_ip, port, {"index": index})
            return result
        except Exception as e:
            self._log_to_service("get_device_biquad", f"Error: {e}", target_ip, port, {"index": index})
            raise
    
    def set_device_biquad(self, index, coefficients, target_ip, port=50001):
        """Set device biquad with service logging."""
        device = self.create_device(target_ip, port)
        try:
            result = device.set_device_biquad(index, coefficients)
            self._log_to_service("set_device_biquad", result, target_ip, port, {"index": index, "coefficients": coefficients})
            return result
        except Exception as e:
            self._log_to_service("set_device_biquad", f"Error: {e}", target_ip, port, {"index": index, "coefficients": coefficients})
            raise