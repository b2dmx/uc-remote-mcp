"""FastMCP server — registers all UC Remote tools."""

from typing import Optional

import fastmcp

from .tools.setup import setup_remote as _setup_remote
from .tools.discovery import (
    discover_remotes as _discover_remotes,
    get_remote_info as _get_remote_info,
)
from .tools.devices import (
    list_devices as _list_devices,
    get_device as _get_device,
    list_device_commands as _list_device_commands,
)
from .tools.activities import (
    list_activities as _list_activities,
    get_activity as _get_activity,
)
from .tools.buttons import get_button_mapping as _get_button_mapping
from .tools.ui import list_ui_pages as _list_ui_pages, get_ui_page as _get_ui_page
from .tools.backup import backup_config as _backup_config
from .tools.mutations import (
    send_command as _send_command,
    set_button_mapping as _set_button_mapping,
    bulk_set_button_mapping as _bulk_set_button_mapping,
)
from .tools.ui_mutations import (
    update_ui_page as _update_ui_page,
    delete_ui_page as _delete_ui_page,
    set_default_ui_page as _set_default_ui_page,
    update_activity_sequence as _update_activity_sequence,
)
from .tools.restore import (
    diff_config as _diff_config,
    restore_config as _restore_config,
)

mcp = fastmcp.FastMCP(
    name="UC Remote MCP",
    instructions=(
        "Tools for reading and configuring Unfolded Circle Remote 3 / Remote Two. "
        "Start with setup_remote (first run only), then use discover_remotes or get_remote_info."
    ),
)


# ---------------------------------------------------------------- setup / info

@mcp.tool()
async def setup_remote(
    host: str, pin: str, port: int = 80, name: str = "UC Remote"
) -> dict:
    """
    First-run setup. Authenticate with admin PIN, create a long-lived API key,
    and save config. Only needed once per remote.
    """
    return await _setup_remote(host=host, pin=pin, port=port, name=name)


@mcp.tool()
async def discover_remotes(timeout_s: float = 8.0) -> list[dict]:
    """
    Scan the LAN via mDNS for UC remotes.
    Returns a list of {name, host, port, model, fw, id}.
    """
    return await _discover_remotes(timeout_s=timeout_s)


@mcp.tool()
async def get_remote_info(host: Optional[str] = None) -> dict:
    """
    Return model, firmware, battery level/status, and currently active activities.
    Uses the first configured remote if host is not specified.
    """
    return await _get_remote_info(host=host)


# ------------------------------------------------------------------- devices

@mcp.tool()
async def list_devices(
    host: Optional[str] = None, entity_type: Optional[str] = None
) -> list[dict]:
    """
    List all configured devices (entities). Each physical device may appear as
    several entities (e.g. a TV has both a media_player and a remote entity).
    Optionally filter by entity_type (media_player, remote, light, switch, sensor).
    Returns {id, name, type, integration, device_class, state} per entity.
    """
    return await _list_devices(host=host, entity_type=entity_type)


@mcp.tool()
async def get_device(device_id: str, host: Optional[str] = None) -> dict:
    """
    Full config for one device (entity): features, available commands,
    current attributes, and options.
    """
    return await _get_device(device_id=device_id, host=host)


@mcp.tool()
async def list_device_commands(device_id: str, host: Optional[str] = None) -> dict:
    """
    Commands a device exposes, for picking when mapping buttons.
    Returns {features, simple_commands}.
    """
    return await _list_device_commands(device_id=device_id, host=host)


# ---------------------------------------------------------------- activities

@mcp.tool()
async def list_activities(host: Optional[str] = None) -> list[dict]:
    """
    List all activities with id, name, state, description, and included entities.
    """
    return await _list_activities(host=host)


@mcp.tool()
async def get_activity(activity_id: str, host: Optional[str] = None) -> dict:
    """
    Full activity config: included entities, on/off power sequences,
    button overrides, and the list of UI pages.
    """
    return await _get_activity(activity_id=activity_id, host=host)


# ------------------------------------------------------------ buttons / UI

@mcp.tool()
async def get_button_mapping(
    scope: str, scope_id: Optional[str] = None, host: Optional[str] = None
) -> dict:
    """
    Physical-button -> command bindings. scope is 'activity' (needs
    scope_id=activity_id), 'remote' (needs scope_id=remote entity_id), or 'device'
    (needs scope_id=target entity_id; returns every binding across all activities
    and remotes that targets that device).
    """
    return await _get_button_mapping(scope=scope, scope_id=scope_id, host=host)


@mcp.tool()
async def list_ui_pages(scope: str, scope_id: str, host: Optional[str] = None) -> dict:
    """
    List UI pages for a scope: 'activity' or 'remote'. scope_id is that entity's id.
    Returns page ids, names, grids, and item counts.
    """
    return await _list_ui_pages(scope=scope, scope_id=scope_id, host=host)


@mcp.tool()
async def get_ui_page(
    scope: str, scope_id: str, page_id: str, host: Optional[str] = None
) -> dict:
    """
    Items on one UI page: grid size and each item's position, type, and command.
    Identify the page by its parent scope ('activity'/'remote'), the scope's
    entity_id, and the page_id (from list_ui_pages).
    """
    return await _get_ui_page(scope=scope, scope_id=scope_id, page_id=page_id, host=host)


# ------------------------------------------------------------------- backup

@mcp.tool()
async def backup_config(
    output_path: Optional[str] = None, host: Optional[str] = None
) -> dict:
    """
    Dump the entire remote configuration (system, entities, activities,
    remote-entities, UI pages — full detail) to one JSON file. Defaults to
    %APPDATA%/uc-remote-mcp/backups/<timestamp>.json, keeping the last 50.
    """
    return await _backup_config(output_path=output_path, host=host)


# --------------------------------------------------------- mutations (Phase 2)

@mcp.tool()
async def send_command(
    device_id: str,
    command: str,
    params: Optional[dict] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Fire a one-off command at a device (entity). Transient (does not change saved
    config) but affects the device, so defaults to dry_run=True. Set dry_run=false
    to actually send. Body: PUT /entities/{id}/command {cmd_id, params?}.
    """
    return await _send_command(
        device_id=device_id, command=command, params=params, dry_run=dry_run, host=host
    )


@mcp.tool()
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
    Set one physical-button -> command binding on an 'activity' or 'remote'.
    entity_id is REQUIRED for activities (the command target) and ignored for
    remotes. Defaults to dry_run=True (shows before/after); auto-backs-up before
    any real write. Set dry_run=false to apply.
    """
    return await _set_button_mapping(
        scope=scope,
        scope_id=scope_id,
        button=button,
        command=command,
        press=press,
        entity_id=entity_id,
        params=params,
        dry_run=dry_run,
        host=host,
    )


@mcp.tool()
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
    Set the same button binding across many activities at once (e.g. route
    VOLUME_UP on every activity to the AVR). Filter with activity_ids and/or
    name_contains; no filter = all activities. Invalid activities are skipped
    with a reason. One backup before the batch. Defaults to dry_run=True
    (returns the full per-activity plan); set dry_run=false to apply.
    """
    return await _bulk_set_button_mapping(
        button=button,
        command=command,
        entity_id=entity_id,
        press=press,
        params=params,
        activity_ids=activity_ids,
        name_contains=name_contains,
        dry_run=dry_run,
        host=host,
    )


@mcp.tool()
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
    Update a UI page's name, grid, and/or items on an 'activity' or 'remote'.
    Omitted fields stay unchanged; an EMPTY items list clears the page. Item
    commands are validated against the scope before writing. Defaults to
    dry_run=True; auto-backup before any real write.
    """
    return await _update_ui_page(
        scope=scope, scope_id=scope_id, page_id=page_id,
        name=name, grid=grid, items=items, dry_run=dry_run, host=host,
    )


@mcp.tool()
async def delete_ui_page(
    scope: str, scope_id: str, page_id: str,
    dry_run: bool = True, host: Optional[str] = None,
) -> dict:
    """
    Delete a UI page from an 'activity' or 'remote'. IRREVOCABLE on the device —
    the auto-backup taken before the write is the only way back. Dry-run (default)
    shows the full page content that would be lost.
    """
    return await _delete_ui_page(
        scope=scope, scope_id=scope_id, page_id=page_id, dry_run=dry_run, host=host
    )


@mcp.tool()
async def set_default_ui_page(
    scope: str, scope_id: str, page_id: str,
    dry_run: bool = True, host: Optional[str] = None,
) -> dict:
    """
    Make a page the first/default page of an 'activity' or 'remote' UI (the page
    shown when it opens). Implemented as a page reorder — the API has no explicit
    default-page property. Defaults to dry_run=True.
    """
    return await _set_default_ui_page(
        scope=scope, scope_id=scope_id, page_id=page_id, dry_run=dry_run, host=host
    )


@mcp.tool()
async def update_activity_sequence(
    activity_id: str,
    on_sequence: Optional[list] = None,
    off_sequence: Optional[list] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Replace an activity's on and/or off power sequence. Steps are
    {"type":"command","command":{"entity_id","cmd_id","params"?}} or
    {"type":"delay","delay":<ms>}. Omitted sequence = unchanged; empty list
    clears it. Command steps are validated against the activity's included
    entities. Defaults to dry_run=True; auto-backup before any real write.
    """
    return await _update_activity_sequence(
        activity_id=activity_id,
        on_sequence=on_sequence,
        off_sequence=off_sequence,
        dry_run=dry_run,
        host=host,
    )


@mcp.tool()
async def diff_config(against_path: str, host: Optional[str] = None) -> dict:
    """
    Show what changed between the current live config and a backup file
    (read-only). Reports the operations a restore would perform plus
    differences that cannot be restored.
    """
    return await _diff_config(against_path=against_path, host=host)


@mcp.tool()
async def restore_config(
    input_path: str,
    confirmation_token: Optional[str] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Restore activities/remotes customization (names, button mappings, UI pages,
    sequences) from a backup file. First call returns a confirmation_token +
    full plan without writing; call again with the token and dry_run=false to
    apply. Auto-backup of the current state is taken before applying.
    """
    return await _restore_config(
        input_path=input_path,
        confirmation_token=confirmation_token,
        dry_run=dry_run,
        host=host,
    )


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
