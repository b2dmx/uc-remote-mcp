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
