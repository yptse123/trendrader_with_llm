"""News crawlers for multiple platforms."""

from .base import BaseCrawler, NewsItem
from .aggregator import NewsAggregator

__all__ = ["BaseCrawler", "NewsItem", "NewsAggregator"]
