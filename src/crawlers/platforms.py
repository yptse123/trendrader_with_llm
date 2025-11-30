"""International news platform crawlers."""

import re
from datetime import datetime
from typing import Any

from .base import BaseCrawler, NewsItem


class HackerNewsCrawler(BaseCrawler):
    """Crawler for Hacker News (Tech/Startup news)."""

    API_URL = "https://hacker-news.firebaseio.com/v0"

    def __init__(self, **kwargs):
        super().__init__(
            platform_id="hackernews",
            platform_name="Hacker News",
            **kwargs
        )

    async def fetch_news(self) -> list[NewsItem]:
        """Fetch top stories from Hacker News."""
        try:
            # Get top story IDs
            response = await self._fetch(f"{self.API_URL}/topstories.json")
            story_ids = response.json()[:30]  # Top 30 stories

            items = []
            for rank, story_id in enumerate(story_ids, 1):
                try:
                    story_response = await self._fetch(f"{self.API_URL}/item/{story_id}.json")
                    story = story_response.json()

                    if story and story.get("title"):
                        items.append(NewsItem(
                            title=story.get("title", ""),
                            url=story.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                            platform_id=self.platform_id,
                            platform_name=self.platform_name,
                            rank=rank,
                            hotness=story.get("score", 0),
                            extra={
                                "comments": story.get("descendants", 0),
                                "by": story.get("by", ""),
                                "type": story.get("type", "story"),
                            }
                        ))
                except Exception:
                    continue

            return items
        except Exception as e:
            print(f"Error fetching Hacker News: {e}")
            return []


class RedditCrawler(BaseCrawler):
    """Crawler for Reddit popular posts."""

    API_URL = "https://www.reddit.com"

    def __init__(self, subreddit: str = "all", **kwargs):
        super().__init__(
            platform_id=f"reddit_{subreddit}",
            platform_name=f"Reddit r/{subreddit}",
            **kwargs
        )
        self.subreddit = subreddit

    async def fetch_news(self) -> list[NewsItem]:
        """Fetch hot posts from Reddit."""
        try:
            headers = {
                "User-Agent": "TrendRadar/1.0 (News Aggregator)"
            }
            response = await self._fetch(
                f"{self.API_URL}/r/{self.subreddit}/hot.json?limit=30",
                headers=headers
            )
            data = response.json()

            items = []
            children = data.get("data", {}).get("children", [])

            for rank, post in enumerate(children, 1):
                post_data = post.get("data", {})
                if post_data.get("stickied"):
                    continue

                items.append(NewsItem(
                    title=post_data.get("title", ""),
                    url=f"https://reddit.com{post_data.get('permalink', '')}",
                    platform_id=self.platform_id,
                    platform_name=self.platform_name,
                    rank=rank,
                    hotness=post_data.get("score", 0),
                    extra={
                        "subreddit": post_data.get("subreddit", ""),
                        "comments": post_data.get("num_comments", 0),
                        "author": post_data.get("author", ""),
                    }
                ))

            return items
        except Exception as e:
            print(f"Error fetching Reddit: {e}")
            return []


class BBCNewsCrawler(BaseCrawler):
    """Crawler for BBC News RSS feed."""

    RSS_URL = "https://feeds.bbci.co.uk/news/rss.xml"

    def __init__(self, **kwargs):
        super().__init__(
            platform_id="bbc",
            platform_name="BBC News",
            **kwargs
        )

    async def fetch_news(self) -> list[NewsItem]:
        """Fetch news from BBC RSS."""
        try:
            response = await self._fetch(self.RSS_URL)
            content = response.text

            items = []
            # Simple XML parsing for RSS
            item_pattern = r'<item>(.*?)</item>'
            title_pattern = r'<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>'
            link_pattern = r'<link>(.*?)</link>'
            desc_pattern = r'<description><!\[CDATA\[(.*?)\]\]></description>|<description>(.*?)</description>'

            matches = re.findall(item_pattern, content, re.DOTALL)

            for rank, item_content in enumerate(matches[:25], 1):
                title_match = re.search(title_pattern, item_content)
                link_match = re.search(link_pattern, item_content)

                if title_match and link_match:
                    title = title_match.group(1) or title_match.group(2)
                    link = link_match.group(1)

                    items.append(NewsItem(
                        title=title.strip(),
                        url=link.strip(),
                        platform_id=self.platform_id,
                        platform_name=self.platform_name,
                        rank=rank,
                        hotness=100 - rank,  # Simulate hotness based on rank
                    ))

            return items
        except Exception as e:
            print(f"Error fetching BBC News: {e}")
            return []


class ReutersCrawler(BaseCrawler):
    """Crawler for Reuters News."""

    API_URL = "https://www.reuters.com/pf/api/v3/content/fetch/articles-by-section-alias-or-id-v1"

    def __init__(self, **kwargs):
        super().__init__(
            platform_id="reuters",
            platform_name="Reuters",
            **kwargs
        )

    async def fetch_news(self) -> list[NewsItem]:
        """Fetch news from Reuters."""
        try:
            # Use a simpler approach - fetch from their sitemap/RSS alternative
            params = {
                "query": '{"section_id":"/","size":30}',
                "d": "111",
                "_website": "reuters"
            }
            response = await self._fetch(
                "https://www.reuters.com/arc/outboundfeeds/v3/all/?outputType=json&size=30"
            )
            data = response.json()

            items = []
            articles = data.get("items", [])

            for rank, article in enumerate(articles[:25], 1):
                title = article.get("title", "")
                if not title:
                    continue

                items.append(NewsItem(
                    title=title,
                    url=article.get("link", ""),
                    platform_id=self.platform_id,
                    platform_name=self.platform_name,
                    rank=rank,
                    hotness=100 - rank,
                    extra={
                        "category": article.get("category", ""),
                    }
                ))

            return items
        except Exception as e:
            print(f"Error fetching Reuters: {e}")
            return []


class GoogleNewsCrawler(BaseCrawler):
    """Crawler for Google News RSS."""

    RSS_URL = "https://news.google.com/rss"

    def __init__(self, topic: str = "", **kwargs):
        topic_name = topic.capitalize() if topic else "Top Stories"
        super().__init__(
            platform_id=f"google_news_{topic or 'top'}",
            platform_name=f"Google News ({topic_name})",
            **kwargs
        )
        self.topic = topic

    async def fetch_news(self) -> list[NewsItem]:
        """Fetch news from Google News RSS."""
        try:
            url = self.RSS_URL
            if self.topic:
                topic_map = {
                    "business": "CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pWVXlnQVAB",
                    "technology": "CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtVnVHZ0pWVXlnQVAB",
                    "science": "CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp0Y1RjU0FtVnVHZ0pWVXlnQVAB",
                    "world": "CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1YlY4U0FtVnVHZ0pWVXlnQVAB",
                }
                if self.topic in topic_map:
                    url = f"{self.RSS_URL}/topics/{topic_map[self.topic]}"

            response = await self._fetch(url)
            content = response.text

            items = []
            item_pattern = r'<item>(.*?)</item>'
            title_pattern = r'<title>(.*?)</title>'
            link_pattern = r'<link>(.*?)</link>'
            source_pattern = r'<source[^>]*>(.*?)</source>'

            matches = re.findall(item_pattern, content, re.DOTALL)

            for rank, item_content in enumerate(matches[:25], 1):
                title_match = re.search(title_pattern, item_content)
                link_match = re.search(link_pattern, item_content)
                source_match = re.search(source_pattern, item_content)

                if title_match and link_match:
                    title = title_match.group(1).strip()
                    # Clean HTML entities
                    title = title.replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")

                    items.append(NewsItem(
                        title=title,
                        url=link_match.group(1).strip(),
                        platform_id=self.platform_id,
                        platform_name=self.platform_name,
                        rank=rank,
                        hotness=100 - rank,
                        extra={
                            "source": source_match.group(1) if source_match else "",
                        }
                    ))

            return items
        except Exception as e:
            print(f"Error fetching Google News: {e}")
            return []


class TechCrunchCrawler(BaseCrawler):
    """Crawler for TechCrunch RSS."""

    RSS_URL = "https://techcrunch.com/feed/"

    def __init__(self, **kwargs):
        super().__init__(
            platform_id="techcrunch",
            platform_name="TechCrunch",
            **kwargs
        )

    async def fetch_news(self) -> list[NewsItem]:
        """Fetch news from TechCrunch RSS."""
        try:
            response = await self._fetch(self.RSS_URL)
            content = response.text

            items = []
            item_pattern = r'<item>(.*?)</item>'
            title_pattern = r'<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>'
            link_pattern = r'<link>(.*?)</link>'
            category_pattern = r'<category><!\[CDATA\[(.*?)\]\]></category>'

            matches = re.findall(item_pattern, content, re.DOTALL)

            for rank, item_content in enumerate(matches[:20], 1):
                title_match = re.search(title_pattern, item_content)
                link_match = re.search(link_pattern, item_content)
                categories = re.findall(category_pattern, item_content)

                if title_match and link_match:
                    title = title_match.group(1) or title_match.group(2)

                    items.append(NewsItem(
                        title=title.strip(),
                        url=link_match.group(1).strip(),
                        platform_id=self.platform_id,
                        platform_name=self.platform_name,
                        rank=rank,
                        hotness=100 - rank,
                        extra={
                            "categories": categories[:3],
                        }
                    ))

            return items
        except Exception as e:
            print(f"Error fetching TechCrunch: {e}")
            return []


class ArsTechnicaCrawler(BaseCrawler):
    """Crawler for Ars Technica RSS."""

    RSS_URL = "https://feeds.arstechnica.com/arstechnica/index"

    def __init__(self, **kwargs):
        super().__init__(
            platform_id="arstechnica",
            platform_name="Ars Technica",
            **kwargs
        )

    async def fetch_news(self) -> list[NewsItem]:
        """Fetch news from Ars Technica RSS."""
        try:
            response = await self._fetch(self.RSS_URL)
            content = response.text

            items = []
            item_pattern = r'<item>(.*?)</item>'
            title_pattern = r'<title>(.*?)</title>'
            link_pattern = r'<link>(.*?)</link>'

            matches = re.findall(item_pattern, content, re.DOTALL)

            for rank, item_content in enumerate(matches[:20], 1):
                title_match = re.search(title_pattern, item_content)
                link_match = re.search(link_pattern, item_content)

                if title_match and link_match:
                    items.append(NewsItem(
                        title=title_match.group(1).strip(),
                        url=link_match.group(1).strip(),
                        platform_id=self.platform_id,
                        platform_name=self.platform_name,
                        rank=rank,
                        hotness=100 - rank,
                    ))

            return items
        except Exception as e:
            print(f"Error fetching Ars Technica: {e}")
            return []


class BloombergCrawler(BaseCrawler):
    """Crawler for Bloomberg News (via RSS alternative)."""

    RSS_URL = "https://feeds.bloomberg.com/markets/news.rss"

    def __init__(self, **kwargs):
        super().__init__(
            platform_id="bloomberg",
            platform_name="Bloomberg",
            **kwargs
        )

    async def fetch_news(self) -> list[NewsItem]:
        """Fetch news from Bloomberg."""
        try:
            response = await self._fetch(self.RSS_URL)
            content = response.text

            items = []
            item_pattern = r'<item>(.*?)</item>'
            title_pattern = r'<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>'
            link_pattern = r'<link>(.*?)</link>'

            matches = re.findall(item_pattern, content, re.DOTALL)

            for rank, item_content in enumerate(matches[:20], 1):
                title_match = re.search(title_pattern, item_content)
                link_match = re.search(link_pattern, item_content)

                if title_match and link_match:
                    title = title_match.group(1) or title_match.group(2)

                    items.append(NewsItem(
                        title=title.strip(),
                        url=link_match.group(1).strip(),
                        platform_id=self.platform_id,
                        platform_name=self.platform_name,
                        rank=rank,
                        hotness=100 - rank,
                    ))

            return items
        except Exception as e:
            print(f"Error fetching Bloomberg: {e}")
            return []


class CNBCCrawler(BaseCrawler):
    """Crawler for CNBC Finance News."""

    RSS_URL = "https://www.cnbc.com/id/100003114/device/rss/rss.html"

    def __init__(self, **kwargs):
        super().__init__(
            platform_id="cnbc",
            platform_name="CNBC",
            **kwargs
        )

    async def fetch_news(self) -> list[NewsItem]:
        """Fetch news from CNBC RSS."""
        try:
            response = await self._fetch(self.RSS_URL)
            content = response.text

            items = []
            item_pattern = r'<item>(.*?)</item>'
            title_pattern = r'<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>'
            link_pattern = r'<link>(.*?)</link>'

            matches = re.findall(item_pattern, content, re.DOTALL)

            for rank, item_content in enumerate(matches[:20], 1):
                title_match = re.search(title_pattern, item_content)
                link_match = re.search(link_pattern, item_content)

                if title_match and link_match:
                    title = title_match.group(1) or title_match.group(2)

                    items.append(NewsItem(
                        title=title.strip(),
                        url=link_match.group(1).strip(),
                        platform_id=self.platform_id,
                        platform_name=self.platform_name,
                        rank=rank,
                        hotness=100 - rank,
                    ))

            return items
        except Exception as e:
            print(f"Error fetching CNBC: {e}")
            return []


class TheVergerCrawler(BaseCrawler):
    """Crawler for The Verge (Tech news)."""

    RSS_URL = "https://www.theverge.com/rss/index.xml"

    def __init__(self, **kwargs):
        super().__init__(
            platform_id="theverge",
            platform_name="The Verge",
            **kwargs
        )

    async def fetch_news(self) -> list[NewsItem]:
        """Fetch news from The Verge RSS."""
        try:
            response = await self._fetch(self.RSS_URL)
            content = response.text

            items = []
            # Atom feed format
            entry_pattern = r'<entry>(.*?)</entry>'
            title_pattern = r'<title[^>]*>(.*?)</title>'
            link_pattern = r'<link[^>]*href="([^"]+)"'

            matches = re.findall(entry_pattern, content, re.DOTALL)

            for rank, entry_content in enumerate(matches[:20], 1):
                title_match = re.search(title_pattern, entry_content)
                link_match = re.search(link_pattern, entry_content)

                if title_match and link_match:
                    items.append(NewsItem(
                        title=title_match.group(1).strip(),
                        url=link_match.group(1).strip(),
                        platform_id=self.platform_id,
                        platform_name=self.platform_name,
                        rank=rank,
                        hotness=100 - rank,
                    ))

            return items
        except Exception as e:
            print(f"Error fetching The Verge: {e}")
            return []


class WiredCrawler(BaseCrawler):
    """Crawler for Wired Magazine."""

    RSS_URL = "https://www.wired.com/feed/rss"

    def __init__(self, **kwargs):
        super().__init__(
            platform_id="wired",
            platform_name="Wired",
            **kwargs
        )

    async def fetch_news(self) -> list[NewsItem]:
        """Fetch news from Wired RSS."""
        try:
            response = await self._fetch(self.RSS_URL)
            content = response.text

            items = []
            item_pattern = r'<item>(.*?)</item>'
            title_pattern = r'<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>'
            link_pattern = r'<link>(.*?)</link>'

            matches = re.findall(item_pattern, content, re.DOTALL)

            for rank, item_content in enumerate(matches[:20], 1):
                title_match = re.search(title_pattern, item_content)
                link_match = re.search(link_pattern, item_content)

                if title_match and link_match:
                    title = title_match.group(1) or title_match.group(2)

                    items.append(NewsItem(
                        title=title.strip(),
                        url=link_match.group(1).strip(),
                        platform_id=self.platform_id,
                        platform_name=self.platform_name,
                        rank=rank,
                        hotness=100 - rank,
                    ))

            return items
        except Exception as e:
            print(f"Error fetching Wired: {e}")
            return []
