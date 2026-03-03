#!/usr/bin/env python3
"""Screen 2 — System Scan"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk

from .base import WizardScreen

_STATUS_ICON = {"ok": "✔", "warning": "⚠", "fail": "✖", "unknown": "…"}
_STATUS_COLOR = {
    "ok": "#006600",
    "warning": "#996600",
    "fail": "#CC0000",
    "unknown": "#666666",
}


class SystemScanScreen(WizardScreen):
    TITLE = "System Check"
    SUBTITLE = "Checking your system for Phantom compatibility…"

    def __init__(self, parent, wizard):
        super().__init__(parent, wizard)
        t = wizard.theme

        self._status_lbl = tk.Label(
            self, text="Click 'Scan' to check system requirements.",
            bg=t.BG, fg=t.TEXT_FG, font=t.FONT, anchor="w"
        )
        self._status_lbl.pack(anchor="w", pady=(0, 8))

        # Results table
        cols = ("Check", "Status", "Detail")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=7)
        self._tree.heading("Check", text="Check")
        self._tree.heading("Status", text="Status")
        self._tree.heading("Detail", text="Detail")
        self._tree.column("Check", width=140, anchor="w")
        self._tree.column("Status", width=80, anchor="center")
        self._tree.column("Detail", width=260, anchor="w")
        self._tree.pack(fill=tk.BOTH, expand=True)

        btn_row = tk.Frame(self, bg=t.BG)
        btn_row.pack(fill=tk.X, pady=(8, 0))
        tk.Button(
            btn_row, text="Re-scan", font=t.FONT, bg=t.BUTTON_BG,
            command=self._start_scan
        ).pack(side=tk.LEFT)

        self._scan_done = False

    def on_enter(self) -> None:
        self.set_next_enabled(False)
        self._start_scan()

    def _start_scan(self) -> None:
        self._scan_done = False
        self.set_next_enabled(False)
        self._status_lbl.config(text="Scanning system…")
        for row in self._tree.get_children():
            self._tree.delete(row)
        threading.Thread(target=self._run_scan, daemon=True).start()

    def _run_scan(self) -> None:
        result = self.wizard.api.run_system_scan(ports=[8080, 8081])
        self.after(0, lambda: self._apply_results(result))

    def _apply_results(self, result: dict) -> None:
        for row in self._tree.get_children():
            self._tree.delete(row)

        for key, info in result["checks"].items():
            icon = _STATUS_ICON.get(info["status"], "?")
            self._tree.insert(
                "", "end",
                values=(info["name"], f"{icon} {info['status'].upper()}", info["detail"])
            )

        if result["ok"]:
            self._status_lbl.config(
                text="✔  All critical checks passed — you may proceed.",
                fg=_STATUS_COLOR["ok"]
            )
        else:
            self._status_lbl.config(
                text="✖  Critical checks failed — resolve issues before continuing.",
                fg=_STATUS_COLOR["fail"]
            )

        self._scan_done = True
        self.set_next_enabled(result["ok"])
