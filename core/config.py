from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional

from dotenv import dotenv_values


class ConfigManager:
    _env_map: Optional[Dict[str, str]] = None
    _env_path: str = ".env"

    @classmethod
    def set_env_path(cls, env_path: str) -> None:
        cls._env_path = env_path or ".env"
        cls._env_map = None

    @classmethod
    def _load_env_map(cls) -> Dict[str, str]:
        if cls._env_map is not None:
            return cls._env_map
        try:
            values = dotenv_values(cls._env_path)
            cls._env_map = {str(k): str(v) for k, v in values.items() if k and v is not None}
        except Exception:
            cls._env_map = {}
        return cls._env_map

    @classmethod
    def env_map(cls, env_path: Optional[str] = None) -> Dict[str, str]:
        if env_path and env_path != cls._env_path:
            try:
                values = dotenv_values(env_path)
                return {str(k): str(v) for k, v in values.items() if k and v is not None}
            except Exception:
                return {}
        return cls._load_env_map().copy()

    @classmethod
    def get(cls, *keys: str, default: str = "", env_map: Optional[Dict[str, str]] = None) -> str:
        source = env_map if env_map is not None else cls._load_env_map()
        for key in keys:
            value = os.getenv(key)
            if value:
                return value
            value = source.get(key)
            if value:
                return value
        return default

    @classmethod
    def get_bool(cls, *keys: str, default: bool = False, env_map: Optional[Dict[str, str]] = None) -> bool:
        value = cls.get(*keys, default="", env_map=env_map)
        if not value:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @classmethod
    def get_int(cls, *keys: str, default: int = 0, env_map: Optional[Dict[str, str]] = None) -> int:
        value = cls.get(*keys, default="", env_map=env_map)
        if not value:
            return default
        try:
            return int(value)
        except Exception:
            return default

    @classmethod
    def get_float(cls, *keys: str, default: float = 0.0, env_map: Optional[Dict[str, str]] = None) -> float:
        value = cls.get(*keys, default="", env_map=env_map)
        if not value:
            return default
        try:
            return float(value)
        except Exception:
            return default

    @classmethod
    def project_root(cls) -> Path:
        return Path(__file__).resolve().parents[1]


@dataclass
class JarvisConfig:
    streaming_mode: bool
    vad_sensitivity: float
    interrupt_enabled: bool
    max_silence_seconds: float
    stream_buffer_size: int
    early_response: bool
    context_window: int


@dataclass
class ConfigValidationResult:
    config: JarvisConfig
    warnings: List[str]


def load_config() -> JarvisConfig:
    return JarvisConfig(
        streaming_mode=ConfigManager.get_bool("JARVIS_STREAMING_MODE", default=True),
        vad_sensitivity=float(ConfigManager.get("JARVIS_VAD_SENSITIVITY", default="0.7")),
        interrupt_enabled=ConfigManager.get_bool("JARVIS_INTERRUPT_ENABLED", default=True),
        max_silence_seconds=float(ConfigManager.get("JARVIS_MAX_SILENCE_SECONDS", default="1.2")),
        stream_buffer_size=int(ConfigManager.get("JARVIS_STREAM_BUFFER_SIZE", default="1024")),
        early_response=ConfigManager.get_bool("JARVIS_EARLY_RESPONSE", default=True),
        context_window=int(ConfigManager.get("JARVIS_CONTEXT_WINDOW", default="10")),
    )


def validate_config(config: JarvisConfig) -> ConfigValidationResult:
    warnings: List[str] = []

    if not 0.0 <= config.vad_sensitivity <= 1.0:
        warnings.append("JARVIS_VAD_SENSITIVITY should be between 0.0 and 1.0")

    if config.max_silence_seconds < 0.2 or config.max_silence_seconds > 5.0:
        warnings.append("JARVIS_MAX_SILENCE_SECONDS should be between 0.2 and 5.0")

    if config.stream_buffer_size < 64 or config.stream_buffer_size > 8192:
        warnings.append("JARVIS_STREAM_BUFFER_SIZE should be between 64 and 8192")

    if config.context_window < 2 or config.context_window > 50:
        warnings.append("JARVIS_CONTEXT_WINDOW should be between 2 and 50")

    return ConfigValidationResult(config=config, warnings=warnings)


def render_validation_warnings(result: ConfigValidationResult) -> str:
    if not result.warnings:
        return ""
    return "\n".join(["️ Config warnings:"] + [f"- {item}" for item in result.warnings])
