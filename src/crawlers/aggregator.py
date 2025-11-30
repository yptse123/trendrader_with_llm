"""News aggregator that combines results from multiple international crawlers."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from .base import BaseCrawler, NewsItem
from .platforms import (
    HackerNewsCrawler,
    RedditCrawler,
    BBCNewsCrawler,
    GoogleNewsCrawler,
    TechCrunchCrawler,
    ArsTechnicaCrawler,
    BloombergCrawler,
    CNBCCrawler,
    TheVergerCrawler,
    WiredCrawler,
)
from ..utils.config import Config
from ..utils.keyword_filter import KeywordFilter


@dataclass
class AggregatedNews:
    """Container for aggregated news from all platforms."""
    items: list[NewsItem] = field(default_factory=list)
    platforms_fetched: list[str] = field(default_factory=list)
    platforms_failed: list[str] = field(default_factory=list)
    fetch_time: datetime = field(default_factory=datetime.now)
    total_raw_items: int = 0
    total_filtered_items: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "items": [item.to_dict() for item in self.items],
            "platforms_fetched": self.platforms_fetched,
            "platforms_failed": self.platforms_failed,
            "fetch_time": self.fetch_time.isoformat(),
            "total_raw_items": self.total_raw_items,
            "total_filtered_items": self.total_filtered_items,
        }


class NewsAggregator:
    """Aggregates news from multiple international platforms with filtering and ranking."""

    def __init__(
        self,
        config: Config,
        keyword_filter: KeywordFilter | None = None,
    ):
        """Initialize the news aggregator.

        Args:
            config: Application configuration
            keyword_filter: Optional keyword filter for news matching
        """
        self.config = config
        self.keyword_filter = keyword_filter
        self.crawlers: list[BaseCrawler] = []
        self._setup_crawlers()

    def _setup_crawlers(self) -> None:
        """Set up crawlers for international news platforms."""
        crawler_config = {
            "request_interval": self.config.crawler.request_interval,
            "timeout": self.config.crawler.timeout,
            "max_retries": self.config.crawler.max_retries,
            "proxy": self.config.crawler.default_proxy if self.config.crawler.use_proxy else None,
        }

        # International Big News (20%)
        self.crawlers.extend([
            BBCNewsCrawler(**crawler_config),
            GoogleNewsCrawler(topic="world", **crawler_config),
        ])

        # AI & Technology (20%)
        self.crawlers.extend([
            HackerNewsCrawler(**crawler_config),
            TechCrunchCrawler(**crawler_config),
            ArsTechnicaCrawler(**crawler_config),
            TheVergerCrawler(**crawler_config),
            WiredCrawler(**crawler_config),
        ])

        # Finance (20%)
        self.crawlers.extend([
            BloombergCrawler(**crawler_config),
            CNBCCrawler(**crawler_config),
            GoogleNewsCrawler(topic="business", **crawler_config),
        ])

        # General/Other Important News (40%)
        self.crawlers.extend([
            GoogleNewsCrawler(topic="", **crawler_config),  # Top stories
            GoogleNewsCrawler(topic="science", **crawler_config),
            RedditCrawler(subreddit="worldnews", **crawler_config),
            RedditCrawler(subreddit="technology", **crawler_config),
        ])

    async def fetch_all(
        self,
        progress_callback: Callable[[str, str], None] | None = None,
    ) -> AggregatedNews:
        """Fetch news from all configured platforms.

        Args:
            progress_callback: Optional callback for progress updates (platform_id, status)

        Returns:
            AggregatedNews containing all fetched items
        """
        result = AggregatedNews()
        all_items: list[NewsItem] = []

        # Fetch from all platforms concurrently
        tasks = []
        for crawler in self.crawlers:
            task = self._fetch_from_crawler(crawler, progress_callback)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for crawler, fetch_result in zip(self.crawlers, results):
            if isinstance(fetch_result, Exception):
                result.platforms_failed.append(crawler.platform_id)
                if progress_callback:
                    progress_callback(crawler.platform_id, "failed")
            else:
                items = fetch_result
                all_items.extend(items)
                result.platforms_fetched.append(crawler.platform_id)
                if progress_callback:
                    progress_callback(crawler.platform_id, f"success ({len(items)} items)")

        result.total_raw_items = len(all_items)

        # Deduplicate first
        unique_items = self.deduplicate_items(all_items)

        # Apply keyword filtering
        if self.keyword_filter:
            filtered_items = self._apply_keyword_filter(unique_items)
        else:
            filtered_items = unique_items

        result.total_filtered_items = len(filtered_items)

        # Apply ranking algorithm
        ranked_items = self._rank_news(filtered_items)

        # Limit to top 10 trending news
        result.items = ranked_items[:10]

        return result

    async def _fetch_from_crawler(
        self,
        crawler: BaseCrawler,
        progress_callback: Callable[[str, str], None] | None = None,
    ) -> list[NewsItem]:
        """Fetch news from a single crawler.

        Args:
            crawler: The crawler to fetch from
            progress_callback: Optional callback for progress updates

        Returns:
            List of NewsItem objects
        """
        if progress_callback:
            progress_callback(crawler.platform_id, "fetching")

        try:
            items = await crawler.fetch_news()
            return items
        except Exception as e:
            raise RuntimeError(f"Failed to fetch from {crawler.platform_id}: {e}")

    def _apply_keyword_filter(self, items: list[NewsItem]) -> list[NewsItem]:
        """Apply keyword filtering to news items.

        Args:
            items: List of NewsItem to filter

        Returns:
            Filtered list of NewsItem
        """
        if not self.keyword_filter:
            return items

        # Convert to dict format for filtering
        dict_items = [item.to_dict() for item in items]

        # Apply filter
        filtered_dicts = self.keyword_filter.filter_news(
            dict_items,
            title_key="title",
            global_max_per_keyword=self.config.report.max_news_per_keyword,
        )

        # Convert back to NewsItem
        filtered_items = [NewsItem.from_dict(d) for d in filtered_dicts]
        return filtered_items

    def _rank_news(self, items: list[NewsItem]) -> list[NewsItem]:
        """Rank news items using the configured weights.

        The ranking algorithm considers:
        - Rank weight: Prioritize top-ranked news from each platform
        - Frequency weight: Prioritize news that appears on multiple platforms
        - Hotness weight: Prioritize consistently high-ranking news

        Args:
            items: List of NewsItem to rank

        Returns:
            Sorted list of NewsItem
        """
        weights = self.config.weight

        # Calculate frequency (how many platforms have similar titles)
        title_frequency: dict[str, int] = {}
        for item in items:
            # Normalize title for comparison
            normalized = self._normalize_title(item.title)
            title_frequency[normalized] = title_frequency.get(normalized, 0) + 1

        # Calculate scores
        scored_items: list[tuple[float, NewsItem]] = []
        for item in items:
            normalized = self._normalize_title(item.title)

            # Rank score: Lower rank = higher score (invert rank)
            max_rank = 50  # Assume max rank of 50
            rank_score = (max_rank - min(item.rank, max_rank)) / max_rank

            # Frequency score: More appearances = higher score
            frequency = title_frequency.get(normalized, 1)
            max_frequency = len(self.crawlers)
            frequency_score = frequency / max_frequency

            # Hotness score: Normalize hotness
            hotness = item.hotness if isinstance(item.hotness, (int, float)) else 0
            # Use log scale for hotness to prevent extreme values from dominating
            import math
            hotness_score = math.log10(max(hotness, 1)) / 10  # Normalize to roughly 0-1

            # Platform priority bonus
            platform_bonus = self._get_platform_priority(item.platform_id)

            # Combined score
            total_score = (
                weights.rank_weight * rank_score +
                weights.frequency_weight * frequency_score +
                weights.hotness_weight * hotness_score +
                0.1 * platform_bonus  # Small bonus for authority platforms
            )

            scored_items.append((total_score, item))

        # Sort by score (descending)
        scored_items.sort(key=lambda x: x[0], reverse=True)

        return [item for _, item in scored_items]

    def _get_platform_priority(self, platform_id: str) -> float:
        """Get priority bonus for authoritative platforms."""
        # Higher priority for major international news sources
        priority_map = {
            "bbc": 1.0,
            "reuters": 1.0,
            "bloomberg": 0.9,
            "cnbc": 0.8,
            "google_news_world": 0.9,
            "google_news_top": 0.85,
            "hackernews": 0.8,
            "techcrunch": 0.7,
            "arstechnica": 0.7,
            "theverge": 0.6,
            "wired": 0.6,
            "reddit_worldnews": 0.5,
            "reddit_technology": 0.5,
        }
        return priority_map.get(platform_id, 0.5)

    def _normalize_title(self, title: str) -> str:
        """Normalize title for comparison.

        Args:
            title: Original title

        Returns:
            Normalized title
        """
        import re
        # Remove special characters and convert to lowercase
        normalized = re.sub(r'[^\w\s]', '', title.lower())
        # Remove extra whitespace
        normalized = ' '.join(normalized.split())
        return normalized

    def get_new_items(
        self,
        current_items: list[NewsItem],
        previous_items: list[NewsItem],
    ) -> list[NewsItem]:
        """Get items that are new compared to previous fetch.

        Args:
            current_items: Current list of news items
            previous_items: Previous list of news items

        Returns:
            List of new NewsItem
        """
        previous_titles = {
            self._normalize_title(item.title)
            for item in previous_items
        }

        new_items = [
            item for item in current_items
            if self._normalize_title(item.title) not in previous_titles
        ]

        return new_items

    def deduplicate_items(self, items: list[NewsItem]) -> list[NewsItem]:
        """Remove duplicate news items based on title similarity.

        Args:
            items: List of NewsItem

        Returns:
            Deduplicated list of NewsItem
        """
        seen_titles: set[str] = set()
        unique_items: list[NewsItem] = []

        for item in items:
            normalized = self._normalize_title(item.title)
            # Use first 50 chars for fuzzy matching
            short_key = normalized[:50] if len(normalized) > 50 else normalized

            if short_key not in seen_titles:
                seen_titles.add(short_key)
                unique_items.append(item)

        return unique_items
