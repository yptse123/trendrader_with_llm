"""Report generation for TrendRadar AI."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from .crawlers.base import NewsItem
from .crawlers.aggregator import AggregatedNews
from .agents.news_crew import NewsAnalysisResult
from .utils.config import Config


class ReportGenerator:
    """Generates reports in multiple formats."""

    def __init__(self, config: Config):
        """Initialize the report generator.

        Args:
            config: Application configuration
        """
        self.config = config
        self.output_dir = Path(config.output.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Setup Jinja2 environment
        template_dir = Path(__file__).parent.parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=True,
        )

    def generate_all(
        self,
        news: AggregatedNews,
        analysis: NewsAnalysisResult | None = None,
        new_items: list[NewsItem] | None = None,
    ) -> dict[str, Path]:
        """Generate reports in all configured formats.

        Args:
            news: Aggregated news data
            analysis: Optional AI analysis results
            new_items: Optional list of new items (for incremental mode)

        Returns:
            Dictionary mapping format to output file path
        """
        outputs = {}
        timestamp = datetime.now()
        date_str = timestamp.strftime(self.config.output.date_format)
        time_str = timestamp.strftime(self.config.output.time_format)

        # Create date directory
        date_dir = self.output_dir / date_str
        date_dir.mkdir(parents=True, exist_ok=True)

        if self.config.output.save_html:
            html_path = self._generate_html(news, analysis, new_items, date_dir, time_str)
            outputs["html"] = html_path

        if self.config.output.save_txt:
            txt_path = self._generate_txt(news, analysis, new_items, date_dir, time_str)
            outputs["txt"] = txt_path

        if self.config.output.save_json:
            json_path = self._generate_json(news, analysis, new_items, date_dir, time_str)
            outputs["json"] = json_path

        # Also generate index.html for GitHub Pages
        self._generate_index(news, analysis, new_items)

        return outputs

    def _generate_html(
        self,
        news: AggregatedNews,
        analysis: NewsAnalysisResult | None,
        new_items: list[NewsItem] | None,
        output_dir: Path,
        time_str: str,
    ) -> Path:
        """Generate HTML report.

        Args:
            news: Aggregated news data
            analysis: Optional AI analysis results
            new_items: Optional list of new items
            output_dir: Output directory
            time_str: Time string for filename

        Returns:
            Path to generated file
        """
        template = self.jinja_env.get_template("report.html")

        # Group news by platform
        news_by_platform: dict[str, list[dict]] = {}
        new_item_titles = {item.title for item in (new_items or [])}

        for item in news.items:
            platform = item.platform_name
            if platform not in news_by_platform:
                news_by_platform[platform] = []

            item_dict = item.to_dict()
            item_dict["is_new"] = item.title in new_item_titles
            news_by_platform[platform].append(item_dict)

        # Calculate stats
        all_keywords = set()
        for item in news.items:
            all_keywords.update(item.matched_keywords)

        context = {
            "title": f"Trending News Report - {time_str}",
            "generated_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "report_mode": self.config.report.mode,
            "total_news": len(news.items),
            "platforms_count": len(news.platforms_fetched),
            "new_items_count": len(new_items) if new_items else 0,
            "keywords_matched": len(all_keywords),
            "rank_threshold": self.config.report.rank_threshold,
            "news_by_platform": news_by_platform,
            "analysis_summary": analysis.summary if analysis else "",
            "recommendations": analysis.recommendations if analysis else [],
        }

        html_content = template.render(**context)

        # Write to file
        output_path = output_dir / f"{time_str.replace(':', '-')}.html"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return output_path

    def _generate_txt(
        self,
        news: AggregatedNews,
        analysis: NewsAnalysisResult | None,
        new_items: list[NewsItem] | None,
        output_dir: Path,
        time_str: str,
    ) -> Path:
        """Generate plain text report.

        Args:
            news: Aggregated news data
            analysis: Optional AI analysis results
            new_items: Optional list of new items
            output_dir: Output directory
            time_str: Time string for filename

        Returns:
            Path to generated file
        """
        txt_dir = output_dir / "txt"
        txt_dir.mkdir(parents=True, exist_ok=True)

        lines = []
        lines.append("=" * 60)
        lines.append(f"TrendRadar AI Report - {time_str}")
        lines.append(f"Mode: {self.config.report.mode}")
        lines.append("=" * 60)
        lines.append("")

        # Stats
        lines.append(f"Total News: {len(news.items)}")
        lines.append(f"Platforms: {len(news.platforms_fetched)}")
        if new_items:
            lines.append(f"New Items: {len(new_items)}")
        lines.append("")

        # AI Analysis
        if analysis and analysis.summary:
            lines.append("-" * 40)
            lines.append("AI Analysis Summary")
            lines.append("-" * 40)
            lines.append(analysis.summary)
            lines.append("")

            if analysis.recommendations:
                lines.append("Recommendations:")
                for rec in analysis.recommendations:
                    lines.append(f"  - {rec}")
                lines.append("")

        # News by platform
        news_by_platform: dict[str, list[NewsItem]] = {}
        for item in news.items:
            if item.platform_name not in news_by_platform:
                news_by_platform[item.platform_name] = []
            news_by_platform[item.platform_name].append(item)

        new_item_titles = {item.title for item in (new_items or [])}

        for platform, items in news_by_platform.items():
            lines.append("-" * 40)
            lines.append(f"{platform} ({len(items)} items)")
            lines.append("-" * 40)

            for item in items:
                is_new = item.title in new_item_titles
                new_marker = " [NEW]" if is_new else ""
                rank_marker = f"[#{item.rank}]" if item.rank <= 10 else f"#{item.rank}"
                keywords = f" ({', '.join(item.matched_keywords)})" if item.matched_keywords else ""

                lines.append(f"{rank_marker} {item.title}{new_marker}{keywords}")

            lines.append("")

        # Write to file
        content = "\n".join(lines)
        output_path = txt_dir / f"{time_str.replace(':', '-')}.txt"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        return output_path

    def _generate_json(
        self,
        news: AggregatedNews,
        analysis: NewsAnalysisResult | None,
        new_items: list[NewsItem] | None,
        output_dir: Path,
        time_str: str,
    ) -> Path:
        """Generate JSON report.

        Args:
            news: Aggregated news data
            analysis: Optional AI analysis results
            new_items: Optional list of new items
            output_dir: Output directory
            time_str: Time string for filename

        Returns:
            Path to generated file
        """
        json_dir = output_dir / "json"
        json_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "generated_time": datetime.now().isoformat(),
            "report_mode": self.config.report.mode,
            "stats": {
                "total_news": len(news.items),
                "total_raw": news.total_raw_items,
                "total_filtered": news.total_filtered_items,
                "platforms_fetched": news.platforms_fetched,
                "platforms_failed": news.platforms_failed,
                "new_items": len(new_items) if new_items else 0,
            },
            "news": news.to_dict(),
        }

        if analysis:
            data["analysis"] = analysis.to_dict()

        if new_items:
            data["new_items"] = [item.to_dict() for item in new_items]

        # Write to file
        output_path = json_dir / f"{time_str.replace(':', '-')}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return output_path

    def _generate_index(
        self,
        news: AggregatedNews,
        analysis: NewsAnalysisResult | None,
        new_items: list[NewsItem] | None,
    ) -> Path:
        """Generate index.html for GitHub Pages.

        Args:
            news: Aggregated news data
            analysis: Optional AI analysis results
            new_items: Optional list of new items

        Returns:
            Path to generated file
        """
        template = self.jinja_env.get_template("report.html")

        # Group news by platform
        news_by_platform: dict[str, list[dict]] = {}
        new_item_titles = {item.title for item in (new_items or [])}

        for item in news.items:
            platform = item.platform_name
            if platform not in news_by_platform:
                news_by_platform[platform] = []

            item_dict = item.to_dict()
            item_dict["is_new"] = item.title in new_item_titles
            news_by_platform[platform].append(item_dict)

        # Calculate stats
        all_keywords = set()
        for item in news.items:
            all_keywords.update(item.matched_keywords)

        context = {
            "title": "TrendRadar AI - Latest Trending News",
            "generated_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "report_mode": self.config.report.mode,
            "total_news": len(news.items),
            "platforms_count": len(news.platforms_fetched),
            "new_items_count": len(new_items) if new_items else 0,
            "keywords_matched": len(all_keywords),
            "rank_threshold": self.config.report.rank_threshold,
            "news_by_platform": news_by_platform,
            "analysis_summary": analysis.summary if analysis else "",
            "recommendations": analysis.recommendations if analysis else [],
        }

        html_content = template.render(**context)

        # Write to root index.html
        output_path = self.output_dir.parent / "index.html"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return output_path

    def format_for_notification(
        self,
        news: AggregatedNews,
        analysis: NewsAnalysisResult | None = None,
        new_items: list[NewsItem] | None = None,
    ) -> str:
        """Format news for notification message.

        Args:
            news: Aggregated news data
            analysis: Optional AI analysis results
            new_items: Optional list of new items

        Returns:
            Formatted markdown string
        """
        lines = []
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        lines.append(f"**TrendRadar AI Report** - {timestamp}")
        lines.append(f"Mode: {self.config.report.mode}")
        lines.append("")

        # AI Summary if available
        if analysis and analysis.summary:
            lines.append("**AI Analysis**")
            # Truncate long summaries
            summary = analysis.summary[:500] + "..." if len(analysis.summary) > 500 else analysis.summary
            lines.append(summary)
            lines.append("")

        # New items section
        if new_items:
            lines.append(f"**New Trending ({len(new_items)} items)**")
            for item in new_items[:10]:  # Limit to top 10
                keywords = f" `{', '.join(item.matched_keywords)}`" if item.matched_keywords else ""
                lines.append(f"- [{item.platform_name}] {item.title}{keywords}")
            if len(new_items) > 10:
                lines.append(f"- ... and {len(new_items) - 10} more")
            lines.append("")

        # Top news by platform (condensed)
        lines.append("**Top News by Platform**")

        news_by_platform: dict[str, list[NewsItem]] = {}
        for item in news.items:
            if item.platform_name not in news_by_platform:
                news_by_platform[item.platform_name] = []
            news_by_platform[item.platform_name].append(item)

        for platform, items in news_by_platform.items():
            top_items = [i for i in items if i.rank <= self.config.report.rank_threshold][:3]
            if top_items:
                lines.append(f"**{platform}**")
                for item in top_items:
                    lines.append(f"  #{item.rank} {item.title}")

        lines.append("")
        lines.append(f"Total: {len(news.items)} items from {len(news.platforms_fetched)} platforms")

        return "\n".join(lines)
