"""diff_config + restore_config: compare live config against a backup and roll back.

Restorable subset = the customization layer of activities and remote-entities:
name, button_mapping, UI pages, and (activities only) power sequences. Entities
and integration instances come from integrations and cannot be recreated through
these endpoints — differences there are reported but never applied.

restore_config token flow (per project safety rules):
1. First call returns a sha256 confirmation_token of the CURRENT live subset plus
   the full dry-run plan. Nothing is written.
2. Calling again with that token AND dry_run=false applies the plan (after an
   auto-backup). If the live config changed in between, the token no longer
   matches and the call returns a fresh token instead of writing.
"""

import hashlib
import json
from pathlib import Path
from typing import Optional

from ._common import get_client
from ..safety.backup import collect_config, create_backup


# ------------------------------------------------------------- subset + token

def _strip_empty_params(cmd: Optional[dict]) -> Optional[dict]:
    if not isinstance(cmd, dict):
        return cmd
    out = {k: v for k, v in cmd.items() if not (k == "params" and not v)}
    return out


def _norm_buttons(button_mapping: list) -> dict:
    """{button: {press: normalized_cmd}} with empty params stripped."""
    out: dict = {}
    for b in button_mapping or []:
        presses = {}
        for press in ("short_press", "long_press"):
            if b.get(press):
                presses[press] = _strip_empty_params(b[press])
        out[b.get("button")] = presses
    return out


def _norm_pages(pages: list) -> dict:
    """{page_id: {name, grid, items}} with item command params normalized."""
    out: dict = {}
    for p in pages or []:
        items = []
        for it in p.get("items") or []:
            it = dict(it)
            if it.get("command"):
                it["command"] = _strip_empty_params(it["command"])
            items.append(it)
        out[p.get("page_id")] = {
            "name": p.get("name"),
            "grid": p.get("grid"),
            "items": items,
        }
    return out


def restorable_subset(config: dict) -> dict:
    """Extract the restorable customization layer from a full snapshot."""
    out: dict = {"activities": {}, "remotes": {}}
    for aid, a in (config.get("activities") or {}).items():
        opts = a.get("options") or {}
        # Drop empty on/off arrays so "no sequences" and "cleared sequences"
        # compare as equal.
        sequences = {
            k: v for k, v in (opts.get("sequences") or {}).items() if v
        }
        out["activities"][aid] = {
            "name": a.get("name"),
            "buttons": _norm_buttons(opts.get("button_mapping")),
            "sequences": sequences,
            "pages": _norm_pages((opts.get("user_interface") or {}).get("pages")),
            "page_order": [
                p.get("page_id")
                for p in (opts.get("user_interface") or {}).get("pages") or []
            ],
        }
    for rid, r in (config.get("remotes") or {}).items():
        opts = r.get("options") or {}
        out["remotes"][rid] = {
            "name": r.get("name"),
            "buttons": _norm_buttons(opts.get("button_mapping")),
            "pages": _norm_pages((opts.get("user_interface") or {}).get("pages")),
            "page_order": [
                p.get("page_id")
                for p in (opts.get("user_interface") or {}).get("pages") or []
            ],
        }
    return out


def subset_token(subset: dict) -> str:
    canonical = json.dumps(subset, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


# ------------------------------------------------------------------ diff plan

def _diff_scope(kind: str, sid: str, want: dict, live: dict) -> list[dict]:
    """Operations to turn `live` scope config into `want`. kind: activity|remote."""
    base = "activities" if kind == "activity" else "remotes"
    ops: list[dict] = []

    if want["name"] != live["name"]:
        ops.append({"op": "patch_name", "kind": kind, "scope_id": sid,
                    "path": f"/api/{base}/{sid}",
                    "from": live["name"], "to": want["name"]})

    # Buttons: per button+press — set where different, clear where live-only.
    all_buttons = set(want["buttons"]) | set(live["buttons"])
    for btn in sorted(all_buttons):
        w, l = want["buttons"].get(btn, {}), live["buttons"].get(btn, {})
        for press in ("short_press", "long_press"):
            if w.get(press) != l.get(press):
                if w.get(press):
                    ops.append({"op": "patch_button", "kind": kind, "scope_id": sid,
                                "path": f"/api/{base}/{sid}/buttons/{btn}",
                                "button": btn, "press": press,
                                "from": l.get(press), "to": w[press]})
                else:
                    ops.append({"op": "delete_button_press", "kind": kind,
                                "scope_id": sid,
                                "path": f"/api/{base}/{sid}/buttons/{btn}/{press}",
                                "button": btn, "press": press,
                                "from": l.get(press), "to": None})

    # Sequences (activities only)
    if kind == "activity" and want.get("sequences", {}) != live.get("sequences", {}):
        to = {
            "on": want.get("sequences", {}).get("on") or [],
            "off": want.get("sequences", {}).get("off") or [],
        }
        ops.append({"op": "patch_sequences", "kind": kind, "scope_id": sid,
                    "path": f"/api/{base}/{sid}",
                    "from": live.get("sequences"), "to": to})

    # Pages: patch same-id-changed, delete live-only, create backup-only.
    want_pages, live_pages = want["pages"], live["pages"]
    for pid in sorted(set(want_pages) | set(live_pages)):
        wp, lp = want_pages.get(pid), live_pages.get(pid)
        if wp and lp and wp != lp:
            ops.append({"op": "patch_page", "kind": kind, "scope_id": sid,
                        "path": f"/api/{base}/{sid}/ui/pages/{pid}",
                        "page_id": pid, "to": wp,
                        "changed_fields": [k for k in ("name", "grid", "items")
                                           if wp.get(k) != lp.get(k)]})
        elif lp and not wp:
            ops.append({"op": "delete_page", "kind": kind, "scope_id": sid,
                        "path": f"/api/{base}/{sid}/ui/pages/{pid}",
                        "page_id": pid, "from_name": lp.get("name")})
        elif wp and not lp:
            ops.append({"op": "create_page", "kind": kind, "scope_id": sid,
                        "path": f"/api/{base}/{sid}/ui/pages",
                        "old_page_id": pid, "to": wp})

    # Page order — only when the surviving-page order differs.
    want_order = want.get("page_order") or []
    live_order = [p for p in (live.get("page_order") or []) if p in want_pages]
    if want_order != live_order and len(want_order) > 1:
        ops.append({"op": "patch_page_order", "kind": kind, "scope_id": sid,
                    "path": f"/api/{base}/{sid}/ui/pages",
                    "to": want_order})
    return ops


def compute_restore_plan(backup_subset: dict, live_subset: dict) -> dict:
    """Full plan: ops for shared scopes + report of unrestorable differences."""
    ops: list[dict] = []
    not_restorable: list[str] = []
    for kind, key in (("activity", "activities"), ("remote", "remotes")):
        want_all, live_all = backup_subset.get(key, {}), live_subset.get(key, {})
        for sid in sorted(set(want_all) | set(live_all)):
            if sid in want_all and sid in live_all:
                ops += _diff_scope(kind, sid, want_all[sid], live_all[sid])
            elif sid in want_all:
                not_restorable.append(
                    f"{kind} {sid} exists in backup but not on the remote "
                    "(cannot recreate via API)."
                )
            else:
                not_restorable.append(
                    f"{kind} {sid} exists on the remote but not in the backup "
                    "(left untouched)."
                )
    return {"ops": ops, "not_restorable": not_restorable}


# --------------------------------------------------------------------- tools

def _load_backup(input_path: str) -> dict:
    p = Path(input_path)
    if not p.exists():
        raise ValueError(f"Backup file not found: {input_path}")
    data = json.loads(p.read_text())
    if "activities" not in data and "remotes" not in data:
        raise ValueError("File doesn't look like a uc-remote-mcp backup.")
    return data


async def diff_config(against_path: str, host: Optional[str] = None) -> dict:
    """
    Show what changed between the current live config and a backup file.
    Read-only. Reports the operations a restore would perform, plus differences
    that cannot be restored (created/removed activities, entity changes).
    """
    client = get_client(host)
    backup = _load_backup(against_path)
    live = await collect_config(client)
    plan = compute_restore_plan(restorable_subset(backup), restorable_subset(live))

    by_kind: dict = {}
    for op in plan["ops"]:
        by_kind.setdefault(op["op"], 0)
        by_kind[op["op"]] += 1

    return {
        "against": str(against_path),
        "backup_created_at": (backup.get("meta") or {}).get("created_at"),
        "differences": len(plan["ops"]),
        "by_type": by_kind,
        "ops": plan["ops"],
        "not_restorable": plan["not_restorable"],
        "identical": not plan["ops"] and not plan["not_restorable"],
    }


async def _execute_ops(client, ops: list[dict]) -> list[dict]:
    results = []
    page_id_map: dict = {}  # old backup page_id -> newly created page_id
    for op in ops:
        try:
            kind = op["op"]
            if kind == "patch_name":
                r = await client.patch(op["path"], {"name": op["to"]})
            elif kind == "patch_button":
                r = await client.patch(op["path"], {op["press"]: op["to"]})
            elif kind == "delete_button_press":
                r = await client.delete(op["path"])
            elif kind == "patch_sequences":
                r = await client.patch(op["path"], {"options": {"sequences": op["to"]}})
            elif kind == "patch_page":
                r = await client.patch(op["path"], op["to"])
            elif kind == "delete_page":
                r = await client.delete(op["path"])
            elif kind == "create_page":
                r = await client.post(op["path"], op["to"])
                if isinstance(r, dict) and r.get("page_id"):
                    page_id_map[op["old_page_id"]] = r["page_id"]
            elif kind == "patch_page_order":
                order = [page_id_map.get(p, p) for p in op["to"]]
                r = await client.patch(op["path"], {"page_order": order})
            else:
                raise ValueError(f"Unknown op {kind}")
            results.append({"op": kind, "path": op["path"], "ok": True})
        except Exception as e:  # noqa: BLE001
            results.append({"op": op["op"], "path": op["path"], "ok": False,
                            "error": str(e)})
    return results


async def restore_config(
    input_path: str,
    confirmation_token: Optional[str] = None,
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Restore the customization layer (names, button mappings, UI pages, sequences
    of activities/remotes) from a backup file.

    Safety: the first call returns a confirmation_token (sha256 of the current
    live config) and the full plan WITHOUT writing. Call again with that token
    and dry_run=false to apply. A changed config invalidates the token.
    An auto-backup of the current state is taken before applying.
    """
    client = get_client(host)
    backup = _load_backup(input_path)
    live = await collect_config(client)
    live_subset = restorable_subset(live)
    token = subset_token(live_subset)
    plan = compute_restore_plan(restorable_subset(backup), live_subset)

    envelope: dict = {
        "action": "restore_config",
        "from_backup": str(input_path),
        "backup_created_at": (backup.get("meta") or {}).get("created_at"),
        "planned_operations": len(plan["ops"]),
        "plan": plan["ops"],
        "not_restorable": plan["not_restorable"],
    }

    if not plan["ops"]:
        envelope["note"] = "Live config already matches this backup — nothing to restore."
        envelope["dry_run"] = True
        return envelope

    if confirmation_token != token:
        envelope["dry_run"] = True
        envelope["confirmation_token"] = token
        envelope["note"] = (
            "Preview only. To apply, call restore_config again with this "
            "confirmation_token and dry_run=false. The token is bound to the "
            "current config; any change in between invalidates it."
            + (" (The token you supplied did not match — config may have changed.)"
               if confirmation_token else "")
        )
        return envelope

    if dry_run:
        envelope["dry_run"] = True
        envelope["confirmation_token"] = token
        envelope["note"] = "Token matches; re-run with dry_run=false to apply."
        return envelope

    pre = await create_backup(client)
    envelope["dry_run"] = False
    envelope["pre_restore_backup"] = {"path": pre["path"], "size_bytes": pre["size_bytes"]}
    results = await _execute_ops(client, plan["ops"])
    envelope["results"] = results
    envelope["applied"] = all(r["ok"] for r in results)
    return envelope
