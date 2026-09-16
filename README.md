# UC Remote MCP

[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support-FF5E5B?logo=kofi&logoColor=white)](https://ko-fi.com/goobis2dmx)

Control an **Unfolded Circle Remote 3 / Remote Two** by talking to Claude.
Ask what a button does, remap it, redesign a page, back up your config — in
plain language.

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

Restart the client. [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
fetches and builds everything on first launch.

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

Built and tested against a **Remote 3** (core 0.69.x, API 0.16). The Remote Two
shares the same API and should work, but is untested.

## Credits

Built with [Claude](https://claude.com/claude-code), designed and live-tested
against a real Remote 3. Tool design informed by
[ha-mcp](https://pypi.org/project/ha-mcp/); API reference from the
[Unfolded Circle Core API](https://github.com/unfoldedcircle/core-api) spec.

Not affiliated with or endorsed by Unfolded Circle.

## License

[MIT](LICENSE)
