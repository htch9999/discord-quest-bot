# Discord Quest Bot — Implementation Plan

Chuyển đổi script đơn file [main.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/main.py) (873 dòng) thành Discord bot modular theo kiến trúc AGENT.md, sử dụng `discord.py` v2.x với slash commands, SQLite database, AES-256-GCM token encryption, và APScheduler.

## User Review Required

> [!IMPORTANT]
> **Bot Token**: Bạn cần cung cấp Discord Bot Token trong file `.env` (biến `BOT_TOKEN`). Bot phải được tạo trên [Discord Developer Portal](https://discord.com/developers/applications) với các permissions: `Send Messages`, `Embed Links`, `Use Slash Commands`.

> [!WARNING]
> **MASTER_SECRET**: File `.env` cần có `MASTER_SECRET` (chuỗi ngẫu nhiên dài ≥32 ký tự) để mã hóa token. Nếu mất key này, tất cả token đã lưu sẽ không giải mã được.

> [!CAUTION]
> **Self-bot Risk**: Script gốc sử dụng user token để tương tác với Discord API. Điều này vi phạm Discord ToS. Bot mới sẽ giữ nguyên cơ chế này (theo yêu cầu), nhưng hãy cân nhắc rủi ro.

---

## Proposed Changes

### Phase 1: Foundation

#### [NEW] [config.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/config.py)
- Load `.env` via `python-dotenv`
- Constants: `API_BASE`, `POLL_INTERVAL`, `HEARTBEAT_INTERVAL`, `MAX_PARALLEL_PLAY`, `SUPPORTED_TASKS`, `MASTER_SECRET`, `BOT_TOKEN`, `DB_PATH`, `MAX_CONCURRENT_TASKS`, `TASK_TIMEOUT_HOURS`

#### [NEW] [.env.example](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/.env.example)
- Template: `BOT_TOKEN`, `MASTER_SECRET`, `DB_PATH`, `DEBUG`

---

#### [NEW] [models.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/db/models.py)
- Define SQL schema strings: `saved_tokens`, `quest_stats`, `global_stats`, `run_sessions` (theo AGENT.md §2)

#### [NEW] [database.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/db/database.py)
- `Database` class using `aiosqlite`
- Methods: [init()](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/main.py#293-310), `save_token()`, `get_tokens()`, `remove_token()`, `rename_token()`, `update_run_times()`, `get_due_tokens()`, `save_quest_stat()`, `get_stats()`, `update_global_stat()`, `create_session()`, `update_session()`

---

#### [NEW] [crypto.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/services/crypto.py)
- `encrypt_token(token, discord_uid)` → base64 encoded `salt+nonce+ciphertext+tag`
- `decrypt_token(encrypted, discord_uid)` → plain token
- Key derivation: `PBKDF2(MASTER_SECRET + discord_uid, salt, 260000)` → AES-256-GCM

---

#### [NEW] [discord_api.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/core/discord_api.py)
- Port [DiscordAPI](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/main.py#134-186) class từ [main.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/main.py) (giữ nguyên logic)
- Port [fetch_latest_build_number()](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/main.py#67-106) và [make_super_properties()](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/main.py#108-131)
- Thay `requests.Session` bằng `aiohttp.ClientSession` cho async

#### [NEW] [quest_engine.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/core/quest_engine.py)
- Port toàn bộ helper functions: [_get](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/main.py#189-197), [get_task_config](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/main.py#199-202), [get_quest_name](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/main.py#204-217), [get_expires_at](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/main.py#219-222), etc.
- Port [QuestAutocompleter](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/main.py#292-831) class, refactor thành async
- Thêm callback `on_progress(quest_id, done, total)` để `progress_message.py` cập nhật embed
- Thêm callback `on_complete(quest_id, name, duration)` để ghi stats

---

#### [NEW] [token_mask.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/utils/token_mask.py)
- `mask_token(token)` → `...xxxx` (4 ký tự cuối)
- `mask_in_text(text)` → replace any token-like pattern

#### [NEW] [logger.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/utils/logger.py)
- `get_logger(name)` → Python `logging.Logger` with file rotation
- Token-masking filter tự động

---

### Phase 2: Bot Core

#### [NEW] [main.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/main.py)
- `discord.py` Bot init with `commands.Bot`
- Cog auto-loader
- `on_ready` event
- Error handlers

#### [NEW] [progress_message.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/services/progress_message.py)
- `ProgressMessage` class
- Tạo embed ban đầu → lưu `message_id`
- Background task cập nhật embed mỗi 5s (debounce)
- Format embed theo AGENT.md §6

#### [NEW] [task_manager.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/core/task_manager.py)
- `TaskManager` class: `running_tasks`, `user_locks`, `global_semaphore`
- `start_quest_run(uid, token, channel, ...)` → spawn async task
- `cancel_task(uid, token_id)` → cancel running task
- Per-user lock, global semaphore (max concurrent from config)

#### [NEW] [quests.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/cogs/quests.py)
- `/quests {token}` slash command
- Ephemeral response → delete interaction
- Spawn quest completion task via TaskManager
- Live progress via ProgressMessage

---

### Phase 3: Auto System

#### [NEW] [scheduler.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/services/scheduler.py)
- APScheduler async mode
- Check DB mỗi 1 giờ cho tokens có `next_run_at <= now AND is_active = 1`
- Jitter ±30 phút
- Sau mỗi run: update `last_run_at`, `next_run_at = now + 2 days`
- Token invalid (401) → `is_active = 0`, DM user
- DM user kết quả

#### [NEW] [autoquests.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/cogs/autoquests.py)
- `/autoquests {token} [label]` — lưu + chạy ngay
- `/autoquests list` — hiển thị tokens (hint only)
- `/autoquests remove {label}` — xóa token
- `/autoquests rename {label} {new_label}`
- `/autoquests status [label]` — tiến độ
- `/autoquests run [label]` — chạy thủ công
- `/autoquests pause [label]` / `resume [label]`

#### [NEW] [info.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/cogs/info.py)
- `/info` — system stats embed (users, quests done, ping, uptime, OS stats)
- `/autoquests-info` — per-user stats

---

### Phase 4: Polish

#### [NEW] [formatter.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/utils/formatter.py)
- Embed templates: quest list, progress, completion summary, error

#### [NEW] [rate_limiter.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/services/rate_limiter.py)
- Per-user: max 5 runs/hour
- Per-command cooldown

#### [NEW] [admin.py](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/bot/cogs/admin.py)
- `/admin force-run {user_id}`
- `/admin ban {user_id}`
- `/admin stats`

#### [NEW] [requirements.txt](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/requirements.txt)
- `discord.py>=2.3`, `aiohttp`, `aiosqlite`, `cryptography`, `APScheduler`, `python-dotenv`, `psutil`

#### [NEW] [docker-compose.yml](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/docker-compose.yml)

#### [NEW] [README.md](file:///c:/Users/HTCH/Desktop/DIscord%20Auto%20Quests%20-%20Bot/README.md)

---

## Verification Plan

### Automated Tests

1. **Bot startup test** — Chạy `python -m bot.main` và kiểm tra bot kết nối thành công (log "on_ready")
```
cd "c:\Users\HTCH\Desktop\DIscord Auto Quests - Bot"
python -m bot.main
```

2. **Crypto unit test** — Verify encrypt/decrypt roundtrip
```
python -c "from bot.services.crypto import encrypt_token, decrypt_token; enc = encrypt_token('test_token', '123456'); assert decrypt_token(enc, '123456') == 'test_token'; print('PASS')"
```

3. **Database unit test** — Verify tables create, CRUD operations
```
python -c "import asyncio; from bot.db.database import Database; db = Database(':memory:'); asyncio.run(db.init()); print('DB init PASS')"
```

4. **Import test** — Verify all modules import cleanly
```
python -c "from bot.config import *; from bot.db.database import Database; from bot.services.crypto import encrypt_token, decrypt_token; from bot.core.discord_api import DiscordAPI; from bot.core.quest_engine import QuestEngine; from bot.utils.token_mask import mask_token; from bot.utils.logger import get_logger; print('ALL IMPORTS PASS')"
```

### Manual Verification

1. **Slash command test**: Sau khi bot chạy, vào Discord server → gõ `/quests` → kiểm tra bot phản hồi ephemeral
2. **Auto-quest test**: Gõ `/autoquests` với token → kiểm tra token được lưu DB (encrypted) và scheduled
3. **Info test**: Gõ `/info` → kiểm tra embed hiển thị đúng stats

> [!NOTE]
> Manual tests yêu cầu Bot Token hợp lệ trong `.env`. Hãy cấu hình trước khi test.
