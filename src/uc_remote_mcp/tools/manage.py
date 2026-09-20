"""The smaller gaps: entities, activities, macros, activity groups, resources.

Individually unremarkable CRUD, but each one was something that previously had
to be done by calling the API directly.
"""

from typing import Any, Optional

from ..safety.dry_run import apply_mutation
from ._common import get_client, localized

# ------------------------------------------------------------------- entities


async def update_entity(
    entity_id: str,
    name: Optional[str] = None,
    icon: Optional[str] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Rename an entity or change its icon.

    The name is what appears on tiles and in pickers; the icon takes
    ``uc:name`` for a built-in or ``custom:file.png`` for an uploaded one.
    """
    if name is None and icon is None:
        raise ValueError("Provide a name, an icon, or both.")

    client = get_client(host)
    current = await client.get(f"/api/entities/{entity_id}")
    body: dict[str, Any] = {}
    if name is not None:
        body["name"] = {"en": name}
    if icon is not None:
        body["icon"] = icon

    return await apply_mutation(
        client,
        action="update_entity",
        summary=f"update {localized(current.get('name')) or entity_id}"
        + (f" name -> '{name}'" if name else "")
        + (f" icon -> {icon}" if icon else ""),
        change={
            "entity_id": entity_id,
            "from": {"name": localized(current.get("name")), "icon": current.get("icon")},
            "to": {"name": name, "icon": icon},
        },
        do_write=lambda: client.patch(f"/api/entities/{entity_id}", body),
        dry_run=dry_run,
    )


async def delete_entities(
    entity_ids: list[str], dry_run: bool = True, host: Optional[str] = None
) -> dict:
    """
    Remove entities from the remote.

    They come back if their integration still offers them and they are
    configured again -- which is what makes this the cure for an entity stuck
    reporting nothing. Every button mapping and page item using them goes with
    them, so read the preview.
    """
    client = get_client(host)

    return await apply_mutation(
        client,
        action="delete_entities",
        summary=f"delete {len(entity_ids)} entit"
        f"{'y' if len(entity_ids) == 1 else 'ies'}",
        change={"entity_ids": entity_ids},
        do_write=lambda: client.request_with_body(
            "DELETE", "/api/entities", {"entity_ids": entity_ids}
        ),
        dry_run=dry_run,
        warnings=[
            "Buttons and page items referencing these entities are removed too.",
        ],
    )


# ----------------------------------------------------------------- activities


async def delete_activity(
    activity_id: str, dry_run: bool = True, host: Optional[str] = None
) -> dict:
    """
    Delete an activity, with its pages and button mappings.

    The entities it used are not touched -- they belong to their integrations.
    """
    client = get_client(host)
    detail = await client.get(f"/api/activities/{activity_id}")
    pages = (detail.get("options") or {}).get("user_interface", {}).get("pages") or []

    return await apply_mutation(
        client,
        action="delete_activity",
        summary=f"delete activity '{localized(detail.get('name')) or activity_id}' "
        f"({len(pages)} pages)",
        change={"activity_id": activity_id, "pages": [p.get("name") for p in pages]},
        do_write=lambda: client.delete(f"/api/activities/{activity_id}"),
        dry_run=dry_run,
    )


async def clear_button_mapping(
    scope_id: str,
    button: str,
    press: Optional[str] = None,
    scope: str = "activity",
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Unbind a button, or just one of its presses.

    ``press`` is "short_press" or "long_press"; omit it to clear both. scope is
    "activity" or "remote".
    """
    base = {"activity": "activities", "remote": "remotes"}.get(scope)
    if base is None:
        raise ValueError("scope must be 'activity' or 'remote'")
    if press not in (None, "short_press", "long_press"):
        raise ValueError("press must be 'short_press', 'long_press', or omitted")

    client = get_client(host)
    path = f"/api/{base}/{scope_id}/buttons/{button}" + (f"/{press}" if press else "")

    return await apply_mutation(
        client,
        action="clear_button_mapping",
        summary=f"clear {button}{' ' + press if press else ''} on {scope} {scope_id}",
        change={"scope": scope, "scope_id": scope_id, "button": button, "press": press},
        do_write=lambda: client.delete(path),
        dry_run=dry_run,
    )


# --------------------------------------------------------------------- macros


async def list_macros(host: Optional[str] = None) -> dict:
    """Macros on the remote, with the length of each sequence."""
    client = get_client(host)
    macros = await client.get_list("/api/macros")
    out = []
    for m in macros:
        detail = await client.get(f"/api/macros/{m.get('entity_id')}")
        seq = (detail.get("options") or {}).get("sequence") or []
        out.append(
            {
                "macro_id": m.get("entity_id"),
                "name": localized(m.get("name")),
                "steps": len(seq),
            }
        )
    return {"count": len(out), "macros": out}


async def get_macro(macro_id: str, host: Optional[str] = None) -> dict:
    """One macro's full step sequence."""
    client = get_client(host)
    d = await client.get(f"/api/macros/{macro_id}")
    opts = d.get("options") or {}
    return {
        "macro_id": d.get("entity_id"),
        "name": localized(d.get("name")),
        "entities": [
            e.get("entity_id") or e.get("id")
            for e in (opts.get("included_entities") or [])
        ],
        "sequence": opts.get("sequence") or [],
    }


def _macro_steps(steps: list[dict]) -> list[dict]:
    """Accept a friendly step list and emit what the API wants.

    Steps are either {"command": ..., "entity_id": ..., "params": {...}} or
    {"delay": milliseconds}.
    """
    out = []
    for i, s in enumerate(steps):
        if "delay" in s:
            out.append({"type": "delay", "delay": int(s["delay"])})
            continue
        if not s.get("command") or not s.get("entity_id"):
            raise ValueError(
                f"step {i}: needs 'command' and 'entity_id', or 'delay' in milliseconds"
            )
        cmd: dict[str, Any] = {"cmd_id": s["command"], "entity_id": s["entity_id"]}
        if s.get("params"):
            cmd["params"] = s["params"]
        out.append({"type": "command", "command": cmd})
    return out


async def set_macro(
    name: str,
    steps: list[dict],
    macro_id: Optional[str] = None,
    description: Optional[str] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Create a macro, or replace an existing one's steps by passing ``macro_id``.

    Steps are ``{"command": "media_player.on", "entity_id": "...", "params": {}}``
    or ``{"delay": 1500}`` in milliseconds.

    A macro keeps its own list of permitted entities, exactly like an activity,
    and a step naming an entity outside it is rejected -- so the entity list is
    derived from the steps and written first.
    """
    client = get_client(host)
    sequence = _macro_steps(steps)
    entity_ids = sorted(
        {s["command"]["entity_id"] for s in sequence if s["type"] == "command"}
    )

    async def _write() -> dict:
        target = macro_id
        if target is None:
            created = await client.post(
                "/api/macros",
                {"name": {"en": name}, "options": {"entity_ids": entity_ids}},
            )
            target = created.get("entity_id") or created.get("id")
        else:
            # Entities first: the sequence is refused if it names one that the
            # macro is not allowed to use.
            await client.patch(
                f"/api/macros/{target}", {"options": {"entity_ids": entity_ids}}
            )
        body: dict[str, Any] = {"options": {"sequence": sequence}}
        if macro_id is not None:
            body["name"] = {"en": name}
        if description:
            body["description"] = {"en": description}
        await client.patch(f"/api/macros/{target}", body)
        return {"macro_id": target, "steps": len(sequence), "entities": entity_ids}

    return await apply_mutation(
        client,
        action="set_macro",
        summary=(f"update macro {macro_id}" if macro_id else f"create macro '{name}'")
        + f" with {len(sequence)} steps",
        change={"macro_id": macro_id, "name": name, "steps": sequence},
        do_write=_write,
        dry_run=dry_run,
    )


async def delete_macro(
    macro_id: str, dry_run: bool = True, host: Optional[str] = None
) -> dict:
    """Delete a macro. Anything pointing at it loses that binding."""
    client = get_client(host)
    d = await client.get(f"/api/macros/{macro_id}")

    return await apply_mutation(
        client,
        action="delete_macro",
        summary=f"delete macro '{localized(d.get('name')) or macro_id}'",
        change={"macro_id": macro_id},
        do_write=lambda: client.delete(f"/api/macros/{macro_id}"),
        dry_run=dry_run,
    )


# ------------------------------------------------------------ activity groups


async def list_activity_groups(host: Optional[str] = None) -> dict:
    """
    Activity groups, which decide what happens when you switch between
    activities.

    A group set to turn unused entities off will power devices on and off as
    you move between its activities -- which is a surprise if you expected a
    tile to just open a page. Its members are listed here for that reason.
    """
    client = get_client(host)
    groups = await client.get_list("/api/activity_groups")
    out = []
    for g in groups:
        gid = g.get("group_id")
        # The list endpoint omits options, so a group that powers devices would
        # report as if it did nothing. Read each one.
        detail = await client.get(f"/api/activity_groups/{gid}")
        out.append(
            {
                "group_id": gid,
                "name": localized(g.get("name")),
                "activity_ids": detail.get("activity_ids") or [],
                "turn_off_unused_entities": (detail.get("options") or {}).get(
                    "turn_off_unused_entities"
                ),
            }
        )
    return {"groups": out}


async def update_activity_group(
    group_id: str,
    activity_ids: Optional[list[str]] = None,
    turn_off_unused_entities: Optional[str] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Change a group's members or its switching behaviour.

    An empty ``activity_ids`` removes every member, which is how you stop a
    group powering devices without deleting it -- and the default group should
    not be deleted.
    """
    if activity_ids is None and turn_off_unused_entities is None:
        raise ValueError("Provide activity_ids, turn_off_unused_entities, or both.")

    client = get_client(host)
    before = await client.get(f"/api/activity_groups/{group_id}")
    body: dict[str, Any] = {}
    if activity_ids is not None:
        body["activity_ids"] = activity_ids
    if turn_off_unused_entities is not None:
        body["options"] = {"turn_off_unused_entities": turn_off_unused_entities}

    return await apply_mutation(
        client,
        action="update_activity_group",
        summary=f"update activity group {group_id}",
        change={
            "group_id": group_id,
            "from": {
                "activity_ids": before.get("activity_ids"),
                "turn_off_unused_entities": (before.get("options") or {}).get(
                    "turn_off_unused_entities"
                ),
            },
            "to": body,
        },
        do_write=lambda: client.patch(f"/api/activity_groups/{group_id}", body),
        dry_run=dry_run,
    )


# ------------------------------------------------------------------ resources


async def list_resources(
    resource_type: str = "Icon", host: Optional[str] = None
) -> dict:
    """
    Uploaded resources. ``resource_type`` is "Icon", "CustomIcon" or similar --
    call it with no argument to see what the remote reports.
    """
    client = get_client(host)
    items = await client.get_list(f"/api/resources/{resource_type}")
    return {
        "type": resource_type,
        "count": len(items),
        "resources": [
            {"id": i.get("id"), "size_bytes": i.get("size")} for i in items
        ],
    }


async def upload_resource(
    file_path: str,
    resource_type: str = "Icon",
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Upload a custom icon or image, referenced afterwards as ``custom:<filename>``.

    Icons are 90x90 PNG or JPG, 32 KB at most. Two things to know: replacing an
    existing file means deleting it first, since there is no overwrite; and the
    UI crops transparent margins and scales what remains, so a padded icon still
    renders huge unless a nearly invisible pixel holds each corner.
    """
    client = get_client(host)

    return await apply_mutation(
        client,
        action="upload_resource",
        summary=f"upload {file_path} as a {resource_type}",
        change={"type": resource_type, "file": file_path},
        do_write=lambda: client.post_file(f"/api/resources/{resource_type}", file_path),
        dry_run=dry_run,
    )


async def delete_resource(
    resource_id: str,
    resource_type: str = "Icon",
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Delete an uploaded resource.

    Anything still referencing ``custom:<id>`` will render nothing, so check
    first unless you are replacing it with the same filename.
    """
    client = get_client(host)

    return await apply_mutation(
        client,
        action="delete_resource",
        summary=f"delete {resource_type} '{resource_id}'",
        change={"type": resource_type, "id": resource_id},
        do_write=lambda: client.delete(f"/api/resources/{resource_type}/{resource_id}"),
        dry_run=dry_run,
    )
