# UC Remote MCP

[![tests](https://github.com/b2dmx/uc-remote-mcp/actions/workflows/tests.yml/badge.svg)](https://github.com/b2dmx/uc-remote-mcp/actions/workflows/tests.yml)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support-FF5E5B?logo=kofi&logoColor=white)](https://ko-fi.com/goobis2dmx)

Control an **Unfolded Circle Remote 3 / Remote Two** by talking to Claude.
Ask what a button does, remap it, redesign a page, back up your config — in
plain language.

## Install

**1. Install `uv`**, which is what actually runs this. One line, then reopen the
terminal:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh    # macOS / Linux
```

**2. Add this to your MCP client config**
(Claude Desktop: `%APPDATA%\Claude\claude_desktop_config.json` on Windows,
`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "uc-remote": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/b2dmx/uc-remote-mcp@v1.0.0",
        "uc-remote-mcp"
      ]
    }
  }
}
```

If the file does not exist, create it. If it already has an `"mcpServers"`
section, add the `"uc-remote"` block inside it rather than adding a second one.

**3. Restart the client.** Everything else is fetched and built on first launch,
which takes a minute — there is nothing to download by hand.

### Updating

Change the version in that config to the release you want, then restart the
client — for example `@v1.1.0`. Releases are listed on the
[releases page](https://github.com/b2dmx/uc-remote-mcp/releases); click
**Watch → Custom → Releases** on the repository to be told about new ones.

To always run the newest code instead, drop `@v1.0.0` entirely. That tracks the
default branch, which is less predictable — fine for trying things, less so for
something that edits your remote's configuration.

## Pair

On the remote: **Settings → Web Configurator**, toggle it on, note the PIN.
Then tell Claude:

> Discover my Unfolded Circle remote and set it up with PIN 1234.

The PIN is traded for a long-lived API key. That's the whole setup.

## Try it

- "What's the battery level on my remote?"
- "What does the volume button do in each activity?"
- "Map PLAY in the TV activity to the Apple TV's play/pause."
- "Back up my config." / "What changed since that backup?"

## What it can do

Read everything — devices, activities, button mappings, page layouts — and
change any of it: bind buttons, rebuild pages, edit activity sequences, back up
and restore.

**[Full tool list →](docs/tools.md)**

## Safety

- Writes preview first; nothing changes until you pass `dry_run=false`
- Every real write takes a backup first (last 50 kept)
- Commands and entity names are validated before any network call
- `restore_config` restores your customisations, not entities — those come from
  integrations and are reported rather than touched

## Notes

Things that cost people config, and what to do when the remote misbehaves:
**[Field notes →](docs/notes.md)**

Built and tested against a **Remote 3** on firmware 2.8.x (core 0.69.x, API
0.16). The Remote Two shares the same API and should work, but is untested.

## Credits

Built with [Claude](https://claude.com/claude-code), designed and live-tested
against a real Remote 3. Tool design informed by
[ha-mcp](https://pypi.org/project/ha-mcp/); API reference from the
[Unfolded Circle Core API](https://github.com/unfoldedcircle/core-api) spec.

Not affiliated with or endorsed by Unfolded Circle.

## License

[MIT](LICENSE)
