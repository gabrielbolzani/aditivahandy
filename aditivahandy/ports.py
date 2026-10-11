"""Portas locais que um nobreak pode estar usando."""

from __future__ import annotations

import glob
import os


def list_host_ports() -> list[dict]:
    found = _from_pyserial()
    if os.name == "nt":
        found.extend(_from_windows_registry())
    else:
        found.extend(_from_linux())
    return _dedupe(found)


def _dedupe(ports: list[dict]) -> list[dict]:
    kept: list[dict] = []
    seen: set[str] = set()
    for port in ports:
        device = str(port.get("id") or "").strip()
        if not device:
            continue
        key = os.path.realpath(device) if device.startswith("/") else device.upper()
        if key in seen:
            continue
        seen.add(key)
        kept.append({
            "id": device,
            "name": str(port.get("name") or device),
            "detail": str(port.get("detail") or ""),
        })
    return kept


def _from_pyserial() -> list[dict]:
    try:
        from serial.tools import list_ports
    except Exception:
        return []
    ports = []
    for port in list_ports.comports():
        device = str(port.device or "").strip()
        if not device:
            continue
        ports.append({
            "id": device,
            "name": str(port.description or device),
            "detail": str(port.hwid or ""),
        })
    return ports


def _from_windows_registry() -> list[dict]:
    try:
        import winreg
    except Exception:
        return []
    ports = []
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DEVICEMAP\SERIALCOMM")
    except OSError:
        return []
    try:
        index = 0
        while True:
            try:
                _name, value, _kind = winreg.EnumValue(key, index)
            except OSError:
                break
            device = str(value or "").strip()
            if device:
                ports.append({"id": device, "name": device, "detail": "Porta serial"})
            index += 1
    finally:
        winreg.CloseKey(key)
    return ports


def _from_linux() -> list[dict]:
    ports = []
    for path in sorted(glob.glob("/dev/serial/by-id/*")):
        name = os.path.basename(path).replace("_", " ")
        ports.append({
            "id": os.path.realpath(path),
            "name": name,
            "detail": "Serial USB",
        })
    for pattern, kind in (("/dev/ttyUSB*", "Serial USB"), ("/dev/ttyACM*", "Serial USB"), ("/dev/hidraw*", "USB HID")):
        for path in sorted(glob.glob(pattern)):
            ports.append({
                "id": path,
                "name": _linux_product(path) or os.path.basename(path),
                "detail": kind,
            })
    return ports


def _linux_product(path: str) -> str:
    name = os.path.basename(path)
    candidates = [
        f"/sys/class/tty/{name}/device/../product",
        f"/sys/class/tty/{name}/device/interface",
        f"/sys/class/hidraw/{name}/device/uevent",
    ]
    for candidate in candidates:
        try:
            text = open(candidate, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        if candidate.endswith("uevent"):
            for line in text.splitlines():
                if line.startswith("HID_NAME="):
                    return line.split("=", 1)[1].strip()
            continue
        product = text.strip()
        if product:
            return product
    return ""
