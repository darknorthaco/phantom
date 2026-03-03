#!/usr/bin/env python3
"""Screen 8 — Completion"""
from __future__ import annotations

import tkinter as tk

from .base import WizardScreen


class CompletionScreen(WizardScreen):
    TITLE = "Phantom Setup Complete"
    SUBTITLE = "Your Phantom installation is ready."

    def __init__(self, parent, wizard):
        super().__init__(parent, wizard)
        t = wizard.theme

        tk.Label(
            self,
            text="✔  Phantom has been installed successfully!",
            bg=t.BG, fg=t.SUCCESS, font=("Tahoma", 12, "bold"), anchor="w"
        ).pack(anchor="w", pady=(0, 10))

        # Summary box
        summary = tk.LabelFrame(
            self, text="Installation Summary", bg=t.BG, fg=t.HEADING_FG,
            font=t.FONT_BOLD, padx=10, pady=6
        )
        summary.pack(fill=tk.X, pady=(0, 10))

        self._summary_text = tk.Text(
            summary, height=7, font=t.FONT, bg=t.BG,
            fg=t.TEXT_FG, relief=tk.FLAT, state=tk.DISABLED
        )
        self._summary_text.pack(fill=tk.X)

        # Launch option
        self._launch_var = tk.BooleanVar(value=wizard.state.launch_phantom)
        tk.Checkbutton(
            self,
            text="Launch Phantom environment now",
            variable=self._launch_var,
            bg=t.BG, fg=t.TEXT_FG, font=t.FONT,
            selectcolor=t.CHECK_BG,
            command=self._on_launch_toggle,
        ).pack(anchor="w", pady=4)

        tk.Label(
            self,
            text=(
                "Click Finish to close Setup. "
                "The installation log has been saved to "
                "installation_audit.log in your installation directory."
            ),
            bg=t.BG, fg="#555555", font=t.FONT, anchor="w", wraplength=460
        ).pack(anchor="w", pady=(4, 0))

    def on_enter(self) -> None:
        self._populate_summary()

    def _populate_summary(self) -> None:
        s = self.wizard.state
        lines = [
            f"Installation directory : {s.install_dir}",
            f"Task Master            : {s.task_master.get('ip', '—') if s.task_master else '—'}  "
            f"{s.task_master.get('gpu_name', '') if s.task_master else ''}",
            f"Workers registered     : {len(s.selected_workers)}",
            f"Default model          : {s.selected_model.get('name', '—') if s.selected_model else '—'}",
            f"Model path             : {s.model_path or '—'}",
            "",
            "Phantom is ready. Start the controller to begin processing tasks.",
        ]
        self._summary_text.config(state=tk.NORMAL)
        self._summary_text.delete("1.0", tk.END)
        self._summary_text.insert(tk.END, "\n".join(lines))
        self._summary_text.config(state=tk.DISABLED)

    def _on_launch_toggle(self) -> None:
        self.wizard.state.launch_phantom = self._launch_var.get()
