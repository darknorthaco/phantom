#!/usr/bin/env python3
"""Screen 3 — Worker Discovery"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk

from .base import WizardScreen


class WorkerDiscoveryScreen(WizardScreen):
    TITLE = "Discover Phantom Workers"
    SUBTITLE = "Scanning your local network for available worker nodes…"

    def __init__(self, parent, wizard):
        super().__init__(parent, wizard)
        t = wizard.theme

        # Discovery mode selector
        mode_frame = tk.LabelFrame(
            self, text="Discovery Mode", bg=t.BG, fg=t.HEADING_FG,
            font=t.FONT_BOLD, padx=8, pady=4
        )
        mode_frame.pack(fill=tk.X, pady=(0, 8))

        self._mode_var = tk.StringVar(value=wizard.state.discovery_mode)
        modes = [
            ("Comprehensive (port scan — recommended)", "comprehensive"),
            ("Manual (ping sweep)", "manual"),
            ("Skip (configure workers later)", "skip"),
        ]
        for label, value in modes:
            tk.Radiobutton(
                mode_frame, text=label, variable=self._mode_var, value=value,
                bg=t.BG, fg=t.TEXT_FG, font=t.FONT,
                selectcolor=t.CHECK_BG,
                command=self._on_mode_change,
            ).pack(anchor="w")

        # Worker table
        self._status_lbl = tk.Label(
            self, text="Press 'Scan' to discover workers.",
            bg=t.BG, fg=t.TEXT_FG, font=t.FONT, anchor="w"
        )
        self._status_lbl.pack(anchor="w", pady=(4, 4))

        cols = ("IP Address", "Hostname", "GPU", "VRAM", "Status")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=6)
        for col, w in zip(cols, (110, 120, 120, 80, 80)):
            self._tree.heading(col, text=col)
            self._tree.column(col, width=w, anchor="w")
        self._tree.pack(fill=tk.BOTH, expand=True)

        btn_row = tk.Frame(self, bg=t.BG)
        btn_row.pack(fill=tk.X, pady=(6, 0))
        self._scan_btn = tk.Button(
            btn_row, text="Scan", font=t.FONT, bg=t.BUTTON_BG,
            command=self._start_scan
        )
        self._scan_btn.pack(side=tk.LEFT)

    def on_enter(self) -> None:
        self.set_next_enabled(False)
        # Auto-scan unless skip
        if self._mode_var.get() != "skip":
            self._start_scan()
        else:
            self.set_next_enabled(True)

    def _on_mode_change(self) -> None:
        mode = self._mode_var.get()
        self.wizard.state.discovery_mode = mode
        if mode == "skip":
            self._status_lbl.config(text="Worker discovery skipped.")
            self.set_next_enabled(True)
        else:
            self.set_next_enabled(
                len(self.wizard.state.discovered_workers) > 0
            )

    def _start_scan(self) -> None:
        mode = self._mode_var.get()
        self.wizard.state.discovery_mode = mode
        if mode == "skip":
            self.set_next_enabled(True)
            return

        self._scan_btn.config(state=tk.DISABLED)
        self.set_next_enabled(False)
        self._status_lbl.config(text="Scanning…")
        for row in self._tree.get_children():
            self._tree.delete(row)

        def _scan():
            workers = self.wizard.api.discover_workers(
                mode=mode,
                progress_cb=lambda msg: self.after(
                    0, lambda m=msg: self._status_lbl.config(text=m)
                ),
            )
            self.after(0, lambda: self._apply_results(workers))

        threading.Thread(target=_scan, daemon=True).start()

    def _apply_results(self, workers: list) -> None:
        self.wizard.state.discovered_workers = workers
        for row in self._tree.get_children():
            self._tree.delete(row)

        for w in workers:
            self._tree.insert(
                "", "end",
                values=(
                    w.get("ip", ""),
                    w.get("hostname", ""),
                    w.get("gpu_name", "Unknown"),
                    w.get("vram_display", "Unknown"),
                    w.get("health", "Unknown"),
                ),
            )

        count = len(workers)
        self._status_lbl.config(
            text=f"Scan complete — {count} worker(s) found."
        )
        self._scan_btn.config(state=tk.NORMAL)
        self.set_next_enabled(count > 0 or self._mode_var.get() == "skip")
