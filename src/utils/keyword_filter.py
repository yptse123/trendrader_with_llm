"""Keyword filtering and matching for news content."""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Keyword:
    """Represents a parsed keyword with its modifiers."""
    word: str
    required: bool = False  # + prefix
    exclude: bool = False   # ! prefix
    max_count: int = 0      # @N suffix, 0 = unlimited

    @classmethod
    def parse(cls, text: str) -> "Keyword":
        """Parse a keyword string into a Keyword object.

        Examples:
            "AI" -> Keyword(word="AI")
            "+AI" -> Keyword(word="AI", required=True)
            "!ad" -> Keyword(word="ad", exclude=True)
            "AI@5" -> Keyword(word="AI", max_count=5)
            "+AI@3" -> Keyword(word="AI", required=True, max_count=3)
        """
        text = text.strip()
        if not text:
            return cls(word="")

        required = False
        exclude = False
        max_count = 0

        # Check for prefixes
        if text.startswith("+"):
            required = True
            text = text[1:]
        elif text.startswith("!"):
            exclude = True
            text = text[1:]

        # Check for @N suffix
        match = re.match(r"(.+?)@(\d+)$", text)
        if match:
            text = match.group(1)
            max_count = int(match.group(2))

        return cls(word=text, required=required, exclude=exclude, max_count=max_count)


@dataclass
class KeywordGroup:
    """A group of related keywords."""
    keywords: list[Keyword] = field(default_factory=list)
    matched_count: dict[str, int] = field(default_factory=dict)

    def add_keyword(self, keyword: Keyword) -> None:
        """Add a keyword to this group."""
        if keyword.word:
            self.keywords.append(keyword)

    def get_required_words(self) -> list[str]:
        """Get all required words in this group."""
        return [k.word.lower() for k in self.keywords if k.required]

    def get_exclude_words(self) -> list[str]:
        """Get all exclude words in this group."""
        return [k.word.lower() for k in self.keywords if k.exclude]

    def get_match_words(self) -> list[str]:
        """Get all normal match words (not required, not excluded)."""
        return [k.word.lower() for k in self.keywords if not k.required and not k.exclude]


class KeywordFilter:
    """Filter and match news content based on configured keywords."""

    def __init__(self, keywords_path: str | Path | None = None):
        """Initialize the keyword filter.

        Args:
            keywords_path: Path to frequency_words.txt file
        """
        self.groups: list[KeywordGroup] = []
        self.all_keywords: dict[str, Keyword] = {}

        if keywords_path:
            self.load_keywords(keywords_path)

    def load_keywords(self, path: str | Path) -> None:
        """Load keywords from a file.

        Keywords are grouped by blank lines.
        """
        path = Path(path)
        if not path.exists():
            return

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        self.groups = []
        self.all_keywords = {}

        current_group = KeywordGroup()

        for line in content.split("\n"):
            line = line.strip()

            # Skip comments and empty lines
            if line.startswith("#") or line.startswith("//"):
                continue

            if not line:
                # Blank line - start a new group if current has keywords
                if current_group.keywords:
                    self.groups.append(current_group)
                    current_group = KeywordGroup()
                continue

            # Parse and add keyword
            keyword = Keyword.parse(line)
            if keyword.word:
                current_group.add_keyword(keyword)
                self.all_keywords[keyword.word.lower()] = keyword

        # Don't forget the last group
        if current_group.keywords:
            self.groups.append(current_group)

    def matches(self, text: str) -> tuple[bool, list[str]]:
        """Check if text matches any keyword group.

        Returns:
            Tuple of (is_match, matched_keywords)
        """
        if not self.groups:
            # No keywords configured - match everything
            return True, []

        text_lower = text.lower()
        matched_keywords = []

        for group in self.groups:
            # Check exclude words first
            exclude_words = group.get_exclude_words()
            if any(word in text_lower for word in exclude_words):
                continue

            # Check required words - all must match
            required_words = group.get_required_words()
            if required_words and not all(word in text_lower for word in required_words):
                continue

            # Check match words
            match_words = group.get_match_words()
            for word in match_words:
                if word in text_lower:
                    matched_keywords.append(word)

            # Check required words as matches too
            for word in required_words:
                if word in text_lower:
                    matched_keywords.append(word)

        is_match = len(matched_keywords) > 0 or not any(
            group.get_match_words() or group.get_required_words()
            for group in self.groups
        )

        return is_match, list(set(matched_keywords))

    def filter_news(
        self,
        news_items: list[dict],
        title_key: str = "title",
        global_max_per_keyword: int = 0
    ) -> list[dict]:
        """Filter news items based on keyword matching.

        Args:
            news_items: List of news dictionaries
            title_key: Key to use for the news title
            global_max_per_keyword: Global limit per keyword (0 = use individual limits)

        Returns:
            Filtered list of news items with matched keywords
        """
        if not self.groups:
            return news_items

        results = []
        keyword_counts: dict[str, int] = {}

        for item in news_items:
            title = item.get(title_key, "")
            if not title or not isinstance(title, str):
                continue

            is_match, matched = self.matches(title)
            if not is_match:
                continue

            # Check keyword count limits
            can_add = True
            for keyword in matched:
                keyword_lower = keyword.lower()
                current_count = keyword_counts.get(keyword_lower, 0)

                # Get the limit for this keyword
                max_count = global_max_per_keyword
                if keyword_lower in self.all_keywords:
                    kw = self.all_keywords[keyword_lower]
                    if kw.max_count > 0:
                        max_count = kw.max_count

                if max_count > 0 and current_count >= max_count:
                    can_add = False
                    break

            if can_add:
                # Update counts
                for keyword in matched:
                    keyword_lower = keyword.lower()
                    keyword_counts[keyword_lower] = keyword_counts.get(keyword_lower, 0) + 1

                # Add matched keywords to the item
                item_copy = item.copy()
                item_copy["matched_keywords"] = matched
                results.append(item_copy)

        return results

    def get_statistics(self) -> dict:
        """Get statistics about loaded keywords."""
        total_keywords = len(self.all_keywords)
        total_groups = len(self.groups)
        required_count = sum(1 for k in self.all_keywords.values() if k.required)
        exclude_count = sum(1 for k in self.all_keywords.values() if k.exclude)
        limited_count = sum(1 for k in self.all_keywords.values() if k.max_count > 0)

        return {
            "total_keywords": total_keywords,
            "total_groups": total_groups,
            "required_keywords": required_count,
            "exclude_keywords": exclude_count,
            "limited_keywords": limited_count,
        }
