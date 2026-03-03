#!/usr/bin/env python3
"""Screen 4 — Worker Selection & Task Master Assignment"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Dict, List

from .base import WizardScreen


class WorkerSelectionScreen(WizardScreen):
    TITLE = "Select Workers & Assign Task Master"
    SUBTITLE = "Choose which workers to include and designate a Task Master."

    def __init__(self, parent, wizard):
        super().__init__(parent, wizard)
        t = wizard.theme

        tk.Label(
            self, text="Select workers to include in the Phantom cluster:",
            bg=t.BG, fg=t.TEXT_FG, font=t.FONT_BOLD, anchor="w"
        ).pack(anchor="w", pady=(0, 4))

        # Scrollable worker checkbox list
        list_frame = tk.Frame(self, bg=t.BG, relief=tk.SUNKEN, bd=1)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        canvas = tk.Canvas(list_frame, bg=t.BG, highlightthickness=0)
        sb = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._inner = tk.Frame(canvas, bg=t.BG)
        self._inner_id = canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        self._worker_vars: List[tk.BooleanVar] = []
        self._workers: List[Dict] = []
        self._canvas = canvas

        # Task Master selector
        tm_frame = tk.LabelFrame(
            self, text="Task Master", bg=t.BG, fg=t.HEADING_FG,
            font=t.FONT_BOLD, padx=8, pady=4
        )
        tm_frame.pack(fill=tk.X, pady=(0, 6))

        self._tm_var = tk.StringVar(value="")
        self._tm_menu = ttk.Combobox(
            tm_frame, textvariable=self._tm_var, state="readonly",
            font=t.FONT, width=44
        )
        self._tm_menu.pack(anchor="w")
        self._tm_menu.bind("<<ComboboxSelected>>", self._on_tm_changed)

        self._validation_lbl = tk.Label(
            tm_frame, text="", bg=t.BG, fg=t.TEXT_FG, font=t.FONT, anchor="w"
        )
        self._validation_lbl.pack(anchor="w", pady=(2, 0))

    def on_enter(self) -> None:
        self._workers = list(self.wizard.state.discovered_workers)
        self._rebuild_checkboxes()
        self._refresh_tm_menu()
        self._refresh_next()

    def _rebuild_checkboxes(self) -> None:
        t = self.wizard.theme
        for w in self._inner.winfo_children():
            w.destroy()
        self._worker_vars = []

        if not self._workers:
            tk.Label(
                self._inner,
                text="No workers discovered. You can add workers manually later.",
                bg=t.BG, fg="#666666", font=t.FONT, wraplength=400
            ).pack(anchor="w", padx=8, pady=8)
            return

        for i, worker in enumerate(self._workers):
            var = tk.BooleanVar(value=True)
            self._worker_vars.append(var)
            label = (
                f"{worker.get('ip', '?')}  —  "
                f"{worker.get('gpu_name', 'Unknown')}  —  "
                f"{worker.get('vram_display', 'Unknown VRAM')}"
            )
            tk.Checkbutton(
                self._inner, text=label, variable=var,
                bg=t.BG, fg=t.TEXT_FG, font=t.FONT, anchor="w",
                selectcolor=t.CHECK_BG,
                command=self._on_selection_changed
            ).grid(row=i, column=0, sticky="w", padx=6, pady=1)

    def _refresh_tm_menu(self) -> None:
        selected = self._get_selected_workers()
        options = [
            f"{w.get('ip', '?')} — {w.get('gpu_name', 'Unknown')} "
            f"({w.get('vram_display', '?')})"
            for w in selected
        ]
        self._tm_menu["values"] = options
        if options:
            self._tm_menu.current(0)
            self.wizard.state.task_master = selected[0]
        else:
            self._tm_var.set("")
            self.wizard.state.task_master = None
        self._update_validation()

    def _on_selection_changed(self) -> None:
        self._refresh_tm_menu()
        self._refresh_next()

    def _on_tm_changed(self, _=None) -> None:
        idx = self._tm_menu.current()
        selected = self._get_selected_workers()
        if 0 <= idx < len(selected):
            self.wizard.state.task_master = selected[idx]
        self._update_validation()
        self._refresh_next()

    def _get_selected_workers(self) -> list:
        return [
            w for w, var in zip(self._workers, self._worker_vars)
            if var.get()
        ]

    def _update_validation(self) -> None:
        tm = self.wizard.state.task_master
        model = self.wizard.state.selected_model
        if tm is None:
            self._validation_lbl.config(text="", fg=self.wizard.theme.TEXT_FG)
            return
        vram_needed = model.get("vram_min_gb", 6) if model else 6
        msg = self.wizard.api.worker_adapter.get_task_master_message(tm, vram_needed)
        color = self.wizard.theme.SUCCESS if msg.startswith("✓") else self.wizard.theme.WARNING
        self._validation_lbl.config(text=msg, fg=color)

    def _refresh_next(self) -> None:
        selected = self._get_selected_workers()
        ok = len(selected) >= 1 and self.wizard.state.task_master is not None
        self.set_next_enabled(ok)

    def on_leave(self) -> None:
        self.wizard.state.selected_workers = self._get_selected_workers()
