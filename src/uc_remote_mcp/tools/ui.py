"""UI page tools: list_ui_pages, get_ui_page.

UC embeds UI pages inside each activity/remote under options.user_interface.pages.
There is no standalone /api/profiles/pages endpoint on this firmware, so pages are
addressed by their parent scope plus page_id.
"""

from typing import Optional

from ._common import get_client, localized, normalize_item, pages_of


async def _scope_detail(client, scope: str, scope_id: str) -> dict:
    scope = scope.lower()
    if scope == "activity":
        return await client.get(f"/api/activities/{scope_id}")
    if scope == "remote":
        return await client.get(f"/api/remotes/{scope_id}")
    raise ValueError(f"Unknown scope '{scope}'. Use activity or remote.")


async def list_ui_pages(
    scope: str, scope_id: str, host: Optional[str] = None
) -> dict:
    """
    List UI pages for a scope.

    scope is "activity" or "remote"; scope_id is that entity's id.
    Returns {scope, scope_id, name, pages:[{page_id, name, grid, item_count}]}.
    """
    client = get_client(host)
    detail = await _scope_detail(client, scope, scope_id)
    return {
        "scope": scope.lower(),
        "scope_id": scope_id,
        "name": localized(detail.get("name")),
        "pages": [
            {
                "page_id": p.get("page_id"),
                "name": localized(p.get("name")),
                "grid": p.get("grid"),
                "item_count": len(p.get("items") or []),
            }
            for p in pages_of(detail)
        ],
    }


async def get_ui_page(
    scope: str, scope_id: str, page_id: str, host: Optional[str] = None
) -> dict:
    """
    Items on one UI page, with grid dimensions and each item's position, type,
    and bound command.

    Identify the page by its parent scope ("activity" or "remote"), the scope's
    entity_id, and the page_id (from list_ui_pages).
    """
    client = get_client(host)
    detail = await _scope_detail(client, scope, scope_id)
    for p in pages_of(detail):
        if p.get("page_id") == page_id:
            return {
                "scope": scope.lower(),
                "scope_id": scope_id,
                "page_id": p.get("page_id"),
                "name": localized(p.get("name")),
                "grid": p.get("grid"),
                "items": [normalize_item(it) for it in (p.get("items") or [])],
            }
    raise ValueError(f"No page '{page_id}' found in {scope} {scope_id}.")
