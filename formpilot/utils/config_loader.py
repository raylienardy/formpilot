"""Configuration loading for FormPilot.

Loads YAML config + environment variables, validates via Pydantic.
All fields are required — no defaults in code (see docs/architecture.md).
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError


class OllamaConfig(BaseModel):
    """Ollama LLM server configuration."""

    base_url: str = Field(..., description="Ollama server URL")
    model: str = Field(..., description="Main LLM model name")
    embedding_model: str = Field(..., description="Embedding model name")
    temperature: float = Field(..., ge=0.0, le=2.0, description="LLM temperature")
    timeout_seconds: int = Field(..., gt=0, description="Request timeout in seconds")


class BrowserConfig(BaseModel):
    """Playwright browser configuration."""

    headless: bool = Field(..., description="Run browser headless")
    user_data_dir: str = Field(..., description="Persistent browser state directory")
    timeout_ms: int = Field(..., gt=0, description="Page load timeout in milliseconds")
    preferred: str | None = Field(
        default=None,
        description=(
            "Preferred browser name (edge, chrome, brave, chromium, vivaldi). "
            "None = auto-detect + menu."
        ),
    )
    profile_strategy: str = Field(
        default="ask",
        description="Profile strategy: 'existing' | 'isolated' | 'ask'",
    )


class MemoryConfig(BaseModel):
    """Memory storage configuration."""

    sqlite_path: str = Field(..., description="SQLite database file path")
    chroma_path: str = Field(..., description="ChromaDB directory path")


class CliConfig(BaseModel):
    """CLI behavior configuration."""

    auto_submit: bool = Field(..., description="Auto-submit forms without review")
    batch_questions: bool = Field(..., description="Show all questions per page at once")
    language: str = Field(..., description="CLI interface language (ISO 639-1)")


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = Field(..., description="Log level (DEBUG, INFO, WARNING, ERROR)")
    file: str = Field(..., description="Log file path")


class AppConfig(BaseModel):
    """Top-level application configuration."""

    ollama: OllamaConfig
    browser: BrowserConfig
    memory: MemoryConfig
    cli: CliConfig
    logging: LoggingConfig


class ConfigError(Exception):
    """Raised when configuration is invalid or missing."""


def load_config(config_path: str | Path = "./config/production.yaml") -> AppConfig:
    """Load and validate configuration from YAML file.

    Environment variables are loaded from .env in the current directory
    if present. They do not override YAML values (YAML takes precedence).

    Args:
        config_path: Path to YAML config file.

    Returns:
        Validated AppConfig instance.

    Raises:
        ConfigError: If file not found, YAML invalid, or schema mismatch.
    """
    path = Path(config_path)
    if not path.exists():
        raise ConfigError(
            f"Config file not found: {path}\nCopy config/example.yaml to {path} and edit it."
        )

    try:
        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in {path}: {e}") from e

    if not isinstance(raw, dict):
        raise ConfigError(f"Config file must contain a YAML mapping, got {type(raw).__name__}")

    try:
        config = AppConfig(**raw)
    except ValidationError as e:
        raise ConfigError(f"Config validation failed:\n{e}") from e

    return config


def load_dotenv(dotenv_path: str | Path = ".env") -> dict[str, str]:
    """Load simple KEY=VALUE pairs from .env file.

    Does NOT override existing environment variables.
    Supports comments (#) and blank lines.

    Args:
        dotenv_path: Path to .env file.

    Returns:
        Dictionary of loaded key-value pairs. Empty if file not found.
    """
    path = Path(dotenv_path)
    if not path.exists():
        return {}

    loaded: dict[str, str] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
                loaded[key] = value
    return loaded
