import logging
import re
from oca_tools.oca_utilities import OCP1ToolWrapper
from services.workstation_logger import WorkstationLogger

class OCADevice:
    """OCA Device Network Interface for ADAM Audio production."""

    def __init__(self, target, port=50001, timeout=5, workstation_id=None, service_host=None, service_port=65432):
        self.target = target  # Name or IP
        self.port = port
        self.timeout = timeout
        self.logger = logging.getLogger(f"OCADevice-{target}")
        self.workstation_id = workstation_id
        self.service_host = service_host
        self.service_port = service_port

    def _get_wrapper(self):
        if self._is_ip(self.target):
            return OCP1ToolWrapper(target_ip=self.target, port=self.port)
        else:
            return OCP1ToolWrapper(target_ip=None, port=None)

    def _is_ip(self, value):
        if not isinstance(value, str):
            return False
        return bool(re.match(r"^\d{1,3}(\.\d{1,3}){3}$", value))

    def _cli_options(self):
        if self._is_ip(self.target):
            return {}
        elif self.target is not None:
            return {"--target": self.target}
        else:
            return {}

    def _log_to_service(self, task, result):
        if self.workstation_id and self.service_host:
            WorkstationLogger.send_log_to_service(
                workstation_id=self.workstation_id,
                log_data={
                    "task": task,
                    "target": self.target,
                    "result": result
                },
                service_host=self.service_host,
                service_port=self.service_port
            )

    def discover(self, timeout=1):
        try:
            wrapper = self._get_wrapper()
            result = wrapper.run_cli_command(command="discover", options={"--timeout": timeout})
            self.logger.info("Discovery results: %s", result)
            self._log_to_service("discover", result)
            return result
        except Exception as e:
            error_msg = f"Failed to discover devices: {e}"
            self.logger.error(error_msg)
            raise

    def get_gain_calibration(self):
        wrapper = self._get_wrapper()
        options = self._cli_options()
        result = wrapper.run_cli_command(command="gain-calibration", subcommand="get", options=options)
        self._log_to_service("get_gain_calibration", result)
        return result

    def set_gain_calibration(self, value):
        wrapper = self._get_wrapper()
        options = self._cli_options()
        options["--value"] = value
        result = wrapper.run_cli_command(command="gain-calibration", subcommand="set", options=options)
        self._log_to_service("set_gain_calibration", result)
        return result

    def get_mode(self):
        wrapper = self._get_wrapper()
        options = self._cli_options()
        result = wrapper.run_cli_command(command="mode", subcommand="get", options=options)
        self._log_to_service("get_mode", result)
        return result

    def set_mode(self, mode):
        wrapper = self._get_wrapper()
        options = self._cli_options()
        options["--position"] = mode
        result = wrapper.run_cli_command(command="mode", subcommand="set", options=options)
        self._log_to_service("set_mode", result)
        return result

    def get_audio_input(self):
        wrapper = self._get_wrapper()
        options = self._cli_options()
        result = wrapper.run_cli_command(command="audio-input", subcommand="get", options=options)
        self._log_to_service("get_audio_input", result)
        return result

    def set_audio_input(self, position):
        """Set audio input mode.
        
        Args:
            position (str): Input mode. One of:
                - "aes3"
                - "analogue-xlr"
                - "analogue-rca"
        """
        wrapper = self._get_wrapper()
        options = self._cli_options()
        options["--position"] = position  # Changed from --mode to --position
        result = wrapper.run_cli_command(command="audio-input", subcommand="set", options=options)
        self._log_to_service("set_audio_input", result)
        return result

    def get_bass_management(self):
        wrapper = self._get_wrapper()
        options = self._cli_options()
        result = wrapper.run_cli_command(command="bass-management", subcommand="get", options=options)
        self._log_to_service("get_bass_management", result)
        return result

    def set_bass_management(self, position):
        """Set bass management mode.
        
        Args:
            position (str): Bass management mode. One of:
                - "stereo-bass"
                - "stereo"
                - "wide"
                - "lfe"
        """
        wrapper = self._get_wrapper()
        options = self._cli_options()
        options["--position"] = position
        result = wrapper.run_cli_command(command="bass-management", subcommand="set", options=options)
        self._log_to_service("set_bass_management", result)
        return result

    def get_gain(self):
        """Get current subwoofer gain level (-24 to 0 dB range)."""
        wrapper = self._get_wrapper()
        options = self._cli_options()
        result = wrapper.run_cli_command(command="gain", subcommand="get", options=options)
        self._log_to_service("get_gain", result)
        return result

    def set_gain(self, value):
        """Set subwoofer gain level.
        
        Args:
            value (float): Gain value in dB range from -24 to 0
        """
        wrapper = self._get_wrapper()
        options = self._cli_options()
        options["--value"] = value
        result = wrapper.run_cli_command(command="gain", subcommand="set", options=options)
        self._log_to_service("set_gain", result)
        return result

    def get_phase_delay(self):
        """Get current phase delay setting."""
        wrapper = self._get_wrapper()
        options = self._cli_options()
        result = wrapper.run_cli_command(command="phase-delay", subcommand="get", options=options)
        return result

    def set_phase_delay(self, position):
        """Set phase delay setting."""
        wrapper = self._get_wrapper()
        result = wrapper.run_cli_command(
            command="phase-delay",
            subcommand="set",
            options={
                "--position": position,
                "--target": self.target
            }
        )
        return result

    def get_mute(self):
        """Get current mute state."""
        wrapper = OCP1ToolWrapper(target_ip=None, port=None)
        result = wrapper.run_cli_command(
            command="mute",
            subcommand="get",
            options={"--target": self.target}
        )
        return result

    def set_mute(self, position):
        """Set mute state."""
        wrapper = OCP1ToolWrapper(target_ip=None, port=None)
        result = wrapper.run_cli_command(
            command="mute",
            subcommand="set",
            options={
                "--position": position,
                "--target": self.target
            }
        )
        return result