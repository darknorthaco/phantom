#!/usr/bin/env python3
"""
Phantom Unified Uninstallation Wizard
Main orchestrator for cross-platform uninstallation
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Ensure installer modules can be imported
installer_dir = Path(__file__).parent
if str(installer_dir) not in sys.path:
    sys.path.insert(0, str(installer_dir))

# Import after path setup
from modules.manifest_manager import ManifestManager
from modules.uninstall_manager import UninstallManager


def show_banner():
    """Display uninstaller banner"""
    print("═" * 70)
    print("  🗑️  Phantom Distributed Compute Fabric - Uninstaller")
    print("  Version: 1.0.0")
    print("═" * 70)
    print()


def find_installation() -> Path:
    """Try to find Phantom installation directory"""
    # Common installation paths
    search_paths = [
        Path.home() / "phantom",
        Path("/opt/phantom"),
        Path("/usr/local/phantom"),
        Path.home() / ".phantom",
        Path.cwd(),
    ]

    for path in search_paths:
        manifest_path = path / ".phantom_install_manifest.json"
        if manifest_path.exists():
            return path

    return None


def confirm_uninstall(install_dir: Path, mode: str) -> bool:
    """Ask user to confirm uninstallation"""
    print("\n⚠️  WARNING: You are about to uninstall Phantom")
    print(f"Installation directory: {install_dir}")
    print(f"Uninstall mode: {mode}")
    print()

    if mode == "full":
        print("This will:")
        print("  • Stop all Phantom services and processes")
        print("  • Remove all Phantom files and directories")
        print("  • Remove service definitions")
        print("  • Remove virtual environment")
        print("  • Delete ALL configuration files")
        print("  • Delete ALL log files")
    else:  # safe mode
        print("This will:")
        print("  • Stop all Phantom services and processes")
        print("  • Remove PID and socket files")
        print("  • Remove log files")
        print("  • PRESERVE configuration files")
        print("  • PRESERVE installation directory")

    print()
    response = input("Are you sure you want to continue? [y/N]: ").strip().lower()
    return response in ["y", "yes"]


def safe_uninstall(install_dir: Path, dry_run: bool = False) -> bool:
    """
    Safe uninstall mode:
    - Stops processes
    - Removes runtime files
    - Preserves code and configs
    """
    print("\n🔧 Running SAFE uninstall...")
    print("This will stop services but preserve your installation and configs")
    print()

    manifest = ManifestManager(install_dir)

    if not manifest.has_manifest():
        print("⚠️  No installation manifest found")
        print("Attempting cleanup based on directory structure...")

    uninstaller = UninstallManager(install_dir, manifest, progress_callback=print)
    uninstaller.set_dry_run(dry_run)

    success = True

    # Stop services
    success &= uninstaller.stop_services()

    # Stop processes
    success &= uninstaller.stop_processes_by_pid()

    # Remove PID files
    success &= uninstaller.remove_pid_files()

    # Remove log files
    success &= uninstaller.remove_log_files(preserve_logs=False)

    if not dry_run:
        print("\n" + "=" * 70)
        print("✅ Safe uninstall completed")
        print("=" * 70)
        print()
        print("Your installation and configuration files have been preserved.")
        print("You can restart Phantom at any time.")

    return success


def full_uninstall(
    install_dir: Path, backup_configs: bool = True, dry_run: bool = False
) -> bool:
    """
    Full uninstall mode:
    - Everything from safe mode
    - Plus removes all files, directories, services
    """
    print("\n🔥 Running FULL uninstall...")
    print("This will completely remove Phantom from your system")
    print()

    manifest = ManifestManager(install_dir)

    if not manifest.has_manifest():
        print("⚠️  No installation manifest found")
        print("Will attempt to remove based on directory structure...")

    uninstaller = UninstallManager(install_dir, manifest, progress_callback=print)
    uninstaller.set_dry_run(dry_run)

    # Setup backup if requested
    if backup_configs:
        backup_dir = (
            install_dir.parent
            / f"phantom_backup_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
        )
        uninstaller.set_backup_dir(backup_dir)

    success = True

    # Stop services
    success &= uninstaller.stop_services()

    # Stop processes
    success &= uninstaller.stop_processes_by_pid()

    # Backup configs
    if backup_configs:
        success &= uninstaller.backup_configs()

    # Remove PID files
    success &= uninstaller.remove_pid_files()

    # Remove log files
    success &= uninstaller.remove_log_files(preserve_logs=False)

    # Remove service definitions
    success &= uninstaller.remove_services()

    # Remove virtual environment
    success &= uninstaller.remove_venv()

    # Remove files (tracked by manifest)
    success &= uninstaller.remove_files(preserve_data=False)

    # Remove directories
    success &= uninstaller.remove_directories(preserve_configs=False)

    # Remove manifest last
    success &= uninstaller.remove_manifest()

    if not dry_run:
        print("\n" + "=" * 70)
        print("✅ Full uninstall completed")
        print("=" * 70)
        print()
        if backup_configs and uninstaller.backup_dir:
            print(f"Configuration backup saved to: {uninstaller.backup_dir}")
        print("Phantom has been completely removed from your system.")

    return success


def main():
    """Main entry point for uninstaller"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Phantom Distributed Compute Fabric - Uninstallation Wizard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Uninstall Modes:
  safe    - Stop services, remove runtime files, preserve configs (default)
  full    - Complete removal including all files and configurations

Examples:
  python phantom_uninstaller.py                     # Safe uninstall (interactive)
  python phantom_uninstaller.py --mode full         # Full uninstall
  python phantom_uninstaller.py --dry-run           # Preview without changes
  python phantom_uninstaller.py --install-dir /opt/phantom --mode full
        """,
    )

    parser.add_argument(
        "--install-dir",
        type=str,
        help="Installation directory (auto-detected if not specified)",
    )

    parser.add_argument(
        "--mode",
        type=str,
        choices=["safe", "full"],
        default="safe",
        help="Uninstall mode (default: safe)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview uninstallation without making changes",
    )

    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip configuration backup (only applies to full mode)",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompts",
    )

    args = parser.parse_args()

    show_banner()

    # Determine installation directory
    if args.install_dir:
        install_dir = Path(args.install_dir)
    else:
        print("🔍 Searching for Phantom installation...")
        install_dir = find_installation()

        if not install_dir:
            print("❌ Could not find Phantom installation")
            print()
            print("Please specify the installation directory with --install-dir")
            return 1

        print(f"✓ Found installation at: {install_dir}")

    # Verify directory exists
    if not install_dir.exists():
        print(f"❌ Installation directory does not exist: {install_dir}")
        return 1

    if args.dry_run:
        print("\n🔍 DRY RUN MODE - No changes will be made")
        print()

    # Confirm uninstall
    if not args.force and not args.dry_run:
        if not confirm_uninstall(install_dir, args.mode):
            print("\n❌ Uninstallation cancelled by user")
            return 0

    # Check if running as root on Unix systems
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        print("\n⚠️  WARNING: Running uninstaller as root")
        if not args.force:
            response = input("Continue anyway? [y/N]: ").strip().lower()
            if response not in ["y", "yes"]:
                print("Uninstallation cancelled.")
                return 1

    try:
        # Perform uninstall
        if args.mode == "safe":
            success = safe_uninstall(install_dir, dry_run=args.dry_run)
        else:  # full mode
            success = full_uninstall(
                install_dir,
                backup_configs=not args.no_backup,
                dry_run=args.dry_run,
            )

        if success:
            return 0
        else:
            print("\n⚠️  Some uninstall operations failed")
            print("You may need to manually clean up remaining files")
            return 1

    except KeyboardInterrupt:
        print("\n\n⚠️  Uninstallation cancelled by user")
        return 130
    except Exception as e:
        print(f"\n❌ Uninstallation failed with error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
