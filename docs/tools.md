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
| `delete_integration` | Remove a driver, its instance and all its entities |
| `start_integration_setup` | Begin setup and return the first screen |
| `get_integration_setup` | The current screen of a running flow |
| `answer_integration_setup` | Answer a screen and return the next |
| `cancel_integration_setup` | Abandon a flow, changing nothing |
| `restart_remote` | Restart the `ui`, `core`, or whole `system` |
