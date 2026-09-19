"""Entity-list merging for activities and macros.

The API replaces the list rather than patching it, and anything left out is
removed along with every button mapping and page item that used it. So what is
tested here is mostly that the caller's input is never written straight through.
"""

import pytest

from uc_remote_mcp.safety import dry_run as dry_run_mod
from uc_remote_mcp.tools import inclusion


class FakeClient:
    """Records what would be written, and serves a fixed current list."""

    def __init__(self, current: list[str]):
        self._current = current
        self.patched: list[tuple[str, dict]] = []

    async def get(self, path: str, **params):
        return {
            "options": {
                "included_entities": [
                    {"entity_id": e, "name": {"en": e}, "entity_type": "media_player"}
                    for e in self._current
                ]
            }
        }

    async def patch(self, path: str, body=None):
        self.patched.append((path, body))
        return {}


@pytest.fixture
def client(monkeypatch):
    """A fake remote, with the pre-write snapshot stubbed out.

    Real writes go through apply_mutation, which takes a full config backup
    first. That is the behaviour under test elsewhere; here it would just mean
    the fake had to implement every read endpoint.
    """

    async def _no_backup(_client):
        return {"path": "<test>", "size_bytes": 0}

    monkeypatch.setattr(dry_run_mod, "create_backup", _no_backup)

    def _make(current):
        c = FakeClient(current)
        monkeypatch.setattr(inclusion, "get_client", lambda host=None: c)
        return c

    return _make


def written(c: FakeClient) -> list[str]:
    return c.patched[0][1]["options"]["entity_ids"]


class TestAdd:
    @pytest.mark.asyncio
    async def test_keeps_everything_already_there(self, client):
        c = client(["a", "b"])
        await inclusion.add_scope_entities("act1", ["c"], dry_run=False)
        # The whole list goes back, not just the addition.
        assert written(c) == ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_duplicate_is_not_added_twice(self, client):
        c = client(["a", "b"])
        r = await inclusion.add_scope_entities("act1", ["b"], dry_run=False)
        assert written(c) == ["a", "b"]
        assert any("Already configured" in w for w in r["warnings"])

    @pytest.mark.asyncio
    async def test_dry_run_writes_nothing(self, client):
        c = client(["a"])
        r = await inclusion.add_scope_entities("act1", ["b"], dry_run=True)
        assert c.patched == []
        assert r["dry_run"] is True

    @pytest.mark.asyncio
    async def test_macro_scope_hits_the_macro_endpoint(self, client):
        c = client(["a"])
        await inclusion.add_scope_entities("m1", ["b"], scope="macro", dry_run=False)
        assert c.patched[0][0] == "/api/macros/m1"

    @pytest.mark.asyncio
    async def test_unknown_scope_is_refused(self, client):
        client(["a"])
        with pytest.raises(ValueError):
            await inclusion.add_scope_entities("x", ["b"], scope="profile")


class TestRemove:
    @pytest.mark.asyncio
    async def test_removes_only_what_was_asked(self, client):
        c = client(["a", "b", "c"])
        await inclusion.remove_scope_entities("act1", ["b"], dry_run=False)
        assert written(c) == ["a", "c"]

    @pytest.mark.asyncio
    async def test_always_warns_about_losing_mappings(self, client):
        client(["a", "b"])
        r = await inclusion.remove_scope_entities("act1", ["b"], dry_run=True)
        assert any("button mapping" in w.lower() for w in r["warnings"])

    @pytest.mark.asyncio
    async def test_warns_when_the_list_would_be_emptied(self, client):
        client(["a"])
        r = await inclusion.remove_scope_entities("act1", ["a"], dry_run=True)
        assert any("empties the list" in w for w in r["warnings"])

    @pytest.mark.asyncio
    async def test_entity_that_is_not_there_is_ignored(self, client):
        c = client(["a"])
        r = await inclusion.remove_scope_entities("act1", ["zzz"], dry_run=False)
        assert written(c) == ["a"]
        assert any("Not configured here" in w for w in r["warnings"])
