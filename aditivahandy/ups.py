"""Protocolo serial do SMS Manager III Senoidal, copiado do AditivaHub.

Baud 2400. A consulta é o quadro 51 ff ff ff ff b3 0d.
A resposta começa com 3d e os valores vêm em hexadecimal, divididos por 10.
Os comandos saem byte a byte, com 50 ms entre eles.
A porta fica aberta entre as leituras: o Prolific PL2303GL some se abrir e fechar o tempo todo.
No Windows a porta é COMx; no Linux, /dev/ttyUSB* ou /dev/ttyACM*.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

BAUD = 2400
QUERY = bytes.fromhex("51 ff ff ff ff b3 0d")
COMMANDS = {
    "test": bytes.fromhex("54 00 10 00 00 9c 0d"),
    "test60": bytes.fromhex("54 00 3C 00 00 70 0d"),
    "beep": bytes.fromhex("4d ff ff ff ff b7 0d"),
    "shutdown": bytes.fromhex("52 00 C8 27 0F B0 0D"),
    "cancel": bytes.fromhex("43 ff ff ff ff c1 0d"),
    "mute": bytes.fromhex("4d ff ff ff ff b7 0d"),
    "cancel_shutdown": bytes.fromhex("43 ff ff ff ff c1 0d"),
}
PROTOCOL = "sms_manager_iii"
_LEGACY = {"usb": PROTOCOL, "serial": PROTOCOL, "megatec": PROTOCOL, "sms": PROTOCOL}
DEFAULT_VA = 1800.0
DEFAULT_FP = 0.7


def normalize_protocol(value: str) -> str:
    key = str(value or "").strip().lower()
    if key == PROTOCOL:
        return key
    return _LEGACY.get(key, PROTOCOL)


class _Link:
    def __init__(self) -> None:
        self._serial = None
        self._port = ""

    def read_frame(self, port: str) -> bytes:
        link = self._open(port)
        link.reset_input_buffer()
        link.write(QUERY)
        link.flush()
        frame = link.read(32)
        if len(frame) < 16:
            frame += link.read(32)
        return frame

    def write_paced(self, port: str, payload: bytes) -> None:
        link = self._open(port)
        for index, byte in enumerate(payload):
            link.write(bytes([byte]))
            link.flush()
            if index < len(payload) - 1:
                time.sleep(0.05)

    def _open(self, port: str):
        if self._serial and getattr(self._serial, "is_open", False) and self._port == port:
            return self._serial
        self.close()
        try:
            import serial
        except Exception as exc:
            raise RuntimeError("O AditivaHandy precisa do pacote pyserial para falar com o nobreak.") from exc
        try:
            link = serial.Serial(port, BAUD, bytesize=8, parity="N", stopbits=1, timeout=1, write_timeout=2)
        except Exception as exc:
            message = str(exc).lower()
            if "permission" in message or "access is denied" in message or "errno 13" in message:
                raise RuntimeError(f"Sem permissão para abrir {port}. No Linux, o usuário precisa do grupo dialout.") from exc
            raise RuntimeError(f"Não foi possível abrir {port}: {exc}") from exc
        link.dtr = True
        link.rts = True
        time.sleep(0.4)
        self._serial = link
        self._port = port
        return link

    def close(self) -> None:
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:
                pass
        self._serial = None
        self._port = ""


class EnergyMonitor:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._devices: list[dict] = []
        self._kwh: dict[str, float] = {}
        self._last_at: dict[str, float] = {}
        self._memory: dict[str, dict] = {}
        self._link = _Link()

    def configure(self, devices: list) -> None:
        cleaned = []
        for device in devices:
            if not isinstance(device, dict):
                continue
            sync = str(device.get("sync_code") or "").strip()
            if not sync:
                continue
            kind = _kind(device)
            if kind == "tasmota":
                host = _host(device.get("host") or device.get("tasmota_host"))
                if not host:
                    continue
                cleaned.append({
                    "kind": "tasmota",
                    "sync_code": sync,
                    "host": host,
                    "accumulated_kwh": device.get("accumulated_kwh"),
                })
                continue
            port = str(device.get("port") or "").strip()
            if not port:
                continue
            cleaned.append({
                "kind": "nobreak",
                "sync_code": sync,
                "port": port,
                "protocol": normalize_protocol(str(device.get("protocol") or device.get("driver") or PROTOCOL)),
                "nominal_va": _positive(device.get("nominal_va"), DEFAULT_VA),
                "power_factor": _positive(device.get("power_factor"), DEFAULT_FP),
                "accumulated_kwh": device.get("accumulated_kwh"),
            })
        with self._lock:
            self._devices = cleaned
            for device in cleaned:
                sync = device["sync_code"]
                if sync not in self._kwh:
                    try:
                        self._kwh[sync] = float(device.get("accumulated_kwh") or 0)
                    except (TypeError, ValueError):
                        self._kwh[sync] = 0.0

    def command(self, sync_code: str, action: str) -> str:
        with self._lock:
            device = next((item for item in self._devices if item["sync_code"] == sync_code), None)
            if device is None:
                raise RuntimeError("Este dispositivo não está na lista deste computador.")
            kind = device["kind"]
            host = device.get("host", "")
            port = device.get("port", "")
        if kind == "tasmota":
            _tasmota_command(host, action)
            return "Comando enviado ao Tasmota."
        payload = COMMANDS.get(action)
        if payload is None:
            raise RuntimeError("Esse comando não existe no SMS Manager III.")
        with self._lock:
            self._link.write_paced(port, payload)
        return "Comando enviado ao nobreak."

    def collect(self) -> list[dict]:
        with self._lock:
            devices = list(self._devices)
        readings = []
        now = time.time()
        for device in devices:
            sync = device["sync_code"]
            if device["kind"] == "tasmota":
                try:
                    data = read_tasmota(device["host"])
                except Exception as exc:
                    readings.append({"sync_code": sync, "data": {"error": str(exc)}})
                    continue
                with self._lock:
                    meter = data.pop("meter_kwh", None)
                    if isinstance(meter, (int, float)) and meter > 0:
                        self._kwh[sync] = float(meter)
                    else:
                        previous = self._last_at.get(sync)
                        watts = data.get("watts")
                        if isinstance(watts, (int, float)) and previous:
                            self._kwh[sync] = self._kwh.get(sync, 0.0) + watts * (time.time() - previous) / 3_600_000
                    self._last_at[sync] = time.time()
                    data["accumulated_kwh"] = round(self._kwh.get(sync, 0.0), 4)
                readings.append({"sync_code": sync, "data": data})
                continue
            try:
                with self._lock:
                    frame = self._link.read_frame(device["port"])
                    if len(frame) < 16 or not frame.hex().startswith("3d"):
                        frame = self._link.read_frame(device["port"])
                    data = parse_frame(frame, device["nominal_va"], device["power_factor"])
            except Exception as exc:
                readings.append({"sync_code": sync, "data": {"error": str(exc)}})
                continue
            with self._lock:
                previous = self._last_at.get(sync)
                self._last_at[sync] = now
                watts = data.get("watts")
                if isinstance(watts, (int, float)) and previous:
                    self._kwh[sync] = self._kwh.get(sync, 0.0) + watts * (now - previous) / 3_600_000
                data["accumulated_kwh"] = round(self._kwh.get(sync, 0.0), 4)
                _remember(self._memory.setdefault(sync, {}), data)
            readings.append({"sync_code": sync, "data": data})
        return readings


def read_status(link: _Link, port: str, nominal_va: float = DEFAULT_VA, power_factor: float = DEFAULT_FP) -> dict:
    if "hidraw" in port.replace("\\", "/"):
        raise RuntimeError("Esta porta é USB HID. Escolha a porta serial do nobreak.")
    frame = link.read_frame(port)
    if len(frame) < 16 or not frame.hex().startswith("3d"):
        frame = link.read_frame(port)
    return parse_frame(frame, nominal_va, power_factor)


def parse_frame(frame: bytes, nominal_va: float, power_factor: float) -> dict:
    resp = frame.hex()
    if len(resp) < 32 or not resp.startswith("3d"):
        detail = f" Resposta: {resp}" if resp else ""
        raise RuntimeError(f"O SMS Manager III não respondeu.{detail}")
    input_vac = int(resp[6:10], 16) / 10.0
    output_vac = int(resp[10:14], 16) / 10.0
    load_pct = int(resp[14:18], 16) / 10.0
    output_hz = int(resp[18:22], 16) / 10.0
    battery_level = int(resp[22:26], 16) / 10.0
    temperature = int(resp[26:30], 16) / 10.0
    status = f"{int(resp[30:32], 16):08b}"
    battery_voltage = _battery_voltage(resp)
    watts = (load_pct / 100.0) * (nominal_va * power_factor)
    current = watts / output_vac if output_vac > 50 else 0.0
    return {
        "inputVac": round(input_vac, 1),
        "outputVac": round(output_vac, 1),
        "loadPct": round(load_pct, 1),
        "outputHz": round(output_hz, 1),
        "batterylevel": round(battery_level, 1),
        "temperature": round(temperature, 1),
        "batteryVoltage": battery_voltage,
        "bateriaEmUso": status[0] == "1",
        "bateriaBaixa": status[1] == "1",
        "watts": round(watts, 1),
        "currentA": round(current, 2),
        "protocol": "SMS Manager III Senoidal",
    }


def _battery_voltage(resp: str) -> float | None:
    for start, end in ((2, 6), (32, 36), (36, 40)):
        if len(resp) < end:
            continue
        try:
            value = int(resp[start:end], 16) / 10.0
        except ValueError:
            continue
        if 10.0 < value < 35.0:
            return round(value, 1)
    return None


def _remember(memory: dict, data: dict) -> None:
    watts = data.get("watts") or 0
    current = data.get("currentA") or 0
    data["peakWatts"] = round(max(watts, memory.get("peakWatts", 0)), 1)
    data["peakCurrent"] = round(max(current, memory.get("peakCurrent", 0)), 2)
    memory["peakWatts"] = data["peakWatts"]
    memory["peakCurrent"] = data["peakCurrent"]
    voltage = data.get("batteryVoltage")
    if voltage is None:
        data["batteryVoltage"] = memory.get("batteryVoltage")
    else:
        memory["batteryVoltage"] = voltage
    input_vac = data.get("inputVac") or 0
    if input_vac <= 50:
        data["minInputVac"] = memory.get("minInputVac")
        data["maxInputVac"] = memory.get("maxInputVac")
        return
    minimum = memory.get("minInputVac", input_vac)
    maximum = memory.get("maxInputVac", input_vac)
    if minimum < 50 or input_vac < minimum:
        minimum = input_vac
    if input_vac > maximum:
        maximum = input_vac
    memory["minInputVac"] = minimum
    memory["maxInputVac"] = maximum
    data["minInputVac"] = minimum
    data["maxInputVac"] = maximum


def read_tasmota(host: str) -> dict:
    """Status 8 do Tasmota, o mesmo pedido do AditivaHub."""
    target = _host(host)
    if not target:
        raise RuntimeError("Informe o IP local do Tasmota.")
    url = f"http://{target}/cm?cmnd=Status%208"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8", "replace"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"O Tasmota em {target} não respondeu.") from exc
    except (json.JSONDecodeError, TimeoutError) as exc:
        raise RuntimeError(f"O Tasmota em {target} não respondeu.") from exc
    energy = payload.get("StatusSNS", {}).get("ENERGY", {}) if isinstance(payload, dict) else {}
    if not isinstance(energy, dict) or "Power" not in energy:
        raise RuntimeError(f"O Tasmota em {target} não enviou a medição de energia.")
    return {
        "inputVac": round(float(energy.get("Voltage") or 0), 1),
        "watts": round(float(energy.get("Power") or 0), 1),
        "currentA": round(float(energy.get("Current") or 0), 2),
        "meter_kwh": float(energy.get("Total") or 0),
        "protocol": "Tasmota",
    }


def _tasmota_command(host: str, action: str) -> None:
    state = {"on": "ON", "off": "OFF"}.get(str(action or "").strip().lower())
    if state is None:
        raise RuntimeError("Esse comando não existe no Tasmota.")
    target = _host(host)
    query = urllib.parse.urlencode({"cmnd": f"Power {state}"})
    url = f"http://{target}/cm?{query}"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            response.read()
    except urllib.error.URLError as exc:
        raise RuntimeError(f"O Tasmota em {target} não recebeu o comando.") from exc


def _kind(device: dict) -> str:
    raw = str(device.get("kind") or device.get("driver") or device.get("type") or "").strip().lower()
    return "tasmota" if raw in {"tasmota", "meter"} else "nobreak"


def _host(value) -> str:
    text = str(value or "").strip()
    lowered = text.lower()
    for prefix in ("http://", "https://"):
        if lowered.startswith(prefix):
            text = text[len(prefix):]
            break
    return text.split("/")[0].strip()


def _positive(value, fallback: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return number if number > 0 else fallback
