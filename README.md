# UC Remote MCP

[![tests](https://github.com/b2dmx/uc-remote-mcp/actions/workflows/tests.yml/badge.svg)](https://github.com/b2dmx/uc-remote-mcp/actions/workflows/tests.yml)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support-FF5E5B?logo=kofi&logoColor=white)](https://ko-fi.com/goobis2dmx)

Set up and control an **Unfolded Circle Remote 3 / Remote Two** with natural language through
Claude.

- **Layouts** — build a device or a page
- **Buttons** — ask what a button does, remap it, to both software and hardware
- **Integrations** — install, set up
- **Backups** — snapshot your configuration, see what changed, restore it
- **Updates** — keep your setup up to date

## Installation

**1. Prerequisite Install: [uv](https://docs.astral.sh/uv/getting-started/installation/)**, which runs it.
If you already use another Python MCP server — `ha-mcp`, for instance — you have it already.

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh    # macOS / Linux
```

**2. Add this to your MCP client config.** For Claude Desktop:
`%APPDATA%\Claude\claude_desktop_config.json` (Windows) or
`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) —
create it if it isn't there:

```json
{
  "mcpServers": {
    "uc-remote": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/b2dmx/uc-remote-mcp@v1.0.1",
        "uc-remote-mcp"
      ]
    }
  }
}
```

**3. Restart the client.** First launch takes a minute while it builds.

## Pair

On the remote: **Settings → Web Configurator**, turn it on, note the PIN. Then
tell Claude:

> Discover my Unfolded Circle remote and set it up with PIN 1234.


## Examples

- *"What does the volume button do in each activity?"*
- *"Map PLAY in the TV activity to the Apple TV's play/pause."*
- *"Install [integration] and set it up."*
- *"My Apple TV stopped responding — restart that integration."*
- *"Back up my config."* / *"What changed since that backup?"*

## More

[All the tools →](docs/tools.md) · [Field notes →](docs/notes.md)

To update, change the version in your config and restart. Watch → Custom →
Releases to hear about new ones.

Built and tested against a **Remote 3** on firmware 2.8.x. The Remote Two shares
the same API and should work, but is untested.

## Credits

Built with [Claude](https://claude.com/claude-code). Tool design informed by
[ha-mcp](https://pypi.org/project/ha-mcp/); API reference from the
[Unfolded Circle Core API](https://github.com/unfoldedcircle/core-api).

Not affiliated with or endorsed by Unfolded Circle.

[MIT](LICENSE)
