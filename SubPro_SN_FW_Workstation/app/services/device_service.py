"""
Device service — thin wrapper around OCADevice for the Sub-Pro workstation.

All public methods return (success: bool, value: str | None, error: str | None).
Device communication is via OCADevice imported from the parent repo (oca/).
"""
import logging
from pathlib import Path
import subprocess
import sys
import time
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

Result = Tuple[bool, Optional[str], Optional[str]]


class DeviceService:
    """Wraps OCADevice; device_name is the mDNS hostname used in every CLI call."""

    def __init__(self, device_name: str, port: int = 50001, timeout: int = 10):
        self.device_name = device_name
        self.port = port
        self.timeout = timeout
        self._device = None

    # ── Internal ───────────────────────────────────────────────────────────────

    def _dev(self):
        """Lazy-initialise OCADevice so the import only happens when needed."""
        if self._device is None:
            from oca.oca_device import OCADevice  # type: ignore  (parent repo)
            self._device = OCADevice(
                target=self.device_name,
                port=self.port,
                timeout=self.timeout,
            )
        return self._device

    def _call(self, fn_name: str, *args, **kwargs) -> Result:
        try:
            result = getattr(self._dev(), fn_name)(*args, **kwargs)
            return True, result, None
        except Exception as exc:
            logger.error('%s failed: %s', fn_name, exc)
            return False, None, str(exc)

    @staticmethod
    def _extract_discovered_name(result) -> Optional[str]:
        if isinstance(result, str):
            value = result.strip()
            return value or None
        if isinstance(result, dict):
            devices = result.get('devices')
            if isinstance(devices, list) and devices:
                first = devices[0]
                if isinstance(first, dict):
                    for key in ('name', 'device_name', 'hostname'):
                        value = first.get(key)
                        if value:
                            return str(value).strip()
            for key in ('name', 'device_name', 'hostname'):
                value = result.get(key)
                if value:
                    return str(value).strip()
        if isinstance(result, list) and result:
            first = result[0]
            if isinstance(first, dict):
                for key in ('name', 'device_name', 'hostname'):
                    value = first.get(key)
                    if value:
                        return str(value).strip()
            if isinstance(first, str):
                value = first.strip()
                return value or None
        return None

    def _discover_via_workstation_cli(self, timeout: int) -> Optional[str]:
        script_path = Path(__file__).resolve().parents[3] / 'adam_workstation.py'
        if not script_path.exists():
            return None

        command = [
            sys.executable,
            str(script_path),
            'discover',
            '--timeout',
            str(int(timeout)),
        ]

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=max(15, int(timeout) + 5),
            )
        except Exception as exc:
            logger.warning('discover via adam_workstation failed to execute: %s', exc)
            return None

        if completed.returncode != 0:
            logger.warning(
                'discover via adam_workstation non-zero exit=%s stderr=%r',
                completed.returncode,
                (completed.stderr or '').strip(),
            )
            return None

        lines = [line.strip() for line in (completed.stdout or '').splitlines() if line.strip()]
        if not lines:
            return None
        candidate = lines[-1]
        if candidate.lower().startswith('error:'):
            return None
        return candidate

    # ── Public API ─────────────────────────────────────────────────────────────

    def update_device_name(self, name: str):
        """Change the target device name and reset the cached device."""
        name = name.strip()
        if not name:
            return
        self.device_name = name
        self._device = None

    def discover(self, timeout: int = 2) -> Result:
        cli_name = self._discover_via_workstation_cli(timeout=timeout)
        if cli_name:
            self.update_device_name(cli_name)
            logger.info('discover via adam_workstation: %s', cli_name)
            return True, cli_name, None

        try:
            result = self._dev().discover(timeout=timeout)
            logger.info('discover: %s', result)
            device_name = self._extract_discovered_name(result)
            if not device_name:
                return False, None, 'No device discovered.'
            self.update_device_name(device_name)
            return True, device_name, None
        except Exception as exc:
            return False, None, str(exc)

    def discover_with_retries(self, attempts: int = 3, timeout: int = 2,
                              retry_delay_s: float = 0.5) -> Result:
        attempts = max(1, int(attempts))
        timeout = max(1, int(timeout))
        last_err = 'No device discovered.'

        for try_idx in range(attempts):
            ok, device_name, err = self.discover(timeout=timeout + try_idx)
            if ok and device_name:
                return True, device_name, None
            last_err = err or last_err
            if try_idx < attempts - 1:
                time.sleep(max(0.0, retry_delay_s))

        return False, None, last_err

    def get_firmware_version(self) -> Result:
        ok, raw, err = self._call('get_firmware_version')
        if not ok:
            return False, None, err
        version = raw.get('version') if isinstance(raw, dict) else str(raw)
        return True, version, None

    def flash_firmware(self, fw_path: Path) -> Result:
        try:
            result = self._dev().update_firmware(
                firmware_image_path=str(fw_path), timeout=120)
            return True, str(result), None
        except Exception as exc:
            return False, None, str(exc)

    def get_serial_number(self) -> Result:
        ok, raw, err = self._call('get_serial_number')
        if not ok:
            return False, None, err
        sn = raw.get('value', '') if isinstance(raw, dict) else str(raw)
        return True, sn, None

    def set_serial_number(self, sn: str) -> Result:
        ok, raw, err = self._call('set_serial_number', sn)
        if not ok:
            return False, None, err
        return True, str(raw), None

    def unlock_factory_settings(self, signature: str) -> Result:
        ok, raw, err = self._call('unlock_factory_settings', signature)
        if not ok:
            return False, None, err
        return True, str(raw), None
