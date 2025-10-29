import logging
from oca_tools.oca_utilities import OCP1ToolWrapper

class OCADevice:
    """
    OCA Device Network Interface for ADAM Audio production.
    Unterstützt nur die OCA-Befehle: discover, gain calibration, mode, audio input.
    """

    def __init__(self, target_ip, port=50001, timeout=5):
        self.target_ip = target_ip
        self.port = port
        self.timeout = timeout
        self.logger = logging.getLogger(f"OCADevice-{target_ip}")

    def _get_wrapper(self):
        return OCP1ToolWrapper(
            target_ip=self.target_ip,
            port=self.port
        )

    def discover(self, timeout=1):
        try:
            wrapper = self._get_wrapper()
            result = wrapper.run_cli_command(command="discover", options={"--timeout": timeout})
            self.logger.info("Discovery results: %s", result)
            return result
        except Exception as e:
            error_msg = f"Failed to discover devices: {e}"
            self.logger.error(error_msg)
            raise

    def get_gain_calibration(self):
        try:
            wrapper = self._get_wrapper()
            result = wrapper.run_cli_command(command="gain-calibration", subcommand="get")
            self.logger.info("Gain calibration: %s", result)
            return result
        except Exception as e:
            error_msg = f"Failed to get gain calibration: {e}"
            self.logger.error(error_msg)
            raise

    def set_gain_calibration(self, value):
        try:
            wrapper = self._get_wrapper()
            result = wrapper.run_cli_command(command="gain-calibration", subcommand="set", options={"--value": value})
            self.logger.info("Set gain calibration to %s: %s", value, result)
            return result
        except Exception as e:
            error_msg = f"Failed to set gain calibration to {value}: {e}"
            self.logger.error(error_msg)
            raise

    def get_mode(self):
        try:
            wrapper = self._get_wrapper()
            result = wrapper.run_cli_command(command="mode", subcommand="get")
            self.logger.info("Mode: %s", result)
            return result
        except Exception as e:
            error_msg = f"Failed to get mode: {e}"
            self.logger.error(error_msg)
            raise

    def set_mode(self, position):
        try:
            wrapper = self._get_wrapper()
            result = wrapper.run_cli_command(command="mode", subcommand="set", options={"--position": position})
            self.logger.info("Set mode to %s: %s", position, result)
            return result
        except Exception as e:
            error_msg = f"Failed to set mode to {position}: {e}"
            self.logger.error(error_msg)
            raise

    def get_audio_input(self):
        try:
            wrapper = self._get_wrapper()
            result = wrapper.run_cli_command(command="audio-input", subcommand="get")
            self.logger.info("Audio input: %s", result)
            return result
        except Exception as e:
            error_msg = f"Failed to get audio input: {e}"
            self.logger.error(error_msg)
            raise

    def set_audio_input(self, position):
        try:
            wrapper = self._get_wrapper()
            result = wrapper.run_cli_command(command="audio-input", subcommand="set", options={"--position": position})
            self.logger.info("Set audio input to %s: %s", position, result)
            return result
        except Exception as e:
            error_msg = f"Failed to set audio input to {position}: {e}"
            self.logger.error(error_msg)
            raise