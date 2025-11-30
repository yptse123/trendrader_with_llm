"""CrewAI agents and crew for news analysis."""

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from crewai import Agent, Crew, Process, Task, LLM
from pydantic import BaseModel

from ..crawlers.base import NewsItem
from ..utils.config import Config


class TrendAnalysis(BaseModel):
    """Model for trend analysis results."""
    topic: str
    sentiment: str  # positive, negative, neutral
    trend_direction: str  # rising, falling, stable
    key_points: list[str]
    related_topics: list[str]
    summary: str


class NewsInsight(BaseModel):
    """Model for news insights."""
    category: str
    importance_score: float
    audience_impact: str
    recommended_action: str


@dataclass
class NewsAnalysisResult:
    """Container for news analysis results."""
    trends: list[TrendAnalysis] = field(default_factory=list)
    insights: list[NewsInsight] = field(default_factory=list)
    summary: str = ""
    recommendations: list[str] = field(default_factory=list)
    analysis_time: datetime = field(default_factory=datetime.now)
    raw_output: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "trends": [t.model_dump() for t in self.trends],
            "insights": [i.model_dump() for i in self.insights],
            "summary": self.summary,
            "recommendations": self.recommendations,
            "analysis_time": self.analysis_time.isoformat(),
            "raw_output": self.raw_output,
        }


class NewsCrew:
    """CrewAI crew for analyzing trending news."""

    def __init__(self, config: Config):
        """Initialize the news crew.

        Args:
            config: Application configuration
        """
        self.config = config
        self._setup_agents()
        self._setup_tasks()

    def _get_llm(self) -> LLM:
        """Get LLM instance for agents."""
        llm_config = self.config.crewai.llm

        # Build model string
        model_str = f"{llm_config.provider}/{llm_config.model}"

        # Set up LLM with custom base URL if provided
        llm_kwargs = {
            "model": model_str,
            "temperature": llm_config.temperature,
            "max_tokens": llm_config.max_tokens,
        }

        # Handle custom base URL for Anthropic
        if llm_config.base_url:
            llm_kwargs["base_url"] = llm_config.base_url

        # Get API key from environment
        if llm_config.provider == "anthropic":
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if api_key:
                llm_kwargs["api_key"] = api_key

        return LLM(**llm_kwargs)

    def _setup_agents(self) -> None:
        """Set up the crew agents."""
        llm = self._get_llm()

        # News Analyst Agent
        self.news_analyst = Agent(
            role="Senior News Analyst",
            goal="Analyze trending news and identify key patterns, themes, and implications",
            backstory="""You are an experienced news analyst with expertise in identifying
            trends across multiple platforms. You have a keen eye for detecting emerging
            stories, understanding public sentiment, and connecting seemingly unrelated
            news items into coherent narratives. You've worked with major news organizations
            and have deep knowledge of social media dynamics.""",
            verbose=self.config.crewai.verbose,
            allow_delegation=False,
            llm=llm,
        )

        # Trend Researcher Agent
        self.trend_researcher = Agent(
            role="Trend Research Specialist",
            goal="Research trending topics and provide context and background information",
            backstory="""You are a dedicated researcher who specializes in understanding
            why certain topics become trending. You excel at finding connections between
            current events and historical patterns, identifying the key players and
            stakeholders involved, and predicting how trends might evolve. Your research
            is thorough, unbiased, and data-driven.""",
            verbose=self.config.crewai.verbose,
            allow_delegation=False,
            llm=llm,
        )

        # Report Writer Agent
        self.report_writer = Agent(
            role="Executive Report Writer",
            goal="Create clear, concise, and actionable news reports",
            backstory="""You are a skilled writer who transforms complex news analysis
            into digestible reports for busy executives. Your reports are known for being
            concise yet comprehensive, highlighting what matters most and providing clear
            recommendations. You understand that your readers need to quickly grasp key
            information and make decisions based on your reports.""",
            verbose=self.config.crewai.verbose,
            allow_delegation=False,
            llm=llm,
        )

        # Sentiment Analyzer Agent
        self.sentiment_analyzer = Agent(
            role="Sentiment Analysis Expert",
            goal="Analyze public sentiment and emotional tone of trending topics",
            backstory="""You are an expert in understanding public sentiment and
            emotional reactions to news events. You can detect subtle shifts in public
            opinion, identify potential PR crises or opportunities, and understand
            how different audiences might react to news. Your analysis helps organizations
            prepare appropriate responses to trending topics.""",
            verbose=self.config.crewai.verbose,
            allow_delegation=False,
            llm=llm,
        )

    def _setup_tasks(self) -> None:
        """Set up the crew tasks (templates to be filled with actual news data)."""
        pass  # Tasks are created dynamically in analyze()

    def _create_analysis_tasks(self, news_items: list[NewsItem]) -> list[Task]:
        """Create analysis tasks for the given news items.

        Args:
            news_items: List of news items to analyze

        Returns:
            List of Task objects
        """
        # Format news items for analysis
        news_text = self._format_news_for_analysis(news_items)

        # Task 1: Initial News Analysis
        analysis_task = Task(
            description=f"""Analyze the following trending news items from multiple platforms:

{news_text}

Your analysis should:
1. Identify the top 5 most significant trending topics
2. Group related news items together
3. Assess the overall news landscape
4. Note any emerging patterns or connections between topics

Provide a structured analysis with clear sections.""",
            expected_output="""A comprehensive analysis containing:
- List of top 5 trending topics with brief descriptions
- Groupings of related news items
- Assessment of the current news landscape
- Identified patterns and connections""",
            agent=self.news_analyst,
        )

        # Task 2: Trend Research
        research_task = Task(
            description="""Based on the news analysis, research the top trending topics to provide context:

1. Why are these topics trending now?
2. What are the key stakeholders involved?
3. How might these trends evolve?
4. Are there any historical parallels?

Focus on providing actionable context that helps understand the significance of each trend.""",
            expected_output="""Research findings including:
- Context for each major trend
- Key stakeholders and their interests
- Potential evolution paths
- Historical context where relevant""",
            agent=self.trend_researcher,
            context=[analysis_task],
        )

        # Task 3: Sentiment Analysis
        sentiment_task = Task(
            description="""Analyze the sentiment and public reaction to the trending topics:

1. Determine the overall sentiment (positive, negative, neutral) for each major topic
2. Identify potential controversies or divisive topics
3. Assess audience engagement levels
4. Note any sentiment shifts or emerging reactions

Provide specific sentiment scores and supporting evidence.""",
            expected_output="""Sentiment analysis including:
- Sentiment classification for each topic
- Controversy indicators
- Engagement assessment
- Trend direction for sentiment""",
            agent=self.sentiment_analyzer,
            context=[analysis_task, research_task],
        )

        # Task 4: Executive Report
        report_task = Task(
            description="""Create an executive summary report based on all analysis:

Combine insights from news analysis, research, and sentiment analysis to create:
1. A brief executive summary (2-3 paragraphs)
2. Top 5 trends with key takeaways
3. Risk and opportunity assessment
4. Recommended actions

The report should be clear, concise, and actionable.""",
            expected_output="""Executive report with:
- Executive summary
- Top 5 trends with insights
- Risk/opportunity matrix
- Actionable recommendations""",
            agent=self.report_writer,
            context=[analysis_task, research_task, sentiment_task],
        )

        return [analysis_task, research_task, sentiment_task, report_task]

    def _format_news_for_analysis(self, news_items: list[NewsItem]) -> str:
        """Format news items for analysis by agents.

        Args:
            news_items: List of news items

        Returns:
            Formatted string for agent consumption
        """
        lines = []

        # Group by platform
        by_platform: dict[str, list[NewsItem]] = {}
        for item in news_items:
            if item.platform_name not in by_platform:
                by_platform[item.platform_name] = []
            by_platform[item.platform_name].append(item)

        for platform, items in by_platform.items():
            lines.append(f"\n## {platform}")
            for item in items[:20]:  # Limit to top 20 per platform
                rank_indicator = f"[#{item.rank}]" if item.rank <= 10 else ""
                keywords = ", ".join(item.matched_keywords) if item.matched_keywords else ""
                keyword_str = f" (Keywords: {keywords})" if keywords else ""
                lines.append(f"- {rank_indicator} {item.title}{keyword_str}")

        return "\n".join(lines)

    def analyze(self, news_items: list[NewsItem]) -> NewsAnalysisResult:
        """Analyze news items using the crew.

        Args:
            news_items: List of news items to analyze

        Returns:
            NewsAnalysisResult with analysis findings
        """
        if not news_items:
            return NewsAnalysisResult(
                summary="No news items to analyze.",
                analysis_time=datetime.now(),
            )

        # Create tasks for this specific set of news
        tasks = self._create_analysis_tasks(news_items)

        # Create and run the crew
        crew = Crew(
            agents=[
                self.news_analyst,
                self.trend_researcher,
                self.sentiment_analyzer,
                self.report_writer,
            ],
            tasks=tasks,
            process=Process.sequential,
            verbose=self.config.crewai.verbose,
            memory=self.config.crewai.memory,
        )

        # Execute the crew
        result = crew.kickoff()

        # Parse results
        return self._parse_crew_result(result)

    def _parse_crew_result(self, result: Any) -> NewsAnalysisResult:
        """Parse crew execution result into structured format.

        Args:
            result: Raw result from crew.kickoff()

        Returns:
            NewsAnalysisResult
        """
        raw_output = str(result)

        # Extract sections from the raw output
        analysis_result = NewsAnalysisResult(
            raw_output=raw_output,
            analysis_time=datetime.now(),
        )

        # Try to extract summary
        if "executive summary" in raw_output.lower():
            # Simple extraction - in production, use more sophisticated parsing
            lines = raw_output.split("\n")
            summary_lines = []
            in_summary = False
            for line in lines:
                if "executive summary" in line.lower():
                    in_summary = True
                    continue
                if in_summary:
                    if line.strip().startswith("#") or line.strip().startswith("##"):
                        break
                    if line.strip():
                        summary_lines.append(line.strip())
            analysis_result.summary = " ".join(summary_lines[:5])

        # Extract recommendations if present
        if "recommend" in raw_output.lower():
            lines = raw_output.split("\n")
            for line in lines:
                if line.strip().startswith("-") and "recommend" in line.lower():
                    analysis_result.recommendations.append(line.strip()[1:].strip())
                elif line.strip().startswith("*") and any(
                    word in line.lower() for word in ["should", "consider", "recommend"]
                ):
                    analysis_result.recommendations.append(line.strip()[1:].strip())

        return analysis_result

    async def analyze_async(self, news_items: list[NewsItem]) -> NewsAnalysisResult:
        """Async wrapper for analyze method.

        Args:
            news_items: List of news items to analyze

        Returns:
            NewsAnalysisResult with analysis findings
        """
        import asyncio
        return await asyncio.to_thread(self.analyze, news_items)
