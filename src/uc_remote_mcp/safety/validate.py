"""Client-side validation of command names before writing button mappings.

The remote accepts unknown cmd_ids and silently breaks the binding, so we verify
the command exists on the target entity first.

The authoritative command list for a mappable target lives in the parent
activity/remote's `options.included_entities[].entity_commands` (+ simple_commands).
A bare entity GET does NOT expose entity_commands, so we always validate using the
scope detail we already hold, never by guessing from feature flags.
"""

from typing import Optional


def commands_for_target(scope_detail: dict, entity_id: str) -> Optional[set[str]]:
    """
    Authoritative cmd_id set for `entity_id` as included in this activity/remote.

    Returns None if the target isn't found among included entities (caller decides
    whether that's an error). Returns a (possibly empty) set otherwise.
    """
    opts = scope_detail.get("options") or {}
    for e in opts.get("included_entities") or []:
        if e.get("entity_id") == entity_id:
            names: set[str] = set()
            names.update(e.get("entity_commands") or [])
            names.update(e.get("simple_commands") or [])
            return names
    return None


def included_entity_ids(scope_detail: dict) -> list[str]:
    opts = scope_detail.get("options") or {}
    return [e.get("entity_id") for e in (opts.get("included_entities") or [])]


def validate_activity_command(
    scope_detail: dict, entity_id: str, cmd_id: str
) -> Optional[str]:
    """
    Validate a command for an activity button mapping. Returns None if valid,
    else a human-readable error string.

    Rules (per OpenAPI): for an activity the target entity_id is required and must
    be one of the activity's included entities; the cmd_id must be one of that
    entity's commands.
    """
    targets = included_entity_ids(scope_detail)
    if entity_id not in targets:
        sample = ", ".join(targets[:6])
        return (
            f"Entity '{entity_id}' is not included in this activity. "
            f"Included entities: {sample}"
        )

    valid = commands_for_target(scope_detail, entity_id) or set()
    if not valid or cmd_id in valid:
        return None

    lowered = {v.lower(): v for v in valid}
    hint = lowered.get(cmd_id.lower())
    suffix = f" Did you mean '{hint}'?" if hint else ""
    sample = ", ".join(sorted(valid)[:12])
    return (
        f"Command '{cmd_id}' is not valid for {entity_id}.{suffix} "
        f"Known commands include: {sample}..."
    )


def validate_remote_command(scope_detail: dict, cmd_id: str) -> Optional[str]:
    """
    Validate a command for a remote-entity button mapping. For remotes the command
    is a local code (IR key / simple command) and entity_id is ignored. Validate
    cmd_id against the remote's own simple_commands.
    """
    opts = scope_detail.get("options") or {}
    valid = set(opts.get("simple_commands") or [])
    if not valid or cmd_id in valid:
        return None

    lowered = {v.lower(): v for v in valid}
    hint = lowered.get(cmd_id.lower())
    suffix = f" Did you mean '{hint}'?" if hint else ""
    sample = ", ".join(sorted(valid)[:12])
    return (
        f"Command '{cmd_id}' is not a known code on this remote.{suffix} "
        f"Known codes include: {sample}..."
    )
