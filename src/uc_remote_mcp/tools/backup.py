"""Backup tool: dump the entire remote configuration to one JSON file."""

from typing import Optional

from ._common import get_client
from ..safety.backup import create_backup


async def backup_config(
    output_path: Optional[str] = None, host: Optional[str] = None
) -> dict:
    """
    Dump the complete remote configuration (system info, integrations, and full
    detail for every entity, activity, and remote-entity — including embedded UI
    pages and button mappings) to a single JSON file.

    Defaults to %APPDATA%/uc-remote-mcp/backups/<timestamp>.json and keeps the
    last 50 backups. Pass output_path to write somewhere specific (no pruning).

    Returns a summary with the file path, size, and object counts.
    """
    client = get_client(host)
    return await create_backup(client, output_path=output_path)
