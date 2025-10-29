"""
ADAM Audio OCA Package

OCA (Open Control Architecture) device communication for ADAM Audio.
Handles network-based communication with OCA devices using OCP1 protocol.
"""

from .oca_device import OCADevice

__all__ = ["OCADevice"]