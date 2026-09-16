# Field notes

Behaviour that is not obvious from the API, verified against firmware 0.69.x.

## Things that cost you config

- **Removing an entity silently strips its references.** Drop an entity from an
  activity and every button mapping and page item using it disappears with it.
  Back up first.
- **`included_entities` is read-only.** Write `options.entity_ids` instead — and
  send the *complete* list, because an empty array removes everything.
- **Macros have their own entity list too.** A sequence step naming an entity
  that is not in the macro's list is rejected outright, so repointing a macro
  takes two writes: the entity list first, then the sequence.
- **Commands fail silently when a name goes stale.** Selecting a source that no
  longer exists raises nothing at all — a page button simply stops working. If
  something drives a device by name, check the name still exists.

## Things that look broken but are not

- **"CONNECTED" doesn't mean healthy.** An integration can report `CONNECTED`
  while its entities are stale or `OFF`. Check the entities, not the
  integration.
- **Odd states are usually normal.** `UNKNOWN` is correct for button entities;
  `UNAVAILABLE` usually means that device is powered off.
- **One device, several entities.** A TV typically appears as both a
  `media_player` and a `remote`, with different command sets.
- **Changes may not repaint.** Profile, group and page edits can sit invisible
  until the UI reloads. `POST /api/system?cmd=RESTART_UI` forces it.

## Layout

- Buttons and pages live inside activities, under `options.button_mapping` and
  `options.user_interface.pages` — there are no separate endpoints.
- **The page grid is not fixed at 4 columns.** Wider grids are accepted, which
  is the only way to divide a row evenly into three.
- Custom icons are 90×90 PNGs. The UI auto-crops transparent margins and scales
  the glyph up, so an icon with padding still renders huge — put a nearly
  invisible pixel in each corner so the bounding box spans the full image.

## Troubleshooting

- **Tools suddenly time out** — the remote sleeps and stops answering HTTP while
  still replying to ping. Wake it or dock it. By far the most common issue.
- **Worked before, not now** — its IP probably changed. Run `discover_remotes`
  and `setup_remote` again, or give it a DHCP reservation.
- **`discover_remotes` finds nothing** — mDNS does not cross subnets and some
  firewalls block it. Read the IP from the remote (Settings → About → Network)
  and pass it to `setup_remote`.
- **Wrong PIN** — it changes every time the Web Configurator is toggled.
- **Battery isn't a JSON field** — it is parsed out of the system log.

## Development

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
