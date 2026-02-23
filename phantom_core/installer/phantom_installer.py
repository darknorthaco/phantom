#!/usr/bin/env python3
"""
Phantom Unified Installation Wizard
Main orchestrator for cross-platform installation
"""

import sys
import os
from pathlib import Path

# Ensure installer modules can be imported
installer_dir = Path(__file__).parent
if str(installer_dir) not in sys.path:
    sys.path.insert(0, str(installer_dir))

# Import after path setup
from modules.venv_setup import VenvSetup


# Lazy import to avoid circular dependency issues
def get_cli_wizard():
    from ui.cli_wizard import CLIWizard

    return CLIWizard


def main():
    """Main entry point for installer"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Phantom Distributed Compute Fabric - Installation Wizard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python phantom_installer.py                  # Interactive installation
  python phantom_installer.py --dry-run        # Preview installation without executing
  python phantom_installer.py --non-interactive --install-dir /opt/phantom
        """,
    )

    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Run in non-interactive mode with defaults",
    )

    parser.add_argument(
        "--install-dir",
        type=str,
        help="Installation directory (default: auto-detect based on OS)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview installation without making changes",
    )

    parser.add_argument(
        "--skip-venv", action="store_true", help="Skip virtual environment creation"
    )

    args = parser.parse_args()

    # Check if running as root on Unix systems (not recommended)
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        print("⚠️  WARNING: Running installer as root is not recommended.")
        response = input("Continue anyway? [y/N]: ").strip().lower()
        if response not in ["y", "yes"]:
            print("Installation cancelled.")
            return 1

    try:
        if args.non_interactive:
            print("Non-interactive mode not yet implemented.")
            print("Please run without --non-interactive for interactive installation.")
            return 1

        if args.dry_run:
            print("🔍 DRY RUN MODE - No changes will be made")
            print()

        # Run interactive wizard
        CLIWizard = get_cli_wizard()
        wizard = CLIWizard()

        if args.install_dir:
            wizard.install_dir = Path(args.install_dir)

        success = wizard.run()

        if success and not args.dry_run and not args.skip_venv:
            print("\n" + "=" * 70)
            print("Virtual Environment Setup")
            print("=" * 70 + "\n")

            # Offer to create virtual environment
            response = input("Create virtual environment now? [Y/n]: ").strip().lower()
            if response in ["", "y", "yes"]:
                venv_setup = VenvSetup(wizard.install_dir)

                if venv_setup.create_venv(progress_callback=print):
                    print("\n✅ Virtual environment created successfully")

                    # Offer to install requirements
                    req_file = Path(__file__).parent.parent / "requirements.txt"
                    if req_file.exists():
                        response = (
                            input("Install Python requirements now? [Y/n]: ")
                            .strip()
                            .lower()
                        )
                        if response in ["", "y", "yes"]:
                            if venv_setup.install_requirements(
                                req_file, progress_callback=print
                            ):
                                print("\n✅ Requirements installed successfully")
                            else:
                                print("\n⚠️  Requirements installation failed")
                                print("You can install them manually later with:")
                                print(
                                    f"  {venv_setup.get_venv_pip()} install -r {req_file}"
                                )

                    venv_setup.create_activation_script()
                else:
                    print("\n⚠️  Virtual environment creation failed")
                    print("You can create it manually later with:")
                    print(f"  python -m venv {venv_setup.get_venv_path()}")

        if success:
            print("\n✅ Installation completed successfully!")
            return 0
        else:
            print("\n❌ Installation failed or was cancelled.")
            return 1

    except KeyboardInterrupt:
        print("\n\n⚠️  Installation cancelled by user.")
        return 130
    except Exception as e:
        print(f"\n❌ Installation failed with error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
