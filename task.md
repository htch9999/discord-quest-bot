# Discord Quest Bot — Task Tracker

## Phase 1: Foundation
- [x] [config.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/config.py) — env vars, constants
- [x] [.env.example](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/.env.example) — template
- [x] [db/models.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/db/models.py) + [db/database.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/db/database.py) — SQLite schema & async handler
- [x] [services/crypto.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/services/crypto.py) — AES-256-GCM token encryption
- [x] [core/discord_api.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/core/discord_api.py) — async DiscordAPI class
- [x] [core/quest_engine.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/core/quest_engine.py) — async QuestEngine with callbacks
- [x] [utils/token_mask.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/utils/token_mask.py) — mask tokens in logs
- [x] [utils/logger.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/utils/logger.py) — per-user isolated logger

## Phase 2: Bot Core
- [x] [bot/main.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/main.py) — bot init, cog loader, on_ready
- [x] [services/progress_message.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/services/progress_message.py) — live Discord embed updater
- [x] [core/task_manager.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/core/task_manager.py) — async task isolation, semaphore, locks
- [x] [cogs/quests.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/cogs/quests.py) — `/quests {token}` slash command

## Phase 3: Auto System
- [x] [services/scheduler.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/services/scheduler.py) — APScheduler background job
- [x] [cogs/autoquests.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/cogs/autoquests.py) — `/autoquests` + sub-commands
- [x] [cogs/info.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/cogs/info.py) — `/info`, `/autoquests-info`

## Phase 4: Polish
- [x] [utils/formatter.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/utils/formatter.py) — embed templates
- [x] [services/rate_limiter.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/services/rate_limiter.py) — per-user rate limiting
- [x] [cogs/admin.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/cogs/admin.py) — admin commands
- [x] [requirements.txt](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/requirements.txt)
- [x] [docker-compose.yml](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/docker-compose.yml) + [Dockerfile](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/Dockerfile) + [README.md](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/README.md)

## Verification
- [x] Dependencies installed
- [x] All module imports verified
- [x] Crypto encrypt/decrypt roundtrip
- [x] Database CRUD operations
- [x] Rate limiter logic
- [x] Token masking
- [ ] Bot startup with valid BOT_TOKEN (requires user config)
