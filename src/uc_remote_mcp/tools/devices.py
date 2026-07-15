"""Device (entity) tools: list_devices, get_device, list_device_commands."""

from typing import Optional

from ._common import get_client, localized


async def list_devices(
    host: Optional[str] = None, entity_type: Optional[str] = None
) -> list[dict]:
    """
    List all configured devices (entities) on the remote.

    A physical device may appear as several entities (e.g. an LG TV exposes both
    a 'media_player' and a 'remote' entity). Optionally filter by entity_type
    (media_player, remote, activity, macro, light, switch, sensor, ...).

    Returns list of {id, name, type, integration, device_class, state}.
    """
    client = get_client(host)
    entities = await client.get_list("/api/entities")
    if not isinstance(entities, list):
        entities = []

    result = []
    for e in entities:
        if entity_type and e.get("entity_type") != entity_type:
            continue
        result.append(
            {
                "id": e.get("entity_id"),
                "name": localized(e.get("name")),
                "type": e.get("entity_type"),
                "integration": e.get("integration_id"),
                "device_class": e.get("device_class", ""),
                "state": (e.get("attributes") or {}).get("state"),
            }
        )
    return result


async def get_device(device_id: str, host: Optional[str] = None) -> dict:
    """
    Full configuration for one device (entity): features, available commands,
    current attributes, and options.
    """
    client = get_client(host)
    e = await client.get(f"/api/entities/{device_id}")
    return {
        "id": e.get("entity_id"),
        "name": localized(e.get("name")),
        "type": e.get("entity_type"),
        "integration": e.get("integration_id"),
        "device_class": e.get("device_class", ""),
        "icon": e.get("icon", ""),
        "features": e.get("features", []) or [],
        "simple_commands": (e.get("options") or {}).get("simple_commands", []) or [],
        "attributes": e.get("attributes", {}),
        "options": e.get("options", {}),
    }


async def list_device_commands(device_id: str, host: Optional[str] = None) -> dict:
    """
    Commands a device exposes, for picking when mapping buttons.

    Returns {features, simple_commands}:
      - features: standard command groups (on_off, volume, dpad, play_pause, ...)
      - simple_commands: device-specific extra commands (TOP_MENU, NETFLIX, ...)
    """
    client = get_client(host)
    e = await client.get(f"/api/entities/{device_id}")
    return {
        "id": e.get("entity_id"),
        "name": localized(e.get("name")),
        "type": e.get("entity_type"),
        "features": e.get("features", []) or [],
        "simple_commands": (e.get("options") or {}).get("simple_commands", []) or [],
    }
