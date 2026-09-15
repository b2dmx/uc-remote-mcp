# UC Remote MCP

Control an **Unfolded Circle Remote 3 / Remote Two** by talking to Claude.
Ask what a button does, remap it, redesign a page, back up your config — in plain language.

## Install

Add this to your MCP client config
(Claude Desktop: `%APPDATA%\Claude\claude_desktop_config.json` on Windows,
`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "uc-remote": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/b2dmx/uc-remote-mcp@v0.1.0",
        "uc-remote-mcp"
      ]
    }
  }
}
```

Restart the client. That's it — [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
fetches and builds everything on first launch. Drop `@v0.1.0` to track the latest code.

## Pair with your remote

On the remote: **Settings → Web Configurator**, toggle it on, and note the PIN on screen.

Then tell Claude:

> Discover my Unfolded Circle remote and set it up with PIN 1234.

The PIN is traded for a long-lived API key and never stored. Everything works after that.

## Try it

- "What's the battery level on my remote?"
- "What does the volume button do in each activity?"
- "Map PLAY in the TV activity to the Apple TV's play/pause."
- "Back up my config." / "What changed since that backup?"

## Tools

**Read-only**

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

**Writes** — all default to `dry_run=True` and auto-backup before applying.

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

## Safety

- Writes preview first; nothing changes until you pass `dry_run=false`.
- Every real write takes a full backup first (last 50 kept).
- Command and entity names are validated before any network call, so typos fail fast.
- `restore_config` restores your **customisations** (names, buttons, pages, sequences).
  Entities come from integrations and can't be recreated this way — those are reported, not touched.

## Good to know

Things that surprise people, verified against firmware 0.69.x:

- **Removing an entity silently strips its references.** Drop an entity from an activity and
  every button mapping and page item using it disappears with it. Back up first.
- **`included_entities` is read-only.** Write `options.entity_ids` instead — and send the
  *complete* list, because an empty array removes everything.
- **"CONNECTED" doesn't mean healthy.** An integration can report `CONNECTED` while its
  entities are stale or `OFF`. Check the entities, not the integration.
- **Odd states are often normal.** `UNKNOWN` is correct for button entities; `UNAVAILABLE`
  usually just means that device is powered off.
- **One device, several entities.** A TV typically appears as both a `media_player` and a `remote`.
- **Buttons and pages live inside activities**, under `options.button_mapping` and
  `options.user_interface.pages` — there are no separate endpoints for them.
- **Battery isn't a JSON field** — it's parsed out of the system log.

## Troubleshooting

- **Tools suddenly time out** — the remote sleeps and stops answering. Wake it or dock it.
  This is by far the most common issue.
- **Worked before, not now** — its IP probably changed. Run `discover_remotes` and
  `setup_remote` again, or give it a DHCP reservation.
- **`discover_remotes` finds nothing** — mDNS doesn't cross subnets and some firewalls block it.
  Read the IP from the remote (Settings → About → Network) and pass it to `setup_remote`.
- **Wrong PIN** — it changes every time the Web Configurator is toggled. Re-read it on screen.

## Development

<details>
<summary>Run from a local clone</summary>

```sh
git clone https://github.com/b2dmx/uc-remote-mcp.git
cd uc-remote-mcp
uv sync
uv run pytest
```

Point your client at the clone instead:

```json
{
  "mcpServers": {
    "uc-remote": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/uc-remote-mcp", "run", "uc-remote-mcp"]
    }
  }
}
```

Windows paths need doubled backslashes. Source layout:

```
src/uc_remote_mcp/
  server.py       FastMCP app
  config.py       config load/save
  client/rest.py  async REST client (PIN → key auth)
  tools/          discovery, devices, activities, buttons, ui, backup
  safety/         backup, validation, dry-run
```

</details>

Built and tested against a **Remote 3** (core 0.69.x, API 0.16). The Remote Two shares the
same API and should work, but is untested.

## Credits

Built with [Claude](https://claude.com/claude-code), designed and live-tested against a real
Remote 3. Tool design informed by [ha-mcp](https://pypi.org/project/ha-mcp/); API reference from
the [Unfolded Circle Core API](https://github.com/unfoldedcircle/core-api) spec.

Not affiliated with or endorsed by Unfolded Circle.

## License

[MIT](LICENSE)
