import logging
import re
from oca_tools.oca_utilities import OCP1ToolWrapper

class OCADevice:
    """
    OCA Device Network Interface for ADAM Audio production.
    Unterstützt nur die OCA-Befehle: discover, gain calibration, mode, audio input.
    """

    def __init__(self, target, port=50001, timeout=5):
        self.target = target  # Name oder IP
        self.port = port
        self.timeout = timeout
        self.logger = logging.getLogger(f"OCADevice-{target}")

    def _get_wrapper(self):
        if self._is_ip(self.target):
            return OCP1ToolWrapper(target_ip=self.target, port=self.port)
        else:
            return OCP1ToolWrapper(target_ip=None, port=None)  # Kein Port bei Name!

    def _is_ip(self, value):
        if not isinstance(value, str):
            return False
        return bool(re.match(r"^\d{1,3}(\.\d{1,3}){3}$", value))

    def _cli_options(self):
        # Bei IP KEINE Optionen zurückgeben, alles läuft über den Wrapper-Konstruktor!
        if self._is_ip(self.target):
            return {}
        elif self.target is not None:
            return {"--target": self.target}
        else:
            return {}

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
        wrapper = self._get_wrapper()
        options = self._cli_options()
        return wrapper.run_cli_command(command="gain-calibration", subcommand="get", options=options)

    def set_gain_calibration(self, value):
        wrapper = self._get_wrapper()
        options = self._cli_options()
        options["--value"] = value
        return wrapper.run_cli_command(command="gain-calibration", subcommand="set", options=options)

    def get_mode(self):
        wrapper = self._get_wrapper()
        options = self._cli_options()
        return wrapper.run_cli_command(command="mode", subcommand="get", options=options)

    def set_mode(self, position):
        wrapper = self._get_wrapper()
        options = self._cli_options()
        options["--position"] = position
        return wrapper.run_cli_command(command="mode", subcommand="set", options=options)

    def get_audio_input(self):
        wrapper = self._get_wrapper()
        options = self._cli_options()
        return wrapper.run_cli_command(command="audio-input", subcommand="get", options=options)

    def set_audio_input(self, position):
        wrapper = self._get_wrapper()
        options = self._cli_options()
        options["--position"] = position
        return wrapper.run_cli_command(command="audio-input", subcommand="set", options=options)