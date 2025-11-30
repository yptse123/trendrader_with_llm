"""Main entry point for TrendRadar AI."""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .crawlers import NewsAggregator, NewsItem
from .agents import NewsCrew, NewsAnalysisResult
from .notifiers import NotificationManager
from .reporter import ReportGenerator
from .utils import Config, load_config, KeywordFilter

# Load environment variables from .env file
load_dotenv()


console = Console()


class TrendRadarApp:
    """Main application class for TrendRadar AI."""

    def __init__(self, config_path: str | None = None):
        """Initialize the application.

        Args:
            config_path: Optional path to configuration file
        """
        self.config = load_config(config_path)
        self.keyword_filter = KeywordFilter(
            Path(__file__).parent.parent / "config" / "frequency_words.txt"
        )
        self.aggregator = NewsAggregator(self.config, self.keyword_filter)
        self.notification_manager = NotificationManager(self.config)
        self.reporter = ReportGenerator(self.config)
        self._previous_items: list[NewsItem] = []
        self._history_file = Path(self.config.output.output_dir) / ".history.json"

    def _load_history(self) -> list[NewsItem]:
        """Load previous news items from history file."""
        if not self._history_file.exists():
            return []

        try:
            with open(self._history_file, "r") as f:
                data = json.load(f)
                return [NewsItem.from_dict(item) for item in data.get("items", [])]
        except (json.JSONDecodeError, IOError):
            return []

    def _save_history(self, items: list[NewsItem]) -> None:
        """Save news items to history file."""
        self._history_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "timestamp": datetime.now().isoformat(),
            "items": [item.to_dict() for item in items],
        }

        with open(self._history_file, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    async def run(self, enable_ai: bool = True, force_notify: bool = False) -> None:
        """Run the main application workflow.

        Args:
            enable_ai: Whether to run AI analysis
            force_notify: Force notification regardless of settings
        """
        console.print(Panel.fit(
            "[bold blue]TrendRadar AI[/bold blue]\n"
            f"Version: {self.config.app.version}",
            border_style="blue",
        ))

        # Check if crawler is enabled
        if not self.config.crawler.enable_crawler:
            console.print("[yellow]Crawler is disabled in configuration. Exiting.[/yellow]")
            return

        # Load previous items for incremental mode
        self._previous_items = self._load_history()

        # Fetch news
        news = await self._fetch_news()

        if not news.items:
            console.print("[yellow]No news items fetched. Check your configuration.[/yellow]")
            return

        # Determine new items
        new_items = self.aggregator.get_new_items(news.items, self._previous_items)

        # For incremental mode, only proceed if there are new items
        if self.config.report.mode == "incremental" and not new_items:
            console.print("[green]No new items detected in incremental mode.[/green]")
            return

        # Run AI analysis if enabled
        analysis = None
        if enable_ai:
            analysis = await self._run_analysis(news.items)

        # Generate reports
        self._generate_reports(news, analysis, new_items)

        # Send notifications
        await self._send_notifications(news, analysis, new_items, force_notify)

        # Save history for next run
        self._save_history(news.items)

        # Print summary
        self._print_summary(news, analysis, new_items)

    async def _fetch_news(self):
        """Fetch news from all platforms."""
        console.print("\n[bold]Fetching trending news...[/bold]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Fetching from platforms...", total=None)

            def progress_callback(platform: str, status: str):
                progress.update(task, description=f"[cyan]{platform}[/cyan]: {status}")

            news = await self.aggregator.fetch_all(progress_callback)

        console.print(f"[green]Fetched {news.total_raw_items} items from {len(news.platforms_fetched)} platforms[/green]")
        console.print(f"[green]After filtering: {len(news.items)} items[/green]")

        if news.platforms_failed:
            console.print(f"[yellow]Failed platforms: {', '.join(news.platforms_failed)}[/yellow]")

        return news

    async def _run_analysis(self, items: list[NewsItem]) -> NewsAnalysisResult | None:
        """Run AI analysis on news items."""
        console.print("\n[bold]Running AI analysis...[/bold]")

        try:
            crew = NewsCrew(self.config)

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("AI agents analyzing news...", total=None)
                analysis = await crew.analyze_async(items)

            console.print("[green]AI analysis complete[/green]")
            return analysis

        except Exception as e:
            console.print(f"[yellow]AI analysis failed: {e}[/yellow]")
            return None

    def _generate_reports(
        self,
        news,
        analysis: NewsAnalysisResult | None,
        new_items: list[NewsItem],
    ) -> None:
        """Generate reports in all formats."""
        console.print("\n[bold]Generating reports...[/bold]")

        outputs = self.reporter.generate_all(news, analysis, new_items)

        for format_type, path in outputs.items():
            console.print(f"  [green]{format_type.upper()}[/green]: {path}")

    async def _send_notifications(
        self,
        news,
        analysis: NewsAnalysisResult | None,
        new_items: list[NewsItem],
        force: bool = False,
    ) -> None:
        """Send notifications to configured platforms."""
        if not self.config.notification.enable_notification and not force:
            console.print("\n[yellow]Notifications disabled[/yellow]")
            return

        console.print("\n[bold]Sending notifications...[/bold]")

        # Check if we should send
        should_push, reason = self.notification_manager.should_push()
        if not should_push and not force:
            console.print(f"[yellow]Skipping notifications: {reason}[/yellow]")
            return

        # Format content
        content = self.reporter.format_for_notification(news, analysis, new_items)

        # Send
        summary = await self.notification_manager.send_all(
            content,
            title="TrendRadar AI Report",
            force=force,
        )

        # Report results
        configured = self.notification_manager.get_configured_platforms()
        console.print(f"  Configured platforms: {', '.join(configured)}")
        console.print(f"  [green]Sent: {summary.total_sent}[/green]")
        if summary.total_failed:
            console.print(f"  [red]Failed: {summary.total_failed}[/red]")
            for result in summary.results:
                if not result.success:
                    console.print(f"    [red]{result.platform}: {result.error}[/red]")

    def _print_summary(
        self,
        news,
        analysis: NewsAnalysisResult | None,
        new_items: list[NewsItem],
    ) -> None:
        """Print execution summary."""
        console.print("\n")

        # Create summary table
        table = Table(title="Execution Summary", show_header=True, header_style="bold")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Total Items", str(len(news.items)))
        table.add_row("New Items", str(len(new_items)))
        table.add_row("Platforms Fetched", str(len(news.platforms_fetched)))
        table.add_row("Platforms Failed", str(len(news.platforms_failed)))
        table.add_row("Report Mode", self.config.report.mode)
        table.add_row("AI Analysis", "Yes" if analysis else "No")

        console.print(table)

        # Top news preview
        if news.items:
            console.print("\n[bold]Top 5 Trending:[/bold]")
            for i, item in enumerate(news.items[:5], 1):
                keywords = f" ({', '.join(item.matched_keywords)})" if item.matched_keywords else ""
                console.print(f"  {i}. [{item.platform_name}] {item.title}{keywords}")


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="TrendRadar AI - Trending News Aggregator")
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        help="Path to configuration file",
    )
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Disable AI analysis",
    )
    parser.add_argument(
        "--force-notify",
        action="store_true",
        help="Force send notifications",
    )
    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version="TrendRadar AI 1.0.0",
    )

    args = parser.parse_args()

    try:
        app = TrendRadarApp(config_path=args.config)
        asyncio.run(app.run(
            enable_ai=not args.no_ai,
            force_notify=args.force_notify,
        ))
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
