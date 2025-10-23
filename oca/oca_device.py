"""
oca_device.py

ADAM Audio OCA Device Interface
------------------------------------------------

Author: Thilo Rode
Company: ADAM Audio GmbH
Version: 0.1
Date: 2025-10-22

Features:
- Network-based OCA device communication using OCP1ToolWrapper
- Direct TCP/IP control of OCA devices for production and test automation
- High-level API for device info, audio control, input/mode, phase, and biquad filters
- Robust error handling and detailed logging for traceability

This module provides the OCADevice class for direct network communication with OCA devices in ADAM Audio production environments.
"""

import logging
from oca_tools.oca_utilities import OCP1ToolWrapper

class OCADevice:
    """
    OCA Device Network Interface for ADAM Audio production.

    Handles TCP/IP communication with OCA devices using OCP1ToolWrapper.
    Provides high-level methods for device info, audio control, input/mode, phase, and biquad filters.
    Designed for local network communication (e.g., 192.168.10.x).
    """

    def __init__(self, target_ip, port=50001, timeout=5):
        """
        Initialize the OCADevice instance for a specific device.

        Args:
            target_ip (str): OCA device IP address (e.g., "192.168.10.20").
            port (int, optional): OCA device TCP port. Default is 50001.
            timeout (int, optional): Connection timeout in seconds. Default is 5.

        Sets up logging and stores connection parameters.
        """
        self.target_ip = target_ip
        self.port = port
        self.timeout = timeout
        self.logger = logging.getLogger(f"OCADevice-{target_ip}")

    def _get_wrapper(self):
        """
        Get an OCP1ToolWrapper instance for this device.

        Returns:
            OCP1ToolWrapper: Wrapper for low-level device communication.
        """
        return OCP1ToolWrapper(
            target_ip=self.target_ip,
            port=self.port
            # timeout entfernt - wird von OCP1ToolWrapper nicht unterstützt
        )

    # === Device Information ===

    def get_serial_number(self):
        """
        Get the serial number from the OCA device.

        Returns:
            str: Serial number from the device.
        Raises:
            Exception: If device communication fails.
        """
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
        """
        Get the model description from the OCA device.

        Returns:
            str: Model description from the device.
        Raises:
            Exception: If device communication fails.
        """
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
        """
        Get the firmware version from the OCA device.

        Returns:
            str: Firmware version from the device.
        Raises:
            Exception: If device communication fails.
        """
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
        """
        Get the gain value from the OCA device.

        Returns:
            float or str: Gain value from the device.
        Raises:
            Exception: If device communication fails.
        """
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
        """
        Set the gain value on the OCA device.

        Args:
            value (float): Gain value to set.

        Returns:
            str: Result of the gain operation.
        Raises:
            Exception: If device communication fails.
        """
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
        """
        Get the mute state from the OCA device.

        Returns:
            str: Mute state from the device.
        Raises:
            Exception: If device communication fails.
        """
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
        """
        Set the mute state on the OCA device.

        Args:
            state (str): Mute state to set (e.g., 'muted', 'unmuted').

        Returns:
            str: Result of the mute operation.
        Raises:
            Exception: If device communication fails.
        """
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
        """
        Get the audio input mode from the OCA device.

        Returns:
            str: Audio input mode from the device.
        Raises:
            Exception: If device communication fails.
        """
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
        """
        Set the audio input mode on the OCA device.

        Args:
            position (str): Audio input position to set (e.g., 'aes3', 'analogue').

        Returns:
            str: Result of the audio input operation.
        Raises:
            Exception: If device communication fails.
        """
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
        """
        Get the control mode from the OCA device.

        Returns:
            str: Control mode from the device.
        Raises:
            Exception: If device communication fails.
        """
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
        """
        Set the control mode on the OCA device.

        Args:
            position (str): Control mode to set.

        Returns:
            str: Result of the mode operation.
        Raises:
            Exception: If device communication fails.
        """
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
        """
        Get the phase delay value from the OCA device.

        Returns:
            str: Phase delay value from the device.
        Raises:
            Exception: If device communication fails.
        """
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
        """
        Set the phase delay value on the OCA device.

        Args:
            position (str): Phase delay value to set (e.g., 'deg0', 'deg45', ...).

        Returns:
            str: Result of the phase delay operation.
        Raises:
            Exception: If device communication fails.
        """
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
        """
        Get the biquad filter coefficients from the OCA device.

        Args:
            index (int): Biquad index to query.

        Returns:
            str: Biquad coefficients from the device.
        Raises:
            Exception: If device communication fails.
        """
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
        """
        Set the biquad filter coefficients on the OCA device.

        Args:
            index (int): Biquad index to set.
            coefficients (list): List of biquad coefficients to set.

        Returns:
            str: Result of the set operation.
        Raises:
            Exception: If device communication fails.
        """
        try:
            wrapper = self._get_wrapper()
            result = wrapper.set_biquad(index=index, coefficients=coefficients)
            self.logger.info("Set biquad[%d]: %s", index, result)
            return result
        except Exception as e:
            error_msg = f"Failed to set biquad[{index}]: {e}"
            self.logger.error(error_msg)
            raise
