#!/usr/bin/env python3
"""
Progress Display
Terminal progress and status display
"""

import sys
import time
from typing import Optional


class ProgressDisplay:
    """Display installation progress"""

    def __init__(self):
        self.current_step = 0
        self.total_steps = 0
        self.step_name = ""

    def start(self, total_steps: int):
        """Start progress tracking"""
        self.total_steps = total_steps
        self.current_step = 0

    def step(self, name: str):
        """Move to next step"""
        self.current_step += 1
        self.step_name = name
        self._display_step()

    def _display_step(self):
        """Display current step"""
        percentage = (
            (self.current_step / self.total_steps) * 100 if self.total_steps > 0 else 0
        )
        print(
            f"\n[{self.current_step}/{self.total_steps}] {self.step_name} ({percentage:.0f}%)"
        )

    def sub_step(self, message: str):
        """Display sub-step message"""
        print(f"  ⋯ {message}")

    def complete(self):
        """Mark progress as complete"""
        print(f"\n✅ All {self.total_steps} steps completed!\n")

    @staticmethod
    def spinner(message: str, duration: float = 2.0):
        """Display spinner animation"""
        spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        start_time = time.time()
        i = 0

        while time.time() - start_time < duration:
            sys.stdout.write(f"\r{spinner_chars[i % len(spinner_chars)]} {message}")
            sys.stdout.flush()
            time.sleep(0.1)
            i += 1

        sys.stdout.write(f"\r✓ {message}\n")
        sys.stdout.flush()

    @staticmethod
    def progress_bar(current: int, total: int, width: int = 50, label: str = ""):
        """Display progress bar"""
        if total == 0:
            percentage = 100
        else:
            percentage = (current / total) * 100

        filled = int(width * current / total) if total > 0 else width
        bar = "█" * filled + "░" * (width - filled)

        sys.stdout.write(f"\r{label} |{bar}| {percentage:.1f}% ({current}/{total})")
        sys.stdout.flush()

        if current >= total:
            sys.stdout.write("\n")

    @staticmethod
    def list_items(items: list, checked: Optional[list] = None):
        """Display list of items with checkboxes"""
        if checked is None:
            checked = [False] * len(items)

        for i, item in enumerate(items):
            checkbox = "✓" if checked[i] else " "
            print(f"  [{checkbox}] {item}")
