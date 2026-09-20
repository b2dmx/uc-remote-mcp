"""Remote-entities: the IR devices you add yourself.

A remote-entity is what the remote calls a device it drives by infrared. Unlike
everything else on the remote it comes from no integration -- you create it from
a codeset, and the remote fills in its command list from that codeset.

Creating one is the only place the IR code database becomes useful on its own:
pick a manufacturer with ``list_ir_manufacturers``, a codeset with
``list_ir_codesets``, then create the device here. Its commands are then
ordinary commands -- ``send_command`` fires them, ``set_button_mapping`` binds
them, ``create_ui_page`` puts them on screen.
"""

from typing import Any, Optional

from ..safety.dry_run import apply_mutation
from ._common import get_client, localized


async def list_remote_entities(host: Optional[str] = None) -> dict:
    """
    IR devices defined on this remote, with the codeset and emitter each uses.

    ``output`` is which emitter actually fires. A device with none falls back to
    the remote's internal blaster, which needs line of sight.
    """
    client = get_client(host)
    items = await client.get_list("/api/remotes")
    out = []
    for e in items:
        detail = await client.get(f"/api/remotes/{e['entity_id']}")
        opts = detail.get("options") or {}
        ir = opts.get("ir") or {}
        out.append(
            {
                "entity_id": e.get("entity_id"),
                "name": localized(e.get("name")),
                "icon": e.get("icon"),
                "kind": opts.get("kind"),
                "codeset": (ir.get("codeset") or {}).get("name"),
                "codeset_id": (ir.get("codeset") or {}).get("id"),
                "output": ir.get("output"),
                "cmd_delay_ms": ir.get("cmd_delay"),
                "repeat": ir.get("repeat"),
                "commands": len(opts.get("simple_commands") or []),
            }
        )
    return {"count": len(out), "remotes": out}


async def create_ir_remote(
    name: str,
    codeset_id: Optional[str] = None,
    clone_from: Optional[str] = None,
    icon: Optional[str] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Create an IR device from a codeset.

    ``codeset_id`` takes either a built-in codeset (from ``list_ir_codesets``)
    or a learned one (from ``list_custom_ir_codesets``) -- the remote works out
    which. ``clone_from`` copies an existing remote-entity instead.

    The device's command list comes from the codeset, so it arrives usable: the
    commands are ready for send_command, button mappings and pages. What it does
    not arrive with is an emitter, so it falls back to the internal blaster --
    set_ir_output points it at a dock.
    """
    if bool(codeset_id) == bool(clone_from):
        raise ValueError("Pass either codeset_id or clone_from, not both or neither.")

    client = get_client(host)
    body: dict[str, Any] = {"name": {"en": name}}
    if codeset_id:
        body["codeset_id"] = codeset_id
    else:
        body["clone_from"] = clone_from
    if icon:
        body["icon"] = icon

    async def _create() -> dict:
        created = await client.post("/api/remotes", body)
        eid = created.get("entity_id")
        detail = await client.get(f"/api/remotes/{eid}")
        opts = detail.get("options") or {}
        ir = opts.get("ir") or {}
        return {
            "entity_id": eid,
            "codeset": (ir.get("codeset") or {}).get("name"),
            "commands": opts.get("simple_commands") or [],
        }

    return await apply_mutation(
        client,
        action="create_ir_remote",
        summary=f"create IR device '{name}'"
        + (f" from codeset {codeset_id}" if codeset_id else f" cloned from {clone_from}"),
        change={"name": name, "codeset_id": codeset_id, "clone_from": clone_from},
        do_write=_create,
        dry_run=dry_run,
    )


async def set_ir_output(
    entity_id: str,
    emitter_device_id: Optional[str] = None,
    port_id: Optional[str] = None,
    cmd_delay_ms: Optional[int] = None,
    repeat: Optional[int] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Choose which emitter an IR device sends through, and how.

    ``emitter_device_id`` and ``port_id`` come from ``list_ir_emitters``: use
    "internal" for the remote's own blaster, or a dock id with port "0" for all
    of that dock's outputs. ``cmd_delay_ms`` is the gap between commands -- raise
    it for a device that drops rapid presses -- and ``repeat`` sends each command
    more than once for one that misses them.

    Settings not passed are left alone, but the whole ``ir`` block is rewritten
    underneath, so it is read first.
    """
    client = get_client(host)
    detail = await client.get(f"/api/remotes/{entity_id}")
    opts = detail.get("options") or {}
    ir = dict(opts.get("ir") or {})
    if not ir:
        raise ValueError(
            f"{entity_id} has no IR settings -- it may not be an IR device."
        )
    before = {
        "output": ir.get("output"),
        "cmd_delay": ir.get("cmd_delay"),
        "repeat": ir.get("repeat"),
    }

    if emitter_device_id:
        ir["output"] = {"device_id": emitter_device_id, "port_id": port_id or "0"}
    if cmd_delay_ms is not None:
        ir["cmd_delay"] = cmd_delay_ms
    if repeat is not None:
        ir["repeat"] = repeat

    return await apply_mutation(
        client,
        action="set_ir_output",
        summary=f"IR output for '{localized(detail.get('name')) or entity_id}': "
        + ", ".join(
            f"{k} {before.get(k)!r} -> {ir.get(k)!r}"
            for k in ("output", "cmd_delay", "repeat")
            if before.get(k) != ir.get(k)
        ),
        change={"entity_id": entity_id, "from": before, "to": ir},
        do_write=lambda: client.patch(f"/api/remotes/{entity_id}", {"options": {"ir": ir}}),
        dry_run=dry_run,
    )


async def delete_remote_entity(
    entity_id: str, dry_run: bool = True, host: Optional[str] = None
) -> dict:
    """
    Delete an IR device.

    Its pages and button mappings go with it, and any activity using it loses
    those commands. The codeset it was built from is untouched.
    """
    client = get_client(host)
    detail = await client.get(f"/api/remotes/{entity_id}")
    opts = detail.get("options") or {}
    pages = ((opts.get("user_interface") or {}).get("pages")) or []

    return await apply_mutation(
        client,
        action="delete_remote_entity",
        summary=f"delete IR device '{localized(detail.get('name')) or entity_id}' "
        f"({len(pages)} pages)",
        change={"entity_id": entity_id, "name": localized(detail.get("name"))},
        do_write=lambda: client.delete(f"/api/remotes/{entity_id}"),
        dry_run=dry_run,
        warnings=["Activities using this device lose its commands."],
    )
