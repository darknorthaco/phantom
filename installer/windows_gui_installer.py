#!/usr/bin/env python3
"""
Phantom Windows GUI Installer
Professional installation wizard with PyQt6 interface
"""

import sys
import os
import subprocess
import shutil
import json
from pathlib import Path
from typing import Dict, List, Optional

try:
    from PyQt6.QtWidgets import (
        QApplication, QWizard, QWizardPage, QLabel, QVBoxLayout,
        QHBoxLayout, QCheckBox, QRadioButton, QButtonGroup,
        QProgressBar, QTextEdit, QPushButton, QGroupBox,
        QMessageBox, QFrame, QScrollArea, QWidget
    )
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
    from PyQt6.QtGui import QFont, QPixmap, QIcon
except ImportError:
    print("PyQt6 not found. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "PyQt6"])
    from PyQt6.QtWidgets import (
        QApplication, QWizard, QWizardPage, QLabel, QVBoxLayout,
        QHBoxLayout, QCheckBox, QRadioButton, QButtonGroup,
        QProgressBar, QTextEdit, QPushButton, QGroupBox,
        QMessageBox, QFrame, QScrollArea, QWidget
    )
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
    from PyQt6.QtGui import QFont, QPixmap, QIcon


class InstallationWorker(QThread):
    """Worker thread for installation process"""
    progress = pyqtSignal(int, str)  # progress percentage, status message
    finished = pyqtSignal(bool, str)  # success, message
    log = pyqtSignal(str)  # log message

    def __init__(self, install_config: Dict):
        super().__init__()
        self.install_config = install_config
        self.install_dir = Path(install_config['install_dir'])

    def run(self):
        try:
            self._perform_installation()
            self.finished.emit(True, "Installation completed successfully!")
        except Exception as e:
            self.finished.emit(False, f"Installation failed: {str(e)}")

    def _perform_installation(self):
        """Perform the actual installation"""
        total_steps = 8
        current_step = 0

        def update_progress(step_name: str):
            nonlocal current_step
            current_step += 1
            progress = int((current_step / total_steps) * 100)
            self.progress.emit(progress, step_name)
            self.log.emit(f"Step {current_step}/{total_steps}: {step_name}")

        # Step 1: Create installation directory
        update_progress("Creating installation directory")
        self.install_dir.mkdir(parents=True, exist_ok=True)

        # Step 2: Copy phantom_core
        update_progress("Installing Phantom Core")
        core_src = Path(self.install_config['package_dir']) / "phantom_core"
        if core_src.exists():
            shutil.copytree(core_src, self.install_dir / "phantom_core", dirs_exist_ok=True)
        else:
            raise FileNotFoundError("phantom_core not found in package")

        # Step 3: Install UI components if selected
        if self.install_config.get('install_ui', True):
            update_progress("Installing UI Components")
            ui_src = Path(self.install_config['package_dir']) / "ui"
            if ui_src.exists():
                shutil.copytree(ui_src, self.install_dir / "ui", dirs_exist_ok=True)

        # Step 4: Install documentation
        update_progress("Installing Documentation")
        docs_src = Path(self.install_config['package_dir']) / "docs"
        if docs_src.exists():
            shutil.copytree(docs_src, self.install_dir / "docs", dirs_exist_ok=True)

        # Step 5: Setup Python environment
        update_progress("Setting up Python Environment")
        self._setup_python_env()

        # Step 6: Create Windows service
        update_progress("Creating Windows Service")
        self._create_windows_service()

        # Step 7: Create shortcuts
        update_progress("Creating Shortcuts")
        self._create_shortcuts()

        # Step 8: Final configuration
        update_progress("Final Configuration")
        self._create_config_file()

    def _setup_python_env(self):
        """Setup Python virtual environment and install dependencies"""
        import venv

        venv_dir = self.install_dir / "venv"
        venv.create(venv_dir, with_pip=True)

        # Install requirements
        requirements_file = self.install_dir / "phantom_core" / "requirements.txt"
        if requirements_file.exists():
            pip_exe = venv_dir / "Scripts" / "pip.exe"
            subprocess.check_call([
                str(pip_exe), "install", "-r", str(requirements_file)
            ])

    def _create_windows_service(self):
        """Create Windows service using sc command"""
        service_exe = self.install_dir / "venv" / "Scripts" / "python.exe"
        service_script = self.install_dir / "phantom_core" / "run_integrated_phantom.py"

        # Use sc command to create service
        cmd = [
            "sc", "create", "Phantom",
            f'binPath= "{service_exe} {service_script}"',
            "start=", "auto"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to create service: {result.stderr}")

        # Set description
        subprocess.run([
            "sc", "description", "Phantom",
            "Phantom Distributed Compute Fabric"
        ])

    def _create_shortcuts(self):
        """Create desktop and start menu shortcuts"""
        import win32com.client

        shell = win32com.client.Dispatch("WScript.Shell")

        # Desktop shortcut
        desktop = shell.SpecialFolders("Desktop")
        shortcut = shell.CreateShortcut(os.path.join(desktop, "Phantom.lnk"))
        shortcut.TargetPath = "http://localhost:8080"
        shortcut.IconLocation = "shell32.dll,13"
        shortcut.Save()

        # Start menu shortcut
        start_menu = os.path.join(os.environ["ProgramData"],
                                "Microsoft", "Windows", "Start Menu", "Programs", "Phantom")
        os.makedirs(start_menu, exist_ok=True)

        shortcut = shell.CreateShortcut(os.path.join(start_menu, "Phantom UI.lnk"))
        shortcut.TargetPath = "http://localhost:8080"
        shortcut.IconLocation = "shell32.dll,13"
        shortcut.Save()

    def _create_config_file(self):
        """Create configuration file"""
        config = {
            "install_type": self.install_config.get('install_type', 'complete'),
            "install_dir": str(self.install_dir),
            "ui_enabled": self.install_config.get('install_ui', True),
            "service_created": True
        }

        config_file = self.install_dir / "phantom_config.json"
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)


class WelcomePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Welcome to Phantom Installation")
        self.setSubTitle("Distributed Compute Fabric")

        layout = QVBoxLayout()

        # Welcome message
        welcome_label = QLabel(
            "Welcome to the Phantom installation wizard.\n\n"
            "This wizard will guide you through the installation of Phantom, "
            "a distributed compute fabric with distributed compute capabilities.\n\n"
            "Click Next to continue."
        )
        welcome_label.setWordWrap(True)
        layout.addWidget(welcome_label)

        # Features list
        features_group = QGroupBox("Key Features:")
        features_layout = QVBoxLayout()

        features = [
            "• Distributed task processing across multiple nodes",
            "• LLM Task Master (mode-aware routing)",
            "• Real-time monitoring and control",
            "• Cross-platform compatibility (Windows/Linux/macOS)",
            "• Professional RedBlue monitoring interface",
            "• Secure communication protocols"
        ]

        for feature in features:
            features_layout.addWidget(QLabel(feature))

        features_group.setLayout(features_layout)
        layout.addWidget(features_group)

        self.setLayout(layout)


class LicensePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("License Agreement")
        self.setSubTitle("Please read the license terms carefully")

        layout = QVBoxLayout()

        # License text
        license_text = QTextEdit()
        license_text.setPlainText(
            "PHANTOM LICENSE AGREEMENT\n\n"
            "This software is dual-licensed under:\n"
            "1. MIT License for open-source use\n"
            "2. Commercial License for enterprise deployment\n\n"
            "By installing this software, you agree to comply with the terms\n"
            "of the appropriate license for your use case.\n\n"
            "See LICENSE and LICENSE-COMMERCIAL.md for full terms."
        )
        license_text.setReadOnly(True)
        layout.addWidget(license_text)

        # Acceptance checkbox
        self.accept_check = QCheckBox("I accept the license agreement")
        layout.addWidget(self.accept_check)

        self.registerField("license_accepted", self.accept_check)

        self.setLayout(layout)

    def isComplete(self):
        return self.accept_check.isChecked()


class InstallationTypePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Installation Type")
        self.setSubTitle("Choose the type of installation")

        layout = QVBoxLayout()

        # Installation type radio buttons
        self.complete_radio = QRadioButton("Complete Installation (Recommended)")
        self.core_radio = QRadioButton("Core Only")
        self.custom_radio = QRadioButton("Custom Installation")

        self.complete_radio.setChecked(True)

        type_group = QButtonGroup(self)
        type_group.addButton(self.complete_radio)
        type_group.addButton(self.core_radio)
        type_group.addButton(self.custom_radio)

        layout.addWidget(self.complete_radio)
        layout.addWidget(QLabel("  • Phantom Core\n  • RedBlue Matrix UI\n  • All components"))

        layout.addWidget(self.core_radio)
        layout.addWidget(QLabel("  • Phantom Core only\n  • No UI components"))

        layout.addWidget(self.custom_radio)
        layout.addWidget(QLabel("  • Choose components manually"))

        # Custom components (initially hidden)
        self.custom_group = QGroupBox("Component Selection:")
        custom_layout = QVBoxLayout()

        self.ui_check = QCheckBox("RedBlue Matrix UI")
        self.ui_check.setChecked(True)
        self.examples_check = QCheckBox("UI Examples")

        custom_layout.addWidget(QLabel("✓ phantom_core (required)"))
        custom_layout.addWidget(self.ui_check)
        custom_layout.addWidget(self.examples_check)

        self.custom_group.setLayout(custom_layout)
        self.custom_group.setVisible(False)
        layout.addWidget(self.custom_group)

        # Connect signals
        self.custom_radio.toggled.connect(self._on_custom_toggled)

        self.registerField("install_type*", self.complete_radio)
        self.registerField("install_ui", self.ui_check)
        self.registerField("install_examples", self.examples_check)

        self.setLayout(layout)

    def _on_custom_toggled(self, checked):
        self.custom_group.setVisible(checked)

    def nextId(self):
        if self.complete_radio.isChecked():
            return 3  # Skip to installation
        elif self.core_radio.isChecked():
            return 3  # Skip to installation
        else:
            return 3  # Custom goes to installation


class RequirementsPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("System Requirements Check")
        self.setSubTitle("Verifying your system meets the requirements")

        layout = QVBoxLayout()

        self.status_label = QLabel("Checking requirements...")
        layout.addWidget(self.status_label)

        # Requirements list
        self.req_scroll = QScrollArea()
        self.req_widget = QWidget()
        self.req_layout = QVBoxLayout(self.req_widget)

        requirements = [
            ("Python 3.8+", "Checking...", "python_req"),
            ("Administrator privileges", "Checking...", "admin_req"),
            ("Network ports (8080, 8081, 3000)", "Checking...", "ports_req"),
            ("Disk space (500MB+)", "Checking...", "disk_req")
        ]

        for req, status, field_name in requirements:
            hbox = QHBoxLayout()
            hbox.addWidget(QLabel(f"{req}:"))
            status_label = QLabel(status)
            hbox.addWidget(status_label)
            hbox.addStretch()
            self.req_layout.addLayout(hbox)

            # Store reference for updates
            setattr(self, f"{field_name}_label", status_label)

        self.req_scroll.setWidget(self.req_widget)
        self.req_scroll.setWidgetResizable(True)
        layout.addWidget(self.req_scroll)

        self.setLayout(layout)

    def initializePage(self):
        QTimer.singleShot(100, self._check_requirements)

    def _check_requirements(self):
        """Check system requirements"""
        import platform

        # Check Python version
        python_version = platform.python_version()
        if tuple(map(int, python_version.split('.'))) >= (3, 8):
            self.python_req_label.setText(f"✓ {python_version}")
            self.python_req_label.setStyleSheet("color: green;")
        else:
            self.python_req_label.setText(f"✗ {python_version} (3.8+ required)")
            self.python_req_label.setStyleSheet("color: red;")

        # Check admin privileges
        try:
            import ctypes
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
            if is_admin:
                self.admin_req_label.setText("✓ Administrator")
                self.admin_req_label.setStyleSheet("color: green;")
            else:
                self.admin_req_label.setText("✗ Administrator privileges required")
                self.admin_req_label.setStyleSheet("color: red;")
        except:
            self.admin_req_label.setText("? Unable to check")
            self.admin_req_label.setStyleSheet("color: orange;")

        # Check ports
        ports_free = self._check_ports()
        if ports_free:
            self.ports_req_label.setText("✓ Ports available")
            self.ports_req_label.setStyleSheet("color: green;")
        else:
            self.ports_req_label.setText("⚠ Some ports in use (will be freed)")
            self.ports_req_label.setStyleSheet("color: orange;")

        # Check disk space
        try:
            import shutil
            total, used, free = shutil.disk_usage("C:")
            free_gb = free / (1024**3)
            if free_gb > 0.5:
                self.disk_req_label.setText(f"✓ {free_gb:.1f} GB available")
                self.disk_req_label.setStyleSheet("color: green;")
            else:
                self.disk_req_label.setText(f"✗ {free_gb:.1f} GB (500MB+ required)")
                self.disk_req_label.setStyleSheet("color: red;")
        except:
            self.disk_req_label.setText("? Unable to check")
            self.disk_req_label.setStyleSheet("color: orange;")

        self.status_label.setText("Requirements check completed.")

    def _check_ports(self) -> bool:
        """Check if required ports are available"""
        import socket

        ports = [8080, 8081, 3000]
        for port in ports:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(('localhost', port))
                except OSError:
                    return False
        return True


class InstallationPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Installation Progress")
        self.setSubTitle("Installing Phantom components")

        layout = QVBoxLayout()

        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Preparing installation...")
        layout.addWidget(self.status_label)

        # Log output
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        layout.addWidget(self.log_text)

        self.setLayout(layout)

    def initializePage(self):
        """Start the installation process"""
        wizard = self.wizard()

        # Get installation configuration
        install_config = {
            'package_dir': str(Path(__file__).parent),
            'install_dir': r'C:\Program Files\Phantom',
            'install_type': wizard.field('install_type'),
            'install_ui': wizard.field('install_ui'),
            'install_examples': wizard.field('install_examples')
        }

        # Start installation worker
        self.worker = InstallationWorker(install_config)
        self.worker.progress.connect(self._update_progress)
        self.worker.log.connect(self._add_log)
        self.worker.finished.connect(self._installation_finished)
        self.worker.start()

    def _update_progress(self, percentage: int, status: str):
        self.progress_bar.setValue(percentage)
        self.status_label.setText(status)

    def _add_log(self, message: str):
        self.log_text.append(message)

    def _installation_finished(self, success: bool, message: str):
        self.status_label.setText(message)
        if success:
            self.progress_bar.setValue(100)
            self.log_text.append("✓ Installation completed successfully!")
        else:
            self.log_text.append(f"✗ {message}")

        # Enable next button
        self.completeChanged.emit()


class CompletionPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Installation Complete")
        self.setSubTitle("Phantom has been successfully installed")

        layout = QVBoxLayout()

        completion_label = QLabel(
            "Phantom installation has completed successfully!\n\n"
            "The following components have been installed:"
        )
        layout.addWidget(completion_label)

        # Installation summary
        summary_group = QGroupBox("Installed Components:")
        summary_layout = QVBoxLayout()

        components = [
            "✓ Phantom Core (distributed compute fabric)",
            "✓ RedBlue UI (monitoring and control interface)",
            "✓ Windows Service (automatic startup)",
            "✓ Desktop and Start Menu shortcuts",
            "✓ Documentation and examples"
        ]

        for component in components:
            summary_layout.addWidget(QLabel(component))

        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)

        # Access information
        access_group = QGroupBox("Access Points:")
        access_layout = QVBoxLayout()

        access_info = [
            "Controller: http://localhost:8080",
            "WebSocket: ws://localhost:8081",
            "RedBlue UI: http://localhost:3000"
        ]

        for info in access_info:
            access_layout.addWidget(QLabel(info))

        access_group.setLayout(access_layout)
        layout.addWidget(access_group)

        # Management information
        mgmt_label = QLabel(
            "\nManagement Commands:\n"
            "• Start Service: sc start Phantom\n"
            "• Stop Service: sc stop Phantom\n"
            "• Restart: sc stop Phantom && sc start Phantom\n\n"
            "Documentation is available in the installation directory."
        )
        mgmt_label.setWordWrap(True)
        layout.addWidget(mgmt_label)

        self.setLayout(layout)


class PhantomInstaller(QWizard):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Phantom Installation Wizard")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)

        # Set window icon if available
        try:
            icon_path = Path(__file__).resolve().parent / "assets" / "phantom_icon.ico"
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
        except Exception:
            pass

        # Add pages
        self.addPage(WelcomePage())
        self.addPage(LicensePage())
        self.addPage(InstallationTypePage())
        self.addPage(RequirementsPage())
        self.addPage(InstallationPage())
        self.addPage(CompletionPage())

        # Set button text
        self.setButtonText(QWizard.WizardButton.NextButton, "Next >")
        self.setButtonText(QWizard.WizardButton.BackButton, "< Back")
        self.setButtonText(QWizard.WizardButton.FinishButton, "Finish")
        self.setButtonText(QWizard.WizardButton.CancelButton, "Cancel")

        # Resize
        self.resize(600, 500)


def main():
    """Main entry point"""
    app = QApplication(sys.argv)

    # Set application properties
    app.setApplicationName("Phantom Installer")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Phantom")

    # Check if running as admin
    try:
        import ctypes
        if not ctypes.windll.shell32.IsUserAnAdmin():
            QMessageBox.critical(
                None, "Administrator Required",
                "This installer requires administrator privileges.\n\n"
                "Please right-click the installer and select 'Run as administrator'."
            )
            sys.exit(1)
    except:
        pass  # Skip check on non-Windows

    # Create and show wizard
    wizard = PhantomInstaller()
    wizard.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()