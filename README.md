<div align="center">

# Discord Quest Bot

**Tự động hoàn thành mọi quest Discord — bảo mật, song song, real-time.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![Discord.py](https://img.shields.io/badge/discord.py-2.3+-blue.svg)](https://discordpy.readthedocs.io)

[Add to Discord](#) · [Join Server](#) · [Website](https://ctdoteam.github.io/discord-quest-bot/) · [Self-host Guide](#self-host)

</div>

---

## Features

| Feature                    | Description                                            |
| -------------------------- | ------------------------------------------------------ |
| **Parallel Execution**     | Up to 6 quests simultaneously with isolated threads    |
| **AES-256-GCM Encryption** | Per-user derived keys. Token never touches a log       |
| **Auto Scheduler**         | Runs every 2 days, DMs results automatically           |
| **Live Progress**          | Single message, real-time updates with progress bars   |
| **Token Security**         | Ephemeral commands, masked display, zero exposure      |
| **All Quest Types**        | WATCH_VIDEO · PLAY_ON_DESKTOP · STREAM · PLAY_ACTIVITY |
| **Crash Recovery**         | Interrupted sessions resume automatically              |
| **Open Source**            | 100% public source code, self-host ready               |

## Quick Start

### Use the public bot

1. [Invite the bot](#) to your server
2. Run `/quests <your_discord_token>` for one-time execution
3. Or `/autoquests <token> [label]` for automatic scheduling

### Self-host

```bash
# Clone
git clone https://github.com/ctdoteam/discord-quest-bot.git
cd discord-quest-bot

# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
nano .env  # Fill in BOT_TOKEN and MASTER_SECRET

# Run
python -m bot.main
```

## Commands

### One-time

| Command           | Description                          |
| ----------------- | ------------------------------------ |
| `/quests <token>` | Run quests once, token is NOT stored |
| `/help`           | Detailed usage guide                 |

### Auto (saved token)

| Command                       | Description                        |
| ----------------------------- | ---------------------------------- |
| `/autoquests <token> [label]` | Save token + auto-run every 2 days |
| `/autoquests run [label]`     | Manual run immediately             |
| `/autoquests pause [label]`   | Pause auto-schedule                |
| `/autoquests resume [label]`  | Resume auto-schedule               |

### Management

| Command                          | Description                        |
| -------------------------------- | ---------------------------------- |
| `/autoquests list`               | List saved tokens                  |
| `/autoquests remove <label>`     | Delete token + all associated data |
| `/autoquests rename <old> <new>` | Rename a token label               |

### Info

| Command                      | Description          |
| ---------------------------- | -------------------- |
| `/autoquests status [label]` | Token status details |
| `/autoquests-info`           | Personal statistics  |
| `/info`                      | Bot system info      |

## Architecture

```
bot/
├── main.py              # Entry point + FastAPI integration
├── config.py            # Environment config
├── api/
│   └── stats_router.py  # Public stats API (4 endpoints)
├── cogs/
│   ├── quests.py        # /quests command
│   ├── autoquests.py    # /autoquests commands
│   ├── info.py          # /info, /autoquests-info
│   ├── admin.py         # Admin commands
│   └── help.py          # /help command
├── core/
│   └── task_manager.py  # Async task orchestration
├── db/
│   ├── database.py      # SQLite operations
│   └── models.py        # Schema definitions
├── services/
│   ├── quest_engine.py  # Quest completion logic
│   ├── scheduler.py     # APScheduler integration
│   └── rate_limiter.py  # Token bucket rate limiter
└── utils/
    ├── crypto.py        # AES-256-GCM encryption
    ├── formatter.py     # Embed builders
    └── logger.py        # Structured logging
```

## API Endpoints

The bot includes a built-in FastAPI server (port 8099) for the website:

| Endpoint               | Description         | Cache |
| ---------------------- | ------------------- | ----- |
| `GET /v1/stats/public` | Aggregate stats     | 30s   |
| `GET /v1/stats/server` | Guild/member counts | 30s   |
| `GET /v1/health`       | System health       | none  |
| `GET /v1/github`       | GitHub repo stats   | 5min  |

## Security

- **Encryption**: AES-256-GCM with PBKDF2 key derivation (260,000 iterations)
- **Per-user keys**: Derived from `MASTER_SECRET` + Discord user ID
- **Zero logging**: Token never appears in any log output
- **Ephemeral commands**: All responses visible only to the command user
- **Masked display**: Tokens shown as `MTA...xyz` in any UI

> **Warning**: `MASTER_SECRET` loss = irreversible token loss. Back it up.

## Deployment

### Systemd service

```bash
sudo cp quest-bot.service /etc/systemd/system/
sudo systemctl enable quest-bot.service
sudo systemctl start quest-bot.service
```

### Docker

```bash
docker build -t quest-bot .
docker run -d --env-file .env quest-bot
```

### Website (GitHub Pages)

The `website/` directory contains the static frontend. Push to GitHub and enable Pages from the `gh-pages` branch, or use the included workflow:

```bash
# The workflow at .github/workflows/deploy-pages.yml
# auto-deploys website/ to GitHub Pages on push to main
```

## Environment Variables

| Variable        | Required | Default             | Description           |
| --------------- | -------- | ------------------- | --------------------- |
| `BOT_TOKEN`     | Yes      | —                   | Discord bot token     |
| `MASTER_SECRET` | Yes      | —                   | Encryption master key |
| `DB_PATH`       | No       | `data/quest_bot.db` | SQLite database path  |
| `API_PORT`      | No       | `8099`              | FastAPI server port   |
| `API_HOST`      | No       | `127.0.0.1`         | FastAPI bind address  |

See `.env.example` for all available options.

## License

MIT — see [LICENSE](LICENSE)

## Disclaimer

This project is not affiliated with Discord Inc. Use at your own discretion. Any automation carries inherent risk.

---

<div align="center">
Made by <a href="https://github.com/htch9999">@htch9999🌷</a>
</div>
