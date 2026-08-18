"""Configuration and credential loading.

Revolut X credentials are read from the same config directory the
`revx` CLI (revolut-x-api) already writes to, so running `revx auth
setup` once is enough for both tools to share the same registered
API key and Ed25519 keypair. See revolut-x-api/api/src/config/settings.ts.
"""

from __future__ import annotations

import json
import os
import platform
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _default_revolutx_config_dir() -> Path:
    if platform.system() == "Windows":
        return Path(os.environ.get("APPDATA", str(Path.home()))) / "revolut-x"
    return Path.home() / ".config" / "revolut-x"


def _revolutx_config_dir() -> Path:
    raw = os.environ.get("REVOLUTX_CONFIG_DIR")
    if raw:
        return Path(raw.replace("~", str(Path.home()), 1) if raw.startswith("~") else raw).resolve()
    return _default_revolutx_config_dir()


@dataclass(frozen=True)
class RevolutXCredentials:
    api_key: str
    private_key_path: Path


def load_revolutx_credentials() -> RevolutXCredentials | None:
    config_dir = _revolutx_config_dir()
    config_file = config_dir / "config.json"
    if not config_file.exists():
        return None

    try:
        config = json.loads(config_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    api_key = config.get("api_key")
    if not api_key:
        return None

    key_path = Path(config.get("private_key_path") or (config_dir / "private.pem"))
    if not key_path.exists():
        return None

    return RevolutXCredentials(api_key=api_key, private_key_path=key_path)


@dataclass(frozen=True)
class WiseCredentials:
    api_token: str
    sandbox: bool = True

    @property
    def base_url(self) -> str:
        return "https://api.sandbox.transferwise.tech" if self.sandbox else "https://api.wise.com"


def load_wise_credentials() -> WiseCredentials | None:
    token = os.environ.get("WISE_API_TOKEN")
    if not token:
        return None
    sandbox = os.environ.get("WISE_ENV", "sandbox").lower() != "production"
    return WiseCredentials(api_token=token, sandbox=sandbox)


@dataclass(frozen=True)
class DatabaseConfig:
    dsn: str


def load_database_config() -> DatabaseConfig:
    dsn = os.environ.get(
        "FXPULSE_DATABASE_URL",
        "postgresql://fxpulse:fxpulse@localhost:5432/fxpulse",
    )
    return DatabaseConfig(dsn=dsn)
