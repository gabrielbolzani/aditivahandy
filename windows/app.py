"""Programa do Windows. Ele chama o script Python, não substitui a ponte."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path

from PySide6.QtCore import QProcess, Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

PYTHON_VERSION = "3.12"
PYTHON_INSTALLER = "python-3.12.7-amd64.exe"
PYTHON_URL = f"https://www.python.org/ftp/python/3.12.7/{PYTHON_INSTALLER}"
PYTHON_PAGE = "https://www.python.org/downloads/windows/"
PORT = int(os.environ.get("HANDY_PORT", "8787"))


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def launcher_target() -> tuple[str, str]:
    if getattr(sys, "frozen", False):
        return sys.executable, ""
    return sys.executable, str(Path(__file__).resolve())


def settings_path() -> Path:
    base = Path(os.environ.get("APPDATA", str(Path.home()))) / "AditivaHandy"
    base.mkdir(parents=True, exist_ok=True)
    return base / "launcher.json"


def load_settings() -> dict:
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"start_with_windows": True}
    if not isinstance(data, dict):
        return {"start_with_windows": True}
    data.setdefault("start_with_windows", True)
    return data


def save_settings(data: dict) -> None:
    settings_path().write_text(json.dumps(data, indent=2), encoding="utf-8")


def startup_link() -> Path:
    return (
        Path(os.environ["APPDATA"])
        / "Microsoft/Windows/Start Menu/Programs/Startup/AditivaHandy.lnk"
    )


def set_startup(enabled: bool) -> None:
    link = startup_link()
    if not enabled:
        link.unlink(missing_ok=True)
        return
    target, argument = launcher_target()
    workdir = str(app_root())
    command = (
        "$shell = New-Object -ComObject WScript.Shell; "
        "$shortcut = $shell.CreateShortcut($env:HANDY_SHORTCUT); "
        "$shortcut.TargetPath = $env:HANDY_TARGET; "
        "$shortcut.Arguments = $env:HANDY_ARGS; "
        "$shortcut.WorkingDirectory = $env:HANDY_WORKDIR; "
        "$shortcut.WindowStyle = 1; "
        "$shortcut.Description = 'AditivaHandy'; "
        "$shortcut.Save()"
    )
    env = os.environ.copy()
    env.update({
        "HANDY_SHORTCUT": str(link),
        "HANDY_TARGET": target,
        "HANDY_ARGS": argument,
        "HANDY_WORKDIR": workdir,
    })
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        env=env,
        check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def port_is_open(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.4)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _version_of(executable: str, args: list[str] | None = None) -> str:
    try:
        completed = subprocess.run(
            [executable, *(args or []), "-c", "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')"],
            capture_output=True,
            text=True,
            timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def find_python() -> str:
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Python/Python312/python.exe"
    if local.is_file() and _version_of(str(local)) == PYTHON_VERSION:
        return str(local)
    if _version_of("py", ["-3.12"]) == PYTHON_VERSION:
        completed = subprocess.run(
            ["py", "-3.12", "-c", "import sys; print(sys.executable)"],
            capture_output=True,
            text=True,
            timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if completed.returncode == 0:
            return completed.stdout.strip()
    if _version_of("python") == PYTHON_VERSION:
        completed = subprocess.run(
            ["python", "-c", "import sys; print(sys.executable)"],
            capture_output=True,
            text=True,
            timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if completed.returncode == 0:
            return completed.stdout.strip()
    return ""


def install_python(report) -> str:
    destination = Path(os.environ.get("TEMP", ".")) / PYTHON_INSTALLER
    report(f"Baixando o Python {PYTHON_VERSION} em {PYTHON_PAGE}")
    urllib.request.urlretrieve(PYTHON_URL, destination)
    report("Instalando o Python 3.12 para este usuário.")
    completed = subprocess.run(
        [
            str(destination),
            "/passive",
            "InstallAllUsers=0",
            "PrependPath=1",
            "Include_launcher=1",
            "Include_test=0",
        ],
        timeout=900,
    )
    if completed.returncode not in (0, 3010):
        raise RuntimeError("O instalador do Python não concluiu.")
    found = find_python()
    if not found:
        raise RuntimeError("O Python 3.12 foi instalado, mas ainda não aparece neste usuário.")
    return found


def ensure_venv(python: str, root: Path, report) -> Path:
    venv_python = root / ".venv" / "Scripts" / "python.exe"
    if not venv_python.is_file():
        report("Criando o ambiente do AditivaHandy.")
        subprocess.run(
            [python, "-m", "venv", str(root / ".venv")],
            cwd=root,
            check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    requirements = root / "requirements.txt"
    digest = hashlib.sha256(requirements.read_bytes()).hexdigest()
    stamp = root / ".venv" / "requirements.sha256"
    if stamp.is_file() and stamp.read_text(encoding="utf-8").strip() == digest:
        return venv_python
    report("Instalando as bibliotecas do Python.")
    subprocess.run(
        [str(venv_python), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(requirements)],
        cwd=root,
        check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    stamp.write_text(digest, encoding="utf-8")
    return venv_python


class SetupThread(QThread):
    message = Signal(str)
    ready = Signal(str)
    failed = Signal(str)

    def run(self) -> None:
        try:
            python = find_python()
            if not python:
                python = install_python(self.message.emit)
            venv_python = ensure_venv(python, app_root(), self.message.emit)
            self.ready.emit(str(venv_python))
        except Exception as error:
            self.failed.emit(str(error))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._quitting = False
        self._owns_process = False
        self.settings = load_settings()
        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(app_root()))
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_output)
        self.process.finished.connect(self._finished)

        self.setWindowTitle("AditivaHandy")
        self.resize(520, 420)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        title = QLabel("AditivaHandy")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        layout.addWidget(title)

        self.status = QLabel("Preparando a ponte…")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        note = QLabel(
            f"Este programa chama o Python {PYTHON_VERSION} de 64 bits. "
            "Se ele não estiver instalado, o AditivaHandy baixa o instalador oficial. "
            f'<a href="{PYTHON_PAGE}">{PYTHON_PAGE}</a>'
        )
        note.setWordWrap(True)
        note.setTextFormat(Qt.RichText)
        note.setText(note.text())
        note.setTextInteractionFlags(Qt.TextBrowserInteraction)
        note.setOpenExternalLinks(True)
        layout.addWidget(note)

        self.autostart = QCheckBox("Iniciar com o Windows")
        self.autostart.blockSignals(True)
        self.autostart.setChecked(bool(self.settings.get("start_with_windows", True)))
        self.autostart.blockSignals(False)
        self.autostart.toggled.connect(self._toggle_startup)
        layout.addWidget(self.autostart)

        buttons = QHBoxLayout()
        self.open_button = QPushButton("Abrir painel")
        self.open_button.clicked.connect(self._open_panel)
        self.restart_button = QPushButton("Iniciar de novo")
        self.restart_button.clicked.connect(self._start_bridge)
        self.quit_button = QPushButton("Sair")
        self.quit_button.clicked.connect(self._quit)
        buttons.addWidget(self.open_button)
        buttons.addWidget(self.restart_button)
        buttons.addWidget(self.quit_button)
        layout.addLayout(buttons)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(200)
        layout.addWidget(self.log)

        self._toggle_startup(self.autostart.isChecked())

        self.setup = SetupThread()
        self.setup.message.connect(self._set_status)
        self.setup.ready.connect(self._python_ready)
        self.setup.failed.connect(self._setup_failed)
        self.setup.start()

    def _set_status(self, text: str) -> None:
        self.status.setText(text)
        self.log.appendPlainText(text)

    def _python_ready(self, executable: str) -> None:
        self._python = executable
        if port_is_open(PORT):
            self._set_status(f"A ponte já está em execução na porta {PORT}.")
            return
        self._start_bridge()

    def _setup_failed(self, text: str) -> None:
        self._set_status(text)
        QMessageBox.warning(
            self,
            "AditivaHandy",
            f"{text}\n\nInstale o Python {PYTHON_VERSION} de 64 bits em {PYTHON_PAGE}",
        )

    def _start_bridge(self) -> None:
        if not getattr(self, "_python", ""):
            return
        if self.process.state() != QProcess.NotRunning:
            return
        if port_is_open(PORT) and not self._owns_process:
            self._set_status(f"A ponte já está em execução na porta {PORT}.")
            return
        self._owns_process = True
        self._set_status("Iniciando a ponte.")
        program = Path(self._python).with_name("pythonw.exe")
        executable = str(program if program.is_file() else self._python)
        self.process.start(executable, ["-m", "aditivahandy"])

    def _read_output(self) -> None:
        text = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace").strip()
        if text:
            self.log.appendPlainText(text)

    def _finished(self, code: int, _status) -> None:
        self._owns_process = False
        if self._quitting:
            return
        self._set_status(f"A ponte parou (código {code}).")

    def _open_panel(self) -> None:
        os.startfile(f"http://127.0.0.1:{PORT}")

    def _toggle_startup(self, enabled: bool) -> None:
        try:
            set_startup(enabled)
        except (OSError, subprocess.CalledProcessError) as error:
            self._set_status(f"Não foi possível alterar o início automático. {error}")
            return
        self.settings["start_with_windows"] = enabled
        save_settings(self.settings)

    def _quit(self) -> None:
        self._quitting = True
        if self._owns_process and self.process.state() != QProcess.NotRunning:
            self.process.terminate()
            if not self.process.waitForFinished(4000):
                self.process.kill()
                self.process.waitForFinished(2000)
        QApplication.quit()

    def closeEvent(self, event) -> None:
        if self._quitting:
            event.accept()
            return
        event.ignore()
        self.showMinimized()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == event.Type.WindowStateChange and self.isMinimized():
            self._set_status("O AditivaHandy continua na barra de tarefas.")


def main() -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
