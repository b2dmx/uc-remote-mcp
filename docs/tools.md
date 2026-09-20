# Tools

## Read-only

| Tool | Description |
|------|-------------|
| `discover_remotes` | Find remotes on the LAN via mDNS |
| `setup_remote` | First-run PIN auth; saves an API key |
| `get_remote_info` | Model, firmware, battery, active activities |
| `list_devices` / `get_device` | Entities and their full config |
| `list_device_commands` | Commands an entity accepts |
| `list_activities` / `get_activity` | Activities, their entities, buttons, pages |
| `get_button_mapping` | Button bindings by activity, remote, or device |
| `list_ui_pages` / `get_ui_page` | Page layout, grid positions, bound commands |
| `backup_config` | Full config snapshot to JSON (keeps last 50) |
| `diff_config` | Compare live config against a backup |

## Integrations

| Tool | Description |
|------|-------------|
| `list_integrations` | Installed drivers and configured instances, with state |
| `get_integration` | One instance in full, including its configured entities |
| `list_integration_entities` | What an integration offers; re-polls for new ones |

## Writes

All default to `dry_run=True` and take a backup before applying.

| Tool | Description |
|------|-------------|
| `send_command` | Fire a one-off command at a device |
| `set_button_mapping` | Bind one button |
| `bulk_set_button_mapping` | Bind the same button across many activities |
| `create_activity` | Create an activity — a "device" on the home screen |
| `create_ui_page` | Add a page to an activity or remote-entity |
| `update_ui_page` | Replace a page's name, grid, or items |
| `delete_ui_page` | Remove a page (irreversible on the device) |
| `set_default_ui_page` | Reorder pages — the first one is the default |
| `update_activity_sequence` | Edit an activity's on/off command sequence |
| `restore_config` | Restore from a backup via a two-step token flow |

## Integration writes

| Tool | Description |
|------|-------------|
| `configure_integration_entities` | Expose entities so activities and pages can use them |
| `restart_integration` | Disable and re-enable an instance — the usual fix when devices stop responding |
| `set_integration_enabled` | Enable or disable an instance |
| `install_integration` | Install a custom driver from a `.tar.gz` |
| `update_integration_driver` | Update a custom driver to a new `.tar.gz` — deletes and reinstalls, since the remote has no in-place update |
| `delete_integration` | Remove a driver, its instance and all its entities |
| `delete_integration_instance` | Remove one instance, keeping the driver — the teardown for firmware-shipped drivers |
| `start_integration_setup` | Begin setup and return the first screen |
| `get_integration_setup` | The current screen of a running flow |
| `answer_integration_setup` | Answer a screen and return the next |
| `confirm_integration_setup` | Answer a confirmation screen ("press the button on the device") |
| `cancel_integration_setup` | Abandon a flow, changing nothing |
| `set_integration_connected` | Connect or disconnect without disabling — try before restarting |
| `discover_integrations` | Integrations seen on the network but not set up |
| `restart_remote` | Restart the `ui`, `core`, or whole `system` |

## Activity and macro entities

Exposing an entity from an integration is not enough to use it — the activity or
macro must also be allowed to use it.

| Tool | Description |
|------|-------------|
| `list_scope_entities` | What an activity or macro may currently use |
| `add_scope_entities` | Allow more; existing entries are preserved |
| `remove_scope_entities` | Stop using some — also removes their buttons and page items |

## Home screen and profiles

| Tool | Description |
|------|-------------|
| `list_profiles` | Profiles on the remote and which is active |
| `get_home_layout` | Home pages, their tiles in order, and any groups |
| `set_home_tiles` | Replace a home page's tiles — also how you reorder them |
| `create_home_page` / `delete_home_page` | Add or remove a page of tiles |
| `set_profile_group` | Create or update a group of entities |
| `delete_profile_group` | Delete a group — the usual cure for a stray blank tile |

## Entities, activities, macros, resources

| Tool | Description |
|------|-------------|
| `update_entity` | Rename an entity or change its icon |
| `delete_entities` | Remove entities — the cure for one stuck reporting nothing |
| `delete_activity` | Delete an activity with its pages and buttons |
| `clear_button_mapping` | Unbind a button, or one press of it |
| `list_macros` / `get_macro` | Macros and their step sequences |
| `set_macro` | Create a macro or replace its steps |
| `delete_macro` | Delete a macro |
| `list_activity_groups` | Groups and whether they power unused entities off |
| `update_activity_group` | Change a group's members or switching behaviour |
| `list_resources` / `upload_resource` / `delete_resource` | Custom icons (90×90, ≤32 KB) |

## Settings and system

| Tool | Description |
|------|-------------|
| `get_settings` | Read one section or all — display, sound, haptic, power_saving, button, localization, voice_control, network, software_update, profile |
| `update_settings` | Change a section; pass only the keys you want |
| `get_system_status` | Battery, wi-fi signal, firmware, memory, storage, time to standby |
| `list_features` / `set_feature_enabled` | Experimental firmware features |

## Snapshots and firmware

`create_snapshot` is the remote's own whole-device backup, kept on the remote.
`backup_config` is the readable JSON copy on this machine that `diff_config`
compares against. Both are worth having.

| Tool | Description |
|------|-------------|
| `list_snapshots` | Device snapshots stored on the remote |
| `create_snapshot` | Take one — worth doing before firmware or a teardown |
| `download_snapshot` | Copy one off the remote to this machine |
| `delete_snapshot` / `restore_snapshot` | Remove one, or restore the whole device from it |
| `check_for_update` | Check for firmware now; `available` is null when current |
| `install_update` | Install an update by id; the remote restarts |

## Infrared and docks

| Tool | Description |
|------|-------------|
| `list_ir_manufacturers` | Search the built-in IR database (2+ characters) |
| `list_ir_codesets` / `get_ir_codeset` | A manufacturer's codesets and their command keys |
| `list_custom_ir_codesets` / `get_custom_ir_codeset` | Codesets learned on this remote |
| `create_custom_ir_codeset` | Create one with all its codes (see below) |
| `rename_custom_ir_codeset` | Rename one |
| `delete_custom_ir_codeset` | Delete a learned codeset |
| `list_ir_emitters` | What can send IR — internal blaster and dock ports |
| `list_remote_entities` | IR devices defined here, with codeset and emitter |
| `create_ir_remote` | Add an IR device from a codeset — commands come with it |
| `set_ir_output` | Point a device at an emitter; command delay and repeat |
| `delete_remote_entity` | Delete an IR device with its pages and buttons |
| `list_docks` / `discover_docks` | Paired docks and their port modes; unpaired docks on the network |

Two limits that are the firmware's, not the tool's. **Adding or removing an
individual code is broken in 2.8.4** — both the POST and the DELETE ignore the
command name given and act on a code called literally `codes` — so a codeset's
codes go in at creation, and changing them means creating a replacement and
deleting the old one. And **learning a code** and **dock configuration** (LED brightness, port modes, dock firmware)
are not on the REST API at all; both are WebSocket-only, so they stay in the web
configurator.
