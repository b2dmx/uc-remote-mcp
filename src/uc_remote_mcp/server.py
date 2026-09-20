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
    create_activity as _create_activity,
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
    create_ui_page as _create_ui_page,
    delete_ui_page as _delete_ui_page,
    set_default_ui_page as _set_default_ui_page,
    update_activity_sequence as _update_activity_sequence,
)
from .tools.integrations import (
    list_integrations as _list_integrations,
    get_integration as _get_integration,
    list_integration_entities as _list_integration_entities,
    configure_integration_entities as _configure_integration_entities,
    set_integration_enabled as _set_integration_enabled,
    restart_integration as _restart_integration,
    install_integration as _install_integration,
    delete_integration as _delete_integration,
    start_integration_setup as _start_integration_setup,
    get_integration_setup as _get_integration_setup,
    answer_integration_setup as _answer_integration_setup,
    cancel_integration_setup as _cancel_integration_setup,
    confirm_integration_setup as _confirm_integration_setup,
    delete_integration_instance as _delete_integration_instance,
    restart_remote as _restart_remote,
    set_integration_connected as _set_integration_connected,
    discover_integrations as _discover_integrations,
)
from .tools.inclusion import (
    list_scope_entities as _list_scope_entities,
    add_scope_entities as _add_scope_entities,
    remove_scope_entities as _remove_scope_entities,
)
from .tools.home import (
    list_profiles as _list_profiles,
    get_home_layout as _get_home_layout,
    set_home_tiles as _set_home_tiles,
    create_home_page as _create_home_page,
    delete_home_page as _delete_home_page,
    set_profile_group as _set_profile_group,
    delete_profile_group as _delete_profile_group,
)
from .tools.manage import (
    update_entity as _update_entity,
    delete_entities as _delete_entities,
    delete_activity as _delete_activity,
    clear_button_mapping as _clear_button_mapping,
    list_macros as _list_macros,
    get_macro as _get_macro,
    set_macro as _set_macro,
    delete_macro as _delete_macro,
    list_activity_groups as _list_activity_groups,
    update_activity_group as _update_activity_group,
    list_resources as _list_resources,
    upload_resource as _upload_resource,
    delete_resource as _delete_resource,
)
from .tools.ir import (
    list_ir_manufacturers as _list_ir_manufacturers,
    list_ir_codesets as _list_ir_codesets,
    get_ir_codeset as _get_ir_codeset,
    list_custom_ir_codesets as _list_custom_ir_codesets,
    get_custom_ir_codeset as _get_custom_ir_codeset,
    create_custom_ir_codeset as _create_custom_ir_codeset,
    rename_custom_ir_codeset as _rename_custom_ir_codeset,
    delete_custom_ir_codeset as _delete_custom_ir_codeset,
    list_ir_emitters as _list_ir_emitters,
    list_docks as _list_docks,
    discover_docks as _discover_docks,
)
from .tools.remotes import (
    list_remote_entities as _list_remote_entities,
    create_ir_remote as _create_ir_remote,
    set_ir_output as _set_ir_output,
    delete_remote_entity as _delete_remote_entity,
)
from .tools.settings import (
    get_settings as _get_settings,
    update_settings as _update_settings,
    get_system_status as _get_system_status,
    list_features as _list_features,
    set_feature_enabled as _set_feature_enabled,
)
from .tools.system import (
    list_snapshots as _list_snapshots,
    create_snapshot as _create_snapshot,
    download_snapshot as _download_snapshot,
    delete_snapshot as _delete_snapshot,
    restore_snapshot as _restore_snapshot,
    check_for_update as _check_for_update,
    install_update as _install_update,
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


# ----------------------------------------------------------------- integrations

@mcp.tool()
async def list_integrations(host: Optional[str] = None) -> dict:
    """
    Installed integration drivers and their configured instances.

    device_state is not a health signal: an instance reports CONNECTED while
    its entities are stale. Check the entities too.
    """
    return await _list_integrations(host=host)


@mcp.tool()
async def get_integration(integration_id: str, host: Optional[str] = None) -> dict:
    """One integration instance in full, including the entities it has configured."""
    return await _get_integration(integration_id=integration_id, host=host)


@mcp.tool()
async def list_integration_entities(
    integration_id: str, only_new: bool = True, host: Optional[str] = None
) -> dict:
    """
    Entities an integration offers. only_new re-polls the integration and lists
    what is not exposed yet, which is required after pairing a new device.
    """
    return await _list_integration_entities(
        integration_id=integration_id, only_new=only_new, host=host
    )


@mcp.tool()
async def configure_integration_entities(
    integration_id: str,
    entity_ids: list[str],
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Expose entities from an integration so activities and pages can use them.
    Additive; removes nothing. Setup finishing does not do this for you.
    """
    return await _configure_integration_entities(
        integration_id=integration_id, entity_ids=entity_ids, dry_run=dry_run, host=host
    )


@mcp.tool()
async def set_integration_enabled(
    integration_id: str, enabled: bool, dry_run: bool = True, host: Optional[str] = None
) -> dict:
    """Enable or disable an integration instance."""
    return await _set_integration_enabled(
        integration_id=integration_id, enabled=enabled, dry_run=dry_run, host=host
    )


@mcp.tool()
async def restart_integration(
    integration_id: str, dry_run: bool = True, host: Optional[str] = None
) -> dict:
    """
    Disable and re-enable an integration. The usual fix when devices stop
    responding but the integration still claims to be connected.
    """
    return await _restart_integration(
        integration_id=integration_id, dry_run=dry_run, host=host
    )


@mcp.tool()
async def install_integration(
    file_path: str, dry_run: bool = True, host: Optional[str] = None
) -> dict:
    """
    Install a custom driver from a .tar.gz archive on this machine. There is no
    in-place update: delete the old driver first. Restart the system afterwards
    or its setup flow will not start.
    """
    return await _install_integration(file_path=file_path, dry_run=dry_run, host=host)


@mcp.tool()
async def delete_integration(
    driver_id: str, dry_run: bool = True, host: Optional[str] = None
) -> dict:
    """
    Remove a driver, its instance and all its entities. Also strips every button
    mapping and page item that used them. Read the preview before applying.
    """
    return await _delete_integration(driver_id=driver_id, dry_run=dry_run, host=host)


@mcp.tool()
async def start_integration_setup(
    driver_id: str,
    reconfigure: bool = False,
    setup_data: Optional[dict] = None,
    host: Optional[str] = None,
) -> dict:
    """
    Begin an integration's setup and return its first screen.

    Some drivers require a value up front (usually an API key) and answer
    "400 Setup data not provided for field: X" without it — pass
    setup_data={"X": "..."}. A 503 means the driver process is not running yet,
    which is normal right after installing: restart the system first.
    """
    return await _start_integration_setup(
        driver_id=driver_id, reconfigure=reconfigure, setup_data=setup_data, host=host
    )


@mcp.tool()
async def get_integration_setup(driver_id: str, host: Optional[str] = None) -> dict:
    """The current screen of a setup flow. 404 means no flow is in progress."""
    return await _get_integration_setup(driver_id=driver_id, host=host)


@mcp.tool()
async def answer_integration_setup(
    driver_id: str, values: dict, host: Optional[str] = None
) -> dict:
    """
    Answer the current setup screen and return the next. Send every field the
    screen asks for; a rejected step ends the flow and it must be restarted.
    """
    return await _answer_integration_setup(driver_id=driver_id, values=values, host=host)


@mcp.tool()
async def cancel_integration_setup(driver_id: str, host: Optional[str] = None) -> dict:
    """Abandon an in-progress setup flow, changing nothing."""
    return await _cancel_integration_setup(driver_id=driver_id, host=host)


@mcp.tool()
async def restart_remote(
    target: str = "ui", dry_run: bool = True, host: Optional[str] = None
) -> dict:
    """
    Restart the remote's "ui", "core", or "system". Sends no device commands and
    changes no configuration. "ui" is how configuration changes are made to
    repaint; "system" is required after installing a driver.
    """
    return await _restart_remote(target=target, dry_run=dry_run, host=host)


# ------------------------------------------------------- activity/macro entities

@mcp.tool()
async def list_scope_entities(
    scope_id: str, scope: str = "activity", host: Optional[str] = None
) -> dict:
    """
    Entities an activity or macro is currently allowed to use. scope is
    "activity" or "macro" — both keep their own list, and a command naming an
    entity outside it is rejected.
    """
    return await _list_scope_entities(scope_id=scope_id, scope=scope, host=host)


@mcp.tool()
async def add_scope_entities(
    scope_id: str,
    entity_ids: list[str],
    scope: str = "activity",
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Allow an activity or macro to use more entities. Exposing an entity from an
    integration is not enough on its own — it must also be added here before a
    button or page item can use it. Existing entries are preserved.
    """
    return await _add_scope_entities(
        scope_id=scope_id, entity_ids=entity_ids, scope=scope, dry_run=dry_run, host=host
    )


@mcp.tool()
async def remove_scope_entities(
    scope_id: str,
    entity_ids: list[str],
    scope: str = "activity",
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Stop an activity or macro using entities. Every button mapping and page item
    referencing them is removed too, so read the preview before applying.
    """
    return await _remove_scope_entities(
        scope_id=scope_id, entity_ids=entity_ids, scope=scope, dry_run=dry_run, host=host
    )


@mcp.tool()
async def confirm_integration_setup(
    driver_id: str, confirm: bool = True, host: Optional[str] = None
) -> dict:
    """
    Answer a confirmation screen ("press the button on the device, then
    continue") and return the next one. Use answer_integration_setup for
    screens with fields; this is for the ones without.
    """
    return await _confirm_integration_setup(driver_id=driver_id, confirm=confirm, host=host)


@mcp.tool()
async def delete_integration_instance(
    integration_id: str, dry_run: bool = True, host: Optional[str] = None
) -> dict:
    """
    Remove one configured instance and its entities, keeping the driver. The
    teardown for firmware-shipped drivers. Also strips every button mapping and
    page item that used those entities — read the preview.
    """
    return await _delete_integration_instance(
        integration_id=integration_id, dry_run=dry_run, host=host
    )


@mcp.tool()
async def create_ui_page(
    scope: str,
    scope_id: str,
    name: str,
    grid: dict,
    items: Optional[list] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Add a new page to an activity or remote-entity. scope is "activity" or
    "remote". grid is {"width": N, "height": M}; items use the same shape as
    get_ui_page returns. The page is appended last; reorder with
    set_default_ui_page. Every item command is validated first.
    """
    return await _create_ui_page(
        scope=scope, scope_id=scope_id, name=name, grid=grid, items=items,
        dry_run=dry_run, host=host,
    )


@mcp.tool()
async def create_activity(
    name: str,
    icon: Optional[str] = None,
    description: Optional[str] = None,
    entity_ids: Optional[list[str]] = None,
    clone_from: Optional[str] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Create an activity — a "device" on the remote's home screen.

    Pass entity_ids to build from scratch, or clone_from to copy an existing
    activity/macro/remote-entity; not both. icon takes "uc:name" or
    "custom:file.png". The empty page the remote creates alongside it is
    removed, and the result says if it joined the default activity group, which
    can make its tile power devices on and off.
    """
    return await _create_activity(
        name=name, icon=icon, description=description, entity_ids=entity_ids,
        clone_from=clone_from, dry_run=dry_run, host=host,
    )


# ------------------------------------------------------------------ home screen

@mcp.tool()
async def list_profiles(host: Optional[str] = None) -> dict:
    """Profiles on the remote, and which one is currently active."""
    return await _list_profiles(host=host)


@mcp.tool()
async def get_home_layout(
    profile_id: Optional[str] = None, host: Optional[str] = None
) -> dict:
    """
    The home screen: its pages, the tiles on each in order, and any groups.
    Defaults to the active profile.
    """
    return await _get_home_layout(profile_id=profile_id, host=host)


@mcp.tool()
async def set_home_tiles(
    page_id: str,
    entity_ids: list[str],
    profile_id: Optional[str] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Replace a home page's tiles, in the order given — this is also how you
    reorder them. Send the complete list; anything omitted is removed.
    """
    return await _set_home_tiles(
        page_id=page_id, entity_ids=entity_ids, profile_id=profile_id,
        dry_run=dry_run, host=host,
    )


@mcp.tool()
async def create_home_page(
    name: str,
    entity_ids: Optional[list[str]] = None,
    pos: Optional[int] = None,
    profile_id: Optional[str] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """Add a page of tiles to the home screen."""
    return await _create_home_page(
        name=name, entity_ids=entity_ids, pos=pos, profile_id=profile_id,
        dry_run=dry_run, host=host,
    )


@mcp.tool()
async def delete_home_page(
    page_id: str,
    profile_id: Optional[str] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """Remove a page from the home screen. The activities on it are untouched."""
    return await _delete_home_page(
        page_id=page_id, profile_id=profile_id, dry_run=dry_run, host=host
    )


@mcp.tool()
async def set_profile_group(
    name: str,
    entity_ids: list[str],
    group_id: Optional[str] = None,
    icon: Optional[str] = None,
    profile_id: Optional[str] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Create a group of entities, or update one by passing group_id. A group gets
    its own page on the home carousel.
    """
    return await _set_profile_group(
        name=name, entity_ids=entity_ids, group_id=group_id, icon=icon,
        profile_id=profile_id, dry_run=dry_run, host=host,
    )


@mcp.tool()
async def delete_profile_group(
    group_id: str,
    profile_id: Optional[str] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Delete a group. A forgotten group is the usual cause of a stray or blank
    tile on the home carousel.
    """
    return await _delete_profile_group(
        group_id=group_id, profile_id=profile_id, dry_run=dry_run, host=host
    )


# ------------------------------------------------- entities, activities, macros

@mcp.tool()
async def update_entity(
    entity_id: str,
    name: Optional[str] = None,
    icon: Optional[str] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """Rename an entity or change its icon ("uc:name" or "custom:file.png")."""
    return await _update_entity(
        entity_id=entity_id, name=name, icon=icon, dry_run=dry_run, host=host
    )


@mcp.tool()
async def delete_entities(
    entity_ids: list[str], dry_run: bool = True, host: Optional[str] = None
) -> dict:
    """
    Remove entities. They return if configured again from their integration,
    which makes this the cure for one stuck reporting nothing — but buttons and
    page items using them are removed too.
    """
    return await _delete_entities(entity_ids=entity_ids, dry_run=dry_run, host=host)


@mcp.tool()
async def delete_activity(
    activity_id: str, dry_run: bool = True, host: Optional[str] = None
) -> dict:
    """Delete an activity with its pages and buttons. Entities are untouched."""
    return await _delete_activity(activity_id=activity_id, dry_run=dry_run, host=host)


@mcp.tool()
async def clear_button_mapping(
    scope_id: str,
    button: str,
    press: Optional[str] = None,
    scope: str = "activity",
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Unbind a button, or one press of it. press is "short_press" or
    "long_press"; omit to clear both. scope is "activity" or "remote".
    """
    return await _clear_button_mapping(
        scope_id=scope_id, button=button, press=press, scope=scope,
        dry_run=dry_run, host=host,
    )


@mcp.tool()
async def list_macros(host: Optional[str] = None) -> dict:
    """Macros on the remote, with how many steps each has."""
    return await _list_macros(host=host)


@mcp.tool()
async def get_macro(macro_id: str, host: Optional[str] = None) -> dict:
    """One macro's full step sequence and the entities it may use."""
    return await _get_macro(macro_id=macro_id, host=host)


@mcp.tool()
async def set_macro(
    name: str,
    steps: list[dict],
    macro_id: Optional[str] = None,
    description: Optional[str] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Create a macro, or replace an existing one's steps with macro_id.

    Steps are {"command": "media_player.on", "entity_id": "...", "params": {}}
    or {"delay": 1500} in milliseconds. The macro's permitted-entity list is
    derived from the steps and written first, since a step naming an entity
    outside it is rejected.
    """
    return await _set_macro(
        name=name, steps=steps, macro_id=macro_id, description=description,
        dry_run=dry_run, host=host,
    )


@mcp.tool()
async def delete_macro(
    macro_id: str, dry_run: bool = True, host: Optional[str] = None
) -> dict:
    """Delete a macro. Anything bound to it loses that binding."""
    return await _delete_macro(macro_id=macro_id, dry_run=dry_run, host=host)


@mcp.tool()
async def list_activity_groups(host: Optional[str] = None) -> dict:
    """
    Activity groups and what they do when switching. A group that turns unused
    entities off will power devices on and off as you move between activities.
    """
    return await _list_activity_groups(host=host)


@mcp.tool()
async def update_activity_group(
    group_id: str,
    activity_ids: Optional[list[str]] = None,
    turn_off_unused_entities: Optional[str] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Change a group's members or its switching behaviour. An empty activity_ids
    empties the group, which stops it powering devices without deleting it.
    """
    return await _update_activity_group(
        group_id=group_id, activity_ids=activity_ids,
        turn_off_unused_entities=turn_off_unused_entities, dry_run=dry_run, host=host,
    )


# ------------------------------------------------------------------- resources

@mcp.tool()
async def list_resources(resource_type: str = "Icon", host: Optional[str] = None) -> dict:
    """Uploaded resources of a type — "Icon" by default."""
    return await _list_resources(resource_type=resource_type, host=host)


@mcp.tool()
async def upload_resource(
    file_path: str,
    resource_type: str = "Icon",
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Upload a custom icon, then reference it as "custom:<filename>". Icons are
    90x90 PNG/JPG up to 32 KB. Replacing one means deleting it first, and the
    UI crops transparent margins — so pad with a nearly invisible corner pixel
    or the icon renders oversized.
    """
    return await _upload_resource(
        file_path=file_path, resource_type=resource_type, dry_run=dry_run, host=host
    )


@mcp.tool()
async def delete_resource(
    resource_id: str,
    resource_type: str = "Icon",
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """Delete an uploaded resource. Anything still referencing it renders nothing."""
    return await _delete_resource(
        resource_id=resource_id, resource_type=resource_type, dry_run=dry_run, host=host
    )


# --------------------------------------------------------- settings and system

@mcp.tool()
async def get_settings(section: Optional[str] = None, host: Optional[str] = None) -> dict:
    """
    Read device settings — one section or all of them.

    Sections: display, sound, haptic, power_saving, button, localization,
    voice_control, network, software_update, profile. Screen and standby
    timeouts, the usual suspects for battery life, are in power_saving.
    """
    return await _get_settings(section=section, host=host)


@mcp.tool()
async def update_settings(
    section: str, values: dict, dry_run: bool = True, host: Optional[str] = None
) -> dict:
    """
    Change device settings. Pass only the keys you want to change.

    Writable sections: display (brightness, auto_brightness), sound (enabled,
    volume), haptic (enabled), power_saving (wakeup_sensitivity,
    display_off_sec, standby_sec), button (brightness, auto_brightness,
    static_color), localization (language_code, country_code, time_zone,
    time_format_24h, measurement_unit), software_update (check_for_updates,
    auto_update, ota_window_start/end), network (wifi_enabled, bt_enabled).
    """
    return await _update_settings(
        section=section, values=values, dry_run=dry_run, host=host
    )


@mcp.tool()
async def get_system_status(host: Optional[str] = None) -> dict:
    """
    Battery, charge state, wi-fi signal, firmware versions, memory, storage and
    time to standby. rssi is dBm: better than -60 is strong, worse than -75 is
    where commands start to drop.
    """
    return await _get_system_status(host=host)


@mcp.tool()
async def list_features(host: Optional[str] = None) -> dict:
    """Experimental firmware features and whether each is switched on."""
    return await _list_features(host=host)


@mcp.tool()
async def set_feature_enabled(
    feature_id: str, enabled: bool, dry_run: bool = True, host: Optional[str] = None
) -> dict:
    """Turn an experimental feature on or off. Some need a restart to take hold."""
    return await _set_feature_enabled(
        feature_id=feature_id, enabled=enabled, dry_run=dry_run, host=host
    )


# ----------------------------------------------------- snapshots and firmware

@mcp.tool()
async def list_snapshots(host: Optional[str] = None) -> dict:
    """
    Whole-device snapshots stored on the remote, newest first. Distinct from
    backup_config, which writes an inspectable JSON copy to this machine.
    """
    return await _list_snapshots(host=host)


@mcp.tool()
async def create_snapshot(dry_run: bool = True, host: Optional[str] = None) -> dict:
    """
    Take a snapshot of the whole device — activities, pages, buttons,
    integrations and their settings. Worth doing before firmware or teardowns.
    """
    return await _create_snapshot(dry_run=dry_run, host=host)


@mcp.tool()
async def download_snapshot(
    snapshot_id: str, dest_path: str, host: Optional[str] = None
) -> dict:
    """
    Copy a snapshot off the remote to this machine — snapshots otherwise live
    only on the remote and go with it if it is reset.
    """
    return await _download_snapshot(
        snapshot_id=snapshot_id, dest_path=dest_path, host=host
    )


@mcp.tool()
async def delete_snapshot(
    snapshot_id: str, dry_run: bool = True, host: Optional[str] = None
) -> dict:
    """Delete a snapshot from the remote. Not recoverable afterwards."""
    return await _delete_snapshot(snapshot_id=snapshot_id, dry_run=dry_run, host=host)


@mcp.tool()
async def restore_snapshot(
    snapshot_id: str, dry_run: bool = True, host: Optional[str] = None
) -> dict:
    """
    Restore the remote from a snapshot, replacing its whole configuration.
    Anything created since it was taken is lost and the remote restarts.
    """
    return await _restore_snapshot(snapshot_id=snapshot_id, dry_run=dry_run, host=host)


@mcp.tool()
async def check_for_update(host: Optional[str] = None) -> dict:
    """
    Check for a firmware update now. "available" is null when already current;
    otherwise it carries the update_id that install_update takes.
    """
    return await _check_for_update(host=host)


@mcp.tool()
async def install_update(
    update_id: str, dry_run: bool = True, host: Optional[str] = None
) -> dict:
    """
    Install a firmware update by its update_id. The remote downloads, installs
    and restarts on its own, and is offline for several minutes.
    """
    return await _install_update(update_id=update_id, dry_run=dry_run, host=host)


# -------------------------------------------------------------- infrared, docks

@mcp.tool()
async def list_ir_manufacturers(
    query: str, device_type: Optional[str] = None, host: Optional[str] = None
) -> dict:
    """
    Search the built-in IR database for a manufacturer. The query needs at
    least two characters; device_type ("tv", "avr", ...) narrows it.
    """
    return await _list_ir_manufacturers(
        query=query, device_type=device_type, host=host
    )


@mcp.tool()
async def list_ir_codesets(
    manufacturer_id: str, query: Optional[str] = None, host: Optional[str] = None
) -> dict:
    """
    The codesets a manufacturer offers. They are often near-identical variants;
    picking the right one means trying it and seeing if the device responds.
    """
    return await _list_ir_codesets(
        manufacturer_id=manufacturer_id, query=query, host=host
    )


@mcp.tool()
async def get_ir_codeset(
    manufacturer_id: str, codeset_id: str, host: Optional[str] = None
) -> dict:
    """The command keys a codeset provides, such as POWER_ON or INPUT_1."""
    return await _get_ir_codeset(
        manufacturer_id=manufacturer_id, codeset_id=codeset_id, host=host
    )


@mcp.tool()
async def list_custom_ir_codesets(
    query: Optional[str] = None, host: Optional[str] = None
) -> dict:
    """Codesets learned on this remote, as opposed to ones from the database."""
    return await _list_custom_ir_codesets(query=query, host=host)


@mcp.tool()
async def get_custom_ir_codeset(codeset_id: str, host: Optional[str] = None) -> dict:
    """One learned codeset, with every code and its raw value."""
    return await _get_custom_ir_codeset(codeset_id=codeset_id, host=host)


@mcp.tool()
async def create_custom_ir_codeset(
    name: str,
    codes: list[dict],
    device_type: str = "various",
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Create a custom IR codeset with its codes, as
    {"command": "POWER_ON", "value": "4;0x540C;15;0"} sharing one format (HEX
    or PRONTO).

    All codes must go in at creation: the add/remove endpoint for individual
    codes is broken in firmware 2.8.4 — it ignores the command name and acts on
    a code called literally "codes" — so changing a set means recreating it.
    Learning a code from a physical remote is done on the remote, then read back.
    """
    return await _create_custom_ir_codeset(
        name=name, codes=codes, device_type=device_type, dry_run=dry_run, host=host
    )


@mcp.tool()
async def rename_custom_ir_codeset(
    codeset_id: str,
    name: str,
    device_type: Optional[str] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """Rename a custom codeset. Only its name and device type can change."""
    return await _rename_custom_ir_codeset(
        codeset_id=codeset_id, name=name, device_type=device_type,
        dry_run=dry_run, host=host,
    )


@mcp.tool()
async def delete_custom_ir_codeset(
    codeset_id: str, dry_run: bool = True, host: Optional[str] = None
) -> dict:
    """Delete a learned codeset. Its codes are not in the built-in database."""
    return await _delete_custom_ir_codeset(
        codeset_id=codeset_id, dry_run=dry_run, host=host
    )


@mcp.tool()
async def list_ir_emitters(host: Optional[str] = None) -> dict:
    """
    What can send IR — the remote's internal blaster and any dock — with each
    one's output ports. A device ignoring IR is usually on the wrong emitter.
    """
    return await _list_ir_emitters(host=host)


@mcp.tool()
async def list_docks(host: Optional[str] = None) -> dict:
    """
    Docks paired with the remote: firmware, connection and port modes.
    Read-only — dock settings and dock firmware are not on the REST API.
    """
    return await _list_docks(host=host)


@mcp.tool()
async def discover_docks(host: Optional[str] = None) -> dict:
    """
    Docks visible on the network but not paired. Discovery is started from the
    remote's own dock setup screen, so an empty list usually means it is off.
    """
    return await _discover_docks(host=host)


# ------------------------------------------------------------ IR devices

@mcp.tool()
async def list_remote_entities(host: Optional[str] = None) -> dict:
    """
    IR devices defined on this remote, with the codeset and emitter each uses.
    A device with no output falls back to the remote's internal blaster, which
    needs line of sight.
    """
    return await _list_remote_entities(host=host)


@mcp.tool()
async def create_ir_remote(
    name: str,
    codeset_id: Optional[str] = None,
    clone_from: Optional[str] = None,
    icon: Optional[str] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Create an IR device from a codeset — this is how you add a device the remote
    drives by infrared.

    codeset_id takes a built-in codeset (list_ir_codesets) or a learned one
    (list_custom_ir_codesets); clone_from copies an existing IR device instead.
    The command list comes from the codeset, so the device is usable straight
    away with send_command, set_button_mapping and create_ui_page. Point it at a
    dock with set_ir_output.
    """
    return await _create_ir_remote(
        name=name, codeset_id=codeset_id, clone_from=clone_from, icon=icon,
        dry_run=dry_run, host=host,
    )


@mcp.tool()
async def set_ir_output(
    entity_id: str,
    emitter_device_id: Optional[str] = None,
    port_id: Optional[str] = None,
    cmd_delay_ms: Optional[int] = None,
    repeat: Optional[int] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Choose which emitter an IR device sends through, and how.

    IDs come from list_ir_emitters: "internal" for the remote's own blaster, or
    a dock id with port "0" for all of that dock's outputs. Raise cmd_delay_ms
    for a device that drops rapid presses; raise repeat for one that misses
    commands outright.
    """
    return await _set_ir_output(
        entity_id=entity_id, emitter_device_id=emitter_device_id, port_id=port_id,
        cmd_delay_ms=cmd_delay_ms, repeat=repeat, dry_run=dry_run, host=host,
    )


@mcp.tool()
async def delete_remote_entity(
    entity_id: str, dry_run: bool = True, host: Optional[str] = None
) -> dict:
    """
    Delete an IR device, with its pages and button mappings. Activities using it
    lose those commands; the codeset it was built from is untouched.
    """
    return await _delete_remote_entity(
        entity_id=entity_id, dry_run=dry_run, host=host
    )


@mcp.tool()
async def set_integration_connected(
    integration_id: str,
    connected: bool,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Connect or disconnect an integration without disabling it — lighter than
    restart_integration, and worth trying first when devices stop responding.
    """
    return await _set_integration_connected(
        integration_id=integration_id, connected=connected, dry_run=dry_run, host=host
    )


@mcp.tool()
async def discover_integrations(host: Optional[str] = None) -> dict:
    """
    Integrations visible on the network but not set up. Discovery is started
    from the remote's own screen, so an empty list usually means it is off.
    """
    return await _discover_integrations(host=host)
