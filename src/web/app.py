"""FastAPI web application for TrendRadar AI dashboard."""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..crawlers import NewsAggregator
from ..agents import NewsCrew, NewsAnalysisResult
from ..notifiers import NotificationManager
from ..reporter import ReportGenerator
from ..utils import Config, load_config, KeywordFilter


def create_app(config_path: str | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title="TrendRadar AI",
        description="AI-powered trending news aggregation and analysis",
        version="1.0.0",
    )

    # Load configuration
    config = load_config(config_path)

    # Store app state
    app.state.config = config
    app.state.last_fetch_time = None
    app.state.last_news = None
    app.state.last_analysis = None
    app.state.is_running = False

    # Setup templates
    templates_dir = Path(__file__).parent / "templates"
    templates_dir.mkdir(exist_ok=True)
    templates = Jinja2Templates(directory=str(templates_dir))

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request):
        """Main dashboard page."""
        # Get recent reports
        output_dir = Path(config.output.output_dir)
        reports = []

        if output_dir.exists():
            for date_dir in sorted(output_dir.iterdir(), reverse=True)[:7]:
                if date_dir.is_dir() and not date_dir.name.startswith("."):
                    json_dir = date_dir / "json"
                    if json_dir.exists():
                        for json_file in sorted(json_dir.glob("*.json"), reverse=True)[:5]:
                            try:
                                with open(json_file) as f:
                                    data = json.load(f)
                                reports.append({
                                    "date": date_dir.name,
                                    "time": json_file.stem,
                                    "items_count": len(data.get("items", [])),
                                    "path": str(json_file),
                                })
                            except:
                                pass

        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "config": config,
            "reports": reports[:10],
            "last_fetch_time": app.state.last_fetch_time,
            "last_news": app.state.last_news,
            "last_analysis": app.state.last_analysis,
            "is_running": app.state.is_running,
        })

    @app.get("/api/status")
    async def get_status():
        """Get current application status."""
        return {
            "status": "running" if app.state.is_running else "idle",
            "last_fetch_time": app.state.last_fetch_time.isoformat() if app.state.last_fetch_time else None,
            "news_count": len(app.state.last_news.items) if app.state.last_news else 0,
            "has_analysis": app.state.last_analysis is not None,
        }

    @app.get("/api/news")
    async def get_news():
        """Get latest fetched news."""
        if not app.state.last_news:
            return {"items": [], "message": "No news fetched yet"}

        return {
            "items": [item.to_dict() for item in app.state.last_news.items],
            "platforms_fetched": app.state.last_news.platforms_fetched,
            "platforms_failed": app.state.last_news.platforms_failed,
            "fetch_time": app.state.last_news.fetch_time.isoformat(),
            "total_raw_items": app.state.last_news.total_raw_items,
            "total_filtered_items": app.state.last_news.total_filtered_items,
        }

    @app.get("/api/analysis")
    async def get_analysis():
        """Get latest AI analysis."""
        if not app.state.last_analysis:
            return {"message": "No analysis available"}

        return app.state.last_analysis.to_dict()

    @app.post("/api/fetch")
    async def trigger_fetch(background_tasks: BackgroundTasks, enable_ai: bool = False):
        """Trigger a news fetch."""
        if app.state.is_running:
            return JSONResponse(
                status_code=409,
                content={"error": "A fetch is already in progress"}
            )

        background_tasks.add_task(run_fetch, app, config, enable_ai)
        return {"message": "Fetch started", "enable_ai": enable_ai}

    @app.post("/api/notify")
    async def trigger_notify():
        """Send notification with latest news."""
        if not app.state.last_news:
            return JSONResponse(
                status_code=400,
                content={"error": "No news to notify about"}
            )

        notification_manager = NotificationManager(config)
        reporter = ReportGenerator(config)

        content = reporter.format_for_notification(
            app.state.last_news,
            app.state.last_analysis,
            app.state.last_news.items
        )

        summary = await notification_manager.send_all(
            content,
            title="TrendRadar AI Report",
            force=True,
        )

        return {
            "sent": summary.total_sent,
            "failed": summary.total_failed,
            "platforms": notification_manager.get_configured_platforms(),
        }

    @app.get("/api/reports")
    async def get_reports():
        """Get list of generated reports."""
        output_dir = Path(config.output.output_dir)
        reports = []

        if output_dir.exists():
            for date_dir in sorted(output_dir.iterdir(), reverse=True)[:30]:
                if date_dir.is_dir() and not date_dir.name.startswith("."):
                    for html_file in sorted(date_dir.glob("*.html"), reverse=True):
                        reports.append({
                            "date": date_dir.name,
                            "time": html_file.stem,
                            "html_path": f"/reports/{date_dir.name}/{html_file.name}",
                        })

        return {"reports": reports}

    @app.get("/reports/{date}/{filename}")
    async def serve_report(date: str, filename: str):
        """Serve HTML report files."""
        output_dir = Path(config.output.output_dir)
        file_path = output_dir / date / filename

        if file_path.exists() and file_path.suffix == ".html":
            with open(file_path) as f:
                return HTMLResponse(content=f.read())

        return JSONResponse(status_code=404, content={"error": "Report not found"})

    return app


async def run_fetch(app: FastAPI, config: Config, enable_ai: bool = False):
    """Background task to fetch news."""
    app.state.is_running = True

    try:
        # Setup components
        keyword_filter = KeywordFilter(
            Path(__file__).parent.parent.parent / "config" / "frequency_words.txt"
        )
        aggregator = NewsAggregator(config, keyword_filter)
        reporter = ReportGenerator(config)

        # Fetch news
        news = await aggregator.fetch_all()
        app.state.last_news = news
        app.state.last_fetch_time = datetime.now()

        # Run AI analysis if enabled
        if enable_ai and news.items:
            try:
                crew = NewsCrew(config)
                analysis = await crew.analyze_async(news.items)
                app.state.last_analysis = analysis
            except Exception as e:
                print(f"AI analysis failed: {e}")

        # Generate reports
        reporter.generate_all(news, app.state.last_analysis, news.items)

    except Exception as e:
        print(f"Fetch failed: {e}")
    finally:
        app.state.is_running = False
