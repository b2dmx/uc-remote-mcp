# Field notes

Behaviour that is not obvious from the API, verified against firmware 2.8.x.

## Safety model

- Every write previews first and does nothing until you pass `dry_run=false`.
- Every real write takes a full config backup beforehand; the last 50 are kept.
- Commands and entity names are checked against the device before any network
  call, so a typo fails immediately rather than half-way through.
- `restore_config` restores your customisations — names, buttons, pages,
  sequences. Entities come from integrations and cannot be recreated that way;
  they are reported instead of touched.

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

## Settings

`PATCH /api/cfg/power_saving` rejects a partial body with a 400 — all three of
`wakeup_sensitivity`, `display_off_sec` and `standby_sec` must be present.
`update_settings` reads the section first and fills in the rest, so changing one
field works. No other section behaves this way.

Some fields are reported on read and refused on write: `features` under `button`,
`bt` under `network`.

## Snapshots and firmware

Restoring a device snapshot is `PUT /api/system/backup/snapshots/{id}` — there is
no `/restore` route. Installing firmware is `POST /api/system/update/{update_id}`
— there is no `/install` route either. Both were established by probing, because
the failure modes of guessing are a restore and a flash.

A useful discriminator when probing this API: a route that exists but has no
matching data answers `404 NOT_FOUND: No data found`, while a route that does not
exist answers a bare `404`. That difference is how the two above were confirmed
without performing either operation.

Taking a snapshot takes well over the default 10s timeout; `create_snapshot`
allows 180s.

## Infrared

The code database is three levels deep and the paths are not guessable:

```
/api/ir/codes/manufacturers?q=sony        -> manufacturers (q needs 2+ chars)
/api/ir/codes/manufacturers/sony          -> that manufacturer's codesets
/api/ir/codes/manufacturers/sony/vCQuyR9  -> that codeset's command keys
```

Reads report a `format` per code; writes take one `code_format` for the whole
set and reject per-code formats.

**The `/api/ir/codes/custom/{id}/codes` sub-resource is broken in firmware
2.8.4, in both directions.** POST returns `OK`, ignores the `key` field, and
stores the code under the literal name `codes` — then 422s `ALREADY_EXISTS` on
the next one, because that name is now taken. DELETE with `{"keys": [...]}`
ignores the keys in the same way and only ever removes a code named `codes`,
404ing when there is none.

That second one is worth dwelling on: the DELETE *appears* to work on any
codeset the POST bug has already polluted, because there really is a `codes` key
there to remove. It answers `Removed key codes` — which reads as a status
message and is in fact a literal statement of which key it removed. A tool for
removing individual codes was built, tested against exactly that codeset, and
looked correct; it only failed on a clean one. So codes are fixed at creation,
and no tool here claims otherwise.

`PATCH /api/ir/codes/custom/{id}` changes the name and device type only. Codes
in the same body are accepted and silently ignored — it answers "Modified
codeset" either way.

Dock configuration and IR learning are not on REST at all. Both are WebSocket-
only, so `list_docks` is read-only and learning stays in the web configurator.

## IR devices

`POST /api/remotes` needs one of `bt`, `clone_from`, `codeset_id` or
`custom_codeset` — it says so itself if you send only a name. `codeset_id`
accepts both a built-in codeset id and a learned one; the remote works out
which and fills in `simple_commands` from it, so a new device is immediately
usable. `custom_codeset` is a different thing: a struct for defining a new
codeset inline, and it wants a `device_name`.

`name` must be a map (`{"en": "..."}`), not a string.

Connect and disconnect are `PUT /api/intg/instances/{id}?cmd=CONNECT` — a query
parameter, not a body, and the value is rejected unless it is uppercase.
