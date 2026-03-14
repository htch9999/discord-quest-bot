# Kế hoạch Website Giới thiệu Discord Quest Bot

---

## 1. Tổng quan kiến trúc

```
┌─────────────────────────────────────────────────────────────┐
│                     GitHub Pages (Frontend)                  │
│         ctdoteam.github.io/discord-quest-bot                │
│  HTML + CSS + Vanilla JS — không cần build step            │
└──────────────────────┬──────────────────────────────────────┘
                       │ fetch() API calls
┌──────────────────────▼──────────────────────────────────────┐
│              Bot Server – Public Stats API                   │
│         https://api.yourbot.xyz/v1/stats/*                  │
│  FastAPI (Python) – chạy cùng máy chủ bot, CORS enabled    │
└──────────────────────┬──────────────────────────────────────┘
                       │ read-only queries
┌──────────────────────▼──────────────────────────────────────┐
│                  Database (SQLite/PostgreSQL)                 │
│           global_stats | quest_stats | saved_tokens          │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Cấu trúc file Frontend

```
website/
├── index.html                  # Landing page chính
├── 404.html
├── CNAME                       # Custom domain cho GitHub Pages
├── assets/
│   ├── css/
│   │   ├── main.css            # Design system, CSS variables (dark/light)
│   │   ├── components.css      # Reusable components
│   │   ├── animations.css      # Keyframes, transitions, theme-transition
│   │   └── responsive.css      # Mobile breakpoints
│   ├── js/
│   │   ├── main.js             # Init, scroll effects, bootstrap
│   │   ├── i18n.js             # Engine đa ngôn ngữ (VI/EN/JA)
│   │   ├── theme.js            # Dark / Light / System theme switcher
│   │   ├── stats.js            # Live stats fetcher (30s interval)
│   │   ├── members.js          # Discord widget handler
│   │   ├── counter.js          # Animated number counters
│   │   └── particles.js        # Background canvas particles
│   ├── locales/
│   │   ├── vi.json             # Tiếng Việt (default)
│   │   ├── en.json             # English
│   │   └── ja.json             # 日本語
│   ├── img/
│   │   ├── bot-avatar.png
│   │   ├── og-image.png        # Open Graph 1200×630
│   │   ├── screenshots/        # Bot UI screenshots
│   │   └── icons/              # SVG feature icons
│   └── fonts/                  # Self-hosted Inter + JetBrains Mono
└── .github/
    └── workflows/
        └── deploy.yml          # GitHub Actions auto-deploy
```

---

## 3. Design System

### 3.1 Color Palette — Dark Theme (mặc định)

```css
:root {
  /* Brand */
  --accent-primary: #5865f2; /* Discord blurple */
  --accent-secondary: #eb459e; /* Quest pink */
  --accent-glow: #5865f233;

  /* Dark theme base */
  --bg-void: #0d0e14;
  --bg-surface: #13141c;
  --bg-card: #1a1c27;
  --bg-card-hover: #1f2135;
  --border: #2a2d40;
  --border-glow: #5865f255;

  /* Text */
  --text-primary: #f2f3f7;
  --text-secondary: #8b8fa8;
  --text-muted: #4a4d62;

  /* Status */
  --green: #23a55a;
  --yellow: #f0b132;
  --red: #ed4245;

  /* Effects */
  --gradient-hero: linear-gradient(135deg, #5865f215 0%, #eb459e08 100%);
  --gradient-card: linear-gradient(145deg, #1a1c27, #13141c);
  --shadow-card: 0 8px 32px #00000060;
  --shadow-glow: 0 0 40px #5865f230;
}
```

### 3.2 Color Palette — Light Theme

```css
[data-theme="light"] {
  --bg-void: #f5f6fa;
  --bg-surface: #ffffff;
  --bg-card: #f0f1f7;
  --bg-card-hover: #e8e9f3;
  --border: #d8dae8;
  --border-glow: #5865f240;
  --text-primary: #1a1c27;
  --text-secondary: #4a4d62;
  --text-muted: #8b8fa8;
  --gradient-hero: linear-gradient(135deg, #5865f210 0%, #eb459e06 100%);
  --gradient-card: linear-gradient(145deg, #f0f1f7, #ffffff);
  --shadow-card: 0 8px 32px #00000015;
  --shadow-glow: 0 0 40px #5865f220;
  /* accent-primary, accent-secondary: giữ nguyên ở cả hai theme */
}

/* Particle canvas nhạt hơn ở light mode */
[data-theme="light"] #particles-canvas {
  opacity: 0.35;
}
```

### 3.3 Typography

```
Headings : "Inter"          700, 800  — clean, modern
Body      : "Inter"          400, 500
Code/Token: "JetBrains Mono" 400      — hiển thị snippet, token hint
```

### 3.4 Theme Transition Toàn Trang

```css
/* animations.css */
html.theme-transitioning,
html.theme-transitioning *,
html.theme-transitioning *::before,
html.theme-transitioning *::after {
  transition:
    background-color 200ms ease,
    color 200ms ease,
    border-color 200ms ease,
    box-shadow 200ms ease !important;
}
```

---

## 4. Hệ thống Đa Ngôn Ngữ (i18n)

### 4.1 Ngôn ngữ hỗ trợ

| Flag | Locale | Tên hiển thị | Trạng thái |
| ---- | ------ | ------------ | ---------- |
| 🇻🇳   | `vi`   | Tiếng Việt   | Mặc định   |
| 🇺🇸   | `en`   | English      | Đầy đủ     |
| 🇯🇵   | `ja`   | 日本語       | Đầy đủ     |

### 4.2 Cơ chế hoạt động

```javascript
// i18n.js — Engine không cần thư viện ngoài

// Thứ tự ưu tiên ngôn ngữ:
// 1. localStorage.getItem("lang")
// 2. navigator.language.slice(0,2)  (auto-detect từ browser)
// 3. "vi" (fallback mặc định)

// Đánh dấu element bằng data-attribute:
<h1 data-i18n="hero.title"></h1>
<p  data-i18n="hero.subtitle"></p>
<button data-i18n="hero.cta_add"></button>

// Cho placeholder và aria-label:
<input data-i18n-placeholder="search.placeholder">
<button data-i18n-aria="nav.menu_label">

// Khi đổi ngôn ngữ:
// fade-out (150ms) → swap tất cả text → fade-in (150ms)
// KHÔNG reload page
// Fallback: nếu key thiếu trong ja.json → dùng en.json
```

### 4.3 Cấu trúc locale JSON

```json
// en.json (cấu trúc mẫu đầy đủ)
{
  "meta": {
    "lang": "en",
    "description": "A Discord bot that automatically completes quests..."
  },
  "nav": {
    "features": "Features",
    "security": "Security",
    "commands": "Commands",
    "stats": "Live Stats",
    "community": "Community",
    "github": "GitHub"
  },
  "hero": {
    "badge": "⚡ v1.0 · Production Ready",
    "title": "Complete Discord Quests",
    "title_accent": "Automatic. Secure. Fast.",
    "subtitle": "A bot that handles every Discord quest for you — in parallel, in real-time, with zero token exposure.",
    "cta_add": "Add to Discord",
    "cta_server": "Join Server",
    "cta_github": "View GitHub",
    "stat_users": "Users",
    "stat_quests": "Quests Done",
    "stat_servers": "Servers",
    "stat_uptime": "Uptime"
  },
  "features": {
    "title": "Everything you need",
    "subtitle": "Built for reliability, security, and speed.",
    "parallel_title": "Parallel Execution",
    "parallel_desc": "Run up to 6 PLAY_* quests simultaneously with isolated threads.",
    "security_title": "Zero-Knowledge Security",
    "security_desc": "AES-256-GCM encryption with per-user derived keys. Your token never touches a log.",
    "auto_title": "Auto Every 2 Days",
    "auto_desc": "Smart scheduler checks for new quests and DMs you the results automatically.",
    "live_title": "Live Progress",
    "live_desc": "One message, updated in real-time — no spam, no noise.",
    "hidden_title": "Token Always Hidden",
    "hidden_desc": "Ephemeral commands + masked display. Token is never visible to anyone.",
    "stats_title": "Detailed Statistics",
    "stats_desc": "Full dashboard per token — quests done, pending, last run, next scheduled.",
    "multi_title": "All Quest Types",
    "multi_desc": "WATCH_VIDEO · PLAY_ON_DESKTOP · STREAM · PLAY_ACTIVITY — all supported.",
    "recovery_title": "Crash Recovery",
    "recovery_desc": "Interrupted sessions resume automatically. No quest is ever lost.",
    "oss_title": "Open Source",
    "oss_desc": "100% public source code. Audit it, fork it, self-host it."
  },
  "how_it_works": {
    "title": "How It Works",
    "subtitle": "From command to reward in 5 steps.",
    "step1_title": "Add Bot or Run Command",
    "step1_desc": "Invite the bot to your server or send /quests directly.",
    "step2_title": "Fetch Quest List",
    "step2_desc": "Bot retrieves all available quests from Discord API.",
    "step3_title": "Auto Enroll & Start",
    "step3_desc": "Enrolls in every eligible quest and begins parallel completion.",
    "step4_title": "Live Progress Update",
    "step4_desc": "A single message updates in real-time with progress bars.",
    "step5_title": "Collect Reward",
    "step5_desc": "Quest completed ✅ — rewards delivered to your account."
  },
  "security": {
    "title": "Security & Transparency",
    "subtitle": "We publish what we do. You can verify every claim.",
    "commit1": "Token encrypted with AES-256-GCM",
    "commit2": "Unique key derived per Discord user ID",
    "commit3": "Token never written to any log",
    "commit4": "Source code 100% public on GitHub",
    "commit5": "Self-host guide available",
    "commit6": "Delete token anytime with /autoquests remove",
    "code_label": "Encryption code (actual source):",
    "code_link": "View full source on GitHub →",
    "selfhost": "Don't trust us? Host it yourself.",
    "selfhost_cta": "Self-host Guide"
  },
  "commands": {
    "title": "Commands",
    "subtitle": "Simple, powerful, private.",
    "tab_once": "/quests",
    "tab_auto": "/autoquests",
    "tab_manage": "Manage",
    "tab_stats": "Statistics",
    "col_command": "Command",
    "col_desc": "Description",
    "col_example": "Example"
  },
  "live_stats": {
    "title": "Live Statistics",
    "subtitle": "Real numbers, refreshed every 30 seconds.",
    "live_badge": "LIVE",
    "today": "Quests today",
    "week": "This week",
    "total": "All time",
    "active": "Active sessions",
    "ping": "API ping",
    "uptime": "Uptime",
    "breakdown": "Quest type breakdown",
    "last_updated": "Last updated"
  },
  "community": {
    "title": "Join the Community",
    "subtitle": "Get support, report bugs, and stay updated.",
    "members": "members",
    "online": "online",
    "join_cta": "Join Discord Server"
  },
  "github": {
    "title": "Open Source",
    "subtitle": "Read the code. Trust the code.",
    "stars": "Stars",
    "forks": "Forks",
    "issues": "Issues",
    "last_commit": "Last commit",
    "contributors": "Contributors",
    "latest": "Latest release",
    "view_btn": "View on GitHub",
    "download_btn": "Download Latest"
  },
  "faq": {
    "title": "Frequently Asked Questions",
    "q1": "Does the bot store my token?",
    "a1": "Only if you use /autoquests. The token is encrypted with AES-256-GCM using a key derived from your Discord user ID before being stored. With /quests (one-time mode), nothing is written to disk.",
    "q2": "Will my account get banned?",
    "a2": "The bot mimics normal Discord client behavior using legitimate API endpoints. However, any automation carries inherent risk. Use at your own discretion.",
    "q3": "Which quest types are supported?",
    "a3": "WATCH_VIDEO · WATCH_VIDEO_ON_MOBILE · PLAY_ON_DESKTOP · STREAM_ON_DESKTOP · PLAY_ACTIVITY",
    "q4": "Can I self-host the bot?",
    "a4": "Yes. The full source is on GitHub with a detailed self-host guide. Docker support included.",
    "q5": "When is my data deleted?",
    "a5": "Run /autoquests remove at any time. Your token and all associated stats are permanently deleted.",
    "q6": "Is it free?",
    "a6": "Yes, completely free. No premium tier, no hidden fees.",
    "q7": "How do I report a bug?",
    "a7": "Open an issue on GitHub or send a message in the #bug-report channel on our Discord server."
  },
  "footer": {
    "tagline": "Automate your quests. Keep your token safe.",
    "features": "Features",
    "security": "Security",
    "commands": "Commands",
    "faq": "FAQ",
    "selfhost": "Self-host",
    "privacy": "Privacy Policy",
    "terms": "Terms of Use",
    "status": "Status",
    "made_by": "Made by @htch9999🌷 · Open Source · MIT License",
    "disclaimer": "This project is not affiliated with Discord Inc."
  },
  "theme": {
    "dark": "Dark",
    "light": "Light",
    "system": "System"
  },
  "lang_switcher": {
    "label": "Language"
  }
}
```

### 4.4 UI Switcher (Navbar)

```
Bố cục góc phải navbar (thứ tự từ phải sang trái):

  [🌑 ▾]  [🇻🇳 VI ▾]  [→ Thêm vào Discord]

Theme dropdown:
  🌑 Dark
  ☀️  Light
  💻 System

Language dropdown:
  🇻🇳 Tiếng Việt
  🇺🇸 English
  🇯🇵 日本語

Cả hai dropdown:
  - Blur backdrop + border glow
  - Active item có checkmark ✓
  - Keyboard accessible (arrow keys + Enter)
```

### 4.5 SEO Đa Ngôn Ngữ

```html
<!-- Trong <head> — cập nhật động qua JS khi đổi ngôn ngữ -->
<link rel="alternate" hreflang="vi" href="https://yourbot.xyz/?lang=vi" />
<link rel="alternate" hreflang="en" href="https://yourbot.xyz/?lang=en" />
<link rel="alternate" hreflang="ja" href="https://yourbot.xyz/?lang=ja" />
<link rel="alternate" hreflang="x-default" href="https://yourbot.xyz/" />
<meta property="og:locale" content="vi_VN" />
<!-- cập nhật động -->
<meta name="description" content="..." />
<!-- cập nhật động -->
```

---

## 5. Cấu trúc các Section

### Section 1 — Hero

```
Layout: Fullscreen, centered, 100vh min
Content:
  - Badge: "⚡ v1.0 · Production Ready"
  - H1: [hero.title] + [hero.title_accent] (accent color)
  - Subtitle: [hero.subtitle]
  - CTA buttons:
      [→ Thêm vào Discord]  [Tham gia Server]  [Xem GitHub]
  - Hero visual: Mockup Discord embed message (CSS animated)
  - Background: Particle canvas + gradient mesh + noise overlay

Live counters (fetch từ API, animate khi vào viewport):
  ┌──────────────┬──────────────┬──────────────┬──────────────┐
  │ 1,247        │ 8,392        │ 312          │ 99.8%        │
  │ Người dùng   │ Quest đã làm │ Server       │ Uptime       │
  └──────────────┴──────────────┴──────────────┴──────────────┘
```

### Section 2 — Tính năng (Features Grid)

```
Grid 3 cột (2 cột mobile), mỗi card:
  - Icon SVG animated (stroke-dashoffset khi scroll vào)
  - Tiêu đề   [features.X_title]
  - Mô tả     [features.X_desc]
  - Badge "HOT" / "NEW" nếu nổi bật

9 cards:
  ⚡ Chạy song song        ─ Tối đa 6 PLAY_* cùng lúc
  🔐 Bảo mật tuyệt đối    ─ AES-256-GCM, key per-user
  🤖 Auto 2 ngày/lần      ─ Scheduler + DM kết quả
  📡 Live Progress         ─ 1 tin nhắn, cập nhật real-time
  🛡️  Token ẩn hoàn toàn   ─ Ephemeral, không log
  📊 Thống kê chi tiết     ─ Dashboard đầy đủ từng token
  🔄 Đa nhiệm vụ           ─ WATCH · PLAY · STREAM · ACTIVITY
  💾 Không mất dữ liệu     ─ Crash recovery tự động
  🌐 Open Source            ─ Minh bạch 100% mã nguồn
```

### Section 3 — Cách hoạt động (How It Works)

```
Timeline 5 bước, animate theo thứ tự khi scroll:

  Step 1 → Thêm bot hoặc gửi lệnh /quests
  Step 2 → Bot lấy danh sách quests từ Discord API
  Step 3 → Tự động enroll + bắt đầu song song
  Step 4 → Cập nhật tiến độ real-time qua 1 tin nhắn
  Step 5 → Nhận phần thưởng ✅

Visual bên cạnh: Discord embed mockup CSS-animated
  - Các quest tick ✅ dần dần
  - Progress bar tăng từ 0% → 100%
  - Timestamp cập nhật
```

### Section 4 — Bảo mật & Minh bạch (Trust Section)

```
2 cột:

  LEFT — Danh sách cam kết:
    ✅ Token mã hoá AES-256-GCM
    ✅ Key dẫn xuất riêng biệt từng user ID
    ✅ Token không bao giờ xuất hiện trong log
    ✅ Mã nguồn 100% public trên GitHub
    ✅ Hỗ trợ tự host (self-host guide)
    ✅ Xoá token bất cứ lúc với /autoquests remove

  RIGHT — Code snippet (syntax highlighted, thực từ repo):
    Hiển thị hàm mã hoá crypto.py
    Nút [Xem đầy đủ trên GitHub →]

Banner phía dưới:
  "Không tin tưởng? Tự host bot của bạn."  [→ Self-host Guide]
```

### Section 5 — Lệnh (Commands Reference)

```
Tab switcher: [/quests] [/autoquests] [Quản lý] [Thống kê]

Mỗi tab: bảng Lệnh | Mô tả | Ví dụ
Kèm mockup screenshot thực tế của bot

Bảng tổng hợp đầy đủ:
/quests {token}                     Chạy một lần, không lưu
/autoquests {token} [label]         Lưu + tự động mỗi 2 ngày
/autoquests list                    Danh sách token đã lưu
/autoquests remove {label}          Xoá token
/autoquests rename {label} {new}    Đổi tên gợi nhớ
/autoquests status [label]          Xem trạng thái
/autoquests run [label]             Chạy thủ công ngay
/autoquests pause [label]           Tạm dừng auto
/autoquests resume [label]          Bật lại auto
/autoquests-info                    Thống kê tổng của bạn
/info                               Thông tin bot & server
```

### Section 6 — Live Stats (Real-time Dashboard)

```
Fetch từ /v1/stats/public mỗi 30 giây
Skeleton loading khi đang fetch

  ┌─────────────────────────────────────────────────────┐
  │  📊 Thống kê hệ thống          ● LIVE               │
  │                                                     │
  │  Quest hôm nay: 142   │  Đang chạy: 7 sessions     │
  │  Quest tuần này: 891  │  Ping API: 45ms             │
  │  Tổng mọi thời: 8,392 │  Uptime: 12d 4h 32m        │
  │                                                     │
  │  Loại quest phổ biến:                               │
  │  ████████████ PLAY_ON_DESKTOP   42%                 │
  │  ████████     WATCH_VIDEO       31%                 │
  │  █████        PLAY_ACTIVITY     18%                 │
  │  ███          STREAM_ON_DESKTOP  9%                 │
  │                                                     │
  │  Cập nhật lần cuối: 14:32:07                        │
  └─────────────────────────────────────────────────────┘

Dot "● LIVE" nhấp nháy pulse animation ở góc trên phải
```

### Section 7 — Discord Server (Community)

```
Discord Widget (api.discord.com/guilds/{id}/widget.json):
  - Tên server + icon
  - Tổng thành viên (từ bot backend /v1/stats/server)
  - Số đang online (real-time từ widget JSON)
  - Danh sách tối đa 10 members online: avatar + username
  - Nút [Tham gia Server →]

Custom card (không dùng iframe widget mặc định của Discord):
  - Tự render từ JSON để đồng nhất UI
  - Avatar member: hình tròn, fallback nếu không có ảnh
  - Status dot màu xanh bên cạnh avatar
```

### Section 8 — GitHub & Open Source

```
Card lớn fetch từ api.github.com/repos/{owner}/{repo}:

  ⭐ Stars  🍴 Forks  🐛 Open Issues  ⏱️ Last commit: X ngày trước

  Contributors (tối đa 8):
    [avatar] [avatar] [avatar] ... +N more

  Latest release: v1.2.0
  Changelog snippet (3 dòng đầu)

  Language bar:
    Python ██████████████ 94%  │  Other ██ 6%

  Nút: [View on GitHub ↗]  [Download v1.2.0 ↓]
```

### Section 9 — FAQ

```
Accordion expand/collapse (CSS-only, không cần JS):
  + Bot có lưu token của tôi không?
  + Tài khoản có bị ban không?
  + Bot hỗ trợ loại quest nào?
  + Tôi có thể tự host không?
  + Dữ liệu của tôi được xoá khi nào?
  + Bot có miễn phí không?
  + Làm sao báo cáo lỗi?
```

### Section 10 — Footer

```
3 cột:
  [1] Logo + tagline + social: GitHub | Discord
  [2] Links: Tính năng | Bảo mật | Commands | FAQ | Self-host
  [3] Legal: Privacy Policy | Terms | Status Page

Bottom bar:
  "Made by @htch9999🌷 · Open Source · MIT License"
  "Bot không liên kết với Discord Inc."
```

---

## 6. Backend API (`/v1/`)

```python
# FastAPI — 4 endpoint public, chỉ aggregate stats, không thông tin nhạy cảm
# CORS: chỉ cho phép domain GitHub Pages + localhost (dev)
# Cache: 30 giây in-memory để tránh overload DB

GET /v1/stats/public
{
  "total_users":            1247,
  "total_quests_completed": 8392,
  "quests_today":           142,
  "quests_this_week":       891,
  "active_sessions":        7,
  "uptime_seconds":         1058720,
  "bot_ping_ms":            45,
  "quest_type_breakdown": {
    "PLAY_ON_DESKTOP":    0.42,
    "WATCH_VIDEO":        0.31,
    "PLAY_ACTIVITY":      0.18,
    "STREAM_ON_DESKTOP":  0.09
  },
  "cached_at": "2024-01-15T10:30:00Z"
}

GET /v1/stats/server
{
  "member_count": 3241,
  "online_count": 127,
  "members_online": [
    { "username": "user1", "avatar_url": "...", "status": "online" },
    ...  // tối đa 10
  ],
  "cached_at": "..."
}

GET /v1/health
{
  "status":         "operational",  // "operational" | "degraded" | "down"
  "uptime_pct_30d": 99.8,
  "response_time_ms": 12
}

GET /v1/github
{
  "stars":        142,
  "forks":        28,
  "open_issues":  3,
  "last_commit":  "2024-01-14T08:22:00Z",
  "latest_release": "v1.2.0",
  "cached_at": "..."   // cache 5 phút
}
```

---

## 7. Animations & UX

```
Scroll-triggered (Intersection Observer API):
  - Counter roll-up khi vào viewport (một lần duy nhất)
  - Feature cards: fade-in + slide-up staggered (60ms delay mỗi card)
  - Timeline steps: draw theo thứ tự (50ms giữa mỗi step)
  - Stats bar: fill từ 0% → value% (800ms ease-out)
  - Section headings: slide-up + opacity (400ms)

Hover effects:
  - Card: translateY(-4px) + box-shadow glow (200ms ease)
  - Button primary: gradient shift + scale(1.02)
  - Feature icon: stroke-dashoffset animation
  - Contributor avatar: scale(1.1) + ring glow

Background Hero:
  - Canvas particles: 60 particles, kết nối khi distance < 120px
  - Màu particle: var(--accent-primary) opacity 0.4
  - Gradient mesh chuyển động: 20s linear infinite
  - Noise texture overlay: 5% opacity, pointer-events: none

Micro-interactions:
  - ● LIVE dot: pulse animation 2s infinite
  - Số stats: đếm lên animate khi fetch xong (1.2s ease-out)
  - Skeleton: shimmer effect từ trái sang phải
  - Copy invite link: toast "Đã copy!" ở góc dưới (2s auto-dismiss)
  - Theme switch: fade toàn trang 200ms
  - Language switch: fade text 150ms
  - FAQ accordion: smooth max-height transition

Discord embed mockup (Section How It Works):
  - CSS-only animation, lặp vô hạn
  - Quest items tick ✅ từng cái một (1.5s interval)
  - Progress bar tăng dần từ 0 → 100%
  - Timestamp "Edited just now" cập nhật
```

---

## 8. Performance & SEO

```
Performance:
  - Ảnh: WebP + lazy loading (loading="lazy")
  - Fonts: self-hosted, subset Latin + Vietnamese + Japanese
  - CSS: critical CSS inline trong <style>, các file còn lại defer
  - JS: defer attribute, không blocking render
  - API: cache 30s, hiển thị skeleton trước khi có data
  - Lighthouse target: 95+ Performance | 100 Accessibility | 100 Best Practices | 95+ SEO

GitHub Pages:
  - CNAME file cho custom domain
  - HTTPS tự động
  - Deploy qua GitHub Actions (on push to main)

SEO:
  <meta name="description">          — cập nhật theo ngôn ngữ
  <meta property="og:title">
  <meta property="og:description">
  <meta property="og:image">         — og-image.png 1200×630
  <meta property="og:locale">        — cập nhật động
  <meta name="twitter:card" content="summary_large_image">
  <link rel="alternate" hreflang>    — vi / en / ja / x-default

Accessibility:
  - ARIA labels trên tất cả icon buttons
  - Keyboard navigation: Tab, Enter, Escape, Arrow keys
  - Focus-visible outline trên mọi interactive element
  - Color contrast ratio ≥ 4.5:1 (WCAG AA)
  - Reduced motion: @media (prefers-reduced-motion) → tắt animation
```

---

## 9. Thứ tự implement cho Agent

```
Phase 1 — Foundation
  1.  main.css     : design system, CSS variables dark + light
  2.  animations.css: keyframes, theme-transition
  3.  theme.js     : dark/light/system switch + localStorage
  4.  i18n.js      : locale loader + DOM walker
  5.  vi.json + en.json + ja.json (đầy đủ tất cả keys)
  6.  index.html   : skeleton HTML, <head>, font preload
  7.  Navigation   : sticky, blur backdrop, theme toggle, lang switcher

Phase 2 — Content Sections (static)
  8.  Hero section        : layout, badge, H1, CTA buttons, stat counters (placeholder)
  9.  Features grid       : 9 cards, SVG icons
  10. How It Works        : timeline + Discord embed mockup
  11. Security section    : 2 cột, code snippet (syntax highlight)
  12. Commands reference  : tab switcher + bảng lệnh
  13. FAQ                 : accordion
  14. Footer

Phase 3 — Dynamic Data
  15. FastAPI backend     : 4 endpoints + CORS + cache
  16. stats.js            : fetch /v1/stats/public mỗi 30s → render
  17. Live Stats section  : render cards + bar chart
  18. members.js          : fetch /v1/stats/server → render widget
  19. Discord Community   : render member list
  20. GitHub section      : fetch api.github.com → render stats + contributors

Phase 4 — Polish & Deploy
  21. particles.js        : canvas background
  22. counter.js          : animated roll-up numbers
  23. Skeleton loaders    : shimmer cho tất cả dynamic sections
  24. Scroll animations   : Intersection Observer cho tất cả sections
  25. responsive.css      : mobile breakpoints (375px, 768px, 1024px)
  26. 404.html
  27. deploy.yml          : GitHub Actions workflow
  28. og-image.png        : 1200×630, design đồng nhất với website
  29. Accessibility pass  : ARIA, keyboard nav, contrast check
  30. Lighthouse audit    : fix đến khi đạt 95+ mọi metric
```

---

## 10. Tech Stack

| Layer            | Công nghệ                             | Lý do                                    |
| ---------------- | ------------------------------------- | ---------------------------------------- |
| Frontend         | HTML5 + CSS3 + Vanilla JS             | Không build step → GitHub Pages hoàn hảo |
| i18n             | Vanilla JS + JSON files               | Không dependency, load nhanh             |
| Theme            | CSS variables + `data-theme`          | Smooth transition, không flicker         |
| Icons            | Lucide Icons (SVG inline)             | Nhẹ, scalable, animatable                |
| Fonts            | Inter + JetBrains Mono (self-hosted)  | Không phụ thuộc Google, privacy-friendly |
| Animations       | CSS Keyframes + Intersection Observer | Không thư viện ngoài                     |
| Syntax highlight | highlight.js (chỉ Python subset)      | Nhẹ, tree-shakeable                      |
| Backend API      | FastAPI + uvicorn                     | Async, nhanh, cùng Python stack với bot  |
| Deploy FE        | GitHub Pages + GitHub Actions         | Free, CI/CD tự động                      |
| Deploy BE        | Cùng VPS với bot                      | Không tốn thêm chi phí                   |
| SSL              | Let's Encrypt (Certbot)               | HTTPS miễn phí                           |
| Monitoring       | UptimeRobot (free tier)               | Public status badge                      |
