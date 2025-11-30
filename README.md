# TrendRadar AI

AI-powered trending news aggregation and analysis system using CrewAI.

## Features

- **Multi-Platform News Aggregation**: Monitors 11+ platforms including Zhihu, Weibo, Douyin, Bilibili, Baidu, and more
- **AI-Powered Analysis**: Uses CrewAI agents for intelligent news analysis, trend detection, and sentiment analysis
- **Smart Filtering**: Keyword-based filtering with support for required words, exclude words, and count limits
- **Multi-Channel Notifications**: Push to WeChat Work, Feishu, DingTalk, Telegram, Slack, Email, ntfy, and Bark
- **Flexible Push Modes**: Daily summary, current rankings, or incremental updates
- **Web Reports**: Beautiful HTML reports optimized for both desktop and mobile
- **Easy Deployment**: GitHub Actions, Docker, or local execution

## Quick Start

### 30-Second Deployment (GitHub Actions)

1. Fork this repository
2. Go to Settings > Secrets and variables > Actions
3. Add your notification webhook URL (e.g., `WEWORK_WEBHOOK_URL`)
4. The workflow runs automatically every hour!

### Enable GitHub Pages (Optional)

1. Go to Settings > Pages
2. Source: Deploy from a branch
3. Branch: main, /root
4. Your report will be available at `https://YOUR_USERNAME.github.io/trendradar-ai/`

## Configuration

### Notification Platforms

| Platform | Secret Name | Description |
|----------|-------------|-------------|
| WeChat Work | `WEWORK_WEBHOOK_URL` | Group bot webhook URL |
| Feishu | `FEISHU_WEBHOOK_URL` | Feishu bot webhook URL |
| DingTalk | `DINGTALK_WEBHOOK_URL` | DingTalk bot webhook URL |
| Telegram | `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` | Bot token and chat ID |
| Slack | `SLACK_WEBHOOK_URL` | Incoming webhook URL |
| Email | `EMAIL_FROM` + `EMAIL_PASSWORD` + `EMAIL_TO` | SMTP credentials |
| ntfy | `NTFY_TOPIC` | ntfy.sh topic name |
| Bark | `BARK_URL` | Bark push URL |

### AI Analysis (Optional)

Add your OpenAI API key to enable AI-powered analysis:

```
OPENAI_API_KEY=sk-...
```

### Push Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `daily` | Push all matched news of the day | Daily summary |
| `current` | Push current ranking matches | Real-time tracking |
| `incremental` | Push only new items | Avoid duplicates |

### Keyword Filtering

Edit `config/frequency_words.txt`:

```text
# Basic matching
AI
Bitcoin

# Required words (all must appear)
+machine learning
+investment

# Exclude words
!advertisement
!promotion

# Limit display count
AI@5
Bitcoin@3

# Group keywords with blank lines
```

## Local Development

### Prerequisites

- Python 3.10+
- uv (recommended) or pip

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/trendradar-ai.git
cd trendradar-ai

# Install with uv (recommended)
uv pip install -e .

# Or with pip
pip install -e .
```

### Run

```bash
# Copy environment file
cp .env.example .env
# Edit .env with your configuration

# Run the crawler
python -m src.main

# Run without AI analysis
python -m src.main --no-ai

# Force send notifications
python -m src.main --force-notify
```

## Docker Deployment

### Quick Start

```bash
# Run with Docker
docker run -d \
  --name trendradar-ai \
  -e WEWORK_WEBHOOK_URL="your_webhook_url" \
  -e REPORT_MODE="daily" \
  -v $(pwd)/output:/app/output \
  trendradar-ai
```

### Docker Compose

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ENABLE_CRAWLER` | Enable news fetching | `true` |
| `REPORT_MODE` | Push mode (daily/current/incremental) | `daily` |
| `PUSH_WINDOW_ENABLED` | Enable time window control | `false` |
| `PUSH_WINDOW_START` | Window start time | `09:00` |
| `PUSH_WINDOW_END` | Window end time | `18:00` |

## Project Structure

```
trendradar-ai/
├── src/
│   ├── agents/          # CrewAI agents for analysis
│   ├── crawlers/        # News crawlers
│   ├── notifiers/       # Notification handlers
│   ├── utils/           # Configuration and utilities
│   ├── main.py          # Application entry point
│   └── reporter.py      # Report generation
├── config/
│   ├── config.yaml      # Main configuration
│   └── frequency_words.txt  # Keyword filters
├── templates/
│   └── report.html      # HTML report template
├── output/              # Generated reports
├── .github/workflows/
│   └── crawler.yml      # GitHub Actions workflow
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## CrewAI Agents

TrendRadar AI uses four specialized agents:

1. **News Analyst**: Identifies patterns, themes, and key trends
2. **Trend Researcher**: Provides context and background information
3. **Sentiment Analyzer**: Analyzes public sentiment and reactions
4. **Report Writer**: Creates executive summaries and recommendations

## API Reference

### Main Application

```python
from src.main import TrendRadarApp

app = TrendRadarApp(config_path="config/config.yaml")
await app.run(enable_ai=True, force_notify=False)
```

### News Aggregator

```python
from src.crawlers import NewsAggregator
from src.utils import load_config

config = load_config()
aggregator = NewsAggregator(config)
news = await aggregator.fetch_all()
```

### Notification Manager

```python
from src.notifiers import NotificationManager

manager = NotificationManager(config)
summary = await manager.send_all(content, title="TrendRadar Report")
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Inspired by [TrendRadar](https://github.com/sansan0/TrendRadar)
- Built with [CrewAI](https://github.com/joaomdmoura/crewAI)
- News API provided by [newsnow](https://github.com/ourongxing/newsnow)
