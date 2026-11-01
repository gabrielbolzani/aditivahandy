import asyncio
import threading

import websockets

from .auth import AuthError, device_flow, forget_device, saved_token
from .gateway import GatewaySession
from .printers import PrinterFleet


class Engine:
    def __init__(self):
        self.fleet = PrinterFleet()
        self._lock = threading.Lock()
        self._status = "Iniciando"
        self._lines: list[str] = []
        self._pairing = {"user_code": "", "url": ""}
        self._stop = threading.Event()
        self._relink = threading.Event()
        self._thread = threading.Thread(target=self._run, name="handy-engine", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self.fleet.stop()

    def relink(self) -> None:
        forget_device()
        self._set_pairing("", "")
        self._relink.set()
        self._set_status("Conexão encerrada. Gerando outro link.")

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "status": self._status,
                "log": list(self._lines[-12:]),
                "machines": self.fleet.rows(),
                "pairing": dict(self._pairing),
                "paired": bool(saved_token()),
            }

    def _set_status(self, text: str) -> None:
        with self._lock:
            self._status = text
            self._lines.append(text)
            del self._lines[:-40]

    def _set_pairing(self, code: str, url: str) -> None:
        with self._lock:
            self._pairing = {"user_code": code or "", "url": url or ""}

    def _run(self) -> None:
        asyncio.run(self._loop())

    async def _wait(self, task: asyncio.Task) -> bool:
        """Espera a tarefa. Devolve True se ela deve ser descartada para gerar outro link."""
        while not task.done():
            if self._stop.is_set() or self._relink.is_set():
                task.cancel()
                break
            await asyncio.sleep(0.2)
        if not task.done():
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        return self._stop.is_set() or self._relink.is_set()

    async def _loop(self) -> None:
        backoff = 1
        while not self._stop.is_set():
            if self._relink.is_set():
                self._relink.clear()
                forget_device()
                self._set_pairing("", "")
            token = saved_token()
            try:
                if not token:
                    flow = asyncio.create_task(device_flow(self._set_status, self._set_pairing))
                    if await self._wait(flow):
                        continue
                    token = flow.result()
                session = GatewaySession(token, self.fleet, self._set_status)
                connection = asyncio.create_task(session.run_once())
                if await self._wait(connection):
                    continue
                result = connection.result()
                if result == "relink":
                    forget_device()
                    self._set_pairing("", "")
                    self._set_status("Acesso recusado. Gerando outro link.")
                    backoff = 1
                    continue
                self._set_status("Conexão encerrada. Vou reconectar.")
                backoff = 1
            except AuthError as exc:
                self._set_status(str(exc))
            except websockets.exceptions.ConnectionClosed as exc:
                close_code = getattr(getattr(exc, "rcvd", None), "code", None)
                if close_code == 4001:
                    forget_device()
                    self._set_pairing("", "")
                    self._set_status("Acesso revogado. Gerando outro link.")
                    backoff = 1
                    continue
                self._set_status(f"Conexão caiu. Nova tentativa em {backoff}s.")
            except Exception as exc:
                self._set_status(f"Falha: {exc}. Nova tentativa em {backoff}s.")
            if self._stop.is_set():
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)
