"""Unit tests for safety/validate.py against real API shapes."""

from uc_remote_mcp.safety.validate import (
    commands_for_target,
    validate_activity_command,
    validate_remote_command,
)

SONY = "sonyavr_driver.main.media_player.1234567"
ATV = "uc_appletv_driver.main.AA:BB:CC:00:11:22"


def test_commands_for_target_merges_entity_and_simple(activity_detail):
    cmds = commands_for_target(activity_detail, SONY)
    assert "media_player.volume_up" in cmds
    assert "ZONE_HDMI_OUTPUT_A" in cmds


def test_commands_for_target_unknown_entity(activity_detail):
    assert commands_for_target(activity_detail, "nope.entity") is None


def test_validate_activity_command_ok(activity_detail):
    assert validate_activity_command(activity_detail, SONY, "media_player.volume_up") is None
    assert validate_activity_command(activity_detail, ATV, "TOP_MENU") is None


def test_validate_activity_command_bad_command(activity_detail):
    err = validate_activity_command(activity_detail, SONY, "media_player.bogus")
    assert err is not None and "not valid" in err


def test_validate_activity_command_entity_not_included(activity_detail):
    err = validate_activity_command(activity_detail, "hass.main.light.x", "media_player.on")
    assert err is not None and "not included" in err


def test_validate_activity_command_case_hint(activity_detail):
    err = validate_activity_command(activity_detail, SONY, "MEDIA_PLAYER.VOLUME_UP")
    assert err is not None and "Did you mean 'media_player.volume_up'" in err


def test_validate_remote_command_ok(remote_detail):
    assert validate_remote_command(remote_detail, "Volume_Up") is None


def test_validate_remote_command_bad(remote_detail):
    err = validate_remote_command(remote_detail, "NOT_A_CODE")
    assert err is not None and "not a known code" in err
