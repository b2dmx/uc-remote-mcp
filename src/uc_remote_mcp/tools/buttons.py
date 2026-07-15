"""Button-mapping tool: get_button_mapping across activity / remote / device scopes."""

from typing import Optional

from ._common import get_client, localized, normalize_button_mapping


async def _all_scopes(client):
    """Yield (kind, detail) for every activity and remote-entity that carries
    a button_mapping. Used by the 'device' reverse lookup."""
    acts = await client.get_list("/api/activities")
    for a in acts if isinstance(acts, list) else []:
        yield "activity", await client.get(f"/api/activities/{a['entity_id']}")
    remotes = await client.get_list("/api/remotes")
    for r in remotes if isinstance(remotes, list) else []:
        yield "remote", await client.get(f"/api/remotes/{r['entity_id']}")


async def get_button_mapping(
    scope: str,
    scope_id: Optional[str] = None,
    host: Optional[str] = None,
) -> dict:
    """
    Return physical-button -> command bindings.

    scope:
      - "activity": bindings on one activity.   Requires scope_id = activity_id.
      - "remote":   bindings on one remote-entity (e.g. an IR remote).
                    Requires scope_id = remote entity_id.
      - "device":   every binding (across all activities and remotes) that targets
                    one device.  Requires scope_id = the target device/entity_id.

    Each binding: {button, short_press:{command, entity_id?, params?}, long_press?}.
    IR-remote bindings have no entity_id (the command is a local IR code).
    """
    client = get_client(host)
    scope = scope.lower()

    if scope == "activity":
        if not scope_id:
            raise ValueError("scope='activity' requires scope_id (activity_id).")
        a = await client.get(f"/api/activities/{scope_id}")
        return {
            "scope": "activity",
            "scope_id": scope_id,
            "name": localized(a.get("name")),
            "buttons": normalize_button_mapping((a.get("options") or {}).get("button_mapping")),
        }

    if scope == "remote":
        if not scope_id:
            raise ValueError("scope='remote' requires scope_id (remote entity_id).")
        r = await client.get(f"/api/remotes/{scope_id}")
        return {
            "scope": "remote",
            "scope_id": scope_id,
            "name": localized(r.get("name")),
            "kind": (r.get("options") or {}).get("kind"),
            "buttons": normalize_button_mapping((r.get("options") or {}).get("button_mapping")),
        }

    if scope == "device":
        if not scope_id:
            raise ValueError("scope='device' requires scope_id (target entity_id).")
        matches: list[dict] = []
        async for kind, detail in _all_scopes(client):
            src_id = detail.get("entity_id")
            src_name = localized(detail.get("name"))
            for b in normalize_button_mapping((detail.get("options") or {}).get("button_mapping")):
                for press in ("short_press", "long_press"):
                    bind = b.get(press)
                    if bind and bind.get("entity_id") == scope_id:
                        matches.append(
                            {
                                "source": kind,
                                "source_id": src_id,
                                "source_name": src_name,
                                "button": b["button"],
                                "press": press,
                                "command": bind["command"],
                                "params": bind.get("params", {}),
                            }
                        )
        return {"scope": "device", "scope_id": scope_id, "bindings": matches}

    raise ValueError(f"Unknown scope '{scope}'. Use activity, remote, or device.")
