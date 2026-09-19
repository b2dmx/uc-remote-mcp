"""Which entities an activity or macro is allowed to use.

Exposing an entity from an integration is not enough to use it: an activity or
macro keeps its own list, and a command naming an entity outside that list is
rejected.

The API makes this genuinely dangerous. ``included_entities`` is a read-only
enriched view, so the writable field is ``options.entity_ids`` -- and it is a
*replacement*, not a patch. Sending a partial list silently removes whatever is
missing, and removing an entity takes every button mapping and page item that
referenced it with it. An empty array removes everything.

So these tools never send a caller's list straight through. They read the
current list, merge, and write the whole thing back.
"""

from typing import Optional

from ..safety.dry_run import apply_mutation
from ._common import get_client, localized

_SCOPES = {"activity": "/api/activities", "macro": "/api/macros"}


def _base(scope: str) -> str:
    if scope not in _SCOPES:
        raise ValueError(f"scope must be one of {sorted(_SCOPES)}, got {scope!r}")
    return _SCOPES[scope]


async def _current(client, scope: str, scope_id: str) -> tuple[list[str], list[dict]]:
    """The entity ids currently configured, and their enriched detail."""
    detail = await client.get(f"{_base(scope)}/{scope_id}")
    included = (detail.get("options") or {}).get("included_entities") or []
    ids = [e.get("entity_id") or e.get("id") for e in included]
    return [i for i in ids if i], included


async def list_scope_entities(
    scope_id: str, scope: str = "activity", host: Optional[str] = None
) -> dict:
    """Entities an activity or macro is currently allowed to use."""
    client = get_client(host)
    ids, included = await _current(client, scope, scope_id)
    return {
        "scope": scope,
        "scope_id": scope_id,
        "count": len(ids),
        "entities": [
            {
                "entity_id": e.get("entity_id") or e.get("id"),
                "name": localized(e.get("name")),
                "entity_type": e.get("entity_type") or e.get("type"),
            }
            for e in included
        ],
    }


async def add_scope_entities(
    scope_id: str,
    entity_ids: list[str],
    scope: str = "activity",
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Allow an activity or macro to use additional entities.

    The complete list is rebuilt and written back, so nothing already configured
    is disturbed. Entities already present are left alone.
    """
    client = get_client(host)
    current, _ = await _current(client, scope, scope_id)
    already = [e for e in entity_ids if e in current]
    adding = [e for e in entity_ids if e not in current]
    merged = current + adding

    warnings = []
    if already:
        warnings.append(f"Already configured, unchanged: {', '.join(already)}")
    if not adding:
        warnings.append("Nothing to add; the list is unchanged.")

    return await apply_mutation(
        client,
        action="add_scope_entities",
        summary=f"allow {scope} {scope_id} to use {len(adding)} more entit"
        f"{'y' if len(adding) == 1 else 'ies'}",
        change={
            "scope": scope,
            "scope_id": scope_id,
            "adding": adding,
            "before_count": len(current),
            "after_count": len(merged),
        },
        do_write=lambda: client.patch(
            f"{_base(scope)}/{scope_id}", {"options": {"entity_ids": merged}}
        ),
        dry_run=dry_run,
        warnings=warnings or None,
    )


async def remove_scope_entities(
    scope_id: str,
    entity_ids: list[str],
    scope: str = "activity",
    dry_run: bool = True,
    host: Optional[str] = None,
) -> dict:
    """
    Stop an activity or macro from using entities.

    Destructive beyond the list itself: every button mapping and page item that
    referenced a removed entity is removed with it, and that cannot be undone
    except by restoring the backup this takes first. The preview names what is
    going away -- read it.
    """
    client = get_client(host)
    current, _ = await _current(client, scope, scope_id)
    removing = [e for e in entity_ids if e in current]
    missing = [e for e in entity_ids if e not in current]
    remaining = [e for e in current if e not in removing]

    warnings = [
        "Button mappings and page items using these entities will be removed "
        "with them.",
    ]
    if missing:
        warnings.append(f"Not configured here, ignored: {', '.join(missing)}")
    if not remaining and removing:
        warnings.append(
            f"This empties the list: the {scope} will have no entities left."
        )

    return await apply_mutation(
        client,
        action="remove_scope_entities",
        summary=f"stop {scope} {scope_id} using {len(removing)} entit"
        f"{'y' if len(removing) == 1 else 'ies'}",
        change={
            "scope": scope,
            "scope_id": scope_id,
            "removing": removing,
            "before_count": len(current),
            "after_count": len(remaining),
        },
        do_write=lambda: client.patch(
            f"{_base(scope)}/{scope_id}", {"options": {"entity_ids": remaining}}
        ),
        dry_run=dry_run,
        warnings=warnings,
    )
