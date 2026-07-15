"""mDNS discovery + remote info tools."""

import asyncio
import re
from typing import Optional

from zeroconf import IPVersion, ServiceBrowser, Zeroconf

from ..client.rest import UCClient
from ..config import RemoteConfig, get_remote


SERVICE_TYPE = "_uc-remote._tcp.local."


async def discover_remotes(timeout_s: float = 8.0) -> list[dict]:
    """Scan LAN via mDNS for UC remotes. Returns list of {name, host, port, model, fw}."""
    found: list[dict] = []
    zc = Zeroconf()

    class _Listener:
        def add_service(self, zc, type_, name):
            info = zc.get_service_info(type_, name)
            if info:
                # Prefer IPv4: the remote also advertises fd../fe80.. IPv6
                # addresses that httpx can't use without zone/bracket handling.
                addresses = info.parsed_addresses(IPVersion.V4Only) or info.parsed_addresses()
                host = addresses[0] if addresses else name
                props = {
                    k.decode() if isinstance(k, bytes) else k: (
                        v.decode() if isinstance(v, bytes) else v
                    )
                    for k, v in (info.properties or {}).items()
                }
                # Strip the service type suffix from the name for readability
                short_name = info.name.replace(f".{type_}", "").replace(f"{type_}", "")
                found.append(
                    {
                        "name": props.get("fn", short_name),
                        "host": host,
                        "port": info.port,
                        "model": props.get("model", ""),
                        "fw": props.get("ver", ""),
                        "id": props.get("id", ""),
                    }
                )

        def remove_service(self, *_):
            pass

        def update_service(self, *_):
            pass

    browser = ServiceBrowser(zc, SERVICE_TYPE, _Listener())
    await asyncio.sleep(timeout_s)
    zc.close()
    return found


def _parse_battery_from_logs(logs: str) -> dict:
    """Extract the most recent battery status line from system logs."""
    # Line format: "... Changed battery status: 99% Charging, 4188mV, charger: true"
    pattern = re.compile(r"Changed battery status:\s+(\d+)%\s+(\w+),\s+(\d+)mV,\s+charger:\s+(\w+)")
    for line in logs.splitlines():
        m = pattern.search(line)
        if m:
            return {
                "battery_level": int(m.group(1)),
                "battery_status": m.group(2),   # Charging / Discharging
                "battery_mv": int(m.group(3)),
                "charger_connected": m.group(4).lower() == "true",
            }
    return {"battery_level": None, "battery_status": None, "battery_mv": None, "charger_connected": None}


async def get_remote_info(host: Optional[str] = None) -> dict:
    """Return name, model, firmware, battery, and current activity for a remote."""
    cfg = get_remote(host)
    if not cfg:
        raise ValueError(
            "No remote configured. Run setup_remote first, or provide host."
        )
    client = UCClient(cfg.host, cfg.port, cfg.api_key)

    # Run the three independent fetches concurrently
    version, system, power_data, logs_raw, activities = await asyncio.gather(
        client.get("/api/pub/version"),   # device_name, hostname, fw versions
        client.get("/api/system"),        # model_name, hw_revision, serial_number
        client.get("/api/system/power"),  # mode, power_supply
        client.get_text("/api/system/logs?count=20"),  # battery in log lines
        client.get_list("/api/activities"),
    )

    battery = _parse_battery_from_logs(logs_raw)
    active = [
        a for a in (activities if isinstance(activities, list) else [])
        if (a.get("attributes") or {}).get("state") == "ON"
    ]

    return {
        "name": version.get("device_name", cfg.name),
        "model": system.get("model_name", cfg.model),
        "model_number": system.get("model_number", ""),
        "hw_revision": system.get("hw_revision", ""),
        "serial_number": system.get("serial_number", ""),
        "hostname": version.get("hostname", cfg.host),
        "firmware": {
            "core": version.get("core", ""),
            "ui": version.get("ui", ""),
            "os": version.get("os", ""),
            "api": version.get("api", ""),
        },
        "battery_level": battery["battery_level"],
        "battery_status": battery["battery_status"],
        "battery_mv": battery["battery_mv"],
        "charger_connected": battery["charger_connected"],
        "power_mode": power_data.get("mode", ""),
        "active_activities": [
            {
                "id": a.get("entity_id", a.get("id")),
                "name": (a.get("name") or {}).get("en_US") or next(iter((a.get("name") or {}).values()), ""),
            }
            for a in active
        ],
    }
