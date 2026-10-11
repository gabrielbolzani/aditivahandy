import json
import os
import platform
from pathlib import Path

from . import APP_VERSION

PROJECT_REF = "iwsqfjngeicyrcdowdbi"
ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6"
    "Iml3c3Fmam5nZWljeXJjZG93ZGJpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjI1NjIzMDks"
    "ImV4cCI6MjA3ODEzODMwOX0.CM5OO5AoLcVWShMBcpk8oJaYzNU06jHjbH-Oj3X-uAg"
)
BASE = f"https://{PROJECT_REF}.supabase.co/functions/v1"
WSS = f"wss://{PROJECT_REF}.supabase.co/functions/v1/handy-gateway"
HTTP_HEADERS = {"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}"}
APP_VERSION = APP_VERSION

def resolve_hub_dir() -> Path:
    override = os.getenv("ADITIVA_HUB_DIR", "").strip()
    if override:
        return Path(override)
    here = Path(__file__).resolve()
    packaged = here.parents[1] / "vendor" / "3d_printer_connection_hub"
    if (packaged / "printer_drivers.py").is_file():
        return packaged
    return here.parents[2] / "3d_printer_connection_hub"


HUB_DIR = resolve_hub_dir()


def config_dir() -> Path:
    if platform.system() == "Windows" and os.getenv("APPDATA"):
        return Path(os.environ["APPDATA"]) / "AditivaHandy"
    return Path.home() / ".config" / "aditivahandy"


def token_file() -> Path:
    return config_dir() / "device.json"


def load_device() -> dict | None:
    try:
        data = json.loads(token_file().read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    token = data.get("refresh_token")
    if not isinstance(token, str) or not token:
        return None
    return data


def save_device(refresh_token: str, device_id: str, nickname: str = "") -> None:
    path = token_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "refresh_token": refresh_token,
                "device_id": device_id,
                "nickname": nickname,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    try:
        path.chmod(0o600)
    except OSError:
        pass


def clear_device() -> None:
    try:
        token_file().unlink(missing_ok=True)
    except OSError:
        pass
