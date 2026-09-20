"""Device settings and system status.

The API scatters settings over a dozen near-identical ``/api/cfg/*`` endpoints.
Ten more tools for ten endpoints would be worse than useless -- a long tool list
makes picking the right one harder -- so they are one read and one write here,
with the section named as an argument.

The one section that does not behave like the others is ``power_saving``: it
rejects a partial update with a 400, so its three fields are always sent
together, read-modify-write. Everything else takes just the keys you pass.
"""

from typing import Any, Optional

from ..safety.dry_run import apply_mutation
from ._common import get_client, localized

#: Sections that can be read. ``profile`` only reports whether a PIN is set.
READABLE = (
    "display",
    "sound",
    "haptic",
    "power_saving",
    "button",
    "localization",
    "voice_control",
    "network",
    "software_update",
    "profile",
)

#: Sections that can be written. voice_control and profile are left out: the
#: first is driven by the assistant integration, the second is the admin PIN.
WRITABLE = (
    "display",
    "sound",
    "haptic",
    "power_saving",
    "button",
    "localization",
    "software_update",
    "network",
)

#: Sections the API rejects a partial PATCH on -- every field goes every time.
ALL_OR_NOTHING = {
    "power_saving": ("wakeup_sensitivity", "display_off_sec", "standby_sec"),
}

#: Returned on read, refused on write. Sending them back is a 400.
READ_ONLY_KEYS = {
    "button": ("features",),
    "network": ("bt",),
}


def _describe_voice(section: dict) -> dict:
    """voice_control nests the whole assistant entity; keep the useful part."""
    va = section.get("voice_assistant") or {}
    active = va.get("active") or {}
    return {
        "microphone": section.get("microphone"),
        "assistant": {
            "entity_id": active.get("entity_id"),
            "name": localized(active.get("name")),
            "state": active.get("state"),
            "features": active.get("features") or [],
            "profiles": [
                {"id": p.get("id"), "name": p.get("name")}
                for p in (active.get("profiles") or [])
            ],
        }
        if active
        else None,
    }


async def get_settings(section: Optional[str] = None, host: Optional[str] = None) -> dict:
    """
    Read device settings -- one section, or all of them at once.

    Sections: display, sound, haptic, power_saving, button, localization,
    voice_control, network, software_update, profile.

    The battery-relevant ones live in ``power_saving``: ``display_off_sec`` is
    how long until the screen sleeps, ``standby_sec`` until the remote does.
    """
    client = get_client(host)
    if section and section not in READABLE:
        raise ValueError(f"Unknown section '{section}'. Try: {', '.join(READABLE)}")
    wanted = (section,) if section else READABLE

    out: dict[str, Any] = {}
    for name in wanted:
        try:
            data = await client.get(f"/api/cfg/{name}")
        except Exception as e:  # noqa: BLE001 -- one missing section is not fatal
            out[name] = {"error": str(e)[:150]}
            continue
        out[name] = _describe_voice(data) if name == "voice_control" else data
    return out[section] if section else out


async def update_settings(
    section: str,
    values: dict,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Change a section of device settings. Pass only the keys you want to change.

    Writable: display (brightness 0-100, auto_brightness), sound (enabled,
    volume), haptic (enabled), power_saving (wakeup_sensitivity 0-3,
    display_off_sec, standby_sec), button (brightness, auto_brightness,
    static_color), localization (language_code, country_code, time_zone,
    time_format_24h, measurement_unit), software_update (check_for_updates,
    auto_update, ota_window_start/end), network (wifi_enabled, bt_enabled).

    ``power_saving`` is read-modify-written whole, because it rejects a partial
    update -- so changing just ``standby_sec`` here works as you would expect.
    """
    if section not in WRITABLE:
        raise ValueError(
            f"'{section}' cannot be written. Writable sections: {', '.join(WRITABLE)}"
        )
    if not values:
        raise ValueError("Nothing to change -- pass the values you want to set.")

    blocked = set(values) & set(READ_ONLY_KEYS.get(section, ()))
    if blocked:
        raise ValueError(
            f"{', '.join(sorted(blocked))} is reported by the remote but cannot be set."
        )

    client = get_client(host)
    current = await client.get(f"/api/cfg/{section}")

    body = dict(values)
    required = ALL_OR_NOTHING.get(section)
    if required:
        unknown = set(values) - set(required)
        if unknown:
            raise ValueError(
                f"{section} has no field(s) {', '.join(sorted(unknown))}. "
                f"Fields: {', '.join(required)}"
            )
        # A partial PATCH is a 400 here, so fill the rest in from what is set.
        body = {k: values.get(k, current.get(k)) for k in required}

    before = {k: current.get(k) for k in body}
    changed = ", ".join(
        f"{k} {before.get(k)!r} -> {v!r}" for k, v in body.items() if before.get(k) != v
    )

    return await apply_mutation(
        client,
        action="update_settings",
        summary=f"{section}: {changed or 'no change'}",
        change={"section": section, "from": before, "to": body},
        do_write=lambda: client.patch(f"/api/cfg/{section}", body),
        dry_run=dry_run,
    )


async def get_system_status(host: Optional[str] = None) -> dict:
    """
    How the remote is doing right now: battery, charge state, wi-fi signal,
    firmware versions, memory and storage, and how long until standby.

    ``rssi`` is dBm -- better than -60 is strong, worse than -75 is where
    commands start to drop.
    """
    client = get_client(host)

    async def _try(path: str) -> dict:
        try:
            return await client.get(path)
        except Exception:  # noqa: BLE001 -- partial status beats no status
            return {}

    hw = await _try("/api/system")
    ver = await _try("/api/pub/version")
    power = await _try("/api/system/power")
    battery = await _try("/api/system/power/battery")
    wifi = await _try("/api/system/wifi")
    light = await _try("/api/system/sensors/ambient_light")
    status = await _try("/api/pub/status")
    update = await _try("/api/system/update")

    mem = status.get("memory") or {}
    fs = (status.get("filesystem") or {}).get("user_data") or {}
    mb = lambda v: round(v / 1048576) if isinstance(v, (int, float)) else None  # noqa: E731

    return {
        "model": hw.get("model_name") or ver.get("model"),
        "serial": hw.get("serial_number"),
        "hostname": ver.get("hostname"),
        "firmware": {
            "os": ver.get("os"),
            "core": ver.get("core"),
            "ui": ver.get("ui"),
            "api": ver.get("api"),
        },
        "battery": {
            "percent": battery.get("capacity"),
            "status": battery.get("status"),
            "on_charger": battery.get("power_supply"),
        },
        "power": {
            "mode": power.get("mode"),
            "standby_in_sec": power.get("standby_timeout_sec"),
            "kept_awake": power.get("standby_inhibitors"),
        },
        "wifi": {
            "ssid": wifi.get("ssid"),
            "ip_address": wifi.get("ip_address"),
            "rssi": wifi.get("rssi"),
            "freq_mhz": wifi.get("freq"),
            "state": wifi.get("wpa_state"),
        },
        "ambient_light": light.get("intensity"),
        "memory": {"used_mb": mb(mem.get("used_memory")), "total_mb": mb(mem.get("total_memory"))},
        "storage": {"used_mb": mb(fs.get("used")), "free_mb": mb(fs.get("available"))},
        "update": {
            "installed_version": update.get("installed_version"),
            "in_progress": update.get("update_in_progress"),
            "checks_enabled": update.get("update_check_enabled"),
            "next_check": update.get("next_check_date"),
        },
    }


# ------------------------------------------------------------ optional features


async def list_features(host: Optional[str] = None) -> dict:
    """
    Experimental features the firmware ships behind a toggle, and whether each
    is on. These are the same switches as Settings -> Features on the remote.
    """
    client = get_client(host)
    feats = await client.get_list("/api/cfg/features")
    return {
        "features": [
            {
                "id": f.get("id"),
                "enabled": f.get("enabled"),
                "title": localized(f.get("title")),
                "description": localized(f.get("description")),
            }
            for f in feats
        ]
    }


async def set_feature_enabled(
    feature_id: str,
    enabled: bool,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """Turn an experimental feature on or off. Some need a restart to take hold."""
    client = get_client(host)
    feats = await client.get_list("/api/cfg/features")
    match = next((f for f in feats if f.get("id") == feature_id), None)
    if match is None:
        have = ", ".join(f.get("id", "?") for f in feats)
        raise ValueError(f"No feature '{feature_id}'. Available: {have or 'none'}")

    return await apply_mutation(
        client,
        action="set_feature_enabled",
        summary=f"{'enable' if enabled else 'disable'} feature "
        f"'{localized(match.get('title')) or feature_id}'",
        change={"feature_id": feature_id, "from": match.get("enabled"), "to": enabled},
        do_write=lambda: client.patch(
            f"/api/cfg/features/{feature_id}", {"enabled": enabled}
        ),
        dry_run=dry_run,
    )
