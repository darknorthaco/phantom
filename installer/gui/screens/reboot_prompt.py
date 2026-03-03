#!/usr/bin/env python3
"""Screen — Reboot Prompt

Displayed when a dependency (e.g. WSL kernel) requires a system reboot.
This screen NEVER triggers a reboot — it only advises the user.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .base import WizardScreen


class RebootPromptScreen(WizardScreen):
    TITLE = "Reboot Required"
    SUBTITLE = "A system restart is needed to continue installation."

    def __init__(self, parent, wizard):
        super().__init__(parent, wizard)
        t = wizard.theme

        # Icon + heading
        tk.Label(
            self,
            text="⚠",
            bg=t.BG, fg=t.WARNING,
            font=("Tahoma", 24),
        ).pack(anchor="w", pady=(4, 0))

        tk.Label(
            self,
            text="Your system needs to restart before\nPhantom installation can continue.",
            bg=t.BG, fg=t.TEXT_FG, font=t.FONT_HEADING,
            justify=tk.LEFT, anchor="w",
        ).pack(anchor="w", pady=(4, 12))

        # Reason
        self._reason_lbl = tk.Label(
            self,
            text="",
            bg=t.BG, fg=t.TEXT_FG, font=t.FONT,
            justify=tk.LEFT, anchor="w",
            wraplength=460,
        )
        self._reason_lbl.pack(anchor="w", pady=(0, 12))

        # What happens next
        info_frame = tk.LabelFrame(
            self, text="What happens next?", bg=t.BG, fg=t.HEADING_FG,
            font=t.FONT_BOLD, padx=8, pady=6,
        )
        info_frame.pack(fill=tk.X, pady=(0, 8))

        steps = [
            "1. Close this wizard (your progress is saved automatically).",
            "2. Restart your computer.",
            "3. After logging back in, the installer will resume automatically.",
            "   (A shortcut has been placed in your Startup folder.)",
            "",
            "If auto-resume does not start, re-launch the installer with:",
            "    PhantomInstaller.exe --resume",
        ]
        for step_text in steps:
            tk.Label(
                info_frame, text=step_text, bg=t.BG, fg=t.TEXT_FG,
                font=t.FONT, anchor="w",
            ).pack(anchor="w", pady=0)

        # State file location
        self._state_path_lbl = tk.Label(
            self, text="", bg=t.BG, fg="#666666",
            font=t.FONT_MONO, anchor="w",
        )
        self._state_path_lbl.pack(anchor="w", pady=(8, 4))

        # Skip reboot option
        self._skip_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            self,
            text="Skip reboot and continue anyway (may cause issues)",
            variable=self._skip_var,
            bg=t.BG, fg=t.WARNING,
            font=t.FONT, selectcolor=t.CHECK_BG,
            command=self._on_skip_toggled,
        ).pack(anchor="w", pady=(8, 0))

        self._prepared = False

    def on_enter(self) -> None:
        self.set_next_enabled(False)
        self.wizard.set_back_enabled(True)

        # Prepare the reboot-resume state
        if not self._prepared:
            self._prepare_reboot()

    def can_go_next(self) -> bool:
        # Only allow Next if user checked "skip reboot"
        return self._skip_var.get()

    def can_go_back(self) -> bool:
        return True

    # ------------------------------------------------------------------ #

    def _prepare_reboot(self) -> None:
        """Invoke the RebootManager to save state and create resume shortcut."""
        from backend_interface.reboot_manager import RebootManager

        rm = RebootManager(self.wizard.state.install_dir)

        # Copy wizard state into installer state
        rm.state.install_dir = str(self.wizard.state.install_dir)
        rm.state.model_selection = (
            {"id": self.wizard.state.selected_model.get("id", "")}
            if self.wizard.state.selected_model
            else None
        )

        # Determine reboot reason
        reason = "A system dependency requires a restart."
        try:
            from backend_interface.wsl_orchestrator import WSLOrchestrator
            wsl = WSLOrchestrator()
            status = wsl.detect_wsl_status()
            if wsl.is_reboot_required(status):
                reason = f"WSL setup requires a restart.\n\n{wsl.get_user_instructions(status)}"
        except Exception:
            pass

        self._reason_lbl.config(text=f"Reason: {reason}")

        # Create resume shortcut (non-privileged)
        shortcut_path = rm.prepare_reboot_resume(reason=reason)

        if shortcut_path:
            self._state_path_lbl.config(
                text=f"Resume shortcut: {shortcut_path}"
            )
        else:
            self._state_path_lbl.config(
                text=(
                    "Could not create auto-resume shortcut.\n"
                    "Re-launch manually with: PhantomInstaller.exe --resume"
                )
            )

        self._prepared = True

    def _on_skip_toggled(self) -> None:
        self.refresh_buttons()
