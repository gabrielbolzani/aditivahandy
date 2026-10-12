"""Atualiza o AditivaHandy a pedido da plataforma.

Baixa a versão pedida do repositório oficial, troca os arquivos desta
instalação, instala bibliotecas novas quando o requirements.txt muda e
reinicia a ponte. O endereço vem só da versão: a URL enviada pela
plataforma não é usada para baixar nada.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .config import config_dir

REPO = "gabrielbolzani/aditivahandy"
RESTART_EXIT_CODE = 75
COPIED = ("aditivahandy", "vendor", "requirements.txt", "run.py", "README.md", "install.sh", "Dockerfile", "docker-compose.yml")


def install_root() -> Path:
    return Path(__file__).resolve().parents[1]


def running_in_docker() -> bool:
    return Path("/.dockerenv").exists() or os.environ.get("HANDY_IN_DOCKER") == "1"


def _record(version: str, status: str, detail: str = "") -> None:
    path = config_dir() / "update-request.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "version": version,
                "status": status,
                "detail": detail,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _download(version: str, workdir: Path) -> Path:
    url = f"https://github.com/{REPO}/archive/refs/tags/v{version}.tar.gz"
    archive = workdir / "source.tar.gz"
    request = urllib.request.Request(url, headers={"User-Agent": "AditivaHandy"})
    with urllib.request.urlopen(request, timeout=60) as response, archive.open("wb") as target:
        shutil.copyfileobj(response, target)
    with tarfile.open(archive) as bundle:
        bundle.extractall(workdir, filter="data")
    folders = [item for item in workdir.iterdir() if item.is_dir()]
    if len(folders) != 1:
        raise RuntimeError("O pacote baixado não tem o formato esperado.")
    return folders[0]


def _check_version(source: Path, version: str) -> None:
    text = (source / "aditivahandy" / "__init__.py").read_text(encoding="utf-8")
    found = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', text)
    if not found or found.group(1) != version:
        raise RuntimeError(f"O pacote baixado não é a versão {version}.")


def _replace_files(source: Path, root: Path) -> None:
    for name in COPIED:
        origin = source / name
        if not origin.exists():
            continue
        target = root / name
        if origin.is_dir():
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(origin, target, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(origin, target)


def _install_requirements(root: Path) -> None:
    requirements = root / "requirements.txt"
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", str(requirements)],
        cwd=root,
        check=True,
        timeout=900,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    stamp = root / ".venv" / "requirements.sha256"
    if stamp.parent.is_dir():
        stamp.write_text(_sha256(requirements), encoding="utf-8")


def _restart() -> None:
    time.sleep(2)
    if os.environ.get("HANDY_SUPERVISED") == "1":
        os._exit(RESTART_EXIT_CODE)
    args = [sys.executable, "-m", "aditivahandy", *sys.argv[1:]]
    if os.name == "nt":
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        subprocess.Popen(args, cwd=install_root(), creationflags=flags, close_fds=True)
        os._exit(0)
    os.chdir(install_root())
    os.execv(sys.executable, args)


def apply_update(version: str) -> str:
    target = version.strip().lstrip("v")
    if not re.fullmatch(r"\d+\.\d+\.\d+", target):
        raise ValueError("A plataforma não informou uma versão válida.")
    if running_in_docker():
        raise RuntimeError(
            "Esta ponte roda em Docker. Para atualizar, rode de novo o comando de instalação da versão nova."
        )

    root = install_root()
    before = _sha256(root / "requirements.txt")
    _record(target, "downloading")
    try:
        with tempfile.TemporaryDirectory(prefix="aditivahandy-") as temp:
            source = _download(target, Path(temp))
            _check_version(source, target)
            _replace_files(source, root)
        if _sha256(root / "requirements.txt") != before:
            _record(target, "installing")
            _install_requirements(root)
    except Exception as error:
        _record(target, "failed", str(error))
        raise

    _record(target, "restarting")
    threading.Thread(target=_restart, daemon=True).start()
    return f"Atualizado para v{target}. A ponte reinicia sozinha em alguns segundos."
