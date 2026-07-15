"""Shared helpers for tools."""

from typing import Optional

from ..client.rest import UCClient
from ..config import get_remote


def get_client(host: Optional[str] = None) -> UCClient:
    """Build a REST client from saved config. Raises if no remote is set up."""
    cfg = get_remote(host)
    if not cfg:
        raise ValueError("No remote configured. Run setup_remote first, or pass host.")
    return UCClient(cfg.host, cfg.port, cfg.api_key)


def localized(name) -> str:
    """Pick a human-readable string from a UC localized-name dict."""
    if isinstance(name, str):
        return name
    if isinstance(name, dict):
        return name.get("en_US") or name.get("en") or next(iter(name.values()), "")
    return ""


def binding(press: Optional[dict]) -> Optional[dict]:
    """
    Normalize one button press target. UC uses `cmd_id`; IR-remote bindings
    omit `entity_id` (the command is a local IR code).
    """
    if not press:
        return None
    out = {"command": press.get("cmd_id")}
    if press.get("entity_id"):
        out["entity_id"] = press["entity_id"]
    if press.get("params"):
        out["params"] = press["params"]
    return out


def normalize_button_mapping(button_mapping) -> list[dict]:
    """Turn a raw options.button_mapping list into {button, short_press?, long_press?}."""
    out = []
    for b in button_mapping or []:
        entry = {"button": b.get("button")}
        sp = binding(b.get("short_press"))
        lp = binding(b.get("long_press"))
        if sp:
            entry["short_press"] = sp
        if lp:
            entry["long_press"] = lp
        out.append(entry)
    return out


def normalize_item(it: dict) -> dict:
    """Normalize one UI-page item."""
    out = {"type": it.get("type"), "location": it.get("location"), "size": it.get("size")}
    if it.get("text"):
        out["text"] = localized(it.get("text"))
    if it.get("icon"):
        out["icon"] = it.get("icon")
    if it.get("media_player_id"):
        out["media_player_id"] = it.get("media_player_id")
    cmd = it.get("command")
    if cmd:
        c = {"command": cmd.get("cmd_id")}
        if cmd.get("entity_id"):
            c["entity_id"] = cmd["entity_id"]
        if cmd.get("params"):
            c["params"] = cmd["params"]
        out["command"] = c
    return out


def pages_of(detail: dict) -> list[dict]:
    """Extract the embedded UI pages from an activity or remote detail object."""
    ui = (detail.get("options") or {}).get("user_interface") or {}
    return ui.get("pages") or []
