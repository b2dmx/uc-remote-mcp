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

import asyncio
import json
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
    # Without a filter this endpoint lists what the driver OFFERS, using the
    # driver's own short ids -- not what is configured. CONFIGURED is the
    # exposed set; the remote-wide id is the instance id plus the short id.
    configured = await client.get_list(
        f"/api/intg/instances/{integration_id}/entities?filter=CONFIGURED", page_size=100
    )

    states = {
        e["entity_id"]: e["state"]
        for e in await _states(
            client,
            [f"{integration_id}.{c.get('entity_id')}" for c in configured],
        )
    }

    return {
        "integration_id": inst.get("integration_id"),
        "driver_id": inst.get("driver_id"),
        "name": localized(inst.get("name")),
        "enabled": inst.get("enabled"),
        "device_state": inst.get("device_state"),
        "configured_entities": len(configured),
        "entities": [
            {
                "entity_id": f"{integration_id}.{e.get('entity_id')}",
                "driver_entity_id": e.get("entity_id"),
                "name": localized(e.get("name")),
                "entity_type": e.get("entity_type"),
                # UNKNOWN means the driver has no state for it: not polled yet,
                # or the device is not there.
                "state": states.get(f"{integration_id}.{e.get('entity_id')}"),
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
        # driver_entity_id is what configure_integration_entities takes; the
        # remote-wide entity_id is what exists once it has been configured.
        "entities": [
            {
                "driver_entity_id": e.get("entity_id"),
                "entity_id": f"{integration_id}.{e.get('entity_id')}",
                "name": localized(e.get("name")),
                "entity_type": e.get("entity_type"),
            }
            for e in items
        ],
    }


async def _states(client, entity_ids: list[str]) -> list[dict]:
    """What each entity reports right now, or None if the remote lost it."""
    import httpx

    out = []
    for eid in entity_ids:
        try:
            e = await client.get(f"/api/entities/{eid}")
        except httpx.HTTPStatusError as err:
            if err.response.status_code != 404:
                raise
            out.append({"entity_id": eid, "name": None, "state": "NOT_FOUND"})
            continue
        out.append(
            {
                "entity_id": eid,
                "name": localized(e.get("name")),
                "state": (e.get("attributes") or {}).get("state"),
            }
        )
    return out


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
    full_ids = [
        e if e.startswith(f"{integration_id}.") else f"{integration_id}.{e}"
        for e in entity_ids
    ]

    async def _write() -> dict:
        # The response lists only ids newly added, so an already-configured
        # entity comes back as an empty list rather than an error.
        added = await client.post(
            f"/api/intg/instances/{integration_id}/entities", entity_ids
        )
        states = await _states(client, full_ids)
        result = {
            "newly_added": added if isinstance(added, list) else added,
            "entities": states,
        }
        # A device that is not actually reachable reports UNKNOWN and will not
        # respond to anything put on a page -- worth saying out loud rather than
        # letting it be discovered by pressing a dead button.
        # UNKNOWN is the correct resting state for entity types that have no
        # state of their own -- a remote, a button, a macro -- so flagging them
        # would be crying wolf. Only types that report a state are checked.
        stateless = {"remote", "button", "macro", "voice_assistant"}
        types = {
            e.get("entity_id"): e.get("entity_type")
            for e in await client.get_list(
                f"/api/intg/instances/{integration_id}/entities?filter=CONFIGURED",
                page_size=100,
            )
        }
        unknown = [
            e["entity_id"]
            for e in states
            if e["state"] in (None, "UNKNOWN")
            and types.get(e["entity_id"].split(".")[-1]) not in stateless
        ]
        if unknown:
            result["not_reporting"] = unknown
            result["hint"] = (
                "These report no state. Either the driver has not polled them "
                "yet -- restart_integration forces that -- or the device is not "
                "reachable. Check again before putting them on a page."
            )
        return result

    return await apply_mutation(
        client,
        action="configure_integration_entities",
        summary=f"expose {len(entity_ids)} entit"
        f"{'y' if len(entity_ids) == 1 else 'ies'} from {integration_id}",
        change={"integration_id": integration_id, "entity_ids": full_ids},
        do_write=_write,
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
        do_write=lambda: _install_and_verify(client, file_path),
        dry_run=dry_run,
        warnings=[
            "The driver process only starts after a system restart; run "
            "restart_remote(target='system') before starting its setup flow.",
        ],
    )


async def _install_and_verify(client, file_path: str) -> dict:
    """Upload, then check the driver list rather than trusting the status code.

    The install endpoint has been seen to answer 422 *after* installing the
    driver successfully. Reporting that as a failure sends people off to debug
    something that already worked, so confirm against the driver list either way.
    """
    import httpx

    before = {d.get("driver_id") for d in await client.get_list("/api/intg/drivers")}
    error = None
    try:
        await client.post_file("/api/intg/install", file_path)
    except httpx.HTTPStatusError as err:
        error = str(err)

    after = await client.get_list("/api/intg/drivers")
    new_ids = [d.get("driver_id") for d in after if d.get("driver_id") not in before]

    if not new_ids:
        raise RuntimeError(
            error or "The install reported success but no new driver appeared."
        )

    out = {
        "installed": new_ids,
        "driver": next(
            (
                {k: d.get(k) for k in ("driver_id", "version", "driver_type", "driver_state")}
                for d in after
                if d.get("driver_id") in new_ids
            ),
            None,
        ),
    }
    if error:
        out["note"] = "The remote returned an error, but the driver is installed: " + error
    return out


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
        do_write=lambda: client.delete(f"/api/intg/drivers/{driver_id}", timeout=120),
        dry_run=dry_run,
        warnings=[
            "Every button mapping and page item using this driver's entities "
            "will be removed with them.",
        ],
    )


async def delete_integration_instance(
    integration_id: str,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Remove one configured instance and every entity it provided, leaving the
    driver installed. The right teardown for a firmware-shipped driver, which
    cannot be deleted itself.

    Removing the entities also strips every button mapping and page item that
    referenced them. A backup is taken first, but read the preview.
    """
    client = get_client(host)

    return await apply_mutation(
        client,
        action="delete_integration_instance",
        summary=f"remove instance {integration_id} and all its entities",
        change={"integration_id": integration_id},
        do_write=lambda: client.delete(f"/api/intg/instances/{integration_id}", timeout=60),
        dry_run=dry_run,
        warnings=[
            "Every button mapping and page item using this instance's entities "
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


def _fingerprint(screen: dict) -> tuple:
    """What makes one setup screen distinguishable from the next."""
    return (
        screen.get("state"),
        screen.get("title"),
        tuple(f.get("id") for f in (screen.get("fields") or [])),
    )


async def _wait_for_screen(
    client, driver_id: str, timeout: float = 15.0, previous: Optional[tuple] = None
) -> dict:
    """Poll the flow until the driver has something new to say.

    Two separate waits are needed here, and only one of them is obvious.

    The flow sits in SETUP for a moment while the driver works, and reading it
    then hands back an empty screen. That much is easy to wait out.

    The other: answering a step returns immediately, and for a moment the flow
    is back in WAIT_USER_ACTION still showing the screen just answered. A wait
    that only watches for "no longer SETUP" is satisfied by that instantly and
    returns the old screen -- so a caller driving the flow by this return value
    answers the same question forever. ``previous`` is the fingerprint of the
    screen that was just answered; when given, the poll continues until the
    screen actually differs from it.
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

        screen = _screen(state)
        busy = state.get("state") == "SETUP"
        stale = previous is not None and _fingerprint(screen) == previous
        timed_out = asyncio.get_event_loop().time() >= deadline

        if not busy and not stale:
            return screen
        if timed_out:
            if busy:
                screen["note"] = (
                    "The driver is still working; call get_integration_setup "
                    "again in a moment."
                )
            elif stale:
                screen["note"] = (
                    "The driver has not moved on from this screen. It may have "
                    "rejected the answer -- check 'error'."
                )
            return screen
        await asyncio.sleep(0.5)


async def start_integration_setup(
    driver_id: str,
    reconfigure: bool = False,
    setup_data: Optional[dict] = None,
    host: Optional[str] = None,
) -> dict:
    """
    Begin (or reconfigure) an integration's setup, returning its first screen.

    Some drivers want a value up front rather than asking for it -- an API key,
    typically -- and refuse to start without it: ``400 Setup data not provided
    for field: <name>``. Pass it as ``setup_data={"api_key": "..."}``. The field
    name in that error is the key to use.

    A 503 here means the driver's process is not running, which is normal
    straight after installing one: restart the system and try again.
    """
    client = get_client(host)
    body: dict[str, Any] = {"driver_id": driver_id}
    if reconfigure:
        body["reconfigure"] = True
    if setup_data:
        body["setup_data"] = _stringify(setup_data)
    # The core starts a custom driver lazily, on demand. If the driver was just
    # stopped -- cancelling a flow stops it, "no more instances" -- the start
    # races that shutdown and systemd cancels the job, surfacing as 503. It
    # succeeds moments later, so retry rather than making the caller guess.
    import asyncio

    for attempt in range(4):
        try:
            await client.post("/api/intg/setup", body, timeout=90)
            break
        except httpx.HTTPStatusError as err:
            if err.response.status_code != 503 or attempt == 3:
                raise
            await asyncio.sleep(8)
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
    before = _fingerprint(await get_integration_setup(driver_id, host=host))
    await client.put(
        f"/api/intg/setup/{driver_id}", {"input_values": _stringify(values)}, timeout=90
    )
    return await _wait_for_screen(client, driver_id, previous=before)


async def confirm_integration_setup(
    driver_id: str, confirm: bool = True, host: Optional[str] = None
) -> dict:
    """
    Answer a confirmation screen -- "press the button on the bridge, then
    continue" -- and return the next one.

    Confirmation pages have no fields, so they are answered with a yes/no
    rather than values. ``confirm=False`` is the "no" branch where a flow
    offers one.
    """
    client = get_client(host)
    before = _fingerprint(await get_integration_setup(driver_id, host=host))
    await client.put(f"/api/intg/setup/{driver_id}", {"confirm": confirm}, timeout=90)
    return await _wait_for_screen(client, driver_id, previous=before)


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


async def set_integration_connected(
    integration_id: str,
    connected: bool,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Connect or disconnect an integration instance without disabling it.

    Lighter than restart_integration: the instance stays enabled and keeps its
    configuration, it just drops or re-opens its connection to the device. Try
    this first when devices stop responding; restart the integration if it does
    not help.

    The command is a query parameter and the API only accepts it uppercase.
    """
    client = get_client(host)
    instances = await client.get_list("/api/intg/instances")
    match = next(
        (i for i in instances if i.get("integration_id") == integration_id), None
    )
    if match is None:
        have = ", ".join(i.get("integration_id", "?") for i in instances)
        raise ValueError(f"No integration '{integration_id}'. Have: {have}")

    cmd = "CONNECT" if connected else "DISCONNECT"
    return await apply_mutation(
        client,
        action="set_integration_connected",
        summary=f"{cmd.lower()} '{localized(match.get('name')) or integration_id}' "
        f"(now {match.get('device_state')})",
        change={
            "integration_id": integration_id,
            "from": match.get("device_state"),
            "cmd": cmd,
        },
        do_write=lambda: client.put(
            f"/api/intg/instances/{integration_id}?cmd={cmd}", None, timeout=45
        ),
        dry_run=dry_run,
    )


async def discover_integrations(host: Optional[str] = None) -> dict:
    """
    Integrations the remote can see on the network but has not set up.

    Discovery is a mode the remote enters from its own integration screen, so an
    empty list with ``discovery_active`` false means nothing is looking rather
    than nothing is there.
    """
    client = get_client(host)
    found = await client.get("/api/intg/discover")
    return {
        "discovery_active": found.get("active"),
        "integrations": found.get("integrations") or [],
    }


def _package_driver_json(file_path: str) -> dict:
    """Read driver.json out of an integration .tar.gz without unpacking it."""
    import json as _json
    import tarfile

    with tarfile.open(file_path, "r:gz") as tar:
        for name in ("./driver.json", "driver.json"):
            try:
                fh = tar.extractfile(name)
            except KeyError:
                continue
            if fh:
                return _json.loads(fh.read().decode("utf-8"))
        member = next(
            (m for m in tar.getmembers() if m.name.endswith("driver.json")), None
        )
        if member:
            fh = tar.extractfile(member)
            if fh:
                return _json.loads(fh.read().decode("utf-8"))
    raise ValueError(f"No driver.json inside {file_path} -- is it an integration package?")


async def update_integration_driver(
    driver_id: str,
    file_path: str,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Update a custom integration to a new version from a ``.tar.gz``.

    The remote cannot replace a driver in place. ``POST /api/intg/install``
    answers 422 ALREADY_EXISTS for a driver_id it already has, stopping the
    driver first does not help, and the WebSocket API has no message that takes
    driver bytes either -- its ``update_integration_driver`` only edits
    metadata. The remote's own Integration Manager fails the same way, because
    it calls the same endpoint. So this deletes the driver and installs the new
    package, which is the only path there is.

    **This is not a quiet operation.** Deleting the driver removes its entities,
    and setup has to be run again afterwards. Two things make it far less
    alarming than it sounds, both worth knowing before you panic:

    * Entity ids are derived from the device, not from the install, so they come
      back identical and every button, page item and macro step that referenced
      them resolves again on its own. Count the references before and after
      rather than rebuilding them -- they are very likely untouched.
    * The *pairing* usually does not survive. Expect to confirm a prompt on the
      device itself, so do not start this when nobody can reach it.

    The package is checked against the installed driver first: a ``.tar.gz``
    for a different driver_id is refused before anything is deleted.

    Afterwards: ``start_integration_setup``, answer its screens, then
    ``configure_integration_entities`` to add the entities back.
    """
    client = get_client(host)

    current = await client.get(f"/api/intg/drivers/{driver_id}")
    package = _package_driver_json(file_path)
    pkg_id = package.get("driver_id")
    if pkg_id != driver_id:
        raise ValueError(
            f"That package is for '{pkg_id}', not '{driver_id}'. Nothing was "
            "changed -- installing it would have deleted one driver and "
            "installed a different one."
        )

    # Counted before and after, so a caller can tell at a glance whether the
    # references really did survive.
    refs: dict[str, Any] = {}
    for activity in await client.get_list("/api/activities"):
        detail = await client.get(f"/api/activities/{activity['entity_id']}")
        opts = detail.get("options") or {}
        blob = json.dumps(opts)
        if driver_id in blob:
            refs[localized(detail.get("name")) or activity["entity_id"]] = {
                "entities": sum(
                    1
                    for e in (opts.get("included_entities") or [])
                    if str(e.get("entity_id", "")).startswith(driver_id)
                ),
                "buttons": sum(
                    1
                    for b in (opts.get("button_mapping") or [])
                    if driver_id in json.dumps(b)
                ),
                "page_items": sum(
                    1
                    for p in ((opts.get("user_interface") or {}).get("pages") or [])
                    for i in (p.get("items") or [])
                    if driver_id in json.dumps(i)
                ),
            }

    old_version = current.get("version")
    new_version = package.get("version")

    async def _swap() -> dict:
        await client.delete(f"/api/intg/drivers/{driver_id}", timeout=120)
        await asyncio.sleep(6)
        try:
            await client.post_file("/api/intg/install", file_path)
        except httpx.HTTPStatusError as err:
            # Install answers 422 after succeeding often enough to check rather
            # than trust the status code.
            if err.response.status_code != 422:
                raise
        await asyncio.sleep(10)

        installed = await client.get(f"/api/intg/drivers/{driver_id}")
        return {
            "driver_id": driver_id,
            "version": installed.get("version"),
            "driver_state": installed.get("driver_state"),
            "references_before": refs,
            "next_steps": [
                f"start_integration_setup('{driver_id}') and answer its screens "
                "-- you will probably have to confirm pairing on the device",
                f"configure_integration_entities to add the entities back",
                "then compare references_before against what is there now",
            ],
        }

    return await apply_mutation(
        client,
        action="update_integration_driver",
        summary=f"update {localized(current.get('name')) or driver_id} "
        f"{old_version} -> {new_version} (delete and reinstall)",
        change={
            "driver_id": driver_id,
            "from": old_version,
            "to": new_version,
            "references_at_risk": refs,
        },
        do_write=_swap,
        dry_run=dry_run,
        warnings=[
            "The driver is deleted and reinstalled; there is no in-place update.",
            "Setup must be run again afterwards, and pairing usually has to be "
            "confirmed on the device itself.",
            "Entity ids normally regenerate identically, so references survive -- "
            "check before rebuilding anything.",
        ],
    )
