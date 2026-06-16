from __future__ import annotations

import os
import shutil
import tomllib
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    pass


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")
    with config_path.open("rb") as fh:
        config = tomllib.load(fh)
    _validate_config(config)
    return config


def init_config(target: str | Path, overwrite: bool = False) -> Path:
    target_path = Path(target)
    if target_path.exists() and not overwrite:
        raise ConfigError(f"Refusing to overwrite existing file: {target_path}")
    template = Path(__file__).resolve().parent.parent / "config.example.toml"
    shutil.copyfile(template, target_path)
    return target_path


def env_value(name: str | None, default: str = "") -> str:
    if not name:
        return default
    return os.environ.get(name, default)


def bool_setting(config: dict[str, Any], path: tuple[str, ...], default: bool = False) -> bool:
    value: Any = config
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return default
        value = value[key]
    return bool(value)


def _validate_config(config: dict[str, Any]) -> None:
    profile = config.get("profile")
    if not isinstance(profile, dict):
        raise ConfigError("Missing [profile] section")
    keywords = profile.get("keywords")
    if not isinstance(keywords, list) or not all(isinstance(k, str) and k.strip() for k in keywords):
        raise ConfigError("[profile].keywords must be a non-empty list of strings")

    run = config.get("run", {})
    if not isinstance(run, dict):
        raise ConfigError("[run] must be a table")
    if int(run.get("lookback_days", 7)) < 1:
        raise ConfigError("[run].lookback_days must be at least 1")
