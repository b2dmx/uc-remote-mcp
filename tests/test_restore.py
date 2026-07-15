"""Unit tests for the restore diff engine against real API shapes."""

import copy

from uc_remote_mcp.tools.restore import (
    restorable_subset,
    subset_token,
    compute_restore_plan,
)

ACT = "uc.main.11111111-2222-4333-8444-555555555555"
SONY = "sonyavr_driver.main.media_player.1234567"


def _config(activity_detail, remote_detail) -> dict:
    """Wrap fixtures into a collect_config()-shaped snapshot."""
    return {
        "meta": {},
        "activities": {ACT: activity_detail},
        "remotes": {remote_detail["entity_id"]: remote_detail},
    }


def test_subset_normalizes_empty_params(activity_detail, remote_detail):
    sub = restorable_subset(_config(activity_detail, remote_detail))
    vu = sub["activities"][ACT]["buttons"]["VOLUME_UP"]["short_press"]
    assert "params" not in vu  # empty params dict stripped


def test_subset_drops_empty_sequences(activity_detail, remote_detail):
    a = copy.deepcopy(activity_detail)
    a["options"]["sequences"] = {"on": [], "off": []}
    sub = restorable_subset(_config(a, remote_detail))
    assert sub["activities"][ACT]["sequences"] == {}


def test_token_stable_and_sensitive(activity_detail, remote_detail):
    cfg = _config(activity_detail, remote_detail)
    t1 = subset_token(restorable_subset(cfg))
    t2 = subset_token(restorable_subset(copy.deepcopy(cfg)))
    assert t1 == t2
    changed = copy.deepcopy(cfg)
    changed["activities"][ACT]["options"]["button_mapping"][0]["short_press"][
        "cmd_id"
    ] = "media_player.mute_toggle"
    assert subset_token(restorable_subset(changed)) != t1


def test_plan_identical_is_empty(activity_detail, remote_detail):
    cfg = _config(activity_detail, remote_detail)
    plan = compute_restore_plan(restorable_subset(cfg),
                                restorable_subset(copy.deepcopy(cfg)))
    assert plan["ops"] == [] and plan["not_restorable"] == []


def test_plan_button_change(activity_detail, remote_detail):
    backup = _config(activity_detail, remote_detail)
    live = copy.deepcopy(backup)
    live["activities"][ACT]["options"]["button_mapping"][0]["short_press"][
        "cmd_id"
    ] = "media_player.mute_toggle"
    plan = compute_restore_plan(restorable_subset(backup), restorable_subset(live))
    assert len(plan["ops"]) == 1
    op = plan["ops"][0]
    assert op["op"] == "patch_button" and op["button"] == "VOLUME_UP"
    assert op["to"]["cmd_id"] == "media_player.volume_up"


def test_plan_clears_live_only_press(activity_detail, remote_detail):
    backup = _config(activity_detail, remote_detail)
    live = copy.deepcopy(backup)
    live["activities"][ACT]["options"]["button_mapping"][2]["short_press"] = {
        "cmd_id": "media_player.on", "entity_id": SONY,
    }  # POWER gained a binding live; backup has none
    plan = compute_restore_plan(restorable_subset(backup), restorable_subset(live))
    assert [op["op"] for op in plan["ops"]] == ["delete_button_press"]
    assert plan["ops"][0]["button"] == "POWER"


def test_plan_page_rename_and_pages(activity_detail, remote_detail):
    backup = _config(activity_detail, remote_detail)
    live = copy.deepcopy(backup)
    pages = live["activities"][ACT]["options"]["user_interface"]["pages"]
    pages[0]["name"] = "Inputs RENAMED"           # changed -> patch_page
    del pages[1]                                   # backup-only -> create_page
    pages.append({"page_id": "live-extra", "name": "X",
                  "grid": {"width": 4, "height": 6}, "items": []})  # live-only -> delete
    plan = compute_restore_plan(restorable_subset(backup), restorable_subset(live))
    kinds = sorted(op["op"] for op in plan["ops"])
    # page_order op is expected too: recreated pages get appended, so the
    # engine enforces the backup's ordering afterwards.
    assert kinds == ["create_page", "delete_page", "patch_page", "patch_page_order"]
    patch = next(o for o in plan["ops"] if o["op"] == "patch_page")
    assert patch["page_id"] == "main" and patch["changed_fields"] == ["name"]
    order = next(o for o in plan["ops"] if o["op"] == "patch_page_order")
    assert order["to"] == ["main", "page-two"]


def test_plan_scope_missing_is_not_restorable(activity_detail, remote_detail):
    backup = _config(activity_detail, remote_detail)
    live = {"meta": {}, "activities": {}, "remotes": backup["remotes"]}
    plan = compute_restore_plan(restorable_subset(backup), restorable_subset(live))
    assert plan["ops"] == []
    assert any("exists in backup but not on the remote" in n
               for n in plan["not_restorable"])
