#!/usr/bin/env python3
"""Screen — Dependency Fetch

Downloads and stages pip dependencies into a local cache.
Shows progress, handles errors, and detects privileged dependencies
that require user action.
"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
from pathlib import Path

from .base import WizardScreen


class DependencyFetchScreen(WizardScreen):
    TITLE = "Fetch Dependencies"
    SUBTITLE = "Downloading Python packages for offline installation…"

    def __init__(self, parent, wizard):
        super().__init__(parent, wizard)
        t = wizard.theme

        self._status_lbl = tk.Label(
            self, text="Preparing to download dependencies…",
            bg=t.BG, fg=t.TEXT_FG, font=t.FONT, anchor="w",
            wraplength=460,
        )
        self._status_lbl.pack(anchor="w", pady=(0, 8))

        # Progress bar
        self._progress = ttk.Progressbar(
            self, orient="horizontal", mode="indeterminate"
        )
        self._progress.pack(fill=tk.X, pady=(0, 8))

        # Stage checklist
        stage_frame = tk.LabelFrame(
            self, text="Staging Steps", bg=t.BG, fg=t.HEADING_FG,
            font=t.FONT_BOLD, padx=8, pady=4,
        )
        stage_frame.pack(fill=tk.X, pady=(0, 8))

        self._step_names = [
            "Parse requirements",
            "Check local cache",
            "Download wheels",
            "Verify integrity",
            "Check privileged dependencies",
        ]
        self._step_labels: list[tk.Label] = []
        for name in self._step_names:
            row = tk.Frame(stage_frame, bg=t.BG)
            row.pack(fill=tk.X, pady=1)
            icon_lbl = tk.Label(
                row, text="○", bg=t.BG, fg="#888888", font=t.FONT, width=2
            )
            icon_lbl.pack(side=tk.LEFT)
            tk.Label(
                row, text=name, bg=t.BG, fg=t.TEXT_FG,
                font=t.FONT, anchor="w",
            ).pack(side=tk.LEFT)
            self._step_labels.append(icon_lbl)

        # Privileged deps info area (shown if needed)
        self._priv_frame = tk.LabelFrame(
            self, text="Manual Steps Required", bg=t.BG, fg=t.WARNING,
            font=t.FONT_BOLD, padx=8, pady=4,
        )
        self._priv_text = tk.Text(
            self._priv_frame, height=4, font=t.FONT_MONO,
            bg="#FFFFF0", fg=t.TEXT_FG, state=tk.DISABLED, wrap=tk.WORD,
        )
        self._priv_text.pack(fill=tk.BOTH, expand=True)

        # Log pane
        if wizard.state.show_detailed_logs:
            log_frame = tk.LabelFrame(
                self, text="Log", bg=t.BG, fg=t.HEADING_FG,
                font=t.FONT_BOLD, padx=4, pady=2,
            )
            log_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
            self._log_text = tk.Text(
                log_frame, height=3, font=t.FONT_MONO,
                bg="#F0F0F0", fg=t.TEXT_FG, state=tk.DISABLED, wrap=tk.WORD,
            )
            self._log_text.pack(fill=tk.BOTH, expand=True)
        else:
            self._log_text = None

        self._done = False
        self._success = False

    def on_enter(self) -> None:
        self.set_next_enabled(False)
        self.wizard.set_back_enabled(False)
        self._progress.start(15)
        threading.Thread(target=self._run_fetch, daemon=True).start()

    def can_go_next(self) -> bool:
        return self._done

    def can_go_back(self) -> bool:
        return self._done

    # ------------------------------------------------------------------ #

    def _run_fetch(self) -> None:
        from backend_interface.dependency_fetcher import DependencyFetcher

        install_dir = self.wizard.state.install_dir
        staging_dir = install_dir / "staging"
        fetcher = DependencyFetcher(staging_dir)

        # Locate requirements.txt
        req_file = self._find_requirements()

        # Step 1: Parse
        self._mark_step(0, "running")
        self._set_status("Parsing requirements…")
        specs = fetcher.parse_requirements(req_file) if req_file else []
        specs = fetcher.resolve_platform_constraints(specs)
        self._mark_step(0, "ok")
        self._log(f"Parsed {len(specs)} dependencies.")

        # Step 2: Check cache
        self._mark_step(1, "running")
        self._set_status("Checking local cache…")
        cached = fetcher.check_cache()
        self._mark_step(1, "ok")
        self._log(f"Cache contains {len(cached)} file(s).")

        # Step 3: Download
        self._mark_step(2, "running")
        if req_file and req_file.exists():
            self._set_status("Downloading dependencies — this may take a few minutes…")
            ok = fetcher.download_wheels(
                req_file,
                status_cb=lambda m: self._set_status(m),
            )
            if ok:
                self._mark_step(2, "ok")
            else:
                self._mark_step(2, "warn")
                self._log("Some downloads may have failed — will attempt to continue.")
        else:
            self._log("No requirements.txt found — skipping download.")
            self._mark_step(2, "ok")

        # Step 4: Verify
        self._mark_step(3, "running")
        self._set_status("Verifying downloaded packages…")
        all_ok, bad = fetcher.verify_wheels(
            status_cb=lambda m: self._log(m),
        )
        if all_ok:
            self._mark_step(3, "ok")
        else:
            self._mark_step(3, "warn")
            self._log(f"Corrupt files: {', '.join(bad)}")

        # Step 5: Privileged deps
        self._mark_step(4, "running")
        priv_deps = fetcher.detect_privileged_deps()
        self._mark_step(4, "ok")

        # Write manifest
        if req_file:
            fetcher.write_manifest(req_file)

        # Show privileged deps if any
        if priv_deps:
            self._show_privileged_deps(priv_deps)

        # Done
        self.after(0, self._on_done)

    def _on_done(self) -> None:
        self._progress.stop()
        self._progress["mode"] = "determinate"
        self._progress["value"] = 100
        self._done = True
        self._success = True
        self._set_status("✔  Dependencies staged successfully.")
        self.set_next_enabled(True)
        self.wizard.set_back_enabled(True)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _find_requirements(self) -> Path | None:
        """Locate requirements.txt in the project tree."""
        candidates = [
            Path(__file__).parent.parent.parent.parent / "phantom_core" / "requirements.txt",
            Path(__file__).parent.parent.parent.parent / "requirements.txt",
            self.wizard.state.install_dir / "phantom_core" / "requirements.txt",
        ]
        for c in candidates:
            if c.exists():
                return c
        return None

    def _mark_step(self, idx: int, state: str) -> None:
        """Update a step icon: 'running', 'ok', 'warn', 'fail'."""
        icons = {"running": "►", "ok": "✔", "warn": "⚠", "fail": "✖"}
        colors = {
            "running": "#003399",
            "ok": "#006600",
            "warn": "#996600",
            "fail": "#CC0000",
        }

        def _apply():
            if idx < len(self._step_labels):
                self._step_labels[idx].config(
                    text=icons.get(state, "?"),
                    fg=colors.get(state, "#888888"),
                )
        self.after(0, _apply)

    def _set_status(self, msg: str) -> None:
        self.after(0, lambda: self._status_lbl.config(text=msg))

    def _log(self, msg: str) -> None:
        if self._log_text is None:
            return

        def _apply():
            self._log_text.config(state=tk.NORMAL)
            self._log_text.insert(tk.END, msg + "\n")
            self._log_text.see(tk.END)
            self._log_text.config(state=tk.DISABLED)
        self.after(0, _apply)

    def _show_privileged_deps(self, deps) -> None:
        """Display privileged dependency instructions."""
        lines = []
        for dep in deps:
            lines.append(f"■ {dep.name}")
            lines.append(f"  {dep.user_action}")
            lines.append("")

        def _apply():
            self._priv_frame.pack(fill=tk.X, pady=(4, 0))
            self._priv_text.config(state=tk.NORMAL)
            self._priv_text.insert(tk.END, "\n".join(lines))
            self._priv_text.config(state=tk.DISABLED)
        self.after(0, _apply)
