# 📚 UPSC/SSC Current Affairs Telegram Bot

A production-ready Python bot that automatically fetches India-focused current affairs,
filters them for UPSC/SSC relevance, formats them for exam preparation, and sends them
to your Telegram channel three times a day.

---

## 🗂️ Project Structure

```
telegram_bot/
├── main.py           # Entry point — scheduler & CLI
├── config.py         # All configuration & environment variables
├── news_fetcher.py   # NewsAPI integration & topic filtering
├── formatter.py      # UPSC-format message generator
├── bot.py            # Telegram sender
├── scheduler.py      # APScheduler jobs (morning/afternoon/evening)
├── requirements.txt  # Python dependencies
├── .env.example      # Template for environment variables
└── README.md         # This file
```

---

## ⚙️ Setup Instructions

### Step 1 — Prerequisites

- Python 3.10 or higher
- `pip` (Python package manager)

```bash
python --version   # Should be 3.10+
```

### Step 2 — Get Your API Keys

#### 2a. NewsAPI Key (free)
1. Go to https://newsapi.org/register
2. Sign up for a free account
3. Copy your API key from the dashboard

#### 2b. Telegram Bot Token
1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy the token (looks like `7123456789:AAFxxx...`)

#### 2c. Telegram Channel ID
1. Create a Telegram channel (or use an existing one)
2. Add your bot as an **administrator** of the channel
3. For a **public channel**: use `@channelname`
4. For a **private channel**:
   - Forward any message from the channel to **@userinfobot**
   - The ID starts with `-100...`

---

### Step 3 — Install Dependencies

```bash
cd telegram_bot
pip install -r requirements.txt
```

### Step 4 — Configure Environment Variables

```bash
cp .env.example .env
```

Open `.env` and fill in your keys:

```dotenv
NEWS_API_KEY=your_newsapi_key_here
TELEGRAM_BOT_TOKEN=7123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TELEGRAM_CHANNEL_ID=@yourchannel
```

---

### Step 5 — Verify Setup

Send a test message to confirm everything works:

```bash
python main.py --test
```

You should see: `✅ Test message sent successfully!`
And a confirmation message in your Telegram channel.

---

### Step 6 — Start the Bot

```bash
python main.py
```

The bot runs continuously and sends messages on schedule:
| Time (IST) | Content |
|------------|---------|
| 07:00 AM | 🌅 Daily Current Affairs Summary |
| 01:00 PM | 📝 MCQ Quiz (4 options per question) |
| 07:00 PM | 🌙 Quick Revision Recap |

---

## 🚀 Running Jobs Manually

```bash
# Run all three jobs right now (for testing)
python main.py --now

# Run only the morning job
python main.py --morning

# Run only the afternoon MCQ quiz
python main.py --afternoon

# Run only the evening revision
python main.py --evening
```

---

## 🔄 Running as a Background Service (Linux/Server)

To keep the bot running even after you close the terminal:

```bash
# Using nohup
nohup python main.py > upsc_bot.log 2>&1 &

# Or with screen
screen -S upsc_bot
python main.py
# Press Ctrl+A, then D to detach
```

---

## 📱 Example Output Messages

### 🌅 Morning Current Affairs Card

```
━━━━━━━━━━━━━━━━━━━━━━━
🏛️ CURRENT AFFAIRS | Government Schemes & Policies
━━━━━━━━━━━━━━━━━━━━━━━

📌 Cabinet Approves PM Surya Ghar Muft Bijli Yojana

🔑 Key Points:
  • Key development: Cabinet Approves PM Surya Ghar Muft Bijli Yojana
  • The scheme aims to provide 300 units of free electricity per month to one crore households.
  • Target beneficiaries include middle-class and lower-income families.
  • Implementation will be via solar rooftop installations with central subsidy support.

🎯 Why Important for Exam?
  High-priority for both UPSC and SSC. Remember the ministry, launch year,
  objective, and target beneficiaries.

📡 Source: The Hindu
🔗 Read more
```

### 📝 Afternoon MCQ Quiz

```
Q1. Which Indian ministry is most likely associated with:
    "Cabinet Approves PM Surya Ghar Muft Bijli Yojana"?
  (A) Ministry of Finance / relevant line ministry
  (B) Ministry of External Affairs
  (C) Ministry of Home Affairs
  (D) Ministry of Defence
  Topic: Government Schemes & Policies
  ✅ Answer: (A)   ← tap to reveal
```

### 🌙 Evening Revision

```
🏛️ 1. Government Schemes & Policies
   📌 Cabinet Approves PM Surya Ghar Muft Bijli Yojana
    ▸ Key development: Cabinet Approves PM Surya Ghar Muft Bijli Yojana.
    ▸ The scheme provides 300 units of free electricity per month.
    ▸ Targets one crore households via solar rooftop installations.
```

---

## 🛠️ Customisation

### Change Schedule Timing

Edit `config.py`:

```python
MORNING_HOUR   = 6    # Change to 6 AM
AFTERNOON_HOUR = 14   # Change to 2 PM
EVENING_HOUR   = 21   # Change to 9 PM
```

### Add/Remove Topic Filters

In `config.py`, edit `UPSC_RELEVANT_KEYWORDS` or `IRRELEVANT_KEYWORDS`.

### Increase Number of Articles

```python
NEWS_API_MAX_ARTICLES = 8  # Default is 5
```

---

## 📊 Logs

All activity is logged to:
- **Console** (stdout) — real-time
- **`upsc_bot.log`** — persistent log file

Log format: `2024-04-28 07:00:01 | INFO     | scheduler — Morning Current Affairs Digest`

---

## ❓ Troubleshooting

| Problem | Solution |
|---------|----------|
| `Missing required environment variables` | Copy `.env.example` → `.env` and fill in keys |
| `Telegram API error: Forbidden` | Make sure your bot is added as admin to the channel |
| `NewsAPI returned 0 articles` | Check your API key; free tier has 100 requests/day |
| Bot stops after closing terminal | Use `nohup` or `screen` as shown above |
| Messages not appearing | Run `python main.py --test` to debug connectivity |

---

## 📄 License

MIT — free to use, modify, and distribute.
