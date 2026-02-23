"""
Phantom Installer UI Components
"""


# Import only when needed to avoid circular imports
def get_cli_wizard():
    from .cli_wizard import CLIWizard

    return CLIWizard


def get_progress_display():
    from .progress_display import ProgressDisplay

    return ProgressDisplay


def get_prompts():
    from .prompts import Prompts

    return Prompts


__all__ = ["get_cli_wizard", "get_progress_display", "get_prompts"]
