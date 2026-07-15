import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def activity_detail() -> dict:
    return json.loads((FIXTURES / "activity_detail.json").read_text())


@pytest.fixture
def remote_detail() -> dict:
    """Minimal IR remote-entity, shaped like the real STR-AN1000 IR remote."""
    return {
        "entity_id": "uc.main.99999999-8888-4777-8666-555544443333",
        "entity_type": "remote",
        "name": {"en_US": "STR-AN1000 IR"},
        "options": {
            "kind": "IR",
            "editable": True,
            "simple_commands": ["Main_Power", "Volume_Up", "Volume_Down", "Mute"],
            "button_mapping": [
                {"button": "MUTE", "short_press": {"cmd_id": "Mute"}},
                {"button": "VOLUME_UP", "short_press": {"cmd_id": "Volume_Up"}},
            ],
            "user_interface": {
                "pages": [
                    {
                        "page_id": "main",
                        "name": "Inputs",
                        "grid": {"width": 4, "height": 9},
                        "items": [
                            {
                                "type": "text",
                                "text": "Zone 3 Power",
                                "command": {"cmd_id": "Main_Power"},
                                "location": {"x": 0, "y": 0},
                                "size": {"width": 1, "height": 1},
                            }
                        ],
                    }
                ]
            },
        },
        "attributes": {"state": "UNKNOWN"},
        "enabled": True,
    }
