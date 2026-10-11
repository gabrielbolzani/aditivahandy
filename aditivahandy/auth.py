import asyncio
import platform
import socket
import time

import httpx

from . import APP_VERSION
from .config import BASE, HTTP_HEADERS, clear_device, load_device, save_device


class AuthError(Exception):
    pass


async def device_flow(on_status, on_code=None) -> str:
    """Pede um código e espera a conta aprovar no AditivaFlow."""
    on_status("Gerando o link de autorização.")
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{BASE}/handy-device-authorize",
            headers=HTTP_HEADERS,
            json={
                "nickname": f"Handy-{socket.gethostname()}",
                "os": platform.system(),
                "os_version": platform.release(),
                "app_version": APP_VERSION,
                "hostname": socket.gethostname(),
            },
        )
        response.raise_for_status()
        data = response.json()
        code = data.get("user_code") or ""
        url = data.get("verification_uri_complete") or data.get("verification_uri")
        if not url or not data.get("device_code"):
            raise AuthError("A plataforma não devolveu o link de autorização.")
        if on_code:
            on_code(code, url)
        on_status(f"Abra o link no navegador e entre na sua conta. Código {code}.")

        deadline = time.time() + int(data.get("expires_in") or 900)
        interval = max(3, int(data.get("interval") or 5))
        while time.time() < deadline:
            await asyncio.sleep(interval)
            token_response = await client.post(
                f"{BASE}/handy-device-token",
                headers=HTTP_HEADERS,
                json={"device_code": data["device_code"]},
            )
            body = {}
            if token_response.headers.get("content-type", "").startswith("application/json"):
                body = token_response.json()
            if token_response.status_code == 200 and body.get("refresh_token"):
                save_device(
                    body["refresh_token"],
                    str(body.get("device_id") or ""),
                    str(body.get("nickname") or ""),
                )
                if on_code:
                    on_code("", "")
                on_status("Computador autorizado. Conectando às máquinas da conta.")
                return body["refresh_token"]
            error = body.get("error") if isinstance(body, dict) else ""
            if token_response.status_code in (202, 428) or error == "authorization_pending":
                on_status(f"Aguardando aprovação no navegador ({code}).")
                continue
            if token_response.status_code == 403 or error == "access_denied":
                raise AuthError("A autorização foi recusada na conta.")
            if token_response.status_code == 410:
                raise AuthError("O código expirou. Vou gerar outro.")
            raise AuthError(error or f"Falha ao autorizar ({token_response.status_code}).")
        raise AuthError("O tempo para aprovar no navegador acabou.")


def saved_token() -> str | None:
    device = load_device()
    if not device:
        return None
    return device.get("refresh_token")


def forget_device() -> None:
    clear_device()
