"""Activity tools: list_activities, get_activity."""

from typing import Optional

from ._common import get_client, localized, normalize_button_mapping, pages_of


async def list_activities(host: Optional[str] = None) -> list[dict]:
    """
    List all activities with id, name, state, and the entities each includes.
    Returns {id, name, state, description, included_entities:[{id,name,type}]}.
    """
    client = get_client(host)
    acts = await client.get_list("/api/activities")
    if not isinstance(acts, list):
        acts = []

    result = []
    for a in acts:
        included = (a.get("options") or {}).get("included_entities") or []
        result.append(
            {
                "id": a.get("entity_id"),
                "name": localized(a.get("name")),
                "state": (a.get("attributes") or {}).get("state"),
                "description": localized(a.get("description")),
                "included_entities": [
                    {
                        "id": e.get("entity_id"),
                        "name": localized(e.get("name")),
                        "type": e.get("entity_type"),
                    }
                    for e in included
                ],
            }
        )
    return result


async def get_activity(activity_id: str, host: Optional[str] = None) -> dict:
    """
    Full activity config: included entities (with the commands each exposes),
    physical-button overrides, and the embedded UI pages.
    """
    client = get_client(host)
    a = await client.get(f"/api/activities/{activity_id}")
    opts = a.get("options") or {}

    included = []
    for e in opts.get("included_entities") or []:
        included.append(
            {
                "id": e.get("entity_id"),
                "type": e.get("entity_type"),
                "name": localized(e.get("name")),
                "integration": localized((e.get("integration") or {}).get("name")),
                "entity_commands": e.get("entity_commands") or [],
                "simple_commands": e.get("simple_commands") or [],
            }
        )

    pages = pages_of(a)

    return {
        "id": a.get("entity_id"),
        "name": localized(a.get("name")),
        "state": (a.get("attributes") or {}).get("state"),
        "description": localized(a.get("description")),
        "ready_check": opts.get("ready_check"),
        "included_entities": included,
        "button_mapping": normalize_button_mapping(opts.get("button_mapping")),
        "pages": [
            {
                "page_id": p.get("page_id"),
                "name": localized(p.get("name")),
                "grid": p.get("grid"),
                "item_count": len(p.get("items") or []),
            }
            for p in pages
        ],
    }
