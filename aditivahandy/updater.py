"""Aceita um pedido de atualização vindo da plataforma.

A instalação automática ainda não troca os arquivos. O pedido fica em
update-request.json para o instalador futuro ler e aplicar.
"""

import json
from datetime import datetime, timezone

from .config import config_dir


def accept_update(version: str, url: str) -> str:
    target = version.strip().lstrip("v")
    if not target:
        raise ValueError("A plataforma não informou a versão.")
    path = config_dir() / "update-request.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "version": target,
                "url": url.strip(),
                "requested_at": datetime.now(timezone.utc).isoformat(),
                "status": "accepted",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return (
        f"Atualização v{target} aceita. "
        "A instalação automática ainda será ligada; o pedido ficou guardado neste computador."
    )
