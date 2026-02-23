#!/usr/bin/env python3
"""
Phantom Unified Installation Wizard
Main orchestrator for cross-platform installation
"""

import sys
import os
import logging
from datetime import datetime
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


def show_banner():
    """Display installer banner"""
    print("═" * 70)
    print("  🚀 Phantom Distributed Compute Fabric - Installer")
    print(f"  Version: 1.0.0")
    print("═" * 70)
    print()


def setup_logging(log_file: str = None) -> logging.Logger:
    """Configure timestamped logging, optionally writing to a file"""
    logger = logging.getLogger("phantom_installer")
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)-7s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # File handler (optional)
    if log_file:
        fh = logging.FileHandler(log_file)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
        logger.info(f"Logging to file: {log_file}")

    return logger


def verify_installation(install_dir: Path) -> bool:
    """Verify installation completed successfully"""
    print("\n🔍 Verifying installation...")

    checks = [
        (install_dir.exists(), f"Installation directory exists: {install_dir}"),
        ((install_dir / "config").exists(), "Configuration directory created"),
        ((install_dir / "logs").exists(), "Logs directory created"),
        ((install_dir / "data").exists(), "Data directory created"),
        (
            (install_dir / ".phantom_install_manifest.json").exists(),
            "Installation manifest saved",
        ),
    ]

    all_passed = True
    for passed, description in checks:
        status = "✅" if passed else "❌"
        print(f"  {status} {description}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n✅ Installation verification passed")
    else:
        print("\n⚠️  Some verification checks failed")

    return all_passed


def main():
    """Main entry point for installer"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Phantom Distributed Compute Fabric - Installation Wizard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Installation Types:
  all         - Install all components (default)
  controller  - Install controller components only
  worker      - Install worker components only

Examples:
  python phantom_installer.py                          # Interactive installation
  python phantom_installer.py --silent                 # Silent install with defaults
  python phantom_installer.py --silent --type=worker   # Silent worker-only install
  python phantom_installer.py --dry-run                # Preview without executing
  python phantom_installer.py --force --install-dir /opt/phantom
        """,
    )

    parser.add_argument(
        "--silent",
        action="store_true",
        help="Run in silent mode with no prompts (uses defaults)",
    )

    parser.add_argument(
        "--type",
        dest="install_type",
        type=str,
        choices=["all", "controller", "worker"],
        default="all",
        help="Installation type: all, controller, or worker (default: all)",
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
        "--force",
        action="store_true",
        help="Skip confirmation prompts",
    )

    parser.add_argument(
        "--skip-venv", action="store_true", help="Skip virtual environment creation"
    )

    parser.add_argument(
        "--log-file",
        type=str,
        help="Path to log file for timestamped output",
    )

    # Keep --non-interactive as a hidden alias for --silent (backward compatibility)
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help=argparse.SUPPRESS,
    )

    args = parser.parse_args()

    # --non-interactive is a backward-compatible alias for --silent
    if args.non_interactive:
        args.silent = True

    show_banner()

    # Set up timestamped logging
    logger = setup_logging(args.log_file)

    logger.info(
        f"Phantom Installer started"
        + (f" [silent, type={args.install_type}]" if args.silent else " [interactive]")
    )

    # Check if running as root on Unix systems (not recommended)
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        logger.warning("Running installer as root is not recommended.")
        if not args.force and not args.silent:
            response = input("Continue anyway? [y/N]: ").strip().lower()
            if response not in ["y", "yes"]:
                print("Installation cancelled.")
                return 1

    try:
        if args.dry_run:
            print("🔍 DRY RUN MODE - No changes will be made")
            print()

        # Run installation wizard
        CLIWizard = get_cli_wizard()
        wizard = CLIWizard(
            silent=args.silent,
            install_type=args.install_type,
            force=args.force,
        )

        if args.install_dir:
            wizard.install_dir = Path(args.install_dir)

        success = wizard.run()

        if success and not args.dry_run and not args.skip_venv:
            venv_setup = VenvSetup(wizard.install_dir)

            if args.silent:
                # Silent mode: auto-create venv without prompting
                logger.info("Creating virtual environment...")
                if venv_setup.create_venv():
                    logger.info("Virtual environment created successfully")
                    venv_setup.create_activation_script()
                else:
                    logger.warning("Virtual environment creation failed")
            else:
                print("\n" + "=" * 70)
                print("Virtual Environment Setup")
                print("=" * 70 + "\n")

                # Offer to create virtual environment
                response = (
                    input("Create virtual environment now? [Y/n]: ").strip().lower()
                )
                if response in ["", "y", "yes"]:
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

        # Post-install verification
        if success and not args.dry_run and wizard.install_dir:
            verify_installation(wizard.install_dir)

        if success:
            logger.info("Installation completed successfully")
            print("\n✅ Installation completed successfully!")
            return 0
        else:
            logger.error("Installation failed or was cancelled")
            print("\n❌ Installation failed or was cancelled.")
            return 1

    except KeyboardInterrupt:
        print("\n\n⚠️  Installation cancelled by user.")
        return 130
    except Exception as e:
        logger.error(f"Installation failed with error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
