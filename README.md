# UC Remote MCP

MCP server for Unfolded Circle Remote 3 / Remote Two.
Exposes the remote's configuration as conversational tools for Claude.

## Install

```powershell
uv sync
```

## First run

1. Find your remote's IP in the UC app (Settings -> About), or call `discover_remotes` from Claude.
2. Call `setup_remote(host="<ip>", pin="<pin>")` — creates an API key and saves it to `%APPDATA%\uc-remote-mcp\config.json`.

## Claude Desktop config

Add to `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "uc-remote": {
      "command": "uv",
      "args": [
        "--directory",
        "C:\\path\\to\\uc-remote-mcp",
        "run",
        "uc-remote-mcp"
      ]
    }
  }
}
```

Restart Claude Desktop after saving.

## Tools (Phase 1 — read-only + backup)

| Tool | Description |
|------|-------------|
| `setup_remote` | First-run PIN auth, creates API key, saves config |
| `discover_remotes` | mDNS scan — finds UC remotes on the LAN |
| `get_remote_info` | Name, model, firmware, battery, active activities |
| `list_devices` | All entities; filter by `entity_type` (media_player, remote, activity, macro) |
| `get_device` | Full entity config: features, simple_commands, attributes |
| `list_device_commands` | Commands an entity exposes (features + simple_commands) |
| `list_activities` | All activities with included entities |
| `get_activity` | Included entities (+their commands), button overrides, UI pages |
| `get_button_mapping` | Button→command bindings; scope = `activity` / `remote` / `device` |
| `list_ui_pages` | UI pages for an `activity` or `remote` (needs scope_id) |
| `get_ui_page` | Items on one page: grid, positions, bound commands |
| `backup_config` | Full config snapshot to one JSON file (keeps last 50) |

## Tools (Phase 2 — mutations)

All mutations default to `dry_run=True` (preview only) and take an automatic
config backup before any real write. Set `dry_run=false` to apply.

| Tool | Endpoint | Notes |
|------|----------|-------|
| `send_command` | `PUT /entities/{id}/command` | One-off command; `{cmd_id, params?}` |
| `set_button_mapping` | `PATCH /{activities\|remotes}/{id}/buttons/{BUTTON}` | `entity_id` required for activities, ignored for remotes |
| `bulk_set_button_mapping` | same, fanned across activities | Filter by `activity_ids`/`name_contains`; invalid activities skipped with reason; one backup per batch |
| `update_ui_page` | `PATCH /{…}/{id}/ui/pages/{pageId}` | `{name?, grid?, items?}`; omitted = unchanged, empty items clears; items validated |
| `delete_ui_page` | `DELETE /{…}/{id}/ui/pages/{pageId}` | Irrevocable on device; dry-run shows full content being lost |
| `set_default_ui_page` | `PATCH /{…}/{id}/ui/pages` `{page_order}` | No explicit default-page property — first page wins, so this reorders |
| `update_activity_sequence` | `PATCH /activities/{id}` `{options.sequences}` | Steps: `{type:"command",command:{…}}` / `{type:"delay",delay:ms}` |
| `diff_config` | read-only | Live config vs backup file: restore ops + unrestorable differences |
| `restore_config` | granular PATCH/DELETE/POST per difference | sha256 token flow: 1st call returns token+plan, 2nd call with token + `dry_run=false` applies |

Command names are validated client-side before a write: for an activity the
target `entity_id` must be one of its included entities and the `cmd_id` must be
in that entity's `entity_commands`/`simple_commands`; for a remote the `cmd_id`
must be one of the remote's `simple_commands` (and remote UI/button commands may
NOT carry an `entity_id` — a remote operates on itself). Invalid names raise
before any network call.

`restore_config` restores the *customization layer* (names, button mappings, UI
pages, sequences of activities/remotes). Entities and integration instances come
from integrations and can't be recreated through these endpoints — those
differences are reported as `not_restorable` and left untouched.

### Notes on the UC data model (verified against firmware 0.69.x)

- **Auth**: `POST /api/pub/login` with username `web-configurator` + PIN → session
  cookie → `POST /api/auth/api_keys`. All other calls use `Authorization: Bearer`.
- **Devices are entities.** One physical device often spans several entities
  (the LG TV = a `media_player` "LG WebOS Apps" + a `remote` "LG TV").
- **Button mappings & UI pages are embedded**, not separate endpoints. They live
  under `options.button_mapping` and `options.user_interface.pages` on each
  **activity** (`/api/activities/{id}`) and **remote-entity** (`/api/remotes/{id}`).
  There is no global profile and no `/api/profiles/pages` endpoint on this firmware.
- **Button targets use `cmd_id`.** IR remotes (`options.kind == "IR"`) bind to local
  IR codes with no `entity_id`; device bindings carry the target `entity_id`.
- **Battery level** isn't a JSON field — it's parsed from `/api/system/logs`.

## Layout

```
src/uc_remote_mcp/
  server.py            FastMCP app; wraps every tool with @mcp.tool()
  config.py            config load/save (%APPDATA%\uc-remote-mcp\config.json)
  client/rest.py       async httpx REST client (PIN→key auth, Bearer)
  tools/_common.py     get_client(), localized(), button/page normalizers
  tools/*.py           discovery, setup, devices, activities, buttons, ui, backup
  safety/backup.py     collect_config()/create_backup() (reused by Phase 2)
```

## Safety model

- Mutating tools default to `dry_run=True` — they show exactly what would change
  and write nothing until called again with `dry_run=false`.
- Every real write is preceded by an automatic full-config backup
  (`%APPDATA%\uc-remote-mcp\backups\`, last 50 kept).
- Command names and target entities are validated client-side before any
  network write, so typos fail fast instead of half-applying.

## Credits

- **Built with [Claude](https://claude.com/claude-code)** — this server was
  designed, implemented, and live-tested conversationally using Claude Code
  against a real Remote 3.
- The conversational-tool design was informed by the
  [ha-mcp](https://pypi.org/project/ha-mcp/) Home Assistant MCP server.
- API reference: the official
  [Unfolded Circle Core API](https://github.com/unfoldedcircle/core-api) spec.

This project is not affiliated with or endorsed by Unfolded Circle.

## License

[MIT](LICENSE)
