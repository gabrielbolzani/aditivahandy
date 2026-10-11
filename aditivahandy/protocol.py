import uuid
from datetime import datetime, timezone


def envelope(message_type: str, payload: dict | None = None, message_id: str | None = None) -> dict:
    return {
        "v": 1,
        "type": message_type,
        "id": message_id or str(uuid.uuid4()),
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "payload": payload or {},
    }


def map_state(raw) -> str:
    value = str(raw or "").strip().lower()
    if value in ("printing", "running", "prepare", "preparing", "slicing"):
        return "printing"
    if value in ("pause", "paused"):
        return "paused"
    if value in ("finish", "finished", "complete", "completed"):
        return "finished"
    if value in ("failed", "error"):
        return "error"
    if value in ("offline", "off", "disconnected", "unknown"):
        return "offline"
    return "idle"
