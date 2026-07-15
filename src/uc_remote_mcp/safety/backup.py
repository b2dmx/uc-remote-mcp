"""Config snapshot helper — used by both backup_config (human tool) and
the auto-snapshot taken before every mutation (Phase 2)."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..client.rest import UCClient

MAX_BACKUPS = 50
SCHEMA_VERSION = 1


def backups_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path.home() / ".config"
    d = base / "uc-remote-mcp" / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


async def _safe_get(client: UCClient, path: str):
    try:
        return await client.get(path)
    except Exception as e:  # noqa: BLE001
        return {"_error": str(e), "_path": path}


async def _must_get(client: UCClient, path: str):
    """Structural fetch: a failure here means the snapshot would be hollow
    (e.g. remote in standby), so fail loudly instead of writing a bad backup."""
    try:
        return await client.get(path)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(
            f"Cannot snapshot config: {path} unreachable ({type(e).__name__}). "
            "The remote may be in standby — wake it and retry."
        ) from e


async def _must_get_list(client: UCClient, path: str) -> list:
    """Paginated structural list fetch with the same fail-loud semantics.
    Core list endpoints truncate at 10 items per page by default."""
    try:
        return await client.get_list(path)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(
            f"Cannot snapshot config: {path} unreachable ({type(e).__name__}). "
            "The remote may be in standby — wake it and retry."
        ) from e


async def collect_config(client: UCClient) -> dict:
    """
    Pull a complete, lossless snapshot of the remote configuration: system info,
    integration instances, and full detail for every entity, activity, and
    remote-entity. UI pages and button mappings live inside those details.

    Raises RuntimeError if the structural list endpoints are unreachable —
    a partial/hollow snapshot must never be written or used for diff/restore.
    """
    version = await _must_get(client, "/api/pub/version")
    system = await _safe_get(client, "/api/system")
    try:
        intg = await client.get_list("/api/intg/instances")
    except Exception as e:  # noqa: BLE001
        intg = {"_error": str(e), "_path": "/api/intg/instances"}

    async def detail_map(list_path: str, item_path, id_key="entity_id"):
        items = await _must_get_list(client, list_path)
        out = {}
        for it in items if isinstance(items, list) else []:
            iid = it.get(id_key)
            if iid:
                # Details must be complete too: a snapshot silently missing one
                # object's options would later "restore" it to empty.
                out[iid] = await _must_get(client, item_path(iid))
        return out

    entities = await detail_map("/api/entities", lambda i: f"/api/entities/{i}")
    activities = await detail_map("/api/activities", lambda i: f"/api/activities/{i}")
    remotes = await detail_map("/api/remotes", lambda i: f"/api/remotes/{i}")

    return {
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "device_name": version.get("device_name") if isinstance(version, dict) else None,
            "model": version.get("model") if isinstance(version, dict) else None,
            "core_version": version.get("core") if isinstance(version, dict) else None,
        },
        "version": version,
        "system": system,
        "integrations": intg,
        "entities": entities,
        "activities": activities,
        "remotes": remotes,
    }


def _prune(directory: Path, keep: int = MAX_BACKUPS) -> int:
    files = sorted(directory.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    removed = 0
    for f in files[keep:]:
        try:
            f.unlink()
            removed += 1
        except OSError:
            pass
    return removed


async def create_backup(client: UCClient, output_path: Optional[str] = None) -> dict:
    """Collect a snapshot, write it to disk, prune old backups. Returns a summary."""
    config = await collect_config(client)

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
    else:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = backups_dir() / f"{ts}.json"

    path.write_text(json.dumps(config, indent=2))
    pruned = _prune(path.parent) if not output_path else 0

    return {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "counts": {
            "entities": len(config["entities"]),
            "activities": len(config["activities"]),
            "remotes": len(config["remotes"]),
        },
        "pruned_old_backups": pruned,
    }
