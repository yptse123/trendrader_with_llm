"""Base notifier class and common utilities."""

import asyncio
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx


@dataclass
class NotificationResult:
    """Result of a notification attempt."""
    success: bool
    platform: str
    message: str = ""
    error: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    details: dict[str, Any] = field(default_factory=dict)


class BaseNotifier(ABC):
    """Abstract base class for notification handlers."""

    def __init__(
        self,
        platform_name: str,
        batch_size: int = 4000,
        batch_interval: int = 3,
        timeout: int = 30,
    ):
        """Initialize the notifier.

        Args:
            platform_name: Name of the notification platform
            batch_size: Maximum bytes per message batch
            batch_interval: Seconds between batch sends
            timeout: Request timeout in seconds
        """
        self.platform_name = platform_name
        self.batch_size = batch_size
        self.batch_interval = batch_interval
        self.timeout = timeout

    def _get_http_client(self) -> httpx.AsyncClient:
        """Get configured HTTP client."""
        return httpx.AsyncClient(
            timeout=self.timeout,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "TrendRadar-AI/1.0",
            },
        )

    @abstractmethod
    async def send(self, content: str, title: str | None = None) -> NotificationResult:
        """Send a notification.

        Args:
            content: Message content
            title: Optional message title

        Returns:
            NotificationResult indicating success/failure
        """
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if the notifier is properly configured.

        Returns:
            True if all required configuration is present
        """
        pass

    def _split_content(self, content: str) -> list[str]:
        """Split content into batches respecting the batch size.

        Args:
            content: Full message content

        Returns:
            List of content chunks
        """
        if len(content.encode('utf-8')) <= self.batch_size:
            return [content]

        chunks = []
        current_chunk = ""

        for line in content.split('\n'):
            test_chunk = current_chunk + '\n' + line if current_chunk else line
            if len(test_chunk.encode('utf-8')) > self.batch_size:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = line
            else:
                current_chunk = test_chunk

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    async def send_batched(
        self,
        content: str,
        title: str | None = None,
    ) -> list[NotificationResult]:
        """Send content in batches if necessary.

        Args:
            content: Full message content
            title: Optional message title

        Returns:
            List of NotificationResult for each batch
        """
        chunks = self._split_content(content)
        results = []

        for i, chunk in enumerate(chunks):
            batch_title = f"{title} ({i+1}/{len(chunks)})" if title and len(chunks) > 1 else title
            result = await self.send(chunk, batch_title)
            results.append(result)

            if i < len(chunks) - 1:
                await asyncio.sleep(self.batch_interval)

        return results

    @staticmethod
    def strip_markdown(text: str) -> str:
        """Convert markdown to plain text.

        Args:
            text: Markdown formatted text

        Returns:
            Plain text without markdown formatting
        """
        # Remove bold/italic
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'__(.+?)__', r'\1', text)
        text = re.sub(r'_(.+?)_', r'\1', text)

        # Remove links but keep text
        text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)

        # Remove headers
        text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)

        # Remove code blocks
        text = re.sub(r'```[\s\S]*?```', '', text)
        text = re.sub(r'`(.+?)`', r'\1', text)

        return text

    @staticmethod
    def to_slack_mrkdwn(text: str) -> str:
        """Convert standard markdown to Slack's mrkdwn format.

        Args:
            text: Standard markdown text

        Returns:
            Slack mrkdwn formatted text
        """
        # Bold: **text** -> *text*
        text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)

        # Links: [text](url) -> <url|text>
        text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<\2|\1>', text)

        return text
