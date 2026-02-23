#!/usr/bin/env python3
"""
User Prompts and Messages
Centralized prompts for user interaction
"""


class Prompts:
    """User prompts and messages"""

    @staticmethod
    def welcome():
        """Display welcome message"""
        print("\n" + "=" * 70)
        print("    🚀 PHANTOM DISTRIBUTED COMPUTE FABRIC")
        print("    Unified Installation Wizard")
        print("=" * 70)
        print("\nWelcome to the Phantom ecosystem installer!")
        print("This wizard will guide you through installing:")
        print("  • Phantom Core (distributed compute fabric)")
        print("  • LLM Task Master (AI-powered routing)")
        print("  • Worker Nodes (Linux/Windows)")
        print("  • Socket Infrastructure (real-time communication)")
        print("  • Security Framework (multi-level)")
        print("  • RedBlue UI (monitoring & control)")
        print()

    @staticmethod
    def section(title: str):
        """Display section header"""
        print("\n" + "-" * 70)
        print(f"  {title}")
        print("-" * 70 + "\n")

    @staticmethod
    def confirm(message: str, default: bool = True) -> bool:
        """Ask for confirmation"""
        suffix = " [Y/n]: " if default else " [y/N]: "
        response = input(message + suffix).strip().lower()

        if not response:
            return default

        return response in ["y", "yes"]

    @staticmethod
    def select_option(message: str, options: list, default: int = 0) -> int:
        """Select from a list of options"""
        print(f"\n{message}")
        for i, option in enumerate(options, 1):
            print(f"  [{i}] {option}")

        while True:
            try:
                choice = input(
                    f"\nSelect option [1-{len(options)}] (default: {default+1}): "
                ).strip()
                if not choice:
                    return default

                choice = int(choice) - 1
                if 0 <= choice < len(options):
                    return choice
                else:
                    print(
                        f"Invalid choice. Please enter a number between 1 and {len(options)}"
                    )
            except ValueError:
                print("Invalid input. Please enter a number.")

    @staticmethod
    def input_text(message: str, default: str = "") -> str:
        """Get text input from user"""
        if default:
            response = input(f"{message} [{default}]: ").strip()
            return response if response else default
        else:
            response = input(f"{message}: ").strip()
            return response

    @staticmethod
    def input_number(
        message: str, default: int = None, min_val: int = None, max_val: int = None
    ) -> int:
        """Get numeric input from user"""
        while True:
            try:
                default_str = f" [{default}]" if default is not None else ""
                response = input(f"{message}{default_str}: ").strip()

                if not response and default is not None:
                    return default

                value = int(response)

                if min_val is not None and value < min_val:
                    print(f"Value must be at least {min_val}")
                    continue

                if max_val is not None and value > max_val:
                    print(f"Value must be at most {max_val}")
                    continue

                return value
            except ValueError:
                print("Invalid input. Please enter a number.")

    @staticmethod
    def select_multiple(message: str, options: list) -> list:
        """Select multiple options from a list"""
        print(f"\n{message}")
        for i, option in enumerate(options, 1):
            print(f"  [{i}] {option}")

        print(
            "\nEnter space-separated numbers (e.g., '1 3 5') or 'all' for all options"
        )

        while True:
            response = input("Selection: ").strip().lower()

            if response == "all":
                return list(range(len(options)))

            try:
                selections = [int(x) - 1 for x in response.split()]

                if all(0 <= sel < len(options) for sel in selections):
                    return selections
                else:
                    print(
                        f"Invalid selection. Please enter numbers between 1 and {len(options)}"
                    )
            except ValueError:
                print("Invalid input. Please enter space-separated numbers or 'all'")

    @staticmethod
    def success(message: str):
        """Display success message"""
        print(f"✅ {message}")

    @staticmethod
    def error(message: str):
        """Display error message"""
        print(f"❌ {message}")

    @staticmethod
    def warning(message: str):
        """Display warning message"""
        print(f"⚠️  {message}")

    @staticmethod
    def info(message: str):
        """Display info message"""
        print(f"ℹ️  {message}")

    @staticmethod
    def completion_message(install_dir: str):
        """Display installation completion message"""
        print("\n" + "=" * 70)
        print("    ✅ INSTALLATION COMPLETE!")
        print("=" * 70)
        print(f"\nPhantom has been installed to: {install_dir}")
        print("\n📋 Next Steps:")
        print("  1. Review configuration files in config/")
        print("  2. Activate virtual environment:")
        print(f"     source {install_dir}/activate_phantom.sh")
        print("  3. Start Phantom:")
        print(f"     cd {install_dir}")
        print("     python run_integrated_phantom.py")
        print("  4. Check health:")
        print("     curl http://localhost:8080/health")
        print("\n📖 Documentation:")
        print("  - README.md - Getting started guide")
        print("  - DEPLOYMENT_GUIDE.md - Deployment instructions")
        print("  - TOPOLOGY_SETUP.md - Network topology setup")
        print("\n" + "=" * 70 + "\n")
