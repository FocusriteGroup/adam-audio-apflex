"""
ADAM Audio OCA Device Interface

Network-based OCA device communication using OCP1ToolWrapper.
Handles direct TCP/IP communication with OCA devices.
"""

import logging
from datetime import datetime
from oca_tools.oca_utilities import OCP1ToolWrapper

class OCADevice:
    """
    OCA Device Network Interface.
    
    Handles TCP/IP communication with OCA devices using OCP1ToolWrapper.
    Designed for local network communication (e.g., 192.168.10.x).
    """
    
    def __init__(self, target_ip, port=50001, timeout=5):
        """
        Initialize OCA device connection.
        
        Args:
            target_ip (str): OCA device IP address (e.g., "192.168.10.20")
            port (int): OCA device port (default: 50001)
            timeout (int): Connection timeout in seconds
        """
        self.target_ip = target_ip
        self.port = port
        self.timeout = timeout
        self.logger = logging.getLogger(f"OCADevice-{target_ip}")
        
    def _get_wrapper(self):
        """Get OCP1ToolWrapper instance for this device."""
        return OCP1ToolWrapper(
            target_ip=self.target_ip, 
            port=self.port
            # timeout entfernt - wird von OCP1ToolWrapper nicht unterstützt
        )
    
    # === Device Information ===
    
    def get_serial_number(self):
        """Get serial number from OCA device."""
        try:
            wrapper = self._get_wrapper()
            result = wrapper.get_serial_number()
            self.logger.info("Serial number: %s", result)
            return result
        except Exception as e:
            error_msg = f"Failed to get serial number: {e}"
            self.logger.error(error_msg)
            raise
    
    def get_model_description(self):
        """Get model description from OCA device."""
        try:
            wrapper = self._get_wrapper()
            result = wrapper.get_model_description()
            self.logger.info("Model description: %s", result)
            return result
        except Exception as e:
            error_msg = f"Failed to get model description: {e}"
            self.logger.error(error_msg)
            raise
    
    def get_firmware_version(self):
        """Get firmware version from OCA device."""
        try:
            wrapper = self._get_wrapper()
            result = wrapper.get_firmware_version()
            self.logger.info("Firmware version: %s", result)
            return result
        except Exception as e:
            error_msg = f"Failed to get firmware version: {e}"
            self.logger.error(error_msg)
            raise
    
    # === Audio Control ===
    
    def get_gain(self):
        """Get gain from OCA device."""
        try:
            wrapper = self._get_wrapper()
            result = wrapper.get_gain()
            self.logger.info("Gain: %s", result)
            return result
        except Exception as e:
            error_msg = f"Failed to get gain: {e}"
            self.logger.error(error_msg)
            raise
    
    def set_gain(self, value):
        """Set gain on OCA device."""
        try:
            wrapper = self._get_wrapper()
            result = wrapper.set_gain(value)
            self.logger.info("Set gain to %s: %s", value, result)
            return result
        except Exception as e:
            error_msg = f"Failed to set gain to {value}: {e}"
            self.logger.error(error_msg)
            raise
    
    def get_mute(self):
        """Get mute state from OCA device."""
        try:
            wrapper = self._get_wrapper()
            result = wrapper.get_mute()
            self.logger.info("Mute state: %s", result)
            return result
        except Exception as e:
            error_msg = f"Failed to get mute state: {e}"
            self.logger.error(error_msg)
            raise
    
    def set_mute(self, state):
        """Set mute state on OCA device."""
        try:
            wrapper = self._get_wrapper()
            result = wrapper.set_mute(state)
            self.logger.info("Set mute to %s: %s", state, result)
            return result
        except Exception as e:
            error_msg = f"Failed to set mute to {state}: {e}"
            self.logger.error(error_msg)
            raise
    
    # === Audio Input/Mode Control ===
    
    def get_audio_input(self):
        """Get audio input mode from OCA device."""
        try:
            wrapper = self._get_wrapper()
            result = wrapper.get_audio_input()
            self.logger.info("Audio input: %s", result)
            return result
        except Exception as e:
            error_msg = f"Failed to get audio input: {e}"
            self.logger.error(error_msg)
            raise
    
    def set_audio_input(self, position):
        """Set audio input mode on OCA device."""
        try:
            wrapper = self._get_wrapper()
            result = wrapper.set_audio_input(position)
            self.logger.info("Set audio input to %s: %s", position, result)
            return result
        except Exception as e:
            error_msg = f"Failed to set audio input to {position}: {e}"
            self.logger.error(error_msg)
            raise
    
    def get_mode(self):
        """Get control mode from OCA device."""
        try:
            wrapper = self._get_wrapper()
            result = wrapper.get_mode()
            self.logger.info("Mode: %s", result)
            return result
        except Exception as e:
            error_msg = f"Failed to get mode: {e}"
            self.logger.error(error_msg)
            raise
    
    def set_mode(self, position):
        """Set control mode on OCA device."""
        try:
            wrapper = self._get_wrapper()
            result = wrapper.set_mode(position)
            self.logger.info("Set mode to %s: %s", position, result)
            return result
        except Exception as e:
            error_msg = f"Failed to set mode to {position}: {e}"
            self.logger.error(error_msg)
            raise
    
    # === Phase Delay Control ===
    
    def get_phase_delay(self):
        """Get phase delay from OCA device."""
        try:
            wrapper = self._get_wrapper()
            result = wrapper.get_phase_delay()
            self.logger.info("Phase delay: %s", result)
            return result
        except Exception as e:
            error_msg = f"Failed to get phase delay: {e}"
            self.logger.error(error_msg)
            raise
    
    def set_phase_delay(self, position):
        """Set phase delay on OCA device."""
        try:
            wrapper = self._get_wrapper()
            result = wrapper.set_phase_delay(position)
            self.logger.info("Set phase delay to %s: %s", position, result)
            return result
        except Exception as e:
            error_msg = f"Failed to set phase delay to {position}: {e}"
            self.logger.error(error_msg)
            raise
    
    # === Biquad Filter Control ===
    
    def get_device_biquad(self, index):
        """Get biquad coefficients from OCA device."""
        try:
            wrapper = self._get_wrapper()
            result = wrapper.get_biquad(index=index)
            self.logger.info("Biquad[%d]: %s", index, result)
            return result
        except Exception as e:
            error_msg = f"Failed to get biquad[{index}]: {e}"
            self.logger.error(error_msg)
            raise
    
    def set_device_biquad(self, index, coefficients):
        """Set biquad coefficients on OCA device."""
        try:
            wrapper = self._get_wrapper()
            result = wrapper.set_biquad(index=index, coefficients=coefficients)
            self.logger.info("Set biquad[%d]: %s", index, result)
            return result
        except Exception as e:
            error_msg = f"Failed to set biquad[{index}]: {e}"
            self.logger.error(error_msg)
            raise