"""Conta Amazon neste computador, com a mesma biblioteca do Home Assistant.

O login abre a página da Amazon. A senha não passa por aqui. Quando a
Amazon devolve o código no endereço final, a biblioteca registra o acesso
e o Handy pede para o Echo falar.
"""

import asyncio
import json
import logging
import threading
import time
from urllib.parse import parse_qs, unquote, urlparse

logging.getLogger("aioamazondevices").setLevel(logging.WARNING)

from aioamazondevices import AmazonEchoApi, CannotAuthenticate, CannotConnect
from aioamazondevices.exceptions import CannotRetrieveData, NoOnlineDevicesError, WrongMethod
from aioamazondevices.structures import AmazonDevice, AmazonSaveDataConfig
from aiohttp import ClientSession

from .config import config_dir

_lock = threading.Lock()
_devices: list[dict] = []
_last_error = ""


def _dir():
    path = config_dir() / "amazon"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _login_file():
    return config_dir() / "amazon-login.json"


def _devices_file():
    return config_dir() / "amazon-devices.json"


def _pending_file():
    return config_dir() / "amazon-pending.json"


def _write_private(path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _load_login() -> dict | None:
    try:
        data = json.loads(_login_file().read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    email = str(data.get("email") or "").strip()
    login_data = data.get("login_data")
    if not email or not isinstance(login_data, dict):
        return None
    return {"email": email, "login_data": login_data}


def _save_login(email: str, login_data: dict) -> None:
    _write_private(_login_file(), {"email": email, "login_data": login_data})


def _load_cached_devices() -> list[dict]:
    try:
        data = json.loads(_devices_file().read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    return [row for row in data if isinstance(row, dict) and row.get("serial")]


def _remember_devices(devices: dict[str, AmazonDevice]) -> list[dict]:
    rows = []
    for device in devices.values():
        rows.append(
            {
                "serial": device.serial_number,
                "name": device.account_name or device.serial_number,
                "online": bool(device.online),
                "family": device.device_family or "",
                "model": device.model or "",
            }
        )
    rows.sort(key=lambda row: (not row["online"], row["name"].lower()))
    _write_private(_devices_file(), rows)
    return rows


def _forget_notify_me() -> None:
    old = config_dir() / "alexa.json"
    try:
        old.unlink()
    except OSError:
        pass


def public_status() -> dict:
    global _devices
    _forget_notify_me()
    saved = _load_login()
    if not _devices:
        _devices = _load_cached_devices()
    return {
        "linked": bool(saved),
        "email": saved["email"] if saved else "",
        "devices": _devices,
        "error": _last_error,
    }


def logout() -> dict:
    global _devices, _last_error
    _last_error = ""
    _devices = []
    for path in (_login_file(), _devices_file(), _pending_file()):
        try:
            path.unlink()
        except OSError:
            pass
    status = public_status()
    status["ok"] = True
    status["message"] = "Conta Amazon removida deste computador."
    return status


def _public_error(exc: Exception) -> str:
    text = str(exc).strip()
    lowered = text.lower()
    if "http" in lowered or "openid" in lowered or "token" in lowered or len(text) > 180:
        return "A Amazon recusou esse acesso. Abra o login de novo e cole o endereço da página final."
    return text or "A Amazon recusou esse acesso."


async def _session(email: str, password: str, login_data: dict | None):
    client = ClientSession()
    api = AmazonEchoApi(
        client,
        email,
        password,
        save_data=AmazonSaveDataConfig(path=_dir()),
        login_data=login_data,
    )
    return client, api


def _account_label(login_data: dict) -> str:
    info = login_data.get("customer_info")
    if isinstance(info, dict):
        for key in ("email", "user_email", "name", "given_name"):
            value = str(info.get(key) or "").strip()
            if value:
                return value
    return "Amazon"


def _authorization_code(pasted: str) -> str:
    text = pasted.strip()
    if "http" in text:
        text = text[text.find("http"):].split()[0]
    query = parse_qs(urlparse(text).query)
    code = (query.get("openid.oa2.authorization_code") or [""])[0]
    return unquote(code).strip()


def _load_pending() -> dict | None:
    try:
        data = json.loads(_pending_file().read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    serial = str(data.get("serial") or "")
    verifier = str(data.get("code_verifier") or "")
    created = float(data.get("created") or 0)
    if not serial or not verifier or time.time() - created > 15 * 60:
        return None
    return {"serial": serial, "code_verifier": verifier}


async def _start_amazon_login() -> dict:
    client, api = await _session("amazon", "", None)
    try:
        login = api.login
        verifier = login._create_code_verifier()
        url = login._build_oauth_url(verifier, login._build_client_id(), "pt_BR")
        _write_private(
            _pending_file(),
            {
                "serial": login._serial,
                "code_verifier": verifier.decode(),
                "created": time.time(),
            },
        )
        return {"ok": True, "url": str(url)}
    finally:
        await client.close()


async def _finish_amazon_login(pasted: str) -> dict:
    pending = _load_pending()
    if not pending:
        return {"ok": False, "error": "Abra o login da Amazon de novo. Esse pedido expirou."}
    code = _authorization_code(pasted)
    if not code:
        return {
            "ok": False,
            "error": "Cole o endereço inteiro da página em que a Amazon parou, o que está na barra do navegador.",
        }
    client, api = await _session("amazon", "", None)
    try:
        login = api.login
        login._serial = pending["serial"]
        login_data = await login._register_device(
            {
                "authorization_code": code,
                "code_verifier": pending["code_verifier"].encode(),
            }
        )
        api._session_state_data.login_stored_data = login_data
        await login._domain_refresh_auth_cookies()
        await login._register_device_capabilities()
        await login.obtain_account_customer_id()
        login_data = api._session_state_data.login_stored_data
        login_data["site"] = api._session_state_data.retail_site_url.human_repr().rstrip("/")
        email = _account_label(login_data)
        _save_login(email, login_data)
        try:
            _pending_file().unlink()
        except OSError:
            pass
        try:
            devices = await _load_devices(api)
            rows = _remember_devices(devices)
        except (NoOnlineDevicesError, CannotRetrieveData):
            rows = []
        _save_login(email, api._session_state_data.login_stored_data or login_data)
        return {"ok": True, "devices": rows}
    finally:
        await client.close()


async def _with_stored(after_login):
    saved = _load_login()
    if not saved:
        return {"ok": False, "error": "Entre com a conta Amazon antes."}
    client, api = await _session(saved["email"], "", saved["login_data"])
    try:
        stored = await api.login.login_mode_stored_data()
        result = await after_login(api)
        if isinstance(stored, dict):
            _save_login(saved["email"], stored)
        return result
    finally:
        await client.close()


async def _load_devices(api: AmazonEchoApi) -> dict:
    await api._device_handler.update_devices()
    return api._device_handler.devices


async def _deliver(api: AmazonEchoApi, device: AmazonDevice, text: str, announcement: bool) -> None:
    handler = api._sequence_handler
    errors: list[Exception] = []
    original = handler._post_sequences

    async def post(sequences):
        try:
            await original(sequences)
        except Exception as exc:
            errors.append(exc)
            raise

    handler._post_sequences = post
    if announcement:
        await api.call_alexa_announcement(device, text)
    else:
        await api.call_alexa_speak(device, text)
    pending = list(handler._tasks)
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    if errors:
        raise errors[0]


async def _list_devices() -> dict:
    async def after(api: AmazonEchoApi):
        devices = await _load_devices(api)
        return {"ok": True, "devices": _remember_devices(devices)}

    return await _with_stored(after)


async def _speak(serial: str, text: str, announcement: bool) -> dict:
    async def after(api: AmazonEchoApi):
        devices = await _load_devices(api)
        _remember_devices(devices)
        device = devices.get(serial)
        if device is None:
            return {"ok": False, "error": "Esse aparelho não apareceu na conta Amazon."}
        await _deliver(api, device, text, announcement)
        name = device.account_name or "Echo"
        if announcement:
            return {"ok": True, "message": f"Anúncio enviado para {name}."}
        return {"ok": True, "message": f"Fala enviada para {name}."}

    return await _with_stored(after)


def _finish_result(result: dict) -> dict:
    global _devices, _last_error
    if result.get("ok"):
        _last_error = ""
        if isinstance(result.get("devices"), list):
            _devices = result["devices"]
    elif result.get("error"):
        _last_error = str(result["error"])
    return result


def _run(coro) -> dict:
    with _lock:
        try:
            result = asyncio.run(coro)
        except (CannotAuthenticate, CannotConnect, CannotRetrieveData, NoOnlineDevicesError, WrongMethod) as exc:
            _last_error = _public_error(exc)
            return {"ok": False, "error": _last_error}
        except Exception as exc:
            _last_error = _public_error(exc)
            return {"ok": False, "error": _last_error}
    return _finish_result(result)


def _speak_request(serial: str, text: str) -> tuple[str, str] | dict:
    serial = serial.strip()
    text = " ".join(text.split())
    if not serial:
        return {"ok": False, "error": "Escolha o aparelho."}
    if not text:
        return {"ok": False, "error": "Escreva o que a Alexa deve falar."}
    return serial, text[:400]


async def speak_async(serial: str, text: str, announcement: bool = False) -> dict:
    prepared = _speak_request(serial, text)
    if isinstance(prepared, dict):
        return prepared
    serial, text = prepared
    await asyncio.to_thread(_lock.acquire)
    try:
        return _finish_result(await _speak(serial, text, announcement))
    except (CannotAuthenticate, CannotConnect, CannotRetrieveData, NoOnlineDevicesError, WrongMethod) as exc:
        _last_error = _public_error(exc)
        return {"ok": False, "error": _last_error}
    except Exception as exc:
        _last_error = _public_error(exc)
        return {"ok": False, "error": _last_error}
    finally:
        _lock.release()


def begin_login() -> dict:
    return _run(_start_amazon_login())


def finish_login(pasted: str) -> dict:
    result = _run(_finish_amazon_login(pasted))
    if result.get("ok"):
        status = public_status()
        status["ok"] = True
        status["message"] = "Conta Amazon conectada neste computador."
        return status
    return result


def refresh_devices() -> dict:
    result = _run(_list_devices())
    if result.get("ok"):
        status = public_status()
        status["ok"] = True
        return status
    return result


def speak(serial: str, text: str, announcement: bool) -> dict:
    prepared = _speak_request(serial, text)
    if isinstance(prepared, dict):
        return prepared
    serial, text = prepared
    return _run(_speak(serial, text, announcement))
