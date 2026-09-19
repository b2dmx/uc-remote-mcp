"""Activity tools: list_activities, get_activity."""

from typing import Optional

from ..safety.dry_run import apply_mutation
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


async def create_activity(
    name: str,
    icon: Optional[str] = None,
    description: Optional[str] = None,
    entity_ids: Optional[list[str]] = None,
    clone_from: Optional[str] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Create an activity -- a "device" on the remote's home screen.

    Give it ``entity_ids`` to build from scratch, or ``clone_from`` to copy an
    existing activity, macro or remote-entity; the two are mutually exclusive.
    Entities can be added later with add_scope_entities.

    Two behaviours worth knowing, both handled here:

    * The remote creates an empty, unnamed first page with every new activity.
      It is removed, so the activity starts clean and pages appear in the order
      you add them.
    * A new activity joins the **default activity group** automatically. If that
      group is configured to turn unused entities off, selecting this activity's
      tile will power devices on and off. The result says whether it joined.
    """
    if entity_ids and clone_from:
        raise ValueError(
            "Pass entity_ids or clone_from, not both -- the API rejects it."
        )

    client = get_client(host)
    body: dict = {"name": {"en": name}}
    if icon:
        body["icon"] = icon
    if description:
        body["description"] = {"en": description}
    if clone_from:
        body["clone_from"] = clone_from
    elif entity_ids:
        body["options"] = {"entity_ids": entity_ids}

    async def _create() -> dict:
        created = await client.post("/api/activities", body)
        activity_id = created.get("entity_id") or created.get("id")
        out: dict = {"activity_id": activity_id}

        detail = await client.get(f"/api/activities/{activity_id}")
        pages = pages_of(detail)
        for page in pages:
            if not page.get("items"):
                await client.delete(
                    f"/api/activities/{activity_id}/ui/pages/{page['page_id']}"
                )
                out["removed_empty_page"] = page["page_id"]

        # Say so rather than let it be discovered by a tile powering the room.
        try:
            group = await client.get("/api/activity_groups/default")
            members = group.get("activity_ids") or []
            if activity_id in members:
                out["joined_default_activity_group"] = True
                if (group.get("options") or {}).get("turn_off_unused_entities") not in (
                    None,
                    "never",
                ):
                    out["warning"] = (
                        "It joined the default activity group, which turns unused "
                        "entities off -- selecting its tile will power devices on "
                        "and off. Remove it from the group if that is not wanted."
                    )
        except Exception:  # noqa: BLE001 -- reporting only; creation succeeded
            pass
        return out

    return await apply_mutation(
        client,
        action="create_activity",
        summary=f"create activity '{name}'"
        + (f" cloned from {clone_from}" if clone_from else "")
        + (f" with {len(entity_ids)} entities" if entity_ids else ""),
        change={
            "name": name,
            "icon": icon,
            "entity_ids": entity_ids,
            "clone_from": clone_from,
        },
        do_write=_create,
        dry_run=dry_run,
    )
