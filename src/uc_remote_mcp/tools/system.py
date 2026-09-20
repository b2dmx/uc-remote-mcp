"""Device snapshots and firmware updates.

A *snapshot* is the remote's own whole-device backup, taken and kept on the
remote. It is a different thing from ``backup_config``, which writes a readable
JSON copy of the configuration to this machine so it can be diffed. The two are
complementary: the snapshot restores everything including things the API does
not expose, the JSON backup is the one you can actually inspect.

Two endpoint shapes were established against the hardware rather than guessed,
because guessing here restores or flashes something:

* Restoring a snapshot is ``PUT`` on the snapshot itself. There is no
  ``/restore`` route -- a POST to one 404s with no route matched at all.
* Installing firmware is ``POST /api/system/update/{update_id}``, where the id
  comes from a check. There is no ``/install`` route either.
"""

import os
from typing import Optional

from ..safety.dry_run import apply_mutation
from ._common import get_client

SNAPSHOTS = "/api/system/backup/snapshots"


def _mb(size) -> Optional[float]:
    return round(size / 1048576, 2) if isinstance(size, (int, float)) else None


async def list_snapshots(host: Optional[str] = None) -> dict:
    """
    Device snapshots stored on the remote, newest first.

    A snapshot captures the whole device -- activities, pages, buttons,
    integrations and their settings.
    """
    client = get_client(host)
    snaps = await client.get(SNAPSHOTS)
    items = [
        {
            "snapshot_id": s.get("id"),
            "created": s.get("creation_date"),
            "size_mb": _mb(s.get("size")),
        }
        for s in (snaps or [])
    ]
    items.sort(key=lambda s: s.get("created") or "", reverse=True)
    return {"count": len(items), "snapshots": items}


async def create_snapshot(dry_run: bool = True, host: Optional[str] = None) -> dict:
    """
    Take a snapshot of the whole device, stored on the remote.

    Worth doing before installing firmware or tearing an integration down. The
    remote names it itself, from the model and the time -- a name passed in is
    accepted and ignored, so none is offered here.
    """
    client = get_client(host)

    return await apply_mutation(
        client,
        action="create_snapshot",
        summary="take a device snapshot",
        change={"target": "device snapshot"},
        # Snapshotting a full configuration is slow; the default 10s is not enough.
        do_write=lambda: client.post(SNAPSHOTS, {}, timeout=180),
        dry_run=dry_run,
    )


async def download_snapshot(
    snapshot_id: str, dest_path: str, host: Optional[str] = None
) -> dict:
    """
    Copy a snapshot off the remote to this machine.

    Snapshots live on the remote, so a remote that is reset or replaced takes
    them with it. This is how one survives that.
    """
    client = get_client(host)
    data = await client.get_bytes(f"{SNAPSHOTS}/{snapshot_id}")
    dest = os.path.abspath(os.path.expanduser(dest_path))
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    with open(dest, "wb") as fh:
        fh.write(data)
    return {"snapshot_id": snapshot_id, "path": dest, "size_mb": _mb(len(data))}


async def delete_snapshot(
    snapshot_id: str, dry_run: bool = True, host: Optional[str] = None
) -> dict:
    """Delete a snapshot from the remote. It is not recoverable afterwards."""
    client = get_client(host)
    snaps = await client.get(SNAPSHOTS) or []
    match = next((s for s in snaps if s.get("id") == snapshot_id), None)
    if match is None:
        raise ValueError(f"No snapshot '{snapshot_id}' on the remote.")

    return await apply_mutation(
        client,
        action="delete_snapshot",
        summary=f"delete snapshot {snapshot_id} (taken {match.get('creation_date')})",
        change={"snapshot_id": snapshot_id},
        do_write=lambda: client.delete(f"{SNAPSHOTS}/{snapshot_id}"),
        dry_run=dry_run,
    )


async def restore_snapshot(
    snapshot_id: str, dry_run: bool = True, host: Optional[str] = None
) -> dict:
    """
    Restore the remote from a snapshot, replacing its entire configuration.

    Everything added since the snapshot was taken is gone: activities, pages,
    button mappings, integrations and their settings. The remote restarts. Take
    a fresh snapshot first if there is anything since the old one worth keeping.
    """
    client = get_client(host)
    snaps = await client.get(SNAPSHOTS) or []
    match = next((s for s in snaps if s.get("id") == snapshot_id), None)
    if match is None:
        have = ", ".join(s.get("id", "?") for s in snaps) or "none"
        raise ValueError(f"No snapshot '{snapshot_id}' on the remote. Have: {have}")

    return await apply_mutation(
        client,
        action="restore_snapshot",
        summary=f"restore the remote from snapshot {snapshot_id} "
        f"(taken {match.get('creation_date')})",
        change={"snapshot_id": snapshot_id, "created": match.get("creation_date")},
        # Restore is a PUT on the snapshot; there is no /restore route.
        do_write=lambda: client.put(f"{SNAPSHOTS}/{snapshot_id}", None, timeout=300),
        dry_run=dry_run,
        warnings=[
            "This replaces the whole configuration -- anything created since this "
            "snapshot was taken is lost.",
            "The remote restarts and is unreachable for a minute or two.",
        ],
    )


# -------------------------------------------------------------------- firmware


async def check_for_update(host: Optional[str] = None) -> dict:
    """
    Ask the remote to check for a firmware update now, and report what it finds.

    Returns the installed version either way; ``available`` is null when the
    remote is already current.
    """
    client = get_client(host)
    status = await client.get("/api/system/update")

    available = None
    try:
        # Returns the update when there is one; 404 NOT_FOUND when current.
        available = await client.post("/api/system/update/check", {}, timeout=60)
    except Exception as e:  # noqa: BLE001 -- "nothing to install" arrives as a 404
        if "NOT_FOUND" not in str(e):
            raise

    out = {
        "installed_version": status.get("installed_version"),
        "update_in_progress": status.get("update_in_progress"),
        "checks_enabled": status.get("update_check_enabled"),
        "next_automatic_check": status.get("next_check_date"),
        "available": None,
    }
    if isinstance(available, dict) and available:
        out["available"] = {
            "update_id": available.get("update_id") or available.get("id"),
            "version": available.get("version"),
            "release_notes": available.get("description") or available.get("release_notes"),
            "size_mb": _mb(available.get("size")),
        }
    elif isinstance(available, list) and available:
        out["available"] = available
    return out


async def install_update(
    update_id: str, dry_run: bool = True, host: Optional[str] = None
) -> dict:
    """
    Install a firmware update, by the ``update_id`` from check_for_update.

    The remote downloads, installs and restarts on its own; it is unreachable
    while it does. Take a snapshot first.
    """
    client = get_client(host)
    status = await client.get("/api/system/update")
    if status.get("update_in_progress"):
        raise ValueError("An update is already in progress on the remote.")

    return await apply_mutation(
        client,
        action="install_update",
        summary=f"install firmware update {update_id} "
        f"(currently on {status.get('installed_version')})",
        change={"update_id": update_id, "from": status.get("installed_version")},
        do_write=lambda: client.post(f"/api/system/update/{update_id}", {}, timeout=120),
        dry_run=dry_run,
        warnings=[
            "The remote restarts and is offline for several minutes.",
            "Take a snapshot first if you have not recently.",
        ],
    )
