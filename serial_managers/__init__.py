"""
ADAM Audio Serial Managers Package

High-level serial device management with retry logic and service integration.
Specialized for USB-Serial and RS232 communication devices.
"""

from .scanner_manager import ScannerManager
from .switchbox_manager import SwitchBoxManager

__all__ = ['ScannerManager', 'SwitchBoxManager']