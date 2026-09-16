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
