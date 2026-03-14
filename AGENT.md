# Kế hoạch xây dựng Discord Quest Bot

## 1. Tổng quan kiến trúc

```
discord-quest-bot/
├── bot/
│   ├── main.py                 # Entry point, bot init
│   ├── cogs/
│   │   ├── quests.py           # /quests command
│   │   ├── autoquests.py       # /autoquests + sub-commands
│   │   ├── info.py             # /info, /autoquests-info
│   │   └── admin.py            # Admin commands
│   ├── core/
│   │   ├── quest_engine.py     # Toàn bộ logic từ script gốc
│   │   ├── task_manager.py     # Quản lý đa luồng/task
│   │   └── discord_api.py      # DiscordAPI class (giữ nguyên)
│   ├── db/
│   │   ├── database.py         # SQLite/PostgreSQL handler
│   │   ├── models.py           # Schema definitions
│   │   └── migrations/
│   ├── services/
│   │   ├── crypto.py           # Mã hoá/giải mã token
│   │   ├── scheduler.py        # Cron job kiểm tra 2 ngày/lần
│   │   ├── progress_message.py # Live-edit message handler
│   │   └── rate_limiter.py     # Global rate limit manager
│   ├── utils/
│   │   ├── token_mask.py       # Che token trong log/message
│   │   ├── formatter.py        # Discord embed builder
│   │   └── logger.py           # Per-user isolated logger
│   └── config.py               # Env vars, constants
├── .env
├── requirements.txt
└── docker-compose.yml
```

---

## 2. Database Schema

```sql
-- Bảng lưu token đã mã hoá
CREATE TABLE saved_tokens (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_uid TEXT NOT NULL,          -- ID người dùng Discord
    label       TEXT DEFAULT 'default', -- Tên gợi nhớ
    token_enc   BLOB NOT NULL,          -- Token đã mã hoá AES-256
    token_hint  TEXT,                   -- 4 ký tự cuối để nhận diện (VD: ...a1b2)
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_run_at DATETIME,
    next_run_at DATETIME,               -- Lần chạy tiếp theo (2 ngày)
    is_active   BOOLEAN DEFAULT 1,
    UNIQUE(discord_uid, label)
);

-- Bảng thống kê nhiệm vụ
CREATE TABLE quest_stats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    token_id        INTEGER REFERENCES saved_tokens(id),
    discord_uid     TEXT NOT NULL,
    quest_id        TEXT NOT NULL,
    quest_name      TEXT,
    task_type       TEXT,
    completed_at    DATETIME,
    duration_secs   INTEGER,           -- Thời gian hoàn thành
    run_mode        TEXT               -- 'once' | 'auto'
);

-- Bảng global stats
CREATE TABLE global_stats (
    key   TEXT PRIMARY KEY,
    value TEXT
);
-- Ghi nhận: total_quests_done, total_users, ...

-- Bảng run sessions (tracking tiến độ real-time)
CREATE TABLE run_sessions (
    id              TEXT PRIMARY KEY,  -- UUID
    discord_uid     TEXT,
    token_id        INTEGER,
    channel_id      TEXT,
    message_id      TEXT,              -- ID tin nhắn bot đang edit
    started_at      DATETIME,
    finished_at     DATETIME,
    status          TEXT,              -- 'running' | 'done' | 'error'
    summary         TEXT               -- JSON tóm tắt kết quả
);
```

---

## 3. Mã hoá Token (`services/crypto.py`)

**Nguyên tắc:** Mỗi token được mã hoá bằng khóa dẫn xuất từ `(MASTER_KEY + discord_user_id)` — nghĩa là dù database bị lộ, kẻ tấn công cũng không thể giải mã token của user A bằng key của user B.

```
Key = PBKDF2(MASTER_SECRET + discord_uid, salt, iterations=260000)
Encrypt = AES-256-GCM(Key, token)
Store = base64(salt + nonce + ciphertext + tag)
```

- `MASTER_SECRET` lưu trong `.env`, không commit lên git
- Token hint (4 ký tự cuối) lưu plain để hiển thị trong `/list`

---

## 4. Chi tiết từng lệnh

### `/quests {token}` — Chạy một lần, không lưu

```
Luồng xử lý:
1. Nhận slash command → xoá tin nhắn của user ngay lập tức (ephemeral reply)
2. Validate token format cơ bản (regex)
3. Tạo LiveMessage (1 embed) → gửi vào DM của user (private) hoặc ephemeral
4. Spawn task async:
   a. Validate token qua Discord API
   b. Fetch quests → hiển thị danh sách
   c. Auto-enroll → hoàn thành từng quest
   d. Edit embed mỗi HEARTBEAT_INTERVAL giây
5. Kết thúc → cập nhật embed "✅ Hoàn thành" + tổng kết
6. Token không được ghi bất cứ đâu vào đĩa/DB
```

**Bảo mật slash command:** Discord gửi token trong interaction data — cần bật `ephemeral=True` và xoá interaction gốc ngay để token không hiển thị trong channel.

---

### `/autoquests {token} [label]` — Lưu & tự động

```
Luồng xử lý:
1. Ephemeral reply ngay (chỉ user thấy)
2. Validate + kiểm tra trùng label
3. Mã hoá token → lưu DB
4. Chạy ngay lần đầu (fork sang task_manager)
5. Lên lịch next_run_at = now + 2 ngày
6. Reply ephemeral: "✅ Đã lưu token ...a1b2 với tên 'label'"
```

---

### Các lệnh `/autoquests-*` (sub-commands)

| Lệnh | Chức năng |
|---|---|
| `/autoquests list` | Hiển thị danh sách token đã lưu của user (ephemeral), chỉ thấy hint 4 ký tự |
| `/autoquests remove {label}` | Xoá token + stats liên quan (soft delete) |
| `/autoquests rename {label} {new_label}` | Đổi tên gợi nhớ |
| `/autoquests status [label]` | Xem tiến độ: đã hoàn thành X quest, chưa làm Y, lần chạy cuối/tiếp theo |
| `/autoquests run [label]` | Chạy thủ công ngay (không chờ lịch) |
| `/autoquests pause [label]` | Tạm dừng auto-schedule |
| `/autoquests resume [label]` | Bật lại auto-schedule |
| `/autoquests-info` | Thống kê tổng: số token lưu, tổng quest đã làm, next scheduled run |

---

### `/info` — Thông tin server bot

```
Hiển thị embed:
├── 👥 Tổng người dùng: X
├── ✅ Tổng quest đã hoàn thành: Y
├── 🖥️  Servers tham gia: Z
├── 📡 Ping: Xms (WebSocket latency)
├── ⏱️  Uptime: X ngày Y giờ
├── 💻 OS: Ubuntu 22.04 / CPU: X% / RAM: X/XGB
├── 💾 Storage: X/XGB
└── 🔧 Version: v1.0.0
```

---

## 5. Task Manager & Đa luồng (`core/task_manager.py`)

```
Thiết kế:
- Mỗi user có namespace riêng (keyed by discord_uid)
- Dùng asyncio + ThreadPoolExecutor cho quest engine
- Semaphore global giới hạn tổng số quest đang chạy (tránh OOM)
- Per-user lock: tránh 1 user spawn 2 task cùng lúc cho cùng 1 token
- Log isolation: mỗi task có logger riêng, không lẫn với task khác

TaskManager:
  running_tasks: Dict[str, asyncio.Task]  # uid+token_id → Task
  user_locks: Dict[str, asyncio.Lock]     # uid → Lock
  global_semaphore: asyncio.Semaphore     # max concurrent = config
```

---

## 6. Live Progress Message (`services/progress_message.py`)

```
Cơ chế:
- Gửi 1 embed ban đầu → lưu message_id
- Background coroutine cập nhật embed mỗi 5 giây (hoặc khi có sự kiện)
- Rate limit Discord edit: tối thiểu 1 edit/giây → dùng debounce 3-5s
- Nội dung embed:
  ┌─────────────────────────────────────┐
  │ 🎮 Discord Quest Auto-Completer     │
  │ Token: ...a1b2                      │
  │                                     │
  │ 📋 Danh sách quest:                 │
  │  ✅ Quest A [WATCH_VIDEO]           │
  │  ▶️  Quest B [PLAY_ON_DESKTOP] 45%  │
  │  ○  Quest C [PLAY_ACTIVITY]         │
  │                                     │
  │ ⏱️  Thời gian chạy: 5 phút 32 giây  │
  │ 📊 Tiến độ: 1/3 hoàn thành         │
  └─────────────────────────────────────┘
```

---

## 7. Scheduler (`services/scheduler.py`)

```
- Chạy coroutine nền mỗi 1 giờ kiểm tra DB
- Lấy tất cả token có next_run_at <= now AND is_active = 1
- Group theo thời gian để tránh spike (jitter ±30 phút)
- Sau mỗi lần chạy: cập nhật last_run_at, next_run_at = now + 2 ngày
- Nếu token invalid (401): đánh dấu is_active = 0, DM user thông báo
- Kết quả auto-run: gửi DM tóm tắt cho user
```

---

## 8. Bảo mật & Production

| Vấn đề | Giải pháp |
|---|---|
| Token lộ trong channel | Slash command ephemeral + xoá interaction gốc |
| Token lộ trong log | `token_mask.py` thay thế mọi token bằng `...xxxx` trước khi log |
| Token lộ trong DB | AES-256-GCM với key per-user |
| Brute force | Rate limit per-user: tối đa 5 lần chạy/giờ |
| Spam lệnh | Cooldown per-command per-user |
| Memory leak | Task timeout tối đa 6 giờ/session |
| DB corruption | WAL mode + backup định kỳ |
| Crash recovery | Khi bot restart, session "running" cũ → đánh dấu "interrupted" |

---

## 9. Thứ tự implement (cho AI agent)

```
Phase 1 – Nền tảng:
  1. config.py + .env setup
  2. db/models.py + database.py (SQLite trước, PostgreSQL sau)
  3. services/crypto.py (AES-256-GCM)
  4. core/discord_api.py + core/quest_engine.py (port từ script gốc)
  5. utils/token_mask.py + utils/logger.py

Phase 2 – Bot core:
  6. bot/main.py (bot init, cog loader)
  7. services/progress_message.py (live embed)
  8. core/task_manager.py (async task isolation)
  9. cogs/quests.py (/quests command)

Phase 3 – Auto system:
  10. services/scheduler.py
  11. cogs/autoquests.py (tất cả sub-commands)
  12. cogs/info.py (/info, /autoquests-info)

Phase 4 – Polish:
  13. utils/formatter.py (embed templates)
  14. services/rate_limiter.py
  15. cogs/admin.py (lệnh admin: force-run, ban user, stats)
  16. docker-compose.yml + README
```

---

## 10. Stack đề xuất

- **Runtime:** Python 3.11+
- **Discord:** `discord.py` v2.x (hỗ trợ slash commands native)
- **DB:** SQLite (development) → PostgreSQL (production)
- **ORM:** `aiosqlite` / `asyncpg` (async)
- **Crypto:** `cryptography` (PyCA) — AES-256-GCM
- **Scheduler:** `APScheduler` async mode
- **Deploy:** Docker + docker-compose
- **Monitoring:** Python `logging` → file + console (rotation)
