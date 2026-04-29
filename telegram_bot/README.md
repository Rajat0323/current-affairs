# Telegram Current Affairs Bot

A lightweight Python bot that fetches live news, turns it into short current-affairs posts for UPSC and SSC aspirants, generates MCQs with an LLM, and publishes everything to Telegram.

## What it does

- Pulls the latest articles using multiple providers with fallback:
  - `newsdata.io` India-focused query first
  - `newsdata.io` worldwide query second
  - `NewsAPI` worldwide query as an additional fallback
- Uses an OpenAI-compatible LLM API to create:
  - a short readable current-affairs summary
  - "why it matters" points for government exam aspirants
  - 3 practice MCQs
- Posts the summary to a Telegram channel and optionally a Telegram group.
- Sends MCQs as Telegram quiz polls, or you can switch them off and keep them as text.
- Stores posted article URLs in `data/posted_articles.json` to avoid reposting.
- Includes a GitHub Actions workflow for scheduled runs.

## Project structure

```text
telegram_bot/
|-- current_affairs_bot/
|   |-- __init__.py
|   |-- config.py
|   |-- llm_client.py
|   |-- models.py
|   |-- news_client.py
|   |-- service.py
|   |-- state_store.py
|   `-- telegram_client.py
|-- data/
|   `-- posted_articles.json
|-- .env.example
|-- main.py
|-- README.md
`-- requirements.txt
```

## Local setup

1. Create a Telegram bot with BotFather.
2. Add the bot as an admin in your channel and, if needed, in your group.
3. Copy `.env.example` to `.env` and fill in your keys.
4. Install dependencies:

```bash
cd telegram_bot
pip install -r requirements.txt
```

## Local run

Run one cycle:

```bash
python main.py --once
```

Preview content without posting to Telegram:

```bash
python main.py --once --dry-run
```

Run continuously with polling:

```bash
python main.py
```

## GitHub Actions

The workflow file is:

```text
.github/workflows/current-affairs-bot.yml
```

It supports:

- scheduled runs every 15 minutes
- manual runs from the Actions tab
- committing `telegram_bot/data/posted_articles.json` back to the repo so posted-news state survives across runs

### Required repository secrets

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHANNEL_ID`
- `OPENAI_API_KEY`

### Optional repository secrets

- `NEWS_API_KEY`
- `NEWSDATA_API_KEY`
- `TELEGRAM_GROUP_ID`
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`

Set at least one of `NEWS_API_KEY` or `NEWSDATA_API_KEY`.

### Optional repository variables

- `CURRENT_AFFAIRS_QUERY`
- `NEWSDATA_INDIA_QUERY`
- `NEWSDATA_WORLD_QUERY`
- `NEWSDATA_INDIA_COUNTRY`
- `NEWS_PAGE_SIZE`
- `MAX_ARTICLES_PER_CYCLE`
- `REQUEST_TIMEOUT_SECONDS`

If `OPENAI_MODEL` is not set, the bot defaults to `gpt-4.1-mini`.

## Notes

- This project uses direct Telegram Bot API calls, so there is no heavy Telegram framework to maintain.
- "Real time" here means scheduled polling. Adjust the GitHub Actions cron or local run mode as needed.
- The default query is broad. You should tune it further for polity, economy, science-tech, international relations, environment, and sports.

