"""Infrared: the built-in code database, learned codes, emitters and docks.

Most IR use needs none of this -- an IR device shows up as an ordinary entity
and ``send_command`` drives it. This is for the layer underneath: finding the
right codeset for a device, seeing which emitter will actually fire, and keeping
codes you learned.

The code database is three levels deep and the paths are not guessable, so, for
the record: manufacturers are ``/api/ir/codes/manufacturers?q=``, a
manufacturer's codesets are ``/api/ir/codes/manufacturers/{id}``, and one
codeset's command list is ``/api/ir/codes/manufacturers/{id}/{codeset_id}``.

Not here, because the core does not expose them over REST at all: **learning a
code** and **dock configuration** (LED brightness, port modes, dock firmware).
Both are WebSocket-only. ``list_docks`` reads what REST does report.

Also established the hard way: the ``/codes`` sub-resource of a custom codeset
is broken in firmware 2.8.4, in both directions. POST returns OK but ignores the
``key`` given and stores the code under the literal name "codes", then 422s on
the next one. DELETE ignores the keys given in the same way and only ever
removes a code named "codes", 404ing when there is none -- which reads exactly
like success on the one codeset where the POST bug had already created one.

So a custom codeset's codes are fixed at creation. Changing them means creating
a replacement set and deleting the old one. There is no tool here for adding or
removing individual codes, because there is no request that does it.
"""

from typing import Any, Optional

from ..safety.dry_run import apply_mutation
from ._common import get_client

CODES = "/api/ir/codes"


async def list_ir_manufacturers(
    query: str, device_type: Optional[str] = None, host: Optional[str] = None
) -> dict:
    """
    Search the built-in IR database for a manufacturer.

    ``query`` must be at least two characters -- the remote rejects shorter.
    ``device_type`` narrows it ("tv", "avr", and so on).
    """
    if len(query.strip()) < 2:
        raise ValueError("The search needs at least two characters.")
    client = get_client(host)
    path = f"{CODES}/manufacturers?q={query.strip()}"
    if device_type:
        path += f"&device_type={device_type}"
    found = await client.get(path)
    return {
        "count": len(found or []),
        "manufacturers": [
            {"manufacturer_id": m.get("id"), "name": m.get("name"), "custom": m.get("custom")}
            for m in (found or [])
        ],
    }


async def list_ir_codesets(
    manufacturer_id: str, query: Optional[str] = None, host: Optional[str] = None
) -> dict:
    """
    The codesets a manufacturer offers -- one per device or device family.

    Manufacturers ship many near-identical sets ("Generic AVR 1", "Generic AVR
    2"); the reliable way to pick is to try one and see if the device responds.
    """
    client = get_client(host)
    path = f"{CODES}/manufacturers/{manufacturer_id}"
    if query:
        path += f"?q={query}"
    sets = await client.get(path)
    return {
        "manufacturer_id": manufacturer_id,
        "count": len(sets or []),
        "codesets": [
            {"codeset_id": s.get("id"), "name": s.get("name"), "custom": s.get("custom")}
            for s in (sets or [])
        ],
    }


async def get_ir_codeset(
    manufacturer_id: str, codeset_id: str, host: Optional[str] = None
) -> dict:
    """The command keys a codeset provides, such as POWER_ON or INPUT_1."""
    client = get_client(host)
    keys = await client.get(f"{CODES}/manufacturers/{manufacturer_id}/{codeset_id}")
    return {
        "manufacturer_id": manufacturer_id,
        "codeset_id": codeset_id,
        "count": len(keys or []),
        "commands": keys or [],
    }


# ------------------------------------------------------------- learned codes


async def list_custom_ir_codesets(
    query: Optional[str] = None, host: Optional[str] = None
) -> dict:
    """Codesets learned on this remote, as opposed to ones from the database."""
    client = get_client(host)
    sets = await client.get(f"{CODES}/custom" + (f"?q={query}" if query else ""))
    return {
        "count": len(sets or []),
        "codesets": [
            {
                "codeset_id": s.get("device_id"),
                "name": s.get("device"),
                "device_type": s.get("device_type"),
            }
            for s in (sets or [])
        ],
    }


async def get_custom_ir_codeset(codeset_id: str, host: Optional[str] = None) -> dict:
    """One learned codeset, with every code and its raw value."""
    client = get_client(host)
    d = await client.get(f"{CODES}/custom/{codeset_id}")
    return {
        "codeset_id": d.get("device_id"),
        "name": d.get("device"),
        "device_type": d.get("device_type"),
        "codes": [
            {"command": c.get("key"), "format": c.get("format"), "value": c.get("value")}
            for c in (d.get("codes") or [])
        ],
    }


def _codes(codes: Optional[list[dict]]) -> tuple[list[dict], str]:
    """Take {command, value, format} and emit what a write wants.

    Reads report a format per code, but a write takes one ``code_format`` for
    the whole set and rejects per-code formats -- so the format is collected
    here and a mixed set is refused rather than silently flattened.
    """
    out: list[dict] = []
    formats = set()
    for i, c in enumerate(codes or []):
        key = c.get("command") or c.get("key")
        if not key or not c.get("value"):
            raise ValueError(f"code {i}: needs 'command' and 'value'")
        formats.add((c.get("format") or "HEX").upper())
        out.append({"key": key, "value": c["value"]})
    if len(formats) > 1:
        raise ValueError(
            "All codes in a set must share one format; got "
            + ", ".join(sorted(formats))
        )
    return out, (formats.pop() if formats else "HEX")


async def create_custom_ir_codeset(
    name: str,
    codes: list[dict],
    device_type: str = "various",
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Create a custom codeset with its codes.

    Codes are ``{"command": "POWER_ON", "value": "4;0x540C;15;0"}``; the whole
    set shares one ``format``, HEX or PRONTO, taken from the codes given.

    Everything has to go in at creation. The endpoint for adding or removing an
    individual code is broken in firmware 2.8.4 -- it ignores the command name
    given and acts on a code called literally "codes" -- so changing a codeset
    means creating a replacement with the full list and deleting the old one.

    Learning a code from a physical remote is not on the REST API at all. Learn
    it on the remote, then read the value back with get_custom_ir_codeset.
    """
    if not codes:
        raise ValueError(
            "A codeset needs its codes at creation -- they cannot be added "
            "afterwards on this firmware."
        )
    client = get_client(host)
    body: dict[str, Any] = {"device": name, "device_type": device_type}
    body["codes"], body["code_format"] = _codes(codes)

    return await apply_mutation(
        client,
        action="create_custom_ir_codeset",
        summary=f"create IR codeset '{name}' with {len(body['codes'])} codes "
        f"({body['code_format']})",
        change={"name": name, "format": body["code_format"], "codes": body["codes"]},
        do_write=lambda: client.post(f"{CODES}/custom", body),
        dry_run=dry_run,
    )


async def rename_custom_ir_codeset(
    codeset_id: str,
    name: str,
    device_type: Optional[str] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Rename a custom codeset. Only the name and device type can be changed this
    way -- codes passed to the same endpoint are accepted and silently ignored.
    """
    client = get_client(host)
    current = await client.get(f"{CODES}/custom/{codeset_id}")
    body: dict[str, Any] = {"device": name}
    if device_type:
        body["device_type"] = device_type

    return await apply_mutation(
        client,
        action="rename_custom_ir_codeset",
        summary=f"rename codeset '{current.get('device')}' -> '{name}'",
        change={"codeset_id": codeset_id, "from": current.get("device"), "to": name},
        do_write=lambda: client.patch(f"{CODES}/custom/{codeset_id}", body),
        dry_run=dry_run,
    )


async def delete_custom_ir_codeset(
    codeset_id: str, dry_run: bool = True, host: Optional[str] = None
) -> dict:
    """
    Delete a learned codeset. Codes in it are gone -- they were learned from a
    physical remote and are not in the built-in database.
    """
    client = get_client(host)
    d = await client.get(f"{CODES}/custom/{codeset_id}")

    return await apply_mutation(
        client,
        action="delete_custom_ir_codeset",
        summary=f"delete learned codeset '{d.get('device')}' "
        f"({len(d.get('codes') or [])} codes)",
        change={"codeset_id": codeset_id, "name": d.get("device")},
        do_write=lambda: client.delete(f"{CODES}/custom/{codeset_id}"),
        dry_run=dry_run,
        warnings=["Learned codes cannot be recovered from the built-in database."],
    )


# ------------------------------------------------------------ emitters, docks


async def list_ir_emitters(host: Optional[str] = None) -> dict:
    """
    What can actually send IR: the remote's own blaster and any dock, with the
    output ports each offers.

    A device that ignores IR commands is usually pointed at the wrong emitter --
    the remote's internal blaster needs line of sight, a dock port does not.
    """
    client = get_client(host)
    emitters = await client.get("/api/ir/emitters")
    return {
        "emitters": [
            {
                "device_id": e.get("device_id"),
                "name": e.get("name"),
                "type": e.get("type"),
                "active": e.get("active"),
                "can_learn": "learning" in (e.get("capabilities") or {}),
                "ports": [
                    {"port_id": p.get("port_id"), "name": p.get("name")}
                    for p in (e.get("ports") or [])
                ],
            }
            for e in (emitters or [])
        ]
    }


async def list_docks(host: Optional[str] = None) -> dict:
    """
    Docks paired with the remote: firmware, connection, and what each port is
    set to.

    Read-only -- changing dock settings or updating dock firmware is not on the
    REST API, only in the web configurator.
    """
    client = get_client(host)
    docks = await client.get("/api/docks")
    return {
        "count": len(docks or []),
        "docks": [
            {
                "dock_id": d.get("dock_id"),
                "name": d.get("name"),
                "model": d.get("model"),
                "state": d.get("state"),
                "version": d.get("version"),
                "connection": d.get("connection_type"),
                "url": d.get("resolved_ws_url"),
                "led_brightness": d.get("led_brightness"),
                "learning_active": d.get("learning_active"),
                "ports": [
                    {
                        "port": p.get("port"),
                        "mode": p.get("mode"),
                        "active_mode": p.get("active_mode"),
                    }
                    for p in (d.get("ports") or [])
                ],
            }
            for d in (docks or [])
        ],
    }


async def discover_docks(host: Optional[str] = None) -> dict:
    """
    Docks visible on the network but not yet paired.

    An empty list with ``discovery_active`` false usually means discovery is not
    running -- it is started from the remote's dock setup screen.
    """
    client = get_client(host)
    found = await client.get("/api/docks/discover")
    return {
        "discovery_active": found.get("active"),
        "docks": found.get("docks") or [],
    }
