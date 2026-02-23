#!/usr/bin/env python3
"""
Demo script to showcase installer features
Non-interactive demonstration
"""

import sys
from pathlib import Path

# Add installer to path
installer_path = Path(__file__).parent
sys.path.insert(0, str(installer_path))

from modules.system_check import SystemChecker
from modules.component_manager import ComponentManager
from modules.worker_discovery import WorkerDiscovery
from modules.socket_manager import SocketManager
from modules.ui_integration import UIIntegration
from ui.progress_display import ProgressDisplay
from ui.prompts import Prompts


def demo_system_check():
    """Demonstrate system requirements check"""
    print("\n" + "=" * 70)
    print("DEMO: System Requirements Check")
    print("=" * 70)

    checker = SystemChecker()
    checker.run_all_checks()
    checker.print_report()


def demo_component_selection():
    """Demonstrate component selection"""
    print("\n" + "=" * 70)
    print("DEMO: Component Selection")
    print("=" * 70)

    manager = ComponentManager("/tmp/phantom-demo", use_git=False)

    print("\nAvailable Components:")
    for comp in manager.list_components():
        required = "✓ Required" if comp["required"] else "  Optional"
        print(f"  [{required}] {comp['name']}")
        print(f"      {comp['description']}")

    print("\nSelecting optional components...")
    manager.select_component("llm_taskmaster")
    manager.select_component("socket_infrastructure")
    manager.select_component("security_framework")

    print(f"\n✅ Selected {len(manager.selected_components)} components:")
    for comp_id in manager.selected_components:
        comp = manager.get_component_info(comp_id)
        print(f"  • {comp['name']}")


def demo_socket_config():
    """Demonstrate socket configuration"""
    print("\n" + "=" * 70)
    print("DEMO: Socket Infrastructure Configuration")
    print("=" * 70)

    socket_mgr = SocketManager()

    print("\nEnabling socket infrastructure...")
    socket_mgr.enable()
    socket_mgr.configure(host="0.0.0.0", port=8081)

    config = socket_mgr.get_config()
    print("\n✅ Socket Configuration:")
    print(f"  • Enabled: {config['enabled']}")
    print(f"  • Host: {config['host']}")
    print(f"  • Port: {config['port']}")
    print(f"  • SSL: {config['ssl_enabled']}")


def demo_ui_integration():
    """Demonstrate UI integration"""
    print("\n" + "=" * 70)
    print("DEMO: RedBlue UI Integration")
    print("=" * 70)

    ui = UIIntegration()

    print("\nConfiguring RedBlue UI...")
    ui.enable()
    ui.configure(host="0.0.0.0", port=3000)
    ui.enable_socket_integration()

    config = ui.get_config()
    print("\n✅ UI Configuration:")
    print(f"  • Enabled: {config['enabled']}")
    print(f"  • Host: {config['host']}")
    print(f"  • Port: {config['port']}")
    print(f"  • Socket Integration: {config['socket_integration']}")
    print(f"  • Controller URL: {config['controller_url']}")


def demo_progress_display():
    """Demonstrate progress display"""
    print("\n" + "=" * 70)
    print("DEMO: Installation Progress")
    print("=" * 70)

    progress = ProgressDisplay()

    progress.start(5)

    import time

    progress.step("Checking system requirements")
    time.sleep(0.5)

    progress.step("Creating directory structure")
    progress.sub_step("Creating config directory")
    progress.sub_step("Creating logs directory")
    time.sleep(0.5)

    progress.step("Installing components")
    progress.sub_step("Installing Phantom Core")
    progress.sub_step("Installing Socket Infrastructure")
    time.sleep(0.5)

    progress.step("Generating configurations")
    time.sleep(0.5)

    progress.step("Finalizing installation")
    time.sleep(0.5)

    progress.complete()


def main():
    """Run all demos"""
    prompts = Prompts()
    prompts.welcome()

    print("\n" + "=" * 70)
    print("INSTALLER FEATURE DEMONSTRATION")
    print("This is a non-interactive demo of the installer's capabilities")
    print("=" * 70)

    try:
        demo_system_check()
        demo_component_selection()
        demo_socket_config()
        demo_ui_integration()
        demo_progress_display()

        print("\n" + "=" * 70)
        print("✅ DEMO COMPLETE")
        print("=" * 70)
        print("\nTo run the full interactive installer:")
        print("  Linux/Mac: ./phantom_installer.sh")
        print("  Windows:   .\\phantom_installer.ps1")
        print("\nFor more information, see installer/README.md")
        print("=" * 70 + "\n")

    except KeyboardInterrupt:
        print("\n\nDemo interrupted.")


if __name__ == "__main__":
    main()
