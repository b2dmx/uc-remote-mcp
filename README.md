# UC Remote MCP

MCP server for the Unfolded Circle Remote 3 / Remote Two.
Exposes the remote's configuration as conversational tools for Claude — ask
questions about your setup, remap buttons, redesign UI pages, and restore from
backups, all in plain language.

## Requirements

- An Unfolded Circle **Remote 3** or **Remote Two** on the same LAN as your computer
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) (manages Python and dependencies — Python 3.11+ is fetched automatically)
- An MCP client — the examples below use [Claude Desktop](https://claude.com/download)

## Quick start

**1. Clone and install**

```sh
git clone https://github.com/b2dmx/uc-remote-mcp.git
cd uc-remote-mcp
uv sync
```

**2. Wire it into Claude Desktop**

Add to your Claude Desktop config file
(Windows: `%APPDATA%\Claude\claude_desktop_config.json`,
macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "uc-remote": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/uc-remote-mcp",
        "run",
        "uc-remote-mcp"
      ]
    }
  }
}
```

Use the absolute path of the folder you cloned (Windows paths need doubled
backslashes: `"C:\\path\\to\\uc-remote-mcp"`). Restart Claude Desktop after saving.

**3. Pair with your remote (one time)**

You need the remote's **Web Configurator PIN**: on the remote, go to
**Settings → Web Configurator** and toggle it on — the PIN is shown on the
remote's screen.

Then just tell Claude:

> Discover my Unfolded Circle remote, then set it up with PIN 1234.

`discover_remotes` finds the remote via mDNS; `setup_remote` exchanges the PIN
for a long-lived API key stored in `%APPDATA%\uc-remote-mcp\config.json`
(Windows) or `~/.config/uc-remote-mcp/config.json` (macOS/Linux, chmod 600).
The PIN itself is never stored. After that, every tool works without further auth.

## Things to ask once it's running

- "What's the battery level on my remote?"
- "List my activities and what's on their UI pages."
- "What does the volume button do in each activity?"
- "Map the PLAY button in the TV activity to the Apple TV's play/pause."
- "Back up my remote's config." / "What changed since that backup?"

## Troubleshooting

- **`ConnectTimeout` / tools suddenly fail** — the remote parks its HTTP server
  in standby. Wake it (lift it or press a button) or keep it docked. This is by
  far the most common failure mode.
- **Remote not found / timeouts after it worked before** — DHCP may have moved
  its IP. Ask Claude to run `discover_remotes` again and re-run `setup_remote`
  (or give the remote a DHCP reservation in your router).
- **`discover_remotes` returns nothing** — mDNS only works on the same
  subnet/VLAN, and some firewalls block it. Find the IP on the remote
  (Settings → About → Network) and call `setup_remote` with it directly.
- **Wrong PIN** — the PIN changes each time the Web Configurator is toggled;
  read it off the remote's screen, not from memory.

## Compatibility

Developed and battle-tested against a **Remote 3** (firmware/core 0.69.x, API
0.16). The Remote Two exposes the same Core API and should work identically,
but hasn't been tested by the author.

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
