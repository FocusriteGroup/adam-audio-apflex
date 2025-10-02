"""
ADAM Audio Hardware Control Package

Low-level hardware interfaces for Audio Precision production line.
Provides unified control for serial devices, scanners, and audio routing.
"""

# Import base class first
from .serial_device import SerialDevice

# Then import derived classes
from .honeywell_scanner import HoneywellScanner
from .switchbox import SwitchBox

__version__ = "1.0.0"

__all__ = [
    'SerialDevice',
    'HoneywellScanner', 
    'SwitchBox'
]