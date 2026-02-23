#!/usr/bin/env python3
"""
Phantom UI Framework
Swappable UI architecture for custom Phantom interfaces
"""

from .base_ui import PhantomUI
from .ui_manager import UIManager
from .protocol_adapter import ProtocolAdapter

__all__ = [
    'PhantomUI',
    'UIManager',
    'ProtocolAdapter'
]

__version__ = '1.0.0'