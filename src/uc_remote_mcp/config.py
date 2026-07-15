"""Config file load/save. Stored at %APPDATA%/uc-remote-mcp/config.json on Windows."""

import json
import os
import stat
from pathlib import Path
from typing import Optional

from pydantic import BaseModel


def _config_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path.home() / ".config"
    return base / "uc-remote-mcp"


def _config_path() -> Path:
    return _config_dir() / "config.json"


class RemoteConfig(BaseModel):
    host: str
    port: int = 80
    api_key: str
    name: str = ""
    model: str = ""


class AppConfig(BaseModel):
    remotes: dict[str, RemoteConfig] = {}  # keyed by host


def load_config() -> AppConfig:
    path = _config_path()
    if not path.exists():
        return AppConfig()
    data = json.loads(path.read_text())
    return AppConfig.model_validate(data)


def save_config(cfg: AppConfig) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cfg.model_dump_json(indent=2))
    if os.name != "nt":
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def get_remote(host: Optional[str] = None) -> Optional[RemoteConfig]:
    cfg = load_config()
    if not cfg.remotes:
        return None
    if host:
        return cfg.remotes.get(host)
    return next(iter(cfg.remotes.values()))


def save_remote(remote: RemoteConfig) -> None:
    cfg = load_config()
    cfg.remotes[remote.host] = remote
    save_config(cfg)
