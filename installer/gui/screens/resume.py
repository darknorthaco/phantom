#!/usr/bin/env python3
"""Screen — Resume After Reboot

Post-reboot landing page.  Verifies that the pre-reboot action
(e.g. WSL kernel install) completed, then continues the installer.
"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk

from .base import WizardScreen


class ResumeScreen(WizardScreen):
    TITLE = "Resuming Installation"
    SUBTITLE = "Verifying post-reboot state…"

    def __init__(self, parent, wizard):
        super().__init__(parent, wizard)
        t = wizard.theme

        tk.Label(
            self,
            text="Welcome back!  The installer is checking that\nthe pre-reboot steps completed successfully.",
            bg=t.BG, fg=t.TEXT_FG, font=t.FONT,
            justify=tk.LEFT, anchor="w",
            wraplength=460,
        ).pack(anchor="w", pady=(8, 12))

        # Check results
        self._check_frame = tk.LabelFrame(
            self, text="Verification Checks", bg=t.BG, fg=t.HEADING_FG,
            font=t.FONT_BOLD, padx=8, pady=4,
        )
        self._check_frame.pack(fill=tk.X, pady=(0, 8))

        self._check_labels: list[tuple[tk.Label, tk.Label]] = []
        checks = [
            "Installer state file",
            "Staged dependencies",
            "WSL status",
        ]
        for name in checks:
            row = tk.Frame(self._check_frame, bg=t.BG)
            row.pack(fill=tk.X, pady=1)
            icon_lbl = tk.Label(
                row, text="…", bg=t.BG, fg="#888888", font=t.FONT, width=2,
            )
            icon_lbl.pack(side=tk.LEFT)
            name_lbl = tk.Label(
                row, text=name, bg=t.BG, fg=t.TEXT_FG, font=t.FONT, anchor="w",
            )
            name_lbl.pack(side=tk.LEFT)
            detail_lbl = tk.Label(
                row, text="", bg=t.BG, fg="#666666", font=t.FONT, anchor="e",
            )
            detail_lbl.pack(side=tk.RIGHT)
            self._check_labels.append((icon_lbl, detail_lbl))

        # Status
        self._status_lbl = tk.Label(
            self, text="", bg=t.BG, fg=t.TEXT_FG, font=t.FONT, anchor="w",
            wraplength=460,
        )
        self._status_lbl.pack(anchor="w", pady=(8, 4))

        # Buttons
        btn_row = tk.Frame(self, bg=t.BG)
        btn_row.pack(fill=tk.X, pady=(4, 0))
        tk.Button(
            btn_row, text="Re-check", font=t.FONT, bg=t.BUTTON_BG,
            command=self._start_verify,
        ).pack(side=tk.LEFT, padx=(0, 8))

        self._verified = False

    def on_enter(self) -> None:
        self.set_next_enabled(False)
        self.wizard.set_back_enabled(False)
        self._start_verify()

    def can_go_next(self) -> bool:
        return self._verified

    def can_go_back(self) -> bool:
        return False

    # ------------------------------------------------------------------ #

    def _start_verify(self) -> None:
        self._verified = False
        self.set_next_enabled(False)

        # Reset icons
        for icon_lbl, detail_lbl in self._check_labels:
            icon_lbl.config(text="…", fg="#888888")
            detail_lbl.config(text="")
        self._status_lbl.config(text="Running verification…", fg=self.wizard.theme.TEXT_FG)

        threading.Thread(target=self._run_verify, daemon=True).start()

    def _run_verify(self) -> None:
        all_ok = True

        # Check 1: State file
        self._set_check(0, "running")
        try:
            from backend_interface.reboot_manager import RebootManager
            rm = RebootManager(self.wizard.state.install_dir)
            has_state = rm.load_state() is not None
            if has_state:
                self._set_check(0, "ok", "State file found")
            else:
                self._set_check(0, "warn", "No state file (fresh install)")
        except Exception as exc:
            self._set_check(0, "fail", str(exc)[:60])
            all_ok = False

        # Check 2: Staged dependencies
        self._set_check(1, "running")
        staging_dir = self.wizard.state.install_dir / "staging"
        if staging_dir.exists() and any(staging_dir.iterdir()):
            count = sum(1 for f in staging_dir.iterdir() if f.suffix in (".whl", ".tar.gz"))
            self._set_check(1, "ok", f"{count} packages cached")
        else:
            self._set_check(1, "warn", "No cached packages")

        # Check 3: WSL status
        self._set_check(2, "running")
        try:
            from backend_interface.wsl_orchestrator import WSLOrchestrator, WSLStatus
            wsl = WSLOrchestrator()
            status = wsl.detect_wsl_status()
            if status == WSLStatus.READY:
                self._set_check(2, "ok", "WSL2 ready")
            elif status == WSLStatus.NOT_AVAILABLE:
                self._set_check(2, "warn", "WSL not available (optional)")
            else:
                self._set_check(2, "warn", f"{status.value}")
        except Exception as exc:
            self._set_check(2, "warn", f"Check skipped: {str(exc)[:40]}")

        # Clean up resume artefact
        try:
            from backend_interface.reboot_manager import RebootManager
            rm = RebootManager(self.wizard.state.install_dir)
            rm.complete_resume()
        except Exception:
            pass

        # Done
        def _finish():
            t = self.wizard.theme
            if all_ok:
                self._status_lbl.config(
                    text="✔  Verification complete — ready to continue.",
                    fg=t.SUCCESS,
                )
            else:
                self._status_lbl.config(
                    text="⚠  Some checks had issues — you may still continue.",
                    fg=t.WARNING,
                )
            self._verified = True
            self.set_next_enabled(True)

        self.after(0, _finish)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _set_check(self, idx: int, state: str, detail: str = "") -> None:
        icons = {"running": "►", "ok": "✔", "warn": "⚠", "fail": "✖"}
        colors = {
            "running": "#003399",
            "ok": "#006600",
            "warn": "#996600",
            "fail": "#CC0000",
        }

        def _apply():
            if idx < len(self._check_labels):
                icon_lbl, detail_lbl = self._check_labels[idx]
                icon_lbl.config(
                    text=icons.get(state, "?"),
                    fg=colors.get(state, "#888888"),
                )
                detail_lbl.config(text=detail)
        self.after(0, _apply)
