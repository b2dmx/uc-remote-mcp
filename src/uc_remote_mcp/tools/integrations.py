"""Integration management: drivers, instances, setup flows, entity exposure.

This is the part of the remote that the official apps make painful, and most of
the pain is undocumented behaviour rather than difficulty:

* A driver archive cannot be updated in place. ``?update=true`` answers 422
  ALREADY_EXISTS on current firmware, so replacing a driver means deleting it
  and installing again.
* After installing a driver the remote has not launched its process yet, and
  starting setup answers 503 until the system is restarted.
* Setup flows are a state machine living on the remote, and **every** input
  value must be a string -- a real integer or boolean is rejected outright.
* A rejected step kills the flow: the next GET returns 404 and it has to be
  started again from the beginning.
* Setup finishing does *not* expose any entities. They must be configured in a
  separate call, and the "new entities" listing only populates after a reload.

Each of those is a dead end someone would otherwise have to discover.
"""

from typing import Any, Optional

import httpx

from ..safety.dry_run import apply_mutation
from ._common import get_client, localized


# --------------------------------------------------------------------- reading


async def list_integrations(host: Optional[str] = None) -> dict:
    """Installed drivers and their configured instances, with connection state."""
    client = get_client(host)

    drivers = await client.get_list("/api/intg/drivers")
    instances = await client.get_list("/api/intg/instances")

    return {
        "drivers": [
            {
                "driver_id": d.get("driver_id"),
                "name": localized(d.get("name")),
                "version": d.get("version"),
                "enabled": d.get("enabled"),
                # LOCAL = shipped in the firmware, CUSTOM = user-installed on
                # the remote, EXTERNAL = running elsewhere on the network.
                "driver_type": d.get("driver_type"),
                "driver_state": d.get("driver_state"),
                "developer": d.get("developer_name"),
            }
            for d in drivers
        ],
        "instances": [
            {
                "integration_id": i.get("integration_id"),
                "driver_id": i.get("driver_id"),
                "name": localized(i.get("name")),
                "enabled": i.get("enabled"),
                # Not a health signal. An instance reports CONNECTED while its
                # entities are stale or OFF; check the entities themselves.
                "device_state": i.get("device_state"),
            }
            for i in instances
        ],
    }


async def get_integration(integration_id: str, host: Optional[str] = None) -> dict:
    """One instance in full, with how many entities it has configured."""
    client = get_client(host)
    inst = await client.get(f"/api/intg/instances/{integration_id}")
    configured = await client.get_list(f"/api/intg/instances/{integration_id}/entities")

    return {
        "integration_id": inst.get("integration_id"),
        "driver_id": inst.get("driver_id"),
        "name": localized(inst.get("name")),
        "enabled": inst.get("enabled"),
        "device_state": inst.get("device_state"),
        "configured_entities": len(configured),
        "entities": [
            {
                "entity_id": e.get("entity_id"),
                "name": localized(e.get("name")),
                "entity_type": e.get("entity_type"),
            }
            for e in configured
        ],
    }


async def list_integration_entities(
    integration_id: str, only_new: bool = True, host: Optional[str] = None
) -> dict:
    """
    Entities this integration offers.

    ``only_new`` asks the remote to re-poll the integration and list what is not
    configured yet. That reload matters: without it a freshly paired device can
    report nothing at all.
    """
    client = get_client(host)
    path = f"/api/intg/instances/{integration_id}/entities"
    if only_new:
        path += "?filter=NEW&reload=true"

    # This endpoint rejects a page size above 100, unlike the others.
    items = await client.get_list(path, page_size=100)
    return {
        "integration_id": integration_id,
        "filter": "NEW" if only_new else "ALL",
        "count": len(items),
        "entities": [
            {
                "entity_id": e.get("entity_id"),
                "name": localized(e.get("name")),
                "entity_type": e.get("entity_type"),
            }
            for e in items
        ],
    }


# --------------------------------------------------------------------- writing


async def configure_integration_entities(
    integration_id: str,
    entity_ids: list[str],
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Expose entities from an integration so activities and pages can use them.

    Additive: this adds to what is already configured and removes nothing.
    """
    client = get_client(host)

    return await apply_mutation(
        client,
        action="configure_integration_entities",
        summary=f"expose {len(entity_ids)} entit"
        f"{'y' if len(entity_ids) == 1 else 'ies'} from {integration_id}",
        change={"integration_id": integration_id, "entity_ids": entity_ids},
        do_write=lambda: client.post(
            f"/api/intg/instances/{integration_id}/entities", entity_ids
        ),
        dry_run=dry_run,
    )


async def set_integration_enabled(
    integration_id: str,
    enabled: bool,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """Enable or disable an integration instance."""
    client = get_client(host)

    return await apply_mutation(
        client,
        action="set_integration_enabled",
        summary=f"{'enable' if enabled else 'disable'} {integration_id}",
        change={"integration_id": integration_id, "enabled": enabled},
        do_write=lambda: client.patch(
            f"/api/intg/instances/{integration_id}", {"enabled": enabled}
        ),
        dry_run=dry_run,
    )


async def restart_integration(
    integration_id: str,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Disable an integration and enable it again.

    This is the fix for "everything stopped responding": an instance can wedge
    while still reporting CONNECTED, and a cycle reconnects it without touching
    any configuration. Try this before anything more drastic.
    """
    import asyncio

    client = get_client(host)

    async def _cycle() -> dict:
        await client.patch(f"/api/intg/instances/{integration_id}", {"enabled": False})
        await asyncio.sleep(5)
        await client.patch(f"/api/intg/instances/{integration_id}", {"enabled": True})
        await asyncio.sleep(5)
        inst = await client.get(f"/api/intg/instances/{integration_id}")
        return {"device_state": inst.get("device_state")}

    return await apply_mutation(
        client,
        action="restart_integration",
        summary=f"disable and re-enable {integration_id}",
        change={"integration_id": integration_id},
        do_write=_cycle,
        dry_run=dry_run,
    )


async def install_integration(
    file_path: str,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Install a custom driver from a ``.tar.gz`` archive on this machine.

    There is no in-place update: to replace an existing driver, delete it first.
    The remote does not launch the new driver's process until it restarts, so
    ``restart_remote(target="system")`` is required before setup will start.
    """
    client = get_client(host)

    return await apply_mutation(
        client,
        action="install_integration",
        summary=f"upload and install driver archive {file_path}",
        change={"file": file_path},
        do_write=lambda: client.post_file("/api/intg/install", file_path),
        dry_run=dry_run,
        warnings=[
            "The driver process only starts after a system restart; run "
            "restart_remote(target='system') before starting its setup flow.",
        ],
    )


async def delete_integration(
    driver_id: str,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Remove a driver, its instance, and every entity it provided.

    Destructive in a way that is easy to underestimate: removing the entities
    also strips every button mapping and page item that referenced them, across
    all activities. A backup is taken first, but read the preview.
    """
    client = get_client(host)

    return await apply_mutation(
        client,
        action="delete_integration",
        summary=f"delete driver {driver_id}, its instance and all its entities",
        change={"driver_id": driver_id},
        do_write=lambda: client.delete(f"/api/intg/drivers/{driver_id}"),
        dry_run=dry_run,
        warnings=[
            "Every button mapping and page item using this driver's entities "
            "will be removed with them.",
        ],
    )


# ----------------------------------------------------------------- setup flows


def _stringify(values: dict[str, Any]) -> dict[str, str]:
    """Setup flows reject anything but strings, including numbers and booleans."""
    out: dict[str, str] = {}
    for k, v in values.items():
        if v is None:
            # Flows want every field present; an empty string is how "nothing"
            # is expressed. str(None) would send the word "None".
            out[k] = ""
        elif isinstance(v, bool):
            out[k] = "true" if v else "false"
        else:
            out[k] = str(v)
    return out


def _screen(state: dict) -> dict:
    """Flatten a setup-flow response into the question being asked."""
    step = (state or {}).get("require_user_action") or {}
    form = step.get("input") or step.get("confirmation") or {}
    fields = []
    for f in form.get("settings", []) or []:
        field = f.get("field") or {}
        kind = next(iter(field), None)
        spec = field.get(kind) or {}
        fields.append(
            {
                "id": f.get("id"),
                "label": localized(f.get("label")),
                "type": kind,
                "options": [
                    {"id": o.get("id"), "label": localized(o.get("label"))}
                    for o in (spec.get("items") or [])
                ]
                or None,
                # Label fields carry their text here as a language dict.
                "default": localized(spec["value"]) if isinstance(spec.get("value"), dict) else spec.get("value"),
            }
        )
    out = {
        "state": state.get("state"),
        "error": state.get("error"),
        "title": localized(form.get("title")),
        "fields": fields,
    }
    # A confirmation page has no fields; what it wants read is in its messages.
    message = " ".join(
        m for m in (localized(form.get("message1")), localized(form.get("message2"))) if m
    )
    if message:
        out["message"] = message
    return out


async def _wait_for_screen(client, driver_id: str, timeout: float = 15.0) -> dict:
    """Poll the flow until the driver has something to say.

    Creating or answering a step returns before the driver has produced the
    next screen -- the flow sits in SETUP for a moment first. Reading it once
    hands back an empty screen and no hint that waiting would have helped.
    """
    import asyncio

    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        try:
            state = await client.get(f"/api/intg/setup/{driver_id}")
        except httpx.HTTPStatusError as err:
            if err.response.status_code != 404:
                raise
            # The flow closes itself when it finishes.
            return {"state": "OK", "note": "Setup finished; the flow has closed."}
        if state.get("state") != "SETUP" or asyncio.get_event_loop().time() >= deadline:
            screen = _screen(state)
            if state.get("state") == "SETUP":
                screen["note"] = (
                    "The driver is still working; call get_integration_setup "
                    "again in a moment."
                )
            return screen
        await asyncio.sleep(0.5)


async def start_integration_setup(
    driver_id: str, reconfigure: bool = False, host: Optional[str] = None
) -> dict:
    """
    Begin (or reconfigure) an integration's setup, returning its first screen.

    A 503 here means the driver's process is not running, which is normal
    straight after installing one: restart the remote and try again.
    """
    client = get_client(host)
    body: dict[str, Any] = {"driver_id": driver_id}
    if reconfigure:
        body["reconfigure"] = True
    await client.post("/api/intg/setup", body)
    return await _wait_for_screen(client, driver_id)


async def get_integration_setup(driver_id: str, host: Optional[str] = None) -> dict:
    """The setup flow's current screen, or a plain answer if none is running."""
    client = get_client(host)
    try:
        return _screen(await client.get(f"/api/intg/setup/{driver_id}"))
    except httpx.HTTPStatusError as err:
        if err.response.status_code != 404:
            raise
        return {"state": "NONE", "note": f"No setup flow is in progress for {driver_id}."}


async def answer_integration_setup(
    driver_id: str, values: dict, host: Optional[str] = None
) -> dict:
    """
    Answer the current setup screen and return the next one.

    Every value is sent as a string, which is what the remote requires. Send all
    of a screen's fields: omitting one is rejected, and a rejected step ends the
    flow -- it has to be started again from the beginning.
    """
    client = get_client(host)
    await client.put(
        f"/api/intg/setup/{driver_id}", {"input_values": _stringify(values)}
    )
    return await _wait_for_screen(client, driver_id)


async def cancel_integration_setup(driver_id: str, host: Optional[str] = None) -> dict:
    """Abandon an in-progress setup flow without changing anything."""
    client = get_client(host)
    await client.delete(f"/api/intg/setup/{driver_id}")
    return {"driver_id": driver_id, "cancelled": True}


# -------------------------------------------------------------------- restarts


_RESTART_TARGETS = {
    # The UI app only. Seconds, and the only way to make configuration changes
    # actually repaint -- pages and profiles can otherwise sit stale.
    "ui": "RESTART_UI",
    # The core service. Cures stale entity references after a driver swap.
    "core": "RESTART_CORE",
    # The whole system. Required before a newly installed driver will start.
    "system": "RESTART",
}


async def restart_remote(
    target: str = "ui", dry_run: bool = True, host: Optional[str] = None
) -> dict:
    """
    Restart part of the remote: "ui", "core", or "system".

    No device commands are sent, and configuration is untouched. Activity
    states reset, since they are not persisted across a restart.
    """
    if target not in _RESTART_TARGETS:
        raise ValueError(
            f"target must be one of {sorted(_RESTART_TARGETS)}, got {target!r}"
        )
    client = get_client(host)
    cmd = _RESTART_TARGETS[target]

    return await apply_mutation(
        client,
        action="restart_remote",
        summary=f"restart the remote's {target} ({cmd})",
        change={"target": target, "cmd": cmd},
        do_write=lambda: client.post(f"/api/system?cmd={cmd}"),
        dry_run=dry_run,
    )
