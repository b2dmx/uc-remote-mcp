"""Phase 2 mutation tools. All default to dry_run=True and auto-backup before writing."""

from typing import Optional

from ._common import get_client, localized
from ..safety.backup import create_backup
from ..safety.dry_run import apply_mutation
from ..safety.validate import validate_activity_command, validate_remote_command


async def send_command(
    device_id: str,
    command: str,
    params: Optional[dict] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Fire a one-off command at a device (entity), for debugging / "does this work".

    PUT /api/entities/{id}/command with {cmd_id, params?}. This is a transient
    action (it does not change saved config) but it DOES affect the device, so it
    still defaults to dry_run=True. No backup is taken (nothing persistent changes).

    Args:
        device_id: target entity_id.
        command: cmd_id to send (e.g. "media_player.volume_up" or "NETFLIX").
        params: optional command params.
        dry_run: when True (default), describes the call without sending it.
    """
    client = get_client(host)

    # Best-effort validation against the bare entity (features + simple_commands
    # aren't authoritative for entity_commands, so only warn, never block).
    warnings: list[str] = []
    try:
        e = await client.get(f"/api/entities/{device_id}")
        simple = set((e.get("options") or {}).get("simple_commands") or [])
        # entity_commands aren't on the bare object; accept namespaced cmds silently.
        if simple and command not in simple and "." not in command:
            warnings.append(
                f"'{command}' is not in this device's simple_commands; "
                "sending anyway (entity_commands can't be listed from a bare entity)."
            )
        name = localized(e.get("name"))
    except Exception:
        name = device_id

    body = {"cmd_id": command}
    if params:
        body["params"] = params

    async def do_write():
        return await client.put(f"/api/entities/{device_id}/command", body)

    return await apply_mutation(
        client,
        action="send_command",
        summary=f"Send '{command}' to {name} ({device_id})",
        change={"entity_id": device_id, "cmd_id": command, "params": params or {}},
        do_write=do_write,
        dry_run=dry_run,
        warnings=warnings or None,
    )


async def set_button_mapping(
    scope: str,
    scope_id: str,
    button: str,
    command: str,
    press: str = "short_press",
    entity_id: Optional[str] = None,
    params: Optional[dict] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Set a single physical-button -> command binding on an activity or remote-entity.

    PATCH /api/{activities|remotes}/{scope_id}/buttons/{button} with
    {press: {cmd_id, entity_id?, params?}}.

    Args:
        scope: "activity" or "remote".
        scope_id: the activity_id or remote entity_id.
        button: physical button id (e.g. "VOLUME_UP", "DPAD_UP"). Upper snake case.
        command: cmd_id to bind.
        press: "short_press" (default) or "long_press".
        entity_id: REQUIRED for scope="activity" (the device the command targets);
            ignored for scope="remote".
        params: optional command params.
        dry_run: when True (default), shows the planned change + current value, no write.
    """
    scope = scope.lower()
    if scope not in ("activity", "remote"):
        raise ValueError("scope must be 'activity' or 'remote'.")
    if press not in ("short_press", "long_press"):
        raise ValueError("press must be 'short_press' or 'long_press'.")
    button = button.strip().upper()  # ButtonId spec: ^[A-Z0-9_]+$

    client = get_client(host)
    base = "activities" if scope == "activity" else "remotes"
    detail = await client.get(f"/api/{base}/{scope_id}")

    # Build the EntityCommand body and validate.
    cmd: dict = {"cmd_id": command}
    warnings: list[str] = []

    if scope == "activity":
        if not entity_id:
            raise ValueError("scope='activity' requires entity_id (the command target).")
        err = validate_activity_command(detail, entity_id, command)
        if err:
            raise ValueError(err)
        cmd["entity_id"] = entity_id
    else:  # remote
        err = validate_remote_command(detail, command)
        if err:
            raise ValueError(err)
        if entity_id:
            warnings.append("entity_id is ignored for remote-entity button mappings.")
    if params:
        cmd["params"] = params

    # Find the current binding for before/after preview.
    current = None
    for b in (detail.get("options") or {}).get("button_mapping") or []:
        if b.get("button") == button:
            current = b.get(press)
            break

    button_path = f"/api/{base}/{scope_id}/buttons/{button}"

    async def do_write():
        return await client.patch(button_path, {press: cmd})

    return await apply_mutation(
        client,
        action="set_button_mapping",
        summary=(
            f"{scope} {localized(detail.get('name'))}: bind {button} {press} -> "
            f"{command}" + (f" on {entity_id}" if entity_id and scope == 'activity' else "")
        ),
        change={
            "scope": scope,
            "scope_id": scope_id,
            "button": button,
            "press": press,
            "from": current,
            "to": cmd,
            "endpoint": f"PATCH {button_path}",
        },
        do_write=do_write,
        dry_run=dry_run,
        warnings=warnings or None,
    )


async def bulk_set_button_mapping(
    button: str,
    command: str,
    entity_id: str,
    press: str = "short_press",
    params: Optional[dict] = None,
    activity_ids: Optional[list[str]] = None,
    name_contains: Optional[str] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Set the same physical-button binding across MANY activities at once
    ("route VOLUME_UP on every activity to the AVR").

    Activities only: remote-entities take local IR codes, not device-targeted
    commands, so they are out of scope for a bulk device binding.

    Filtering: pass activity_ids (explicit list) and/or name_contains (substring,
    case-insensitive). No filter = all activities.

    Per-activity validation runs first; activities that fail (target entity not
    included, unknown command) are skipped with a reason — they never block the
    valid ones. One backup is taken before the batch, then each activity gets its
    own PATCH. Defaults to dry_run=True (full plan preview, no writes).
    """
    if press not in ("short_press", "long_press"):
        raise ValueError("press must be 'short_press' or 'long_press'.")
    button = button.strip().upper()
    client = get_client(host)

    acts = await client.get_list("/api/activities")
    selected: list[tuple[str, str]] = []
    for a in acts if isinstance(acts, list) else []:
        aid = a.get("entity_id")
        aname = localized(a.get("name"))
        if activity_ids and aid not in activity_ids:
            continue
        if name_contains and name_contains.lower() not in aname.lower():
            continue
        selected.append((aid, aname))

    cmd: dict = {"cmd_id": command, "entity_id": entity_id}
    if params:
        cmd["params"] = params

    # Validate each activity and build the plan with before/after.
    plan: list[dict] = []
    for aid, aname in selected:
        detail = await client.get(f"/api/activities/{aid}")
        err = validate_activity_command(detail, entity_id, command)
        current = None
        for b in (detail.get("options") or {}).get("button_mapping") or []:
            if b.get("button") == button:
                current = b.get(press)
                break
        entry: dict = {
            "activity_id": aid,
            "activity_name": aname,
            "from": current,
            "to": None if err else cmd,
        }
        if err:
            entry["skip_reason"] = err
        plan.append(entry)

    valid = [p for p in plan if "skip_reason" not in p]
    envelope: dict = {
        "action": "bulk_set_button_mapping",
        "dry_run": dry_run,
        "summary": (
            f"Bind {button} {press} -> {command} on {entity_id} "
            f"across {len(valid)} of {len(plan)} matched activities"
        ),
        "matched": len(plan),
        "will_apply": len(valid),
        "skipped": len(plan) - len(valid),
        "changes": plan,
    }

    if not plan:
        envelope["note"] = "No activities matched the filter. Nothing to do."
        return envelope
    if dry_run:
        envelope["note"] = (
            "Nothing was written. Re-run with dry_run=false to apply to the "
            f"{len(valid)} valid activities."
        )
        return envelope
    if not valid:
        envelope["note"] = "All matched activities failed validation; nothing written."
        return envelope

    # One backup for the whole batch, then per-activity writes.
    backup = await create_backup(client)
    envelope["backup"] = {"path": backup["path"], "size_bytes": backup["size_bytes"]}

    results: list[dict] = []
    for p in valid:
        aid = p["activity_id"]
        try:
            r = await client.patch(f"/api/activities/{aid}/buttons/{button}", {press: cmd})
            results.append({"activity_id": aid, "ok": True, "result": r})
        except Exception as e:  # noqa: BLE001
            results.append({"activity_id": aid, "ok": False, "error": str(e)})
    envelope["results"] = results
    envelope["applied"] = all(r["ok"] for r in results)
    return envelope
