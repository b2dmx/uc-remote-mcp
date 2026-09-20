"""Setup-flow helpers: the string coercion and screen flattening.

These are the two bits of real logic in the integrations module that do not
need a remote. Everything else is a thin call onto the REST client.
"""

import pytest

from uc_remote_mcp.tools.integrations import _screen, _stringify


class TestStringify:
    """Setup flows reject anything that is not a string, silently and fatally."""

    def test_booleans_become_lowercase_words(self):
        # Python's str(True) is "True", which the remote does not accept.
        assert _stringify({"pairing": True}) == {"pairing": "true"}

    def test_false_is_the_word_false_not_empty(self):
        assert _stringify({"test_wakeonlan": False}) == {"test_wakeonlan": "false"}

    def test_numbers_become_strings(self):
        assert _stringify({"wolport": 9}) == {"wolport": "9"}
        assert _stringify({"volume_step": 2.0}) == {"volume_step": "2.0"}

    def test_strings_pass_through(self):
        assert _stringify({"address": "10.0.0.5"}) == {"address": "10.0.0.5"}

    def test_empty_string_is_preserved(self):
        # Several flows require a field to be present but empty; dropping it
        # or sending None is rejected.
        assert _stringify({"broadcast": ""}) == {"broadcast": ""}

    def test_none_becomes_empty_not_the_word_none(self):
        assert _stringify({"broadcast": None}) == {"broadcast": ""}

    def test_everything_is_a_string_afterwards(self):
        out = _stringify({"a": 1, "b": True, "c": "x", "d": 2.5})
        assert all(isinstance(v, str) for v in out.values())


class TestScreen:
    """Flatten the flow's nested shape into the question being asked."""

    def test_extracts_fields_and_labels(self):
        state = {
            "state": "WAIT_USER_ACTION",
            "require_user_action": {
                "input": {
                    "title": {"en": "Additional settings"},
                    "settings": [
                        {
                            "id": "address",
                            "label": {"en": "IP address"},
                            "field": {"text": {"value": "192.0.2.1"}},
                        }
                    ],
                }
            },
        }
        out = _screen(state)
        assert out["state"] == "WAIT_USER_ACTION"
        assert out["title"] == "Additional settings"
        assert out["fields"][0]["id"] == "address"
        assert out["fields"][0]["type"] == "text"
        assert out["fields"][0]["default"] == "192.0.2.1"

    def test_dropdown_options_are_listed(self):
        state = {
            "state": "WAIT_USER_ACTION",
            "require_user_action": {
                "input": {
                    "title": {"en": "Choose your device"},
                    "settings": [
                        {
                            "id": "choice",
                            "label": {"en": "Device"},
                            "field": {
                                "dropdown": {
                                    "items": [
                                        {"id": "a", "label": {"en": "Living room"}},
                                        {"id": "b", "label": {"en": "Bedroom"}},
                                    ]
                                }
                            },
                        }
                    ],
                }
            },
        }
        out = _screen(state)
        assert [o["id"] for o in out["fields"][0]["options"]] == ["a", "b"]
        assert out["fields"][0]["options"][0]["label"] == "Living room"

    def test_label_field_text_is_localized(self):
        state = {"state": "WAIT_USER_ACTION", "require_user_action": {"input": {
            "title": {"en": "Setup"},
            "settings": [{"id": "info", "label": {"en": "Info"},
                          "field": {"label": {"value": {"en": "Leave blank.", "de": "Leer lassen."}}}}]}}}
        assert _screen(state)["fields"][0]["default"] == "Leave blank."

    def test_finished_flow_has_no_fields(self):
        assert _screen({"state": "OK"}) == {
            "state": "OK",
            "error": None,
            "title": "",
            "fields": [],
        }

    def test_error_state_is_surfaced(self):
        # A flow that died still has to be reportable rather than look empty.
        out = _screen({"state": "ERROR", "error": "OTHER"})
        assert out["state"] == "ERROR"
        assert out["error"] == "OTHER"

    def test_confirmation_page_surfaces_its_message(self):
        state = {
            "state": "WAIT_USER_ACTION",
            "require_user_action": {
                "confirmation": {
                    "title": {"en": "Pair"},
                    "message1": {"en": "Accept the prompt on the TV."},
                    "message2": {"en": "Then continue."},
                }
            },
        }
        out = _screen(state)
        assert out["fields"] == []
        assert out["message"] == "Accept the prompt on the TV. Then continue."

    def test_survives_a_missing_action_block(self):
        assert _screen({})["fields"] == []


class TestWaitForScreen:
    """The flow sits in SETUP before the driver produces a screen."""

    @pytest.mark.asyncio
    async def test_polls_past_setup_to_the_first_screen(self):
        from uc_remote_mcp.tools.integrations import _wait_for_screen

        class Client:
            calls = 0

            async def get(self, path, **params):
                Client.calls += 1
                if Client.calls < 3:
                    return {"state": "SETUP"}
                return {
                    "state": "WAIT_USER_ACTION",
                    "require_user_action": {
                        "input": {"title": {"en": "Address"}, "settings": []}
                    },
                }

        out = await _wait_for_screen(Client(), "drv", timeout=5)
        assert out["state"] == "WAIT_USER_ACTION"
        assert out["title"] == "Address"
        assert Client.calls == 3

    @pytest.mark.asyncio
    async def test_gives_up_with_a_hint_rather_than_an_empty_screen(self):
        from uc_remote_mcp.tools.integrations import _wait_for_screen

        class Client:
            async def get(self, path, **params):
                return {"state": "SETUP"}

        out = await _wait_for_screen(Client(), "drv", timeout=0.6)
        assert out["state"] == "SETUP"
        assert "get_integration_setup" in out["note"]


def _flow_screen(title: str, field_id: str, state: str = "WAIT_USER_ACTION") -> dict:
    """A setup-flow response as the remote sends it."""
    return {
        "state": state,
        "require_user_action": {
            "input": {
                "title": {"en": title},
                "settings": [
                    {"id": field_id, "label": {"en": field_id},
                     "field": {"text": {"value": ""}}}
                ],
            }
        },
    }


class FakeFlowClient:
    """Serves a scripted sequence of setup-flow screens."""

    def __init__(self, screens):
        self._screens = list(screens)
        self.gets = 0

    async def get(self, path):  # noqa: D102 - test double
        self.gets += 1
        # Hold on the last screen once the script runs out.
        return self._screens[min(self.gets - 1, len(self._screens) - 1)]


class TestWaitForScreen:
    """The flow briefly re-serves the screen that was just answered.

    Answering returns immediately and the flow goes back to WAIT_USER_ACTION
    still showing the old question. Returning that screen makes a caller answer
    the same step forever, which is how a real Sony setup appeared to hang.
    """

    @pytest.mark.asyncio
    async def test_waits_until_the_screen_actually_changes(self):
        from uc_remote_mcp.tools.integrations import _fingerprint, _wait_for_screen

        old = _flow_screen("Configuration mode", "configuration_mode")
        new = _flow_screen("Setup mode", "address")
        client = FakeFlowClient([old, old, new])

        got = await _wait_for_screen(
            client, "drv", timeout=5, previous=_fingerprint(_screen(old))
        )

        assert got["title"] == "Setup mode"
        assert [f["id"] for f in got["fields"]] == ["address"]

    @pytest.mark.asyncio
    async def test_without_a_previous_screen_the_first_one_is_returned(self):
        from uc_remote_mcp.tools.integrations import _wait_for_screen

        first = _flow_screen("Configuration mode", "configuration_mode")
        got = await _wait_for_screen(FakeFlowClient([first]), "drv", timeout=5)
        assert got["title"] == "Configuration mode"

    @pytest.mark.asyncio
    async def test_a_screen_that_never_changes_says_so_rather_than_hanging(self):
        from uc_remote_mcp.tools.integrations import _fingerprint, _wait_for_screen

        stuck = _flow_screen("Configuration mode", "configuration_mode")
        got = await _wait_for_screen(
            FakeFlowClient([stuck]), "drv", timeout=1,
            previous=_fingerprint(_screen(stuck)),
        )
        assert got["title"] == "Configuration mode"
        assert "not moved on" in got["note"]

    @pytest.mark.asyncio
    async def test_waits_out_the_busy_state(self):
        from uc_remote_mcp.tools.integrations import _wait_for_screen

        busy = {"state": "SETUP"}
        ready = _flow_screen("Please choose your Sony AVR", "choice")
        got = await _wait_for_screen(FakeFlowClient([busy, busy, ready]), "drv", timeout=5)
        assert got["title"] == "Please choose your Sony AVR"


class TestPackageDriverJson:
    """The package is read before the installed driver is deleted.

    Getting this wrong is expensive: the update path deletes first, so a
    mismatched package would leave the remote with neither driver.
    """

    @staticmethod
    def _package(tmp_path, driver_id="lgwebos_driver", version="1.17.1", prefix="./"):
        import io as _io
        import json as _json
        import tarfile

        path = tmp_path / "pkg.tar.gz"
        blob = _json.dumps({"driver_id": driver_id, "version": version}).encode()
        with tarfile.open(path, "w:gz") as tar:
            info = tarfile.TarInfo(f"{prefix}driver.json")
            info.size = len(blob)
            tar.addfile(info, _io.BytesIO(blob))
        return str(path)

    def test_reads_driver_json_from_the_archive(self, tmp_path):
        from uc_remote_mcp.tools.integrations import _package_driver_json

        got = _package_driver_json(self._package(tmp_path))
        assert got["driver_id"] == "lgwebos_driver"
        assert got["version"] == "1.17.1"

    def test_reads_it_without_the_dot_slash_prefix(self, tmp_path):
        from uc_remote_mcp.tools.integrations import _package_driver_json

        got = _package_driver_json(self._package(tmp_path, prefix=""))
        assert got["driver_id"] == "lgwebos_driver"

    def test_finds_it_when_nested_in_a_folder(self, tmp_path):
        from uc_remote_mcp.tools.integrations import _package_driver_json

        got = _package_driver_json(self._package(tmp_path, prefix="uc-intg-lgtv/"))
        assert got["driver_id"] == "lgwebos_driver"

    def test_an_archive_without_one_is_rejected(self, tmp_path):
        import tarfile

        from uc_remote_mcp.tools.integrations import _package_driver_json

        path = tmp_path / "empty.tar.gz"
        with tarfile.open(path, "w:gz"):
            pass
        with pytest.raises(ValueError, match="No driver.json"):
            _package_driver_json(str(path))
