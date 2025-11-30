"""Notification manager for orchestrating multiple notifiers."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, time
from pathlib import Path
from typing import Any
import json

from .base import BaseNotifier, NotificationResult
from .platforms import (
    WeWorkNotifier,
    FeishuNotifier,
    DingTalkNotifier,
    TelegramNotifier,
    SlackNotifier,
    NtfyNotifier,
    BarkNotifier,
    EmailNotifier,
)
from ..utils.config import Config


@dataclass
class NotificationSummary:
    """Summary of notification results."""
    total_sent: int = 0
    total_failed: int = 0
    results: list[NotificationResult] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "total_sent": self.total_sent,
            "total_failed": self.total_failed,
            "results": [
                {
                    "platform": r.platform,
                    "success": r.success,
                    "message": r.message,
                    "error": r.error,
                }
                for r in self.results
            ],
            "timestamp": self.timestamp.isoformat(),
        }


class NotificationManager:
    """Manages notification delivery across multiple platforms."""

    def __init__(self, config: Config):
        """Initialize the notification manager.

        Args:
            config: Application configuration
        """
        self.config = config
        self.notifiers: list[BaseNotifier] = []
        self._push_record_file = Path(config.output.output_dir) / ".push_records.json"
        self._setup_notifiers()

    def _setup_notifiers(self) -> None:
        """Set up notifiers based on configuration."""
        webhooks = self.config.notification.webhooks
        batch_interval = self.config.notification.batch_send_interval

        # WeWork
        if webhooks.wework_url:
            self.notifiers.append(
                WeWorkNotifier(
                    webhook_url=webhooks.wework_url,
                    msg_type=webhooks.wework_msg_type,
                    batch_interval=batch_interval,
                )
            )

        # Feishu
        if webhooks.feishu_url:
            self.notifiers.append(
                FeishuNotifier(
                    webhook_url=webhooks.feishu_url,
                    batch_interval=batch_interval,
                )
            )

        # DingTalk
        if webhooks.dingtalk_url:
            self.notifiers.append(
                DingTalkNotifier(
                    webhook_url=webhooks.dingtalk_url,
                    batch_interval=batch_interval,
                )
            )

        # Telegram
        if webhooks.telegram_bot_token and webhooks.telegram_chat_id:
            self.notifiers.append(
                TelegramNotifier(
                    bot_token=webhooks.telegram_bot_token,
                    chat_id=webhooks.telegram_chat_id,
                    batch_interval=batch_interval,
                )
            )

        # Slack
        if webhooks.slack_webhook_url:
            self.notifiers.append(
                SlackNotifier(
                    webhook_url=webhooks.slack_webhook_url,
                    batch_interval=batch_interval,
                )
            )

        # ntfy
        if webhooks.ntfy_topic:
            self.notifiers.append(
                NtfyNotifier(
                    server_url=webhooks.ntfy_server_url,
                    topic=webhooks.ntfy_topic,
                    token=webhooks.ntfy_token,
                    batch_interval=batch_interval,
                )
            )

        # Bark
        if webhooks.bark_url:
            self.notifiers.append(
                BarkNotifier(
                    bark_url=webhooks.bark_url,
                    batch_interval=batch_interval,
                )
            )

        # Email
        if webhooks.email_from and webhooks.email_password and webhooks.email_to:
            self.notifiers.append(
                EmailNotifier(
                    email_from=webhooks.email_from,
                    email_password=webhooks.email_password,
                    email_to=webhooks.email_to,
                    smtp_server=webhooks.email_smtp_server,
                    smtp_port=webhooks.email_smtp_port,
                    batch_interval=batch_interval,
                )
            )

    def has_configured_notifiers(self) -> bool:
        """Check if any notifiers are configured.

        Returns:
            True if at least one notifier is configured
        """
        return any(n.is_configured() for n in self.notifiers)

    def is_within_push_window(self) -> bool:
        """Check if current time is within the push window.

        Returns:
            True if push is allowed based on time window settings
        """
        push_window = self.config.notification.push_window

        if not push_window.enabled:
            return True

        now = datetime.now()
        current_time = now.time()

        try:
            start_parts = push_window.time_range.start.split(":")
            end_parts = push_window.time_range.end.split(":")

            start_time = time(int(start_parts[0]), int(start_parts[1]))
            end_time = time(int(end_parts[0]), int(end_parts[1]))

            return start_time <= current_time <= end_time

        except (ValueError, IndexError):
            # Invalid time format - allow push
            return True

    def has_pushed_today(self) -> bool:
        """Check if we've already pushed today (for once_per_day mode).

        Returns:
            True if already pushed today
        """
        push_window = self.config.notification.push_window

        if not push_window.once_per_day:
            return False

        records = self._load_push_records()
        today = datetime.now().strftime("%Y-%m-%d")

        return today in records.get("pushed_dates", [])

    def _load_push_records(self) -> dict[str, Any]:
        """Load push records from file."""
        if not self._push_record_file.exists():
            return {"pushed_dates": []}

        try:
            with open(self._push_record_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"pushed_dates": []}

    def _save_push_record(self) -> None:
        """Save push record for today."""
        records = self._load_push_records()
        today = datetime.now().strftime("%Y-%m-%d")

        if today not in records.get("pushed_dates", []):
            if "pushed_dates" not in records:
                records["pushed_dates"] = []
            records["pushed_dates"].append(today)

        # Clean up old records
        retention_days = self.config.notification.push_window.push_record_retention_days
        cutoff = datetime.now().strftime("%Y-%m-%d")

        # Keep only recent dates
        if len(records["pushed_dates"]) > retention_days:
            records["pushed_dates"] = records["pushed_dates"][-retention_days:]

        # Ensure output directory exists
        self._push_record_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self._push_record_file, "w") as f:
            json.dump(records, f)

    def should_push(self) -> tuple[bool, str]:
        """Determine if push should proceed based on settings.

        Returns:
            Tuple of (should_push, reason)
        """
        if not self.config.notification.enable_notification:
            return False, "Notifications disabled in config"

        if not self.has_configured_notifiers():
            return False, "No notifiers configured"

        if not self.is_within_push_window():
            return False, "Outside push time window"

        if self.has_pushed_today():
            return False, "Already pushed today (once_per_day mode)"

        return True, "OK"

    async def send_all(
        self,
        content: str,
        title: str | None = None,
        force: bool = False,
    ) -> NotificationSummary:
        """Send notification to all configured platforms.

        Args:
            content: Message content
            title: Optional message title
            force: If True, bypass push window checks

        Returns:
            NotificationSummary with results
        """
        summary = NotificationSummary()

        if not force:
            should_push, reason = self.should_push()
            if not should_push:
                summary.results.append(
                    NotificationResult(
                        success=False,
                        platform="Manager",
                        error=reason,
                    )
                )
                return summary

        # Send to all notifiers concurrently
        tasks = []
        for notifier in self.notifiers:
            if notifier.is_configured():
                task = notifier.send_batched(content, title)
                tasks.append((notifier.platform_name, task))

        if not tasks:
            summary.results.append(
                NotificationResult(
                    success=False,
                    platform="Manager",
                    error="No configured notifiers available",
                )
            )
            return summary

        # Execute all sends
        for platform_name, task in tasks:
            try:
                results = await task
                for result in results:
                    summary.results.append(result)
                    if result.success:
                        summary.total_sent += 1
                    else:
                        summary.total_failed += 1
            except Exception as e:
                summary.results.append(
                    NotificationResult(
                        success=False,
                        platform=platform_name,
                        error=str(e),
                    )
                )
                summary.total_failed += 1

        # Record successful push
        if summary.total_sent > 0:
            self._save_push_record()

        return summary

    def get_configured_platforms(self) -> list[str]:
        """Get list of configured notification platforms.

        Returns:
            List of platform names
        """
        return [n.platform_name for n in self.notifiers if n.is_configured()]
