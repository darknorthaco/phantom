#!/usr/bin/env python3
"""Screen 7 — Installation Progress"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk

from .base import WizardScreen


class InstallationScreen(WizardScreen):
    TITLE = "Installing Phantom"
    SUBTITLE = "Running the 7-stage Phantom installation…"

    def __init__(self, parent, wizard):
        super().__init__(parent, wizard)
        t = wizard.theme

        # Stage checklist
        self._stage_vars: list[tk.StringVar] = []
        self._stage_labels: list[tk.Label] = []

        stage_frame = tk.LabelFrame(
            self, text="Installation Steps", bg=t.BG, fg=t.HEADING_FG,
            font=t.FONT_BOLD, padx=8, pady=4
        )
        stage_frame.pack(fill=tk.X, pady=(0, 8))

        from backend_interface.installer_driver import INSTALL_STAGES
        for stage_name in INSTALL_STAGES:
            row = tk.Frame(stage_frame, bg=t.BG)
            row.pack(fill=tk.X, pady=1)
            icon_lbl = tk.Label(
                row, text="○", bg=t.BG, fg="#888888", font=t.FONT, width=2
            )
            icon_lbl.pack(side=tk.LEFT)
            tk.Label(
                row, text=stage_name, bg=t.BG, fg=t.TEXT_FG,
                font=t.FONT, anchor="w"
            ).pack(side=tk.LEFT)
            self._stage_labels.append(icon_lbl)

        # Overall progress
        self._progress = ttk.Progressbar(
            self, orient="horizontal", mode="determinate"
        )
        self._progress.pack(fill=tk.X, pady=(0, 6))

        self._status_lbl = tk.Label(
            self, text="", bg=t.BG, fg=t.TEXT_FG, font=t.FONT, anchor="w"
        )
        self._status_lbl.pack(anchor="w")

        # Log pane (shown only in detailed-log mode)
        self._log_frame = tk.Frame(self, bg=t.BG)
        self._log_text = tk.Text(
            self._log_frame, height=5, font=t.FONT_MONO,
            bg="#F0F0F0", fg=t.TEXT_FG, state=tk.DISABLED, wrap=tk.WORD
        )
        self._log_text.pack(fill=tk.BOTH, expand=True)

        self._done = False

    def on_enter(self) -> None:
        self.set_next_enabled(False)
        self.wizard.set_back_enabled(False)

        if self.wizard.state.show_detailed_logs:
            self._log_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        # Build worker configs for the installer driver
        workers = self.wizard.state.selected_workers or []
        worker_configs = [
            {
                "worker_id": w.get("name") or w.get("hostname") or f"worker-{i + 1}",
                "controller_host": "localhost",
                "controller_port": 8080,
                "worker_host": w.get("ip", ""),
                "worker_port": w.get("port", 8090),
                "gpu_name": w.get("gpu_name", "Unknown"),
            }
            for i, w in enumerate(workers)
        ]

        # Write worker registry before starting installation
        if self.wizard.state.task_master and workers:
            try:
                self.wizard.api.write_worker_registry(
                    workers, self.wizard.state.task_master
                )
            except Exception as exc:
                self._append_log(f"WARNING: worker registry: {exc}")

        self.wizard.api.prepare_installer(worker_configs=worker_configs)
        threading.Thread(target=self._run_install, daemon=True).start()

    def can_go_back(self) -> bool:
        return False

    def can_go_next(self) -> bool:
        return self._done

    # ------------------------------------------------------------------ #

    def _run_install(self) -> None:
        from backend_interface.installer_driver import INSTALL_STAGES
        for i in range(len(INSTALL_STAGES)):
            ok = self.wizard.api.run_installation_stage(
                i,
                progress_cb=lambda p, m, idx=i: self.after(
                    0, lambda pp=p, mm=m, ii=idx: self._on_progress(ii, pp, mm)
                ),
                log_cb=lambda m: self.after(0, lambda mm=m: self._append_log(mm)),
            )
            self.after(0, lambda ok=ok, idx=i: self._mark_stage(idx, ok))
            if not ok:
                self.after(0, lambda: self._on_done(False))
                return
        self.after(0, lambda: self._on_done(True))

    def _on_progress(self, stage_idx: int, pct: int, msg: str) -> None:
        self._progress["value"] = pct
        self._status_lbl.config(text=msg)

    def _mark_stage(self, idx: int, ok: bool) -> None:
        if idx < len(self._stage_labels):
            t = self.wizard.theme
            if ok:
                self._stage_labels[idx].config(text="✔", fg=t.SUCCESS)
            else:
                self._stage_labels[idx].config(text="✖", fg=t.FAIL)

    def _append_log(self, msg: str) -> None:
        self._log_text.config(state=tk.NORMAL)
        self._log_text.insert(tk.END, msg + "\n")
        self._log_text.see(tk.END)
        self._log_text.config(state=tk.DISABLED)

    def _on_done(self, success: bool) -> None:
        t = self.wizard.theme
        if success:
            self._progress["value"] = 100
            self._status_lbl.config(
                text="✔  Installation complete!", fg=t.SUCCESS
            )
            self._done = True
            self.set_next_enabled(True)
        else:
            self._status_lbl.config(
                text="✖  Installation failed — see log for details.", fg=t.FAIL
            )
            self.wizard.set_back_enabled(True)
