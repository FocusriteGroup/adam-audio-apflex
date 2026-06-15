"""
Device service — thin wrapper around OCADevice for the Sub-Pro workstation.

All public methods return (success: bool, value: str | None, error: str | None).
Device communication is via OCADevice imported from the parent repo (oca/).
"""
import logging
from pathlib import Path
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

    # ── Public API ─────────────────────────────────────────────────────────────

    def update_device_name(self, name: str):
        """Change the target device name and reset the cached device."""
        self.device_name = name.strip()
        self._device = None

    def discover(self, timeout: int = 2) -> Result:
        try:
            result = self._dev().discover(timeout=timeout)
            logger.info('discover: %s', result)
            return True, str(result), None
        except Exception as exc:
            return False, None, str(exc)

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
