"""Configuration management for TrendRadar AI."""

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class CrawlerConfig(BaseModel):
    """Crawler configuration settings."""
    request_interval: int = 1000
    enable_crawler: bool = True
    use_proxy: bool = False
    default_proxy: str = "http://127.0.0.1:10086"
    timeout: int = 30
    max_retries: int = 3


class TimeRange(BaseModel):
    """Time range for push window."""
    start: str = "09:00"
    end: str = "18:00"


class PushWindow(BaseModel):
    """Push window configuration."""
    enabled: bool = False
    time_range: TimeRange = Field(default_factory=TimeRange)
    once_per_day: bool = True
    push_record_retention_days: int = 7


class Webhooks(BaseModel):
    """Webhook configuration for notifications."""
    wework_url: str = ""
    wework_msg_type: str = "markdown"
    feishu_url: str = ""
    dingtalk_url: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    email_from: str = ""
    email_password: str = ""
    email_to: str = ""
    email_smtp_server: str = ""
    email_smtp_port: str = ""
    ntfy_server_url: str = "https://ntfy.sh"
    ntfy_topic: str = ""
    ntfy_token: str = ""
    bark_url: str = ""
    slack_webhook_url: str = ""


class NotificationConfig(BaseModel):
    """Notification configuration settings."""
    enable_notification: bool = True
    message_batch_size: int = 4000
    batch_send_interval: int = 3
    push_window: PushWindow = Field(default_factory=PushWindow)
    webhooks: Webhooks = Field(default_factory=Webhooks)


class ReportConfig(BaseModel):
    """Report configuration settings."""
    mode: str = "daily"  # daily, current, incremental
    rank_threshold: int = 5
    sort_by_position_first: bool = False
    max_news_per_keyword: int = 0


class WeightConfig(BaseModel):
    """Weight configuration for hotspot ranking."""
    rank_weight: float = 0.6
    frequency_weight: float = 0.3
    hotness_weight: float = 0.1


class Platform(BaseModel):
    """Platform configuration."""
    id: str
    name: str
    enabled: bool = True


class LLMConfig(BaseModel):
    """LLM configuration for CrewAI."""
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    temperature: float = 0.7
    max_tokens: int = 4096
    base_url: str = ""  # Custom API base URL


class EmbedderConfig(BaseModel):
    """Embedder configuration for CrewAI memory."""
    provider: str = "openai"
    model: str = "text-embedding-3-small"


class CrewAIConfig(BaseModel):
    """CrewAI configuration settings."""
    llm: LLMConfig = Field(default_factory=LLMConfig)
    embedder: EmbedderConfig = Field(default_factory=EmbedderConfig)
    memory: bool = True
    verbose: bool = True


class OutputConfig(BaseModel):
    """Output configuration settings."""
    save_html: bool = True
    save_txt: bool = True
    save_json: bool = True
    output_dir: str = "output"
    date_format: str = "%Y-%m-%d"
    time_format: str = "%H:%M"


class AppConfig(BaseModel):
    """Application configuration."""
    name: str = "TrendRadar AI"
    version: str = "1.0.0"
    show_version_update: bool = True


class Config(BaseModel):
    """Main configuration class."""
    app: AppConfig = Field(default_factory=AppConfig)
    crawler: CrawlerConfig = Field(default_factory=CrawlerConfig)
    report: ReportConfig = Field(default_factory=ReportConfig)
    notification: NotificationConfig = Field(default_factory=NotificationConfig)
    weight: WeightConfig = Field(default_factory=WeightConfig)
    platforms: list[Platform] = Field(default_factory=list)
    crewai: CrewAIConfig = Field(default_factory=CrewAIConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)


def load_config(config_path: str | Path | None = None) -> Config:
    """Load configuration from YAML file with environment variable overrides.

    Args:
        config_path: Path to config file. Defaults to config/config.yaml

    Returns:
        Config object with loaded settings
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"

    config_path = Path(config_path)

    if not config_path.exists():
        return Config()

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    # Apply environment variable overrides
    data = _apply_env_overrides(data)

    return Config(**data)


def _apply_env_overrides(data: dict[str, Any]) -> dict[str, Any]:
    """Apply environment variable overrides to configuration.

    Environment variables follow the pattern: TRENDRADAR_SECTION_KEY
    Example: TRENDRADAR_CRAWLER_ENABLE_CRAWLER=false
    """
    env_mappings = {
        # Crawler settings
        "ENABLE_CRAWLER": ("crawler", "enable_crawler", bool),
        "REQUEST_INTERVAL": ("crawler", "request_interval", int),

        # Report settings
        "REPORT_MODE": ("report", "mode", str),

        # Notification settings
        "ENABLE_NOTIFICATION": ("notification", "enable_notification", bool),
        "PUSH_WINDOW_ENABLED": ("notification", "push_window", "enabled", bool),
        "PUSH_WINDOW_START": ("notification", "push_window", "time_range", "start", str),
        "PUSH_WINDOW_END": ("notification", "push_window", "time_range", "end", str),

        # Webhook URLs
        "WEWORK_WEBHOOK_URL": ("notification", "webhooks", "wework_url", str),
        "WEWORK_MSG_TYPE": ("notification", "webhooks", "wework_msg_type", str),
        "FEISHU_WEBHOOK_URL": ("notification", "webhooks", "feishu_url", str),
        "DINGTALK_WEBHOOK_URL": ("notification", "webhooks", "dingtalk_url", str),
        "TELEGRAM_BOT_TOKEN": ("notification", "webhooks", "telegram_bot_token", str),
        "TELEGRAM_CHAT_ID": ("notification", "webhooks", "telegram_chat_id", str),
        "EMAIL_FROM": ("notification", "webhooks", "email_from", str),
        "EMAIL_PASSWORD": ("notification", "webhooks", "email_password", str),
        "EMAIL_TO": ("notification", "webhooks", "email_to", str),
        "NTFY_TOPIC": ("notification", "webhooks", "ntfy_topic", str),
        "BARK_URL": ("notification", "webhooks", "bark_url", str),
        "SLACK_WEBHOOK_URL": ("notification", "webhooks", "slack_webhook_url", str),

        # CrewAI settings
        "OPENAI_API_KEY": None,  # Handled by OpenAI SDK
        "ANTHROPIC_API_KEY": None,  # Handled by Anthropic SDK
    }

    for env_key, path in env_mappings.items():
        env_value = os.environ.get(env_key)
        if env_value is not None and path is not None:
            _set_nested_value(data, path, env_value)

    return data


def _set_nested_value(data: dict, path: tuple, value: str) -> None:
    """Set a nested dictionary value from a path tuple."""
    if len(path) < 2:
        return

    *keys, type_converter = path

    # Navigate to the correct nested location
    current = data
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]

    # Convert and set the value
    final_key = keys[-1]
    if type_converter == bool:
        current[final_key] = value.lower() in ("true", "1", "yes")
    elif type_converter == int:
        current[final_key] = int(value)
    elif type_converter == float:
        current[final_key] = float(value)
    else:
        current[final_key] = value
