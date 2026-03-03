#!/usr/bin/env python3
"""
WizardScreen base class
All installer screens inherit from this class.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..wizard import PhantomWizard


class WizardScreen(tk.Frame):
    """Base class for all wizard screens.

    Subclasses set:
        TITLE    – short heading shown in the content area
        SUBTITLE – one-line subtitle shown below the heading
    """

    TITLE: str = ""
    SUBTITLE: str = ""

    def __init__(self, parent: tk.Widget, wizard: "PhantomWizard"):
        super().__init__(parent, bg=wizard.theme.BG)
        self.wizard = wizard

    # ------------------------------------------------------------------ #
    # Lifecycle hooks — override in subclasses
    # ------------------------------------------------------------------ #

    def on_enter(self) -> None:
        """Called when the wizard navigates TO this screen."""

    def on_leave(self) -> None:
        """Called when the wizard navigates AWAY from this screen."""

    def can_go_next(self) -> bool:
        """Return True if the Next button should be enabled."""
        return True

    def can_go_back(self) -> bool:
        """Return True if the Back button should be enabled."""
        return True

    # ------------------------------------------------------------------ #
    # Convenience helpers
    # ------------------------------------------------------------------ #

    def set_next_enabled(self, enabled: bool) -> None:
        """Enable or disable the wizard's Next button."""
        self.wizard.set_next_enabled(enabled)

    def refresh_buttons(self) -> None:
        """Ask the wizard to re-evaluate button states."""
        self.wizard.refresh_buttons()
