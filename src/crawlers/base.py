"""Base crawler class and data models for news aggregation."""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential


@dataclass
class NewsItem:
    """Represents a single news item from a platform."""
    title: str
    url: str
    platform_id: str
    platform_name: str
    rank: int
    hotness: int | float = 0
    timestamp: datetime = field(default_factory=datetime.now)
    extra: dict[str, Any] = field(default_factory=dict)
    matched_keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "url": self.url,
            "platform_id": self.platform_id,
            "platform_name": self.platform_name,
            "rank": self.rank,
            "hotness": self.hotness,
            "timestamp": self.timestamp.isoformat(),
            "extra": self.extra,
            "matched_keywords": self.matched_keywords,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NewsItem":
        """Create from dictionary."""
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now()

        return cls(
            title=data.get("title", ""),
            url=data.get("url", ""),
            platform_id=data.get("platform_id", ""),
            platform_name=data.get("platform_name", ""),
            rank=data.get("rank", 0),
            hotness=data.get("hotness", 0),
            timestamp=timestamp,
            extra=data.get("extra", {}),
            matched_keywords=data.get("matched_keywords", []),
        )


class BaseCrawler(ABC):
    """Abstract base class for platform crawlers."""

    def __init__(
        self,
        platform_id: str,
        platform_name: str,
        request_interval: int = 1000,
        timeout: int = 30,
        max_retries: int = 3,
        proxy: str | None = None,
    ):
        """Initialize the crawler.

        Args:
            platform_id: Unique identifier for the platform
            platform_name: Display name for the platform
            request_interval: Milliseconds between requests
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            proxy: Optional proxy URL
        """
        self.platform_id = platform_id
        self.platform_name = platform_name
        self.request_interval = request_interval / 1000  # Convert to seconds
        self.timeout = timeout
        self.max_retries = max_retries
        self.proxy = proxy
        self._last_request_time: float = 0

    async def _wait_for_rate_limit(self) -> None:
        """Wait to respect rate limiting."""
        import time
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.request_interval:
            await asyncio.sleep(self.request_interval - elapsed)
        self._last_request_time = time.time()

    def _get_http_client(self) -> httpx.AsyncClient:
        """Get configured HTTP client."""
        kwargs = {
            "timeout": self.timeout,
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            },
            "follow_redirects": True,
        }
        # Add proxy if configured (use 'proxy' for newer httpx versions)
        if self.proxy:
            kwargs["proxy"] = self.proxy
        return httpx.AsyncClient(**kwargs)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def _fetch(self, url: str, **kwargs) -> httpx.Response:
        """Fetch URL with retry logic.

        Args:
            url: URL to fetch
            **kwargs: Additional arguments for httpx

        Returns:
            HTTP response
        """
        await self._wait_for_rate_limit()
        async with self._get_http_client() as client:
            response = await client.get(url, **kwargs)
            response.raise_for_status()
            return response

    @abstractmethod
    async def fetch_news(self) -> list[NewsItem]:
        """Fetch news from the platform.

        Returns:
            List of NewsItem objects
        """
        pass

    def parse_response(self, data: Any) -> list[NewsItem]:
        """Parse API response into NewsItem objects.

        Override this method for custom parsing logic.

        Args:
            data: Raw API response data

        Returns:
            List of NewsItem objects
        """
        return []


class APICrawler(BaseCrawler):
    """Crawler that uses multiple APIs for fetching trending news."""

    # Primary API - topurl.cn (working, reliable)
    TOPURL_API = "https://news.topurl.cn/api"

    def __init__(
        self,
        platform_id: str,
        platform_name: str,
        api_key: str | None = None,
        **kwargs,
    ):
        """Initialize the API crawler.

        Args:
            platform_id: Platform identifier
            platform_name: Platform display name
            api_key: Optional API key for premium access
            **kwargs: Additional BaseCrawler arguments
        """
        super().__init__(platform_id, platform_name, **kwargs)
        self.api_key = api_key

    async def fetch_news(self) -> list[NewsItem]:
        """Fetch news from the API.

        Returns:
            List of NewsItem objects
        """
        # Use topurl API which aggregates news from multiple sources
        try:
            response = await self._fetch(self.TOPURL_API)
            data = response.json()

            if data.get("code") == 200 and "data" in data:
                news_list = data["data"].get("newsList", [])
                return self._parse_topurl_response(news_list)
            else:
                print(f"API returned unexpected response: code={data.get('code')}")

        except Exception as e:
            print(f"Error fetching news: {type(e).__name__}: {e}")

        return []

    def _parse_topurl_response(self, data: list) -> list[NewsItem]:
        """Parse response from topurl API.

        Args:
            data: List of news items from API

        Returns:
            List of NewsItem objects
        """
        items = []
        for i, item in enumerate(data, start=1):
            if not isinstance(item, dict):
                continue

            title = item.get("title") or ""
            if not title or not isinstance(title, str):
                continue

            url = item.get("url") or ""
            score = item.get("score") or 0
            category = item.get("category") or "General"

            news_item = NewsItem(
                title=title.strip(),
                url=url,
                platform_id=self.platform_id,
                platform_name=self.platform_name,
                rank=i,
                hotness=score,
                extra={
                    "category": category,
                    "score": score,
                },
            )
            items.append(news_item)

        return items
