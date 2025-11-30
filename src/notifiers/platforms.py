"""Platform-specific notifier implementations."""

import json
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import urlparse

import httpx

from .base import BaseNotifier, NotificationResult
from ..utils.config import Webhooks


class WeWorkNotifier(BaseNotifier):
    """WeChat Work (WeCom) notification handler."""

    def __init__(self, webhook_url: str, msg_type: str = "markdown", **kwargs):
        """Initialize WeWork notifier.

        Args:
            webhook_url: WeWork webhook URL
            msg_type: Message type - "markdown" for group bot, "text" for personal WeChat
            **kwargs: Additional BaseNotifier arguments
        """
        super().__init__(platform_name="WeWork", **kwargs)
        self.webhook_url = webhook_url
        self.msg_type = msg_type

    def is_configured(self) -> bool:
        return bool(self.webhook_url)

    async def send(self, content: str, title: str | None = None) -> NotificationResult:
        if not self.is_configured():
            return NotificationResult(
                success=False,
                platform=self.platform_name,
                error="WeWork webhook URL not configured",
            )

        try:
            # Prepare message content
            if self.msg_type == "text":
                # Plain text for personal WeChat
                text_content = self.strip_markdown(content)
                if title:
                    text_content = f"{title}\n\n{text_content}"
                payload = {
                    "msgtype": "text",
                    "text": {"content": text_content},
                }
            else:
                # Markdown for group bot
                md_content = content
                if title:
                    md_content = f"## {title}\n\n{content}"
                payload = {
                    "msgtype": "markdown",
                    "markdown": {"content": md_content},
                }

            async with self._get_http_client() as client:
                response = await client.post(self.webhook_url, json=payload)
                response.raise_for_status()
                data = response.json()

                if data.get("errcode") == 0:
                    return NotificationResult(
                        success=True,
                        platform=self.platform_name,
                        message="Message sent successfully",
                    )
                else:
                    return NotificationResult(
                        success=False,
                        platform=self.platform_name,
                        error=f"WeWork API error: {data.get('errmsg', 'Unknown error')}",
                    )

        except Exception as e:
            return NotificationResult(
                success=False,
                platform=self.platform_name,
                error=str(e),
            )


class FeishuNotifier(BaseNotifier):
    """Feishu (Lark) notification handler."""

    def __init__(self, webhook_url: str, **kwargs):
        super().__init__(platform_name="Feishu", batch_size=30000, **kwargs)
        self.webhook_url = webhook_url

    def is_configured(self) -> bool:
        return bool(self.webhook_url)

    async def send(self, content: str, title: str | None = None) -> NotificationResult:
        if not self.is_configured():
            return NotificationResult(
                success=False,
                platform=self.platform_name,
                error="Feishu webhook URL not configured",
            )

        try:
            # Feishu uses interactive card for rich formatting
            card_content = {
                "config": {"wide_screen_mode": True},
                "elements": [
                    {
                        "tag": "markdown",
                        "content": content,
                    }
                ],
            }

            if title:
                card_content["header"] = {
                    "template": "blue",
                    "title": {"tag": "plain_text", "content": title},
                }

            payload = {
                "msg_type": "interactive",
                "card": card_content,
            }

            async with self._get_http_client() as client:
                response = await client.post(self.webhook_url, json=payload)
                response.raise_for_status()
                data = response.json()

                if data.get("code") == 0 or data.get("StatusCode") == 0:
                    return NotificationResult(
                        success=True,
                        platform=self.platform_name,
                        message="Message sent successfully",
                    )
                else:
                    return NotificationResult(
                        success=False,
                        platform=self.platform_name,
                        error=f"Feishu API error: {data.get('msg', 'Unknown error')}",
                    )

        except Exception as e:
            return NotificationResult(
                success=False,
                platform=self.platform_name,
                error=str(e),
            )


class DingTalkNotifier(BaseNotifier):
    """DingTalk notification handler."""

    def __init__(self, webhook_url: str, **kwargs):
        super().__init__(platform_name="DingTalk", batch_size=20000, **kwargs)
        self.webhook_url = webhook_url

    def is_configured(self) -> bool:
        return bool(self.webhook_url)

    async def send(self, content: str, title: str | None = None) -> NotificationResult:
        if not self.is_configured():
            return NotificationResult(
                success=False,
                platform=self.platform_name,
                error="DingTalk webhook URL not configured",
            )

        try:
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "title": title or "TrendRadar News",
                    "text": content,
                },
            }

            async with self._get_http_client() as client:
                response = await client.post(self.webhook_url, json=payload)
                response.raise_for_status()
                data = response.json()

                if data.get("errcode") == 0:
                    return NotificationResult(
                        success=True,
                        platform=self.platform_name,
                        message="Message sent successfully",
                    )
                else:
                    return NotificationResult(
                        success=False,
                        platform=self.platform_name,
                        error=f"DingTalk API error: {data.get('errmsg', 'Unknown error')}",
                    )

        except Exception as e:
            return NotificationResult(
                success=False,
                platform=self.platform_name,
                error=str(e),
            )


class TelegramNotifier(BaseNotifier):
    """Telegram notification handler."""

    API_BASE = "https://api.telegram.org"

    def __init__(self, bot_token: str, chat_id: str, **kwargs):
        super().__init__(platform_name="Telegram", **kwargs)
        self.bot_token = bot_token
        self.chat_id = chat_id

    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    async def send(self, content: str, title: str | None = None) -> NotificationResult:
        if not self.is_configured():
            return NotificationResult(
                success=False,
                platform=self.platform_name,
                error="Telegram bot token or chat ID not configured",
            )

        try:
            text = content
            if title:
                text = f"*{title}*\n\n{content}"

            url = f"{self.API_BASE}/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            }

            async with self._get_http_client() as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

                if data.get("ok"):
                    return NotificationResult(
                        success=True,
                        platform=self.platform_name,
                        message="Message sent successfully",
                    )
                else:
                    return NotificationResult(
                        success=False,
                        platform=self.platform_name,
                        error=f"Telegram API error: {data.get('description', 'Unknown error')}",
                    )

        except Exception as e:
            return NotificationResult(
                success=False,
                platform=self.platform_name,
                error=str(e),
            )


class SlackNotifier(BaseNotifier):
    """Slack notification handler."""

    def __init__(self, webhook_url: str, **kwargs):
        super().__init__(platform_name="Slack", **kwargs)
        self.webhook_url = webhook_url

    def is_configured(self) -> bool:
        return bool(self.webhook_url)

    async def send(self, content: str, title: str | None = None) -> NotificationResult:
        if not self.is_configured():
            return NotificationResult(
                success=False,
                platform=self.platform_name,
                error="Slack webhook URL not configured",
            )

        try:
            # Convert to Slack mrkdwn format
            mrkdwn_content = self.to_slack_mrkdwn(content)
            if title:
                mrkdwn_content = f"*{title}*\n\n{mrkdwn_content}"

            payload = {
                "text": mrkdwn_content,
                "mrkdwn": True,
            }

            async with self._get_http_client() as client:
                response = await client.post(self.webhook_url, json=payload)

                if response.status_code == 200 and response.text == "ok":
                    return NotificationResult(
                        success=True,
                        platform=self.platform_name,
                        message="Message sent successfully",
                    )
                else:
                    return NotificationResult(
                        success=False,
                        platform=self.platform_name,
                        error=f"Slack API error: {response.text}",
                    )

        except Exception as e:
            return NotificationResult(
                success=False,
                platform=self.platform_name,
                error=str(e),
            )


class NtfyNotifier(BaseNotifier):
    """ntfy.sh notification handler."""

    def __init__(self, server_url: str, topic: str, token: str = "", **kwargs):
        super().__init__(platform_name="ntfy", **kwargs)
        self.server_url = server_url.rstrip("/")
        self.topic = topic
        self.token = token

    def is_configured(self) -> bool:
        return bool(self.topic)

    async def send(self, content: str, title: str | None = None) -> NotificationResult:
        if not self.is_configured():
            return NotificationResult(
                success=False,
                platform=self.platform_name,
                error="ntfy topic not configured",
            )

        try:
            url = f"{self.server_url}/{self.topic}"
            headers = {
                "Content-Type": "text/plain; charset=utf-8",
            }

            if title:
                headers["Title"] = title.encode("utf-8").decode("utf-8")

            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"

            # Convert to plain text
            plain_content = self.strip_markdown(content)

            async with self._get_http_client() as client:
                response = await client.post(
                    url,
                    content=plain_content.encode("utf-8"),
                    headers=headers,
                )
                response.raise_for_status()

                return NotificationResult(
                    success=True,
                    platform=self.platform_name,
                    message="Message sent successfully",
                )

        except Exception as e:
            return NotificationResult(
                success=False,
                platform=self.platform_name,
                error=str(e),
            )


class BarkNotifier(BaseNotifier):
    """Bark (iOS) notification handler."""

    def __init__(self, bark_url: str, **kwargs):
        super().__init__(platform_name="Bark", **kwargs)
        self.bark_url = bark_url.rstrip("/")

    def is_configured(self) -> bool:
        return bool(self.bark_url)

    async def send(self, content: str, title: str | None = None) -> NotificationResult:
        if not self.is_configured():
            return NotificationResult(
                success=False,
                platform=self.platform_name,
                error="Bark URL not configured",
            )

        try:
            # Bark supports markdown natively now
            payload = {
                "title": title or "TrendRadar",
                "body": content,
                "group": "TrendRadar",
            }

            async with self._get_http_client() as client:
                response = await client.post(self.bark_url, json=payload)
                response.raise_for_status()
                data = response.json()

                if data.get("code") == 200:
                    return NotificationResult(
                        success=True,
                        platform=self.platform_name,
                        message="Message sent successfully",
                    )
                else:
                    return NotificationResult(
                        success=False,
                        platform=self.platform_name,
                        error=f"Bark API error: {data.get('message', 'Unknown error')}",
                    )

        except Exception as e:
            return NotificationResult(
                success=False,
                platform=self.platform_name,
                error=str(e),
            )


class EmailNotifier(BaseNotifier):
    """Email notification handler."""

    # Common SMTP servers
    SMTP_SERVERS = {
        "gmail.com": ("smtp.gmail.com", 587),
        "qq.com": ("smtp.qq.com", 465),
        "163.com": ("smtp.163.com", 465),
        "126.com": ("smtp.126.com", 465),
        "outlook.com": ("smtp.office365.com", 587),
        "hotmail.com": ("smtp.office365.com", 587),
    }

    def __init__(
        self,
        email_from: str,
        email_password: str,
        email_to: str,
        smtp_server: str = "",
        smtp_port: str = "",
        **kwargs,
    ):
        super().__init__(platform_name="Email", **kwargs)
        self.email_from = email_from
        self.email_password = email_password
        self.email_to = email_to
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port

    def is_configured(self) -> bool:
        return bool(self.email_from and self.email_password and self.email_to)

    def _get_smtp_config(self) -> tuple[str, int]:
        """Get SMTP server and port based on email domain."""
        if self.smtp_server and self.smtp_port:
            return self.smtp_server, int(self.smtp_port)

        # Extract domain from email
        domain = self.email_from.split("@")[-1].lower()

        if domain in self.SMTP_SERVERS:
            return self.SMTP_SERVERS[domain]

        # Default to TLS on port 587
        return f"smtp.{domain}", 587

    async def send(self, content: str, title: str | None = None) -> NotificationResult:
        if not self.is_configured():
            return NotificationResult(
                success=False,
                platform=self.platform_name,
                error="Email configuration incomplete",
            )

        try:
            server, port = self._get_smtp_config()
            recipients = [r.strip() for r in self.email_to.split(",")]

            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = title or "TrendRadar News Report"
            msg["From"] = self.email_from
            msg["To"] = ", ".join(recipients)

            # Plain text version
            text_content = self.strip_markdown(content)
            msg.attach(MIMEText(text_content, "plain", "utf-8"))

            # HTML version (convert markdown to basic HTML)
            html_content = self._markdown_to_html(content)
            msg.attach(MIMEText(html_content, "html", "utf-8"))

            # Send email
            context = ssl.create_default_context()

            if port == 465:
                # SSL connection
                with smtplib.SMTP_SSL(server, port, context=context) as smtp:
                    smtp.login(self.email_from, self.email_password)
                    smtp.sendmail(self.email_from, recipients, msg.as_string())
            else:
                # TLS connection
                with smtplib.SMTP(server, port) as smtp:
                    smtp.starttls(context=context)
                    smtp.login(self.email_from, self.email_password)
                    smtp.sendmail(self.email_from, recipients, msg.as_string())

            return NotificationResult(
                success=True,
                platform=self.platform_name,
                message=f"Email sent to {len(recipients)} recipient(s)",
            )

        except Exception as e:
            return NotificationResult(
                success=False,
                platform=self.platform_name,
                error=str(e),
            )

    def _markdown_to_html(self, text: str) -> str:
        """Convert markdown to basic HTML."""
        import re
        import html

        # Escape HTML
        text = html.escape(text)

        # Convert headers
        text = re.sub(r'^### (.+)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
        text = re.sub(r'^## (.+)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
        text = re.sub(r'^# (.+)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)

        # Convert bold and italic
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)

        # Convert links
        text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', text)

        # Convert line breaks
        text = text.replace('\n', '<br>\n')

        return f"""
        <html>
        <head><meta charset="utf-8"></head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px;">
        {text}
        </body>
        </html>
        """
