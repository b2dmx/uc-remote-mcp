"""First-run setup: PIN auth → API key → write config."""

from ..client.rest import UCClient
from ..config import RemoteConfig, save_remote


async def setup_remote(
    host: str,
    pin: str,
    port: int = 80,
    name: str = "UC Remote",
) -> dict:
    """
    Authenticate with the remote using the admin PIN, create a long-lived API key,
    and save it to the config file.

    Args:
        host: IP address or hostname of the remote (e.g. '192.168.1.50')
        pin: Admin PIN shown in the remote's settings
        port: HTTP port (default 80)
        name: Friendly label for this remote in config

    Returns:
        Summary dict (api_key is redacted in output).
    """
    # ValueError on wrong PIN is raised directly by with_pin_auth
    client, api_key = await UCClient.with_pin_auth(host, port, pin)

    # Fetch device info to populate model/name in config
    try:
        version = await client.get("/api/pub/version")
        system = await client.get("/api/system")
        resolved_name = version.get("device_name") or name
        model = system.get("model_name", "")
    except Exception:
        resolved_name = name
        model = ""

    cfg = RemoteConfig(
        host=host,
        port=port,
        api_key=api_key,
        name=resolved_name,
        model=model,
    )
    save_remote(cfg)

    return {
        "status": "ok",
        "host": host,
        "port": port,
        "name": resolved_name,
        "model": model,
        "api_key": "***saved***",
        "message": f"API key created and saved. Remote '{resolved_name}' is ready.",
    }
