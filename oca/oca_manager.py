"""
oca_manager.py

ADAM Audio OCA Device Manager
------------------------------------------------

Author: Thilo Rode
Company: ADAM Audio GmbH
Version: 0.1
Date: 2025-10-22

Features:
- High-level OCA device management with workstation integration
- Service logging and coordination for all OCA operations
- Modular, extensible design for production and test automation
- Robust error handling and detailed logging for traceability

This module provides the OCAManager class for managing OCA device communication, logging, and integration with ADAM Audio production workstations and services.
"""

import logging
import socket
import json
from datetime import datetime
from .oca_device import OCADevice

class OCAManager:
    """
    OCA Device Manager for ADAM Audio production environments.

    Manages OCA device communication, provides integration with workstation logging,
    and coordinates service communication for all OCA-related operations.

    Features:
    - High-level API for OCA device control (mute, gain, mode, etc.)
    - Automatic logging of all operations to the production service
    - Extensible for new OCA commands and production workflows
    """
    def __init__(self, workstation_id=None, service_client=None):
        """
        Initialize the OCA Manager instance.

        Args:
            workstation_id (str, optional): Workstation identifier for logging. Defaults to system hostname.
            service_client (optional): Service client for logging (must provide send_command method).

        Sets up logging and stores references for all OCA operations.
        """
        self.workstation_id = workstation_id or socket.gethostname()
        self.service_client = service_client
        self.logger = logging.getLogger(f"OCAManager-{self.workstation_id}")

    def create_device(self, target_ip, port=50001):
        """
        Create an OCADevice instance for the given target IP and port.

        Args:
            target_ip (str): IP address of the OCA device.
            port (int, optional): TCP port for OCA device. Default is 50001.

        Returns:
            OCADevice: Instance for device communication.
        """
        return OCADevice(target_ip=target_ip, port=port)

    def _log_to_service(self, operation, result, target_ip, port, extra_data=None):
        """
        Log an OCA operation to the production service if a service client is available.

        Args:
            operation (str): Name of the OCA operation performed.
            result (str): Result or status of the operation.
            target_ip (str): IP address of the OCA device.
            port (int): TCP port of the OCA device.
            extra_data (dict, optional): Additional metadata for logging.

        Handles errors gracefully and logs warnings if logging fails.
        """
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

        except (socket.error, json.JSONDecodeError, AttributeError) as e:
            self.logger.warning("Failed to log OCA operation to service: %s", e)

    # === High-level OCA operations with logging ===

    def get_serial_number(self, target_ip, port=50001):
        """
        Get the serial number from an OCA device, with service logging.

        Args:
            target_ip (str): IP address of the OCA device.
            port (int, optional): TCP port for OCA device. Default is 50001.

        Returns:
            str: Serial number from the device.
        Raises:
            Exception: If device communication fails.
        """
        device = self.create_device(target_ip, port)
        try:
            result = device.get_serial_number()
            self._log_to_service("get_serial_number", result, target_ip, port)
            return result
        except Exception as e:
            self._log_to_service("get_serial_number", f"Error: {e}", target_ip, port)
            raise

    def set_mute(self, state, target_ip, port=50001):
        """
        Set the mute state on an OCA device, with service logging.

        Args:
            state (str): Mute state to set (e.g., 'muted', 'unmuted').
            target_ip (str): IP address of the OCA device.
            port (int, optional): TCP port for OCA device. Default is 50001.

        Returns:
            str: Result of the mute operation.
        Raises:
            Exception: If device communication fails.
        """
        device = self.create_device(target_ip, port)
        try:
            result = device.set_mute(state)
            self._log_to_service("set_mute", result, target_ip, port, {"state": state})
            return result
        except Exception as e:
            self._log_to_service("set_mute", f"Error: {e}", target_ip, port, {"state": state})
            raise

    def get_mute(self, target_ip, port=50001):
        """
        Get the mute state from an OCA device, with service logging.

        Args:
            target_ip (str): IP address of the OCA device.
            port (int, optional): TCP port for OCA device. Default is 50001.

        Returns:
            str: Mute state from the device.
        Raises:
            Exception: If device communication fails.
        """
        device = self.create_device(target_ip, port)
        try:
            result = device.get_mute()
            self._log_to_service("get_mute", result, target_ip, port)
            return result
        except Exception as e:
            self._log_to_service("get_mute", f"Error: {e}", target_ip, port)
            raise

    def set_gain(self, value, target_ip, port=50001):
        """
        Set the gain value on an OCA device, with service logging.

        Args:
            value (float): Gain value to set.
            target_ip (str): IP address of the OCA device.
            port (int, optional): TCP port for OCA device. Default is 50001.

        Returns:
            str: Result of the gain operation.
        Raises:
            Exception: If device communication fails.
        """
        device = self.create_device(target_ip, port)
        try:
            result = device.set_gain(value)
            self._log_to_service("set_gain", result, target_ip, port, {"value": value})
            return result
        except Exception as e:
            self._log_to_service("set_gain", f"Error: {e}", target_ip, port, {"value": value})
            raise

    def get_gain(self, target_ip, port=50001):
        """
        Get the gain value from an OCA device, with service logging.

        Args:
            target_ip (str): IP address of the OCA device.
            port (int, optional): TCP port for OCA device. Default is 50001.

        Returns:
            str: Gain value from the device.
        Raises:
            Exception: If device communication fails.
        """
        device = self.create_device(target_ip, port)
        try:
            result = device.get_gain()
            self._log_to_service("get_gain", result, target_ip, port)
            return result
        except Exception as e:
            self._log_to_service("get_gain", f"Error: {e}", target_ip, port)
            raise

    def get_model_description(self, target_ip, port=50001):
        """
        Get the model description from an OCA device, with service logging.

        Args:
            target_ip (str): IP address of the OCA device.
            port (int, optional): TCP port for OCA device. Default is 50001.

        Returns:
            str: Model description from the device.
        Raises:
            Exception: If device communication fails.
        """
        device = self.create_device(target_ip, port)
        try:
            result = device.get_model_description()
            self._log_to_service("get_model_description", result, target_ip, port)
            return result
        except Exception as e:
            self._log_to_service("get_model_description", f"Error: {e}", target_ip, port)
            raise

    def get_firmware_version(self, target_ip, port=50001):
        """
        Get the firmware version from an OCA device, with service logging.

        Args:
            target_ip (str): IP address of the OCA device.
            port (int, optional): TCP port for OCA device. Default is 50001.

        Returns:
            str: Firmware version from the device.
        Raises:
            Exception: If device communication fails.
        """
        device = self.create_device(target_ip, port)
        try:
            result = device.get_firmware_version()
            self._log_to_service("get_firmware_version", result, target_ip, port)
            return result
        except Exception as e:
            self._log_to_service("get_firmware_version", f"Error: {e}", target_ip, port)
            raise

    def get_audio_input(self, target_ip, port=50001):
        """
        Get the audio input mode from an OCA device, with service logging.

        Args:
            target_ip (str): IP address of the OCA device.
            port (int, optional): TCP port for OCA device. Default is 50001.

        Returns:
            str: Audio input mode from the device.
        Raises:
            Exception: If device communication fails.
        """
        device = self.create_device(target_ip, port)
        try:
            result = device.get_audio_input()
            self._log_to_service("get_audio_input", result, target_ip, port)
            return result
        except Exception as e:
            self._log_to_service("get_audio_input", f"Error: {e}", target_ip, port)
            raise

    def set_audio_input(self, position, target_ip, port=50001):
        """
        Set the audio input mode on an OCA device, with service logging.

        Args:
            position (str): Audio input position to set (e.g., 'aes3', 'analogue').
            target_ip (str): IP address of the OCA device.
            port (int, optional): TCP port for OCA device. Default is 50001.

        Returns:
            str: Result of the audio input operation.
        Raises:
            Exception: If device communication fails.
        """
        device = self.create_device(target_ip, port)
        try:
            result = device.set_audio_input(position)
            self._log_to_service("set_audio_input", result, target_ip, port, {"position": position})
            return result
        except Exception as e:
            self._log_to_service("set_audio_input", f"Error: {e}", target_ip, port, {"position": position})
            raise

    def get_mode(self, target_ip, port=50001):
        """
        Get the control mode from an OCA device, with service logging.

        Args:
            target_ip (str): IP address of the OCA device.
            port (int, optional): TCP port for OCA device. Default is 50001.

        Returns:
            str: Control mode from the device.
        Raises:
            Exception: If device communication fails.
        """
        device = self.create_device(target_ip, port)
        try:
            result = device.get_mode()
            self._log_to_service("get_mode", result, target_ip, port)
            return result
        except Exception as e:
            self._log_to_service("get_mode", f"Error: {e}", target_ip, port)
            raise

    def set_mode(self, position, target_ip, port=50001):
        """
        Set the control mode on an OCA device, with service logging.

        Args:
            position (str): Control mode to set.
            target_ip (str): IP address of the OCA device.
            port (int, optional): TCP port for OCA device. Default is 50001.

        Returns:
            str: Result of the mode operation.
        Raises:
            Exception: If device communication fails.
        """
        device = self.create_device(target_ip, port)
        try:
            result = device.set_mode(position)
            self._log_to_service("set_mode", result, target_ip, port, {"position": position})
            return result
        except Exception as e:
            self._log_to_service("set_mode", f"Error: {e}", target_ip, port, {"position": position})
            raise

    def get_phase_delay(self, target_ip, port=50001):
        """
        Get the phase delay value from an OCA device, with service logging.

        Args:
            target_ip (str): IP address of the OCA device.
            port (int, optional): TCP port for OCA device. Default is 50001.

        Returns:
            str: Phase delay value from the device.
        Raises:
            Exception: If device communication fails.
        """
        device = self.create_device(target_ip, port)
        try:
            result = device.get_phase_delay()
            self._log_to_service("get_phase_delay", result, target_ip, port)
            return result
        except Exception as e:
            self._log_to_service("get_phase_delay", f"Error: {e}", target_ip, port)
            raise

    def set_phase_delay(self, position, target_ip, port=50001):
        """
        Set the phase delay value on an OCA device, with service logging.

        Args:
            position (str): Phase delay value to set (e.g., 'deg0', 'deg45', ...).
            target_ip (str): IP address of the OCA device.
            port (int, optional): TCP port for OCA device. Default is 50001.

        Returns:
            str: Result of the phase delay operation.
        Raises:
            Exception: If device communication fails.
        """
        device = self.create_device(target_ip, port)
        try:
            result = device.set_phase_delay(position)
            self._log_to_service("set_phase_delay", result, target_ip, port, {"position": position})
            return result
        except Exception as e:
            self._log_to_service("set_phase_delay", f"Error: {e}", target_ip, port, {"position": position})
            raise

    def get_device_biquad(self, index, target_ip, port=50001):
        """
        Get the biquad filter coefficients from an OCA device, with service logging.

        Args:
            index (int): Biquad index to query.
            target_ip (str): IP address of the OCA device.
            port (int, optional): TCP port for OCA device. Default is 50001.

        Returns:
            str: Biquad coefficients from the device.
        Raises:
            Exception: If device communication fails.
        """
        device = self.create_device(target_ip, port)
        try:
            result = device.get_device_biquad(index)
            self._log_to_service("get_device_biquad", result, target_ip, port, {"index": index})
            return result
        except Exception as e:
            self._log_to_service("get_device_biquad", f"Error: {e}", target_ip, port, {"index": index})
            raise

    def set_device_biquad(self, index, coefficients, target_ip, port=50001):
        """
        Set the biquad filter coefficients on an OCA device, with service logging.

        Args:
            index (int): Biquad index to set.
            coefficients (list): List of biquad coefficients to set.
            target_ip (str): IP address of the OCA device.
            port (int, optional): TCP port for OCA device. Default is 50001.

        Returns:
            str: Result of the set operation.
        Raises:
            Exception: If device communication fails.
        """
        device = self.create_device(target_ip, port)
        try:
            result = device.set_device_biquad(index, coefficients)
            self._log_to_service("set_device_biquad", result, target_ip, port, {"index": index, "coefficients": coefficients})
            return result
        except Exception as e:
            self._log_to_service("set_device_biquad", f"Error: {e}", target_ip, port, {"index": index, "coefficients": coefficients})
            raise
