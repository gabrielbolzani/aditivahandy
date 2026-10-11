"""Liga o snapshot da plataforma aos drivers do Hub, sem cadastro local."""

import base64
import sys
import threading
import time
from hashlib import sha1

from .config import HUB_DIR
from .protocol import map_state

if str(HUB_DIR) not in sys.path:
    sys.path.insert(0, str(HUB_DIR))

from printer_drivers import create_printer_from_config  # noqa: E402

SUPPORTED = {
    "bambulab": "bambu",
    "moonraker": "moonraker",
    "elegoo": "elegoo",
}

TELEMETRY_KEYS = (
    "progress",
    "filename",
    "task_name",
    "layer",
    "total_layers",
    "remaining_time",
    "print_duration",
    "elapsed_time",
    "temp_nozzle",
    "target_nozzle",
    "temp_nozzle_left",
    "temp_nozzle_right",
    "target_nozzle_left",
    "target_nozzle_right",
    "active_nozzle",
    "nozzle_count",
    "nozzle_diameter",
    "nozzle_diameter_left",
    "nozzle_diameter_right",
    "nozzle_type",
    "nozzle_type_left",
    "nozzle_type_right",
    "bed_type",
    "temp_bed",
    "target_bed",
    "chamber_temp",
    "target_chamber",
    "fan_part",
    "fan_aux",
    "fan_chamber",
    "speed_level",
    "led_val",
    "fan_val",
    "wifi_signal",
    "printer_type",
    "print_weight",
    "active_tray_name",
    "active_tray_uuid",
    "ams",
    "hms",
    "print_error",
    "serial",
    "ip",
    "last_update",
)


def _number(value):
    if value is None or value == "" or value == "--":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fingerprint(printer: dict) -> tuple:
    return (
        str(printer.get("protocol") or "").lower(),
        printer.get("ip") or "",
        printer.get("port"),
        printer.get("access_code") or "",
        printer.get("api_key") or "",
        printer.get("serial_number") or "",
    )


def _hub_config(printer: dict) -> dict:
    protocol = str(printer.get("protocol") or "").lower()
    ip = str(printer.get("ip") or "").strip()
    port = printer.get("port")
    if protocol == "moonraker" and port:
        try:
            port_number = int(port)
        except (TypeError, ValueError):
            port_number = 0
        if port_number and port_number not in (80, 443) and ":" not in ip:
            ip = f"{ip}:{port_number}"
    return {
        "id": printer.get("machine_id"),
        "name": printer.get("name") or "Máquina",
        "type": SUPPORTED[protocol],
        "ip": ip,
        "port": port,
        "serial": printer.get("serial_number") or "",
        "access_code": printer.get("access_code") or "",
        "total_usage": 0,
        "enabled": True,
    }


class PrinterFleet:
    def __init__(self):
        self._lock = threading.Lock()
        self._slots: dict[str, dict] = {}
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._poll, name="handy-printers", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            slots = list(self._slots.values())
            self._slots.clear()
        for slot in slots:
            self._stop_driver(slot.get("driver"))

    def apply_snapshot(self, printers: list) -> None:
        incoming = {}
        for item in printers or []:
            machine_id = str(item.get("machine_id") or "")
            if machine_id:
                incoming[machine_id] = item

        with self._lock:
            gone = [machine_id for machine_id in self._slots if machine_id not in incoming]
            for machine_id in gone:
                self._stop_driver(self._slots.pop(machine_id).get("driver"))

            for machine_id, item in incoming.items():
                protocol = str(item.get("protocol") or "").lower()
                current = self._slots.get(machine_id)
                finger = _fingerprint(item)
                if current and current["finger"] == finger:
                    current["info"] = item
                    continue
                carry = 0.0
                if current:
                    carry = self._unsent_hours(current)
                    self._stop_driver(current.get("driver"))
                driver = None
                note = ""
                if protocol not in SUPPORTED:
                    note = "Protocolo ainda sem driver neste computador."
                elif not item.get("ip"):
                    note = "A plataforma não enviou o IP desta máquina."
                else:
                    try:
                        driver = create_printer_from_config(_hub_config(item))
                        if driver is None:
                            note = "Não foi possível abrir o driver."
                    except Exception as exc:
                        note = str(exc)
                        driver = None
                self._slots[machine_id] = {
                    "info": item,
                    "finger": finger,
                    "driver": driver,
                    "note": note,
                    "last_camera": 0.0,
                    "camera_hash": "",
                    "thumb_name": "",
                    "usage_sent": 0.0,
                    "usage_carry": carry,
                    "usage_pending": None,
                }

    def rows(self) -> list[dict]:
        with self._lock:
            rows = []
            for machine_id, slot in self._slots.items():
                info = slot["info"]
                status = {}
                if slot["driver"] is not None:
                    try:
                        status = slot["driver"].get_status() or {}
                    except Exception:
                        status = {}
                rows.append({
                    "machine_id": machine_id,
                    "name": info.get("name") or "Máquina",
                    "protocol": info.get("protocol") or "",
                    "ip": info.get("ip") or "",
                    "state": map_state(status.get("state")) if slot["driver"] else "offline",
                    "progress": status.get("progress") or 0,
                    "note": slot["note"],
                })
            return rows

    def collect_telemetry(self) -> list[dict]:
        items = []
        with self._lock:
            slots = list(self._slots.items())
        for machine_id, slot in slots:
            driver = slot.get("driver")
            if driver is None:
                continue
            try:
                status = driver.get_status() or {}
            except Exception:
                continue
            payload = {"machine_id": machine_id, "state": map_state(status.get("state"))}
            for key in TELEMETRY_KEYS:
                if key not in status:
                    continue
                value = status.get(key)
                if value is None or value == "":
                    continue
                if key in ("filename", "task_name", "active_tray_name", "active_tray_uuid", "serial", "ip", "printer_type", "nozzle_type", "nozzle_type_left", "nozzle_type_right", "bed_type"):
                    payload[key] = value
                elif key in ("ams", "hms", "print_error"):
                    payload[key] = value
                else:
                    number = _number(value)
                    if number is not None:
                        payload[key] = number
            if str(slot["info"].get("protocol") or "").lower() == "elegoo" and "remaining_time" in payload:
                payload["remaining_time"] = int(payload["remaining_time"] * 60)
            firmware = status.get("firmware_update") or {}
            if isinstance(firmware, dict):
                if firmware.get("current"):
                    payload["firmware_version"] = firmware["current"]
                if firmware.get("latest"):
                    payload["firmware_version_latest"] = firmware["latest"]
            counted = _number(status.get("total_usage")) or 0.0
            delta = max(0.0, counted - float(slot.get("usage_sent") or 0)) + float(slot.get("usage_carry") or 0)
            if delta >= 1 / 3600:
                payload["usage_delta_hours"] = round(delta, 6)
                slot["usage_pending"] = counted
            items.append(payload)
        return items

    def commit_usage(self) -> None:
        with self._lock:
            for slot in self._slots.values():
                pending = slot.get("usage_pending")
                if pending is None:
                    continue
                slot["usage_sent"] = pending
                slot["usage_carry"] = 0.0
                slot["usage_pending"] = None

    @staticmethod
    def _unsent_hours(slot: dict) -> float:
        driver = slot.get("driver")
        counted = 0.0
        if driver is not None:
            try:
                counted = _number((driver.get_status() or {}).get("total_usage")) or 0.0
            except Exception:
                counted = 0.0
        return max(0.0, counted - float(slot.get("usage_sent") or 0)) + float(slot.get("usage_carry") or 0)

    def collect_media(self) -> list[tuple[str, dict]]:
        messages = []
        now = time.time()
        with self._lock:
            slots = list(self._slots.items())
        for machine_id, slot in slots:
            driver = slot.get("driver")
            if driver is None:
                continue
            frame = getattr(driver, "last_frame", None)
            if isinstance(frame, (bytes, bytearray)) and now - slot["last_camera"] >= 8:
                digest = sha1(frame[:64] + str(len(frame)).encode()).hexdigest()
                if digest != slot["camera_hash"]:
                    slot["camera_hash"] = digest
                    slot["last_camera"] = now
                    messages.append((
                        "camera.frame",
                        {
                            "machine_id": machine_id,
                            "image_base64": base64.b64encode(frame).decode("ascii"),
                        },
                    ))
            cover = None
            filename = ""
            try:
                status = driver.get_status() or {}
                cover = status.get("cover_image")
                filename = str(status.get("filename") or status.get("task_name") or "")
            except Exception:
                cover = None
            if isinstance(cover, str) and cover and not cover.startswith("http") and filename != slot["thumb_name"]:
                slot["thumb_name"] = filename
                messages.append((
                    "printer.thumbnail",
                    {
                        "machine_id": machine_id,
                        "filename": filename or "job",
                        "image_base64": cover,
                    },
                ))
        return messages

    def execute(self, machine_id: str, command: str, payload: dict | None) -> str:
        with self._lock:
            slot = self._slots.get(str(machine_id))
            driver = slot.get("driver") if slot else None
        if driver is None:
            raise RuntimeError("Esta máquina não está conectada neste computador.")
        payload = payload if isinstance(payload, dict) else {}
        name = {
            "set_led": "led",
            "set_speed": "speed",
            "set_fan": "fan",
        }.get(command, command)
        kwargs = {}
        if "val" in payload:
            kwargs["val"] = payload["val"]
        elif "value" in payload:
            kwargs["val"] = payload["value"]
        if "gcode" in payload:
            kwargs["gcode"] = payload["gcode"]
        driver.send_command(name, **kwargs)
        return "comando enviado"

    def _poll(self) -> None:
        while not self._stop.wait(1):
            with self._lock:
                drivers = [slot.get("driver") for slot in self._slots.values()]
            for driver in drivers:
                if driver is None:
                    continue
                try:
                    driver.update()
                except Exception:
                    pass

    @staticmethod
    def _stop_driver(driver) -> None:
        if driver is None:
            return
        try:
            driver.stop()
        except Exception:
            pass
