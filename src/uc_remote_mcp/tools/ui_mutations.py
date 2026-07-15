"""Phase 2 UI-page and sequence mutations.

Endpoints (verified against UCR-core-openapi.yaml v0.46):
- PATCH /{activities|remotes}/{id}/ui/pages/{pageId}  body {name?, grid?, items?}
  (omitted = unchanged; empty items array clears the page)
- DELETE /{activities|remotes}/{id}/ui/pages/{pageId}  (irrevocable)
- PATCH /{activities|remotes}/{id}/ui/pages  body {page_order: [...]}
  (first page is what the remote shows when the activity starts)
- PATCH /activities/{id}  body {options: {sequences: {"on": [...], "off": [...]}}}
  steps: {type:"command", command:{entity_id, cmd_id, params?}} | {type:"delay", delay:ms}

Validation rules from the spec:
- Activity UI item commands REQUIRE entity_id (one of the included entities).
- Remote UI item commands may NOT contain entity_id (remote operates on itself).
- Sequence command steps always require entity_id + cmd_id, and the entity must be
  included in the activity.
"""

from typing import Optional

from ._common import get_client, localized, pages_of
from ..safety.dry_run import apply_mutation
from ..safety.validate import validate_activity_command, validate_remote_command


def _scope_base(scope: str) -> str:
    scope = scope.lower()
    if scope == "activity":
        return "activities"
    if scope == "remote":
        return "remotes"
    raise ValueError("scope must be 'activity' or 'remote'.")


def _find_page(detail: dict, page_id: str) -> Optional[dict]:
    for p in pages_of(detail):
        if p.get("page_id") == page_id:
            return p
    return None


def _validate_items(scope: str, detail: dict, items: list) -> list[str]:
    """Validate every UI item's command for the scope. Returns error strings."""
    errors: list[str] = []
    included = {
        e.get("entity_id")
        for e in (detail.get("options") or {}).get("included_entities") or []
    }
    for i, it in enumerate(items):
        cmd = it.get("command")
        if cmd:
            cmd_id = cmd.get("cmd_id")
            eid = cmd.get("entity_id")
            if not cmd_id:
                errors.append(f"items[{i}]: command requires cmd_id.")
                continue
            if scope == "activity":
                if not eid:
                    errors.append(f"items[{i}]: activity UI commands require entity_id.")
                    continue
                err = validate_activity_command(detail, eid, cmd_id)
                if err:
                    errors.append(f"items[{i}]: {err}")
            else:  # remote
                if eid:
                    errors.append(
                        f"items[{i}]: remote UI commands may not contain entity_id "
                        "(a remote-entity always operates on itself)."
                    )
                    continue
                err = validate_remote_command(detail, cmd_id)
                if err:
                    errors.append(f"items[{i}]: {err}")
        mp = it.get("media_player_id")
        if mp and scope == "activity" and mp not in included:
            errors.append(
                f"items[{i}]: media_player_id '{mp}' is not an included entity."
            )
    return errors


async def update_ui_page(
    scope: str,
    scope_id: str,
    page_id: str,
    name: Optional[str] = None,
    grid: Optional[dict] = None,
    items: Optional[list] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Update a UI page's name, grid, and/or items. Omitted fields are left
    unchanged; an EMPTY items list removes all items from the page.

    Every item command is validated against the scope before writing
    (activity: entity must be included + command valid; remote: local code only).
    """
    base = _scope_base(scope)
    scope = scope.lower()
    if name is None and grid is None and items is None:
        raise ValueError("Provide at least one of name, grid, items.")

    client = get_client(host)
    detail = await client.get(f"/api/{base}/{scope_id}")
    page = _find_page(detail, page_id)
    if page is None:
        known = [p.get("page_id") for p in pages_of(detail)]
        raise ValueError(f"No page '{page_id}' in {scope} {scope_id}. Pages: {known}")

    body: dict = {}
    if name is not None:
        body["name"] = name
    if grid is not None:
        body["grid"] = grid
    if items is not None:
        errors = _validate_items(scope, detail, items)
        if errors:
            raise ValueError("Invalid items: " + " | ".join(errors))
        body["items"] = items

    current = {
        "name": page.get("name"),
        "grid": page.get("grid"),
        "item_count": len(page.get("items") or []),
    }
    planned = dict(current)
    if name is not None:
        planned["name"] = name
    if grid is not None:
        planned["grid"] = grid
    if items is not None:
        planned["item_count"] = len(items)

    path = f"/api/{base}/{scope_id}/ui/pages/{page_id}"

    async def do_write():
        return await client.patch(path, body)

    return await apply_mutation(
        client,
        action="update_ui_page",
        summary=(
            f"{scope} {localized(detail.get('name'))}: update page "
            f"'{page.get('name') or page_id}' ({', '.join(body.keys())})"
        ),
        change={"scope": scope, "scope_id": scope_id, "page_id": page_id,
                "from": current, "to": planned, "endpoint": f"PATCH {path}"},
        do_write=do_write,
        dry_run=dry_run,
    )


async def delete_ui_page(
    scope: str,
    scope_id: str,
    page_id: str,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Delete a UI page. IRREVOCABLE on the remote — the auto-backup taken before
    the write is the only way back. Dry-run shows exactly what would be lost.
    """
    base = _scope_base(scope)
    scope = scope.lower()
    client = get_client(host)
    detail = await client.get(f"/api/{base}/{scope_id}")
    page = _find_page(detail, page_id)
    if page is None:
        known = [p.get("page_id") for p in pages_of(detail)]
        raise ValueError(f"No page '{page_id}' in {scope} {scope_id}. Pages: {known}")

    path = f"/api/{base}/{scope_id}/ui/pages/{page_id}"

    async def do_write():
        return await client.delete(path)

    return await apply_mutation(
        client,
        action="delete_ui_page",
        summary=(
            f"{scope} {localized(detail.get('name'))}: DELETE page "
            f"'{page.get('name') or page_id}' ({len(page.get('items') or [])} items)"
        ),
        change={
            "scope": scope, "scope_id": scope_id, "page_id": page_id,
            "page_being_deleted": {
                "name": page.get("name"),
                "grid": page.get("grid"),
                "items": page.get("items"),
            },
            "endpoint": f"DELETE {path}",
        },
        do_write=do_write,
        dry_run=dry_run,
        warnings=["This deletion is irrevocable on the remote; restore only via backup."],
    )


async def set_default_ui_page(
    scope: str,
    scope_id: str,
    page_id: str,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Make a page the FIRST page (the one shown when the activity/remote UI opens).

    There is no explicit 'default page' property in the API — page order defines
    it, so this reorders the existing pages with the chosen page moved to front.
    """
    base = _scope_base(scope)
    scope = scope.lower()
    client = get_client(host)
    detail = await client.get(f"/api/{base}/{scope_id}")
    pages = pages_of(detail)
    order = [p.get("page_id") for p in pages]
    if page_id not in order:
        raise ValueError(f"No page '{page_id}' in {scope} {scope_id}. Pages: {order}")

    new_order = [page_id] + [p for p in order if p != page_id]
    path = f"/api/{base}/{scope_id}/ui/pages"

    async def do_write():
        return await client.patch(path, {"page_order": new_order})

    return await apply_mutation(
        client,
        action="set_default_ui_page",
        summary=(
            f"{scope} {localized(detail.get('name'))}: make page '{page_id}' "
            f"the default (first) page"
        ),
        change={"scope": scope, "scope_id": scope_id,
                "from": order, "to": new_order,
                "endpoint": f"PATCH {path} {{page_order}}"},
        do_write=do_write,
        dry_run=dry_run,
    )


def _validate_sequence(detail: dict, seq: list, which: str) -> list[str]:
    """Validate sequence steps: command steps need a valid included entity + cmd."""
    errors: list[str] = []
    for i, step in enumerate(seq):
        stype = step.get("type")
        if stype == "delay":
            if not isinstance(step.get("delay"), int) or step["delay"] < 1:
                errors.append(f"{which}[{i}]: delay must be a positive integer (ms).")
        elif stype == "command":
            cmd = step.get("command") or {}
            eid, cid = cmd.get("entity_id"), cmd.get("cmd_id")
            if not eid or not cid:
                errors.append(f"{which}[{i}]: command steps require entity_id and cmd_id.")
                continue
            err = validate_activity_command(detail, eid, cid)
            if err:
                errors.append(f"{which}[{i}]: {err}")
        else:
            errors.append(f"{which}[{i}]: type must be 'command' or 'delay'.")
    return errors


async def update_activity_sequence(
    activity_id: str,
    on_sequence: Optional[list] = None,
    off_sequence: Optional[list] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Replace an activity's on and/or off power sequence.

    Steps: {"type": "command", "command": {"entity_id", "cmd_id", "params"?}} or
    {"type": "delay", "delay": <ms>}. Omitted sequence = unchanged; empty list
    clears that sequence. Every command step is validated against the activity's
    included entities before writing.
    """
    if on_sequence is None and off_sequence is None:
        raise ValueError("Provide on_sequence and/or off_sequence.")

    client = get_client(host)
    detail = await client.get(f"/api/activities/{activity_id}")

    errors: list[str] = []
    sequences: dict = {}
    if on_sequence is not None:
        errors += _validate_sequence(detail, on_sequence, "on_sequence")
        sequences["on"] = on_sequence
    if off_sequence is not None:
        errors += _validate_sequence(detail, off_sequence, "off_sequence")
        sequences["off"] = off_sequence
    if errors:
        raise ValueError("Invalid sequence: " + " | ".join(errors))

    current = (detail.get("options") or {}).get("sequences") or {}
    path = f"/api/activities/{activity_id}"
    body = {"options": {"sequences": sequences}}

    async def do_write():
        return await client.patch(path, body)

    return await apply_mutation(
        client,
        action="update_activity_sequence",
        summary=(
            f"activity {localized(detail.get('name'))}: replace "
            f"{' + '.join(sequences.keys())} sequence(s)"
        ),
        change={"activity_id": activity_id,
                "from": {k: current.get(k) for k in sequences},
                "to": sequences,
                "endpoint": f"PATCH {path} {{options.sequences}}"},
        do_write=do_write,
        dry_run=dry_run,
    )
