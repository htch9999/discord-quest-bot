# Discord Quest Bot — Walkthrough

## What Was Built

Converted the monolithic 873-line [main.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/main.py) CLI script into a modular **Discord bot** with 20+ files across 4 layers:

| Layer | Files | Purpose |
|---|---|---|
| **Config** | [config.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/config.py), [.env.example](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/.env.example) | Environment-based configuration |
| **Database** | [models.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/db/models.py), [database.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/db/database.py) | SQLite with `aiosqlite`, 4 tables |
| **Core** | [discord_api.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/core/discord_api.py), [quest_engine.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/core/quest_engine.py), [task_manager.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/core/task_manager.py) | Async API client, quest logic, concurrency |
| **Services** | [crypto.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/services/crypto.py), [scheduler.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/services/scheduler.py), [progress_message.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/services/progress_message.py), [rate_limiter.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/services/rate_limiter.py) | Encryption, scheduling, live embeds, limits |
| **Cogs** | [quests.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/cogs/quests.py), [autoquests.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/cogs/autoquests.py), [info.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/cogs/info.py), [admin.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/cogs/admin.py) | Slash commands |
| **Utils** | [token_mask.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/utils/token_mask.py), [logger.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/utils/logger.py), [formatter.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/utils/formatter.py) | Token masking, logging, embed builders |

## Key Design Decisions

- **Async throughout**: Replaced `requests` → `aiohttp`, `threading` → `asyncio.Task`, `time.sleep` → `asyncio.sleep`
- **Callback-based progress**: [QuestEngine](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/core/quest_engine.py#141-627) uses [on_progress](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/cogs/autoquests.py#434-436)/[on_complete](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/cogs/quests.py#164-172) callbacks to decouple from Discord embeds
- **Per-user key derivation**: `PBKDF2(MASTER_SECRET + discord_uid)` ensures tokens can't be cross-decrypted

## Test Results

```
IMPORTS: ALL PASSED
DB: ALL TESTS PASSED
RATE LIMITER: ALL TESTS PASSED
TOKEN MASK: ALL TESTS PASSED

=== ALL VERIFICATION TESTS PASSED ===
```

## Next Steps

1. Copy [.env.example](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/.env.example) → `.env` and fill in `BOT_TOKEN` and `MASTER_SECRET`
2. Run: `python -m bot.main`
