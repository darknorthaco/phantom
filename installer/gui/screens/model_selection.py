#!/usr/bin/env python3
"""Screen 5 — Model Selection"""
from __future__ import annotations

import tkinter as tk
from typing import Dict

from .base import WizardScreen


class ModelSelectionScreen(WizardScreen):
    TITLE = "Choose Your Default AI Model"
    SUBTITLE = "Select the language model to download and configure."

    def __init__(self, parent, wizard):
        super().__init__(parent, wizard)
        t = wizard.theme

        # Task Master compatibility hint
        self._compat_lbl = tk.Label(
            self, text="", bg=t.BG, fg=t.HEADING_FG,
            font=t.FONT_BOLD, anchor="w", wraplength=470
        )
        self._compat_lbl.pack(anchor="w", pady=(0, 8))

        # Model cards
        models_frame = tk.Frame(self, bg=t.BG)
        models_frame.pack(fill=tk.BOTH, expand=True)

        self._model_var = tk.StringVar(value="")
        self._models = wizard.api.get_models()

        for model in self._models:
            self._add_model_card(models_frame, model)

        # Pre-select recommended model
        for m in self._models:
            if m.get("recommended"):
                self._model_var.set(m["id"])
                break

    def on_enter(self) -> None:
        self._update_compat_hint()
        self._on_model_changed()

    def _add_model_card(self, parent, model: Dict) -> None:
        t = self.wizard.theme
        frame = tk.Frame(
            parent, bg=t.BG, relief=tk.RIDGE, bd=1,
            padx=10, pady=6
        )
        frame.pack(fill=tk.X, pady=3)

        rb = tk.Radiobutton(
            frame,
            text="",
            variable=self._model_var,
            value=model["id"],
            bg=t.BG,
            selectcolor=t.CHECK_BG,
            command=self._on_model_changed,
        )
        rb.grid(row=0, column=0, rowspan=2, padx=(0, 6), sticky="ns")

        name = model["name"]
        if model.get("recommended"):
            name += "  (Recommended)"
        tk.Label(
            frame, text=name, bg=t.BG, fg=t.HEADING_FG,
            font=t.FONT_BOLD, anchor="w"
        ).grid(row=0, column=1, sticky="w")

        details = (
            f"{model['description']}   |   "
            f"VRAM: {model['vram_min_gb']}–{model['vram_rec_gb']} GB   |   "
            f"Size: ~{model['file_size_gb']:.1f} GB"
        )
        tk.Label(
            frame, text=details, bg=t.BG, fg=t.TEXT_FG,
            font=t.FONT, anchor="w"
        ).grid(row=1, column=1, sticky="w")

        frame.columnconfigure(1, weight=1)

    def _on_model_changed(self) -> None:
        sel_id = self._model_var.get()
        for m in self._models:
            if m["id"] == sel_id:
                self.wizard.state.selected_model = m
                break
        self._update_compat_hint()
        self.set_next_enabled(bool(self._model_var.get()))

    def _update_compat_hint(self) -> None:
        tm = self.wizard.state.task_master
        model = self.wizard.state.selected_model
        if tm is None:
            hint = "No Task Master selected — assign one in the previous step."
        else:
            gpu = tm.get("gpu_name", "Unknown")
            vram = tm.get("vram_display", "?")
            hint = f"Task Master GPU: {gpu} ({vram})"
            if model:
                needed = model["vram_min_gb"]
                vram_mb = tm.get("vram_total_mb", 0)
                if vram_mb == 0:
                    hint += "  —  VRAM unknown"
                elif vram_mb >= needed * 1024:
                    hint += f"  —  ✔ Sufficient VRAM for all options"
                else:
                    hint += f"  —  ⚠ Limited VRAM ({vram}) for selected model"
        self._compat_lbl.config(text=hint)
