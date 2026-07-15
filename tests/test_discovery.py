"""Unit tests for battery parsing from real /api/system/logs lines."""

from uc_remote_mcp.tools.discovery import _parse_battery_from_logs

REAL_LOGS = """2026-05-30 03:03:18.391941 +00:00\tcore\tNOTICE\tSetting rgb button backlight to: (0, 0, 0)
2026-05-30 03:03:18.390113 +00:00\tcore\tNOTICE\tEnter idle mode: standby in 285s
2026-05-30 03:03:10.424454 +00:00\tcore\tNOTICE\tChanged battery status: 99% Charging, 4188mV, charger: true
2026-05-30 03:03:05.419945 +00:00\tcore\tNOTICE\tChanged battery status: 99% Discharging, 4101mV, charger: true
"""


def test_parses_most_recent_battery_line():
    b = _parse_battery_from_logs(REAL_LOGS)
    assert b["battery_level"] == 99
    assert b["battery_status"] == "Charging"  # first match = newest line
    assert b["battery_mv"] == 4188
    assert b["charger_connected"] is True


def test_no_battery_lines_returns_nones():
    b = _parse_battery_from_logs("no battery info here\njust noise")
    assert b["battery_level"] is None
    assert b["charger_connected"] is None
