"""The home screen: profiles, their pages of tiles, and groups.

This is what you see when the remote wakes -- the grid of devices. A profile
owns pages, a page holds tiles, and a tile points at either an entity or a
group of entities.

Two things the API does not make obvious:

* A tile's ``pos`` is returned on read but **ignored on write** -- order comes
  from the array. So reordering means sending the whole list in the order you
  want, which is what ``set_home_tiles`` does.
* A group renders as an extra page on the home carousel. A leftover group is
  how a "phantom" blank tile appears, and deleting the group is the only fix.
"""

from typing import Optional

from ..safety.dry_run import apply_mutation
from ._common import get_client, localized


async def _default_profile(client) -> str:
    """The profile currently in use, which is the one people mean."""
    cfg = await client.get("/api/cfg/profile")
    pid = cfg.get("profile_id") if isinstance(cfg, dict) else None
    if pid:
        return pid
    profiles = await client.get_list("/api/profiles")
    if not profiles:
        raise ValueError("The remote reports no profiles.")
    return profiles[0].get("profile_id")


async def list_profiles(host: Optional[str] = None) -> dict:
    """Profiles on the remote, and which one is active."""
    client = get_client(host)
    profiles = await client.get_list("/api/profiles")
    active = await _default_profile(client)
    return {
        "active_profile_id": active,
        "profiles": [
            {
                "profile_id": p.get("profile_id"),
                "name": localized(p.get("name")),
                "restricted": p.get("restricted"),
            }
            for p in profiles
        ],
    }


async def get_home_layout(
    profile_id: Optional[str] = None, host: Optional[str] = None
) -> dict:
    """
    The home screen: every page, its tiles in order, and any groups.

    Tiles are what you tap to open a device. A tile naming a group opens that
    group's own page instead of an activity.
    """
    client = get_client(host)
    profile_id = profile_id or await _default_profile(client)
    pages = await client.get_list(f"/api/profiles/{profile_id}/pages")
    groups = await client.get_list(f"/api/profiles/{profile_id}/groups")
    return {
        "profile_id": profile_id,
        "pages": [
            {
                "page_id": p.get("page_id"),
                "name": localized(p.get("name")),
                "pos": p.get("pos"),
                "tiles": [
                    {"entity_id": i.get("entity_id"), "group_id": i.get("group_id")}
                    for i in (p.get("items") or [])
                ],
            }
            for p in pages
        ],
        # Groups add their own page to the carousel; an unwanted one shows up
        # as a stray tile or blank page.
        "groups": [
            {
                "group_id": g.get("group_id"),
                "name": localized(g.get("name")),
                "entities": g.get("entities") or [],
            }
            for g in groups
        ],
    }


async def set_home_tiles(
    page_id: str,
    entity_ids: list[str],
    profile_id: Optional[str] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Replace a home page's tiles, in the order given.

    This is also how tiles are reordered: position comes from the order of the
    list, not from any position field. Send the complete list -- anything left
    out is removed from the page.
    """
    client = get_client(host)
    profile_id = profile_id or await _default_profile(client)
    page = await client.get(f"/api/profiles/{profile_id}/pages/{page_id}")
    before = [i.get("entity_id") or i.get("group_id") for i in (page.get("items") or [])]
    items = [{"entity_id": e} for e in entity_ids]

    return await apply_mutation(
        client,
        action="set_home_tiles",
        summary=f"set {len(entity_ids)} tiles on home page "
        f"'{localized(page.get('name')) or page_id}'",
        change={
            "profile_id": profile_id,
            "page_id": page_id,
            "from": before,
            "to": entity_ids,
        },
        do_write=lambda: client.patch(
            f"/api/profiles/{profile_id}/pages/{page_id}", {"items": items}
        ),
        dry_run=dry_run,
        warnings=(
            ["Anything not in the list is removed from this page."]
            if set(before) - set(entity_ids)
            else None
        ),
    )


async def create_home_page(
    name: str,
    entity_ids: Optional[list[str]] = None,
    pos: Optional[int] = None,
    profile_id: Optional[str] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """Add a page of tiles to the home screen."""
    client = get_client(host)
    profile_id = profile_id or await _default_profile(client)
    body: dict = {"name": name, "items": [{"entity_id": e} for e in (entity_ids or [])]}
    if pos is not None:
        body["pos"] = pos

    return await apply_mutation(
        client,
        action="create_home_page",
        summary=f"create home page '{name}' with {len(entity_ids or [])} tiles",
        change={"profile_id": profile_id, "name": name, "entity_ids": entity_ids},
        do_write=lambda: client.post(f"/api/profiles/{profile_id}/pages", body),
        dry_run=dry_run,
    )


async def delete_home_page(
    page_id: str,
    profile_id: Optional[str] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """Remove a page from the home screen. The activities on it are untouched."""
    client = get_client(host)
    profile_id = profile_id or await _default_profile(client)
    page = await client.get(f"/api/profiles/{profile_id}/pages/{page_id}")

    return await apply_mutation(
        client,
        action="delete_home_page",
        summary=f"delete home page '{localized(page.get('name')) or page_id}' "
        f"({len(page.get('items') or [])} tiles)",
        change={"profile_id": profile_id, "page_id": page_id},
        do_write=lambda: client.delete(f"/api/profiles/{profile_id}/pages/{page_id}"),
        dry_run=dry_run,
    )


async def set_profile_group(
    name: str,
    entity_ids: list[str],
    group_id: Optional[str] = None,
    icon: Optional[str] = None,
    profile_id: Optional[str] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Create a group of entities, or update one by passing its ``group_id``.

    A group appears as its own page on the home carousel, with a switch derived
    from what its entities can do.
    """
    client = get_client(host)
    profile_id = profile_id or await _default_profile(client)
    body: dict = {"name": name, "entities": entity_ids}
    if icon:
        body["icon"] = icon
    base = f"/api/profiles/{profile_id}/groups"

    return await apply_mutation(
        client,
        action="set_profile_group",
        summary=(f"update group {group_id}" if group_id else f"create group '{name}'")
        + f" with {len(entity_ids)} entities",
        change={"profile_id": profile_id, "group_id": group_id, "name": name,
                "entities": entity_ids},
        do_write=(
            (lambda: client.patch(f"{base}/{group_id}", body))
            if group_id
            else (lambda: client.post(base, body))
        ),
        dry_run=dry_run,
    )


async def delete_profile_group(
    group_id: str,
    profile_id: Optional[str] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Delete a group.

    Worth knowing: a forgotten group is the usual cause of a stray or blank
    tile on the home carousel, because every group renders its own page.
    """
    client = get_client(host)
    profile_id = profile_id or await _default_profile(client)

    return await apply_mutation(
        client,
        action="delete_profile_group",
        summary=f"delete group {group_id}",
        change={"profile_id": profile_id, "group_id": group_id},
        do_write=lambda: client.delete(f"/api/profiles/{profile_id}/groups/{group_id}"),
        dry_run=dry_run,
    )
