#!/usr/bin/env python3
"""Screen 6 — Model Download"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk

from .base import WizardScreen


class ModelDownloadScreen(WizardScreen):
    TITLE = "Downloading AI Model"
    SUBTITLE = "Fetching and verifying the selected language model…"

    def __init__(self, parent, wizard):
        super().__init__(parent, wizard)
        t = wizard.theme

        self._model_lbl = tk.Label(
            self, text="", bg=t.BG, fg=t.HEADING_FG,
            font=t.FONT_BOLD, anchor="w"
        )
        self._model_lbl.pack(anchor="w", pady=(0, 6))

        self._status_lbl = tk.Label(
            self, text="Preparing…", bg=t.BG, fg=t.TEXT_FG,
            font=t.FONT, anchor="w"
        )
        self._status_lbl.pack(anchor="w")

        self._progress = ttk.Progressbar(
            self, orient="horizontal", length=420, mode="determinate"
        )
        self._progress.pack(fill=tk.X, pady=8)

        self._bytes_lbl = tk.Label(
            self, text="", bg=t.BG, fg="#666666", font=t.FONT, anchor="w"
        )
        self._bytes_lbl.pack(anchor="w")

        self._log = tk.Text(
            self, height=6, font=t.FONT_MONO, bg="#F0F0F0",
            fg=t.TEXT_FG, state=tk.DISABLED, wrap=tk.WORD
        )
        self._log.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        self._done = False

    def on_enter(self) -> None:
        self.set_next_enabled(False)
        self.wizard.set_back_enabled(False)
        model = self.wizard.state.selected_model
        if model:
            self._model_lbl.config(text=f"Downloading: {model['name']}")
        threading.Thread(target=self._do_download, daemon=True).start()

    def can_go_back(self) -> bool:
        return False

    def can_go_next(self) -> bool:
        return self._done

    # ------------------------------------------------------------------ #

    def _do_download(self) -> None:
        model = self.wizard.state.selected_model
        if model is None:
            self.after(0, lambda: self._finish(None, "No model selected."))
            return
        try:
            path = self.wizard.api.download_model(
                model,
                status_cb=lambda s: self.after(0, lambda m=s: self._set_status(m)),
                progress_cb=lambda d, t: self.after(
                    0, lambda dd=d, tt=t: self._set_progress(dd, tt)
                ),
            )
            self.after(0, lambda: self._finish(path, None))
        except Exception as exc:
            self.after(0, lambda e=exc: self._finish(None, str(e)))

    def _set_status(self, msg: str) -> None:
        self._status_lbl.config(text=msg)
        self._append_log(msg)

    def _set_progress(self, downloaded: int, total: int) -> None:
        if total > 0:
            pct = int(downloaded / total * 100)
            self._progress["value"] = pct
            dl_mb = downloaded / (1024 * 1024)
            tot_mb = total / (1024 * 1024)
            self._bytes_lbl.config(text=f"{dl_mb:.1f} MB / {tot_mb:.1f} MB  ({pct}%)")
        else:
            dl_mb = downloaded / (1024 * 1024)
            self._bytes_lbl.config(text=f"{dl_mb:.1f} MB downloaded")

    def _append_log(self, msg: str) -> None:
        self._log.config(state=tk.NORMAL)
        self._log.insert(tk.END, msg + "\n")
        self._log.see(tk.END)
        self._log.config(state=tk.DISABLED)

    def _finish(self, path, error) -> None:
        t = self.wizard.theme
        if error:
            self._status_lbl.config(
                text=f"Download failed: {error}", fg=t.FAIL
            )
            self._append_log(f"ERROR: {error}")
            self.wizard.set_back_enabled(True)
        else:
            self.wizard.state.model_path = path
            # Write llm_config.json immediately after download
            try:
                self.wizard.api.write_llm_config(
                    path, self.wizard.state.selected_model
                )
            except Exception as exc:
                self._append_log(f"WARNING: Could not write llm_config.json: {exc}")
            self._progress["value"] = 100
            self._status_lbl.config(
                text="✔  Model downloaded and verified.", fg=t.SUCCESS
            )
            self._append_log("Model ready.")
            self._done = True
            self.set_next_enabled(True)
