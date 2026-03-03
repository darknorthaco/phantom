#!/usr/bin/env python3
"""Screen 1 — Welcome"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from pathlib import Path

from .base import WizardScreen


class WelcomeScreen(WizardScreen):
    TITLE = "Welcome to Phantom Setup"
    SUBTITLE = "Distributed Compute Fabric — Installation Wizard"

    def __init__(self, parent, wizard):
        super().__init__(parent, wizard)
        t = wizard.theme

        tk.Label(
            self,
            text=(
                "This wizard will guide you through the installation of the\n"
                "Phantom Distributed Compute Fabric.\n\n"
                "Phantom provides:\n"
                "  •  Constitutional AI task routing (MemoryGuard → ApprovalGate)\n"
                "  •  LAN-based distributed GPU compute across worker nodes\n"
                "  •  An intelligent LLM Task Master with mode-aware routing\n"
                "  •  Real-time monitoring via the RedBlue UI\n\n"
                "Click Next > to begin."
            ),
            bg=t.BG,
            fg=t.TEXT_FG,
            font=t.FONT,
            justify=tk.LEFT,
            anchor="nw",
            wraplength=460,
        ).pack(anchor="nw", pady=(8, 14))

        # Install directory
        dir_frame = tk.LabelFrame(
            self, text="Installation Directory", bg=t.BG, fg=t.HEADING_FG,
            font=t.FONT_BOLD, padx=8, pady=6
        )
        dir_frame.pack(fill=tk.X, pady=(0, 10))

        self._dir_var = tk.StringVar(value=str(wizard.state.install_dir))
        tk.Entry(
            dir_frame,
            textvariable=self._dir_var,
            bg=t.ENTRY_BG,
            font=t.FONT,
            width=44,
        ).pack(side=tk.LEFT, padx=(0, 6))

        tk.Button(
            dir_frame,
            text="Browse…",
            font=t.FONT,
            bg=t.BUTTON_BG,
            command=self._browse,
        ).pack(side=tk.LEFT)

        # Options
        self._log_var = tk.BooleanVar(value=wizard.state.show_detailed_logs)
        tk.Checkbutton(
            self,
            text="Advanced: show detailed log output during installation",
            variable=self._log_var,
            bg=t.BG,
            fg=t.TEXT_FG,
            font=t.FONT,
            selectcolor=t.CHECK_BG,
        ).pack(anchor="w", pady=4)

    def _browse(self) -> None:
        from tkinter import filedialog
        chosen = filedialog.askdirectory(
            title="Select Installation Directory",
            initialdir=str(self.wizard.state.install_dir),
        )
        if chosen:
            self._dir_var.set(chosen)

    def on_leave(self) -> None:
        self.wizard.state.install_dir = Path(self._dir_var.get().strip() or "~/phantom")
        self.wizard.state.show_detailed_logs = self._log_var.get()
        self.wizard.reset_api()
