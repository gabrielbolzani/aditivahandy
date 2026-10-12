import asyncio
import json

import psutil
import websockets

from . import APP_VERSION, alexa
from .config import ANON_KEY, WSS
from .printers import PrinterFleet
from .protocol import envelope
from .ups import EnergyMonitor


class GatewaySession:
    def __init__(self, refresh_token: str, fleet: PrinterFleet, on_status):
        self.refresh_token = refresh_token
        self.fleet = fleet
        self.energy = EnergyMonitor()
        self.on_status = on_status
        self.device_label = ""
        self.device_id = ""

    async def run_once(self) -> str:
        """Conecta, autentica e fica no ar até a conexão cair.

        Retorna "relink" quando o token foi recusado e "retry" nos demais casos.
        """
        self.on_status("Conectando à plataforma…")
        async with websockets.connect(
            WSS,
            additional_headers={"apikey": ANON_KEY},
            ping_interval=None,
            open_timeout=20,
            max_size=4_000_000,
        ) as ws:
            authed = asyncio.Event()
            outcome = "retry"

            async def send(message_type: str, payload: dict | None = None) -> None:
                await ws.send(json.dumps(envelope(message_type, payload)))

            await send("auth", {"refresh_token": self.refresh_token})

            async def reader():
                nonlocal outcome
                async for raw in ws:
                    if isinstance(raw, bytes):
                        continue
                    try:
                        message = json.loads(raw)
                    except ValueError:
                        continue
                    message_type = message.get("type")
                    payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}

                    if message_type == "auth.required":
                        await send("auth", {"refresh_token": self.refresh_token})
                    elif message_type == "auth.ok":
                        self.device_label = str(payload.get("nickname") or "")
                        self.device_id = str(payload.get("device_id") or "")
                        authed.set()
                        self.on_status("Conectado. Recebendo as máquinas da conta.")
                    elif message_type == "auth.error":
                        outcome = "relink"
                        await ws.close(code=4001)
                        return
                    elif message_type == "ping":
                        await send("pong", {"t": payload.get("t")})
                    elif message_type == "config.snapshot":
                        printers = payload.get("printers") if isinstance(payload.get("printers"), list) else []
                        energy = payload.get("energy") if isinstance(payload.get("energy"), list) else []
                        self.fleet.apply_snapshot(printers)
                        self.energy.configure([
                            device for device in energy
                            if isinstance(device, dict) and self._owns(device.get("handy_device_id"))
                        ])
                        self.on_status(f"Conectado. {len(printers)} máquina(s) liberada(s) pela plataforma.")
                    elif message_type == "command.request":
                        await self._run_command(send, payload)
                    elif message_type == "error":
                        reason = payload.get("reason") or message_type
                        self.on_status(f"A plataforma recusou um envio: {reason}")

            async def publisher():
                await authed.wait()
                next_config = asyncio.get_running_loop().time() + 60
                next_telemetry = asyncio.get_running_loop().time()
                next_health = asyncio.get_running_loop().time() + 5
                next_energy = asyncio.get_running_loop().time() + 2
                while True:
                    now = asyncio.get_running_loop().time()
                    if now >= next_config:
                        await send("config.get", {})
                        next_config = now + 60
                    if now >= next_telemetry:
                        items = self.fleet.collect_telemetry()
                        if items:
                            await send("printer.telemetry.batch", {"items": items})
                            self.fleet.commit_usage()
                        for message_type, payload in self.fleet.collect_media():
                            await send(message_type, payload)
                        next_telemetry = now + 3
                    if now >= next_health:
                        await send("handy.health", _health())
                        next_health = now + 30
                    if now >= next_energy:
                        readings = await asyncio.to_thread(self.energy.collect)
                        for reading in readings:
                            await send("energy.reading", reading)
                        next_energy = now + 5
                    await asyncio.sleep(0.5)

            reader_task = asyncio.create_task(reader())
            publisher_task = asyncio.create_task(publisher())
            done, pending = await asyncio.wait(
                {reader_task, publisher_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            for task in done:
                exc = task.exception()
                if exc:
                    raise exc
            return outcome

    def _owns(self, handy_device_id) -> bool:
        target = str(handy_device_id or "")
        return not target or not self.device_id or target == self.device_id

    async def _run_command(self, send, payload: dict) -> None:
        command_id = payload.get("command_id")
        machine_id = payload.get("machine_id")
        command = str(payload.get("command") or "")
        inner = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
        try:
            if command == "ports.list":
                from .ports import list_host_ports
                message = json.dumps({"ports": list_host_ports()}, ensure_ascii=False)
            elif command == "energy.configure":
                devices = inner.get("devices") if isinstance(inner.get("devices"), list) else []
                matched = [
                    device for device in devices
                    if isinstance(device, dict) and self._owns(device.get("handy_device_id"))
                ]
                if matched or not devices:
                    self.energy.configure(matched)
                message = f"{len(matched)} nobreak(s) em leitura."
            elif command == "energy.command":
                if not self._owns(inner.get("handy_device_id")):
                    message = "Comando de outro computador."
                else:
                    message = await asyncio.to_thread(
                        self.energy.command,
                        str(inner.get("sync_code") or ""),
                        str(inner.get("action") or ""),
                    )
            elif command == "app.update":
                from .updater import apply_update

                self.on_status(f"Atualizando para v{str(inner.get('version') or '').lstrip('v')}…")
                message = await asyncio.to_thread(apply_update, str(inner.get("version") or ""))
                self.on_status(message)
            elif command == "alexa.speak":
                result = await alexa.speak_async(
                    str(inner.get("serial") or ""),
                    str(inner.get("text") or "Teste do AditivaFlow."),
                    False,
                )
                if not result.get("ok"):
                    raise RuntimeError(str(result.get("error") or "A Alexa não falou."))
                message = str(result.get("message") or "Fala enviada.")
            else:
                message = self.fleet.execute(machine_id, command, inner)
            await send("command.result", {
                "command_id": command_id,
                "success": True,
                "message": message,
            })
        except Exception as exc:
            await send("command.result", {
                "command_id": command_id,
                "success": False,
                "message": str(exc),
            })


def _alexa_status() -> dict:
    status = alexa.public_status()
    devices = []
    for row in status.get("devices") or []:
        if not isinstance(row, dict) or not row.get("serial"):
            continue
        devices.append({
            "serial": row.get("serial"),
            "name": row.get("name") or row.get("serial"),
            "online": bool(row.get("online")),
        })
    return {
        "linked": bool(status.get("linked")),
        "account": status.get("email") or "",
        "devices": devices,
    }


def _health() -> dict:
    from .ports import list_host_ports

    alexa_status = _alexa_status()
    payload = {
        "version": APP_VERSION,
        "app_version": APP_VERSION,
        "alexa_linked": alexa_status["linked"],
        "alexa_account": alexa_status["account"],
        "alexa_devices": alexa_status["devices"],
        "ports": list_host_ports(),
    }
    try:
        payload["cpu"] = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        payload["ram"] = int(memory.used / (1024 * 1024))
        payload["ram_percent"] = memory.percent
    except Exception:
        pass
    return payload
