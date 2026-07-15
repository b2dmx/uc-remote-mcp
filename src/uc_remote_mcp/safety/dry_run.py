"""Mutation safety envelope: dry-run gating + auto-backup before every write.

Every mutating tool routes through apply_mutation(). When dry_run is True (the
default everywhere) it returns a description of the planned change and writes
nothing. When dry_run is False it first takes a full config snapshot (rolling
backup, last 50 kept) and only then performs the write.
"""

from typing import Awaitable, Callable, Optional

from ..client.rest import UCClient
from .backup import create_backup


async def apply_mutation(
    client: UCClient,
    *,
    action: str,
    summary: str,
    change: dict,
    do_write: Callable[[], Awaitable],
    dry_run: bool,
    warnings: Optional[list[str]] = None,
) -> dict:
    """
    Gate a mutation behind dry-run + auto-backup.

    Args:
        action: machine name of the operation (e.g. "set_button_mapping").
        summary: one-line human description of what will change.
        change: structured before/after (or planned) detail for the preview.
        do_write: zero-arg coroutine performing the actual write; only awaited
            when dry_run is False.
        dry_run: when True, nothing is written.
        warnings: non-fatal validation notes to surface to the caller.

    Returns an envelope dict describing what happened (or would happen).
    """
    envelope: dict = {
        "action": action,
        "dry_run": dry_run,
        "summary": summary,
        "change": change,
    }
    if warnings:
        envelope["warnings"] = warnings

    if dry_run:
        envelope["note"] = (
            "Nothing was written. Re-run with dry_run=false to apply this change."
        )
        return envelope

    # Real write: snapshot the whole config first, then mutate.
    backup = await create_backup(client)
    envelope["backup"] = {"path": backup["path"], "size_bytes": backup["size_bytes"]}
    envelope["result"] = await do_write()
    envelope["applied"] = True
    return envelope
