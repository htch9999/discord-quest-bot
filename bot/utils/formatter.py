"""
Discord embed template builders.
"""

import discord
import platform
import psutil
from datetime import datetime

from bot.config import VERSION


# ── Color palette ────────────────────────────────────────────────────────────
COLOR_INFO    = 0x5865F2   # Blurple
COLOR_SUCCESS = 0x57F287   # Green
COLOR_ERROR   = 0xED4245   # Red
COLOR_WARNING = 0xFEE75C   # Yellow


def info_embed(
    total_users: int,
    total_quests_done: int,
    guild_count: int,
    latency_ms: float,
    uptime_seconds: int,
) -> discord.Embed:
    """Build the /info embed."""
    # Uptime
    days, rem = divmod(uptime_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    mins, _ = divmod(rem, 60)
    uptime_str = f"{days} ngày {hours} giờ {mins} phút"

    # System info
    cpu_pct = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    os_info = f"{platform.system()} {platform.release()}"

    embed = discord.Embed(
        title="📊 Thông tin Bot",
        color=COLOR_INFO,
    )
    embed.add_field(name="👥 Tổng người dùng", value=str(total_users), inline=True)
    embed.add_field(name="✅ Tổng quest đã hoàn thành", value=str(total_quests_done), inline=True)
    embed.add_field(name="🖥️ Servers", value=str(guild_count), inline=True)
    embed.add_field(name="📡 Ping", value=f"{latency_ms:.0f}ms", inline=True)
    embed.add_field(name="⏱️ Uptime", value=uptime_str, inline=True)
    embed.add_field(
        name="💻 Hệ thống",
        value=f"{os_info}\nCPU: {cpu_pct}% | RAM: {mem.used // (1024**3)}/{mem.total // (1024**3)}GB",
        inline=False,
    )
    embed.add_field(
        name="💾 Storage",
        value=f"{disk.used // (1024**3)}/{disk.total // (1024**3)}GB",
        inline=True,
    )
    embed.add_field(name="🔧 Version", value=f"v{VERSION}", inline=True)
    embed.set_footer(text="@htch9999🌷 — Auto Quests Bot")
    return embed


def token_list_embed(tokens: list[dict]) -> discord.Embed:
    """Build the /autoquests list embed."""
    embed = discord.Embed(
        title="🔑 Token đã lưu",
        color=COLOR_INFO,
    )

    if not tokens:
        embed.description = "Chưa có token nào được lưu."
        return embed

    for t in tokens:
        hint = t.get("token_hint", "????")
        label = t.get("label", "default")
        active = "🟢" if t.get("is_active") else "🔴"

        last_run = "Chưa"
        if t.get('last_run_at'):
            try:
                lr_dt = datetime.fromisoformat(str(t['last_run_at']))
                last_run = f"<t:{int(lr_dt.timestamp())}:R>"
            except Exception:
                last_run = str(t['last_run_at'])

        next_run = "N/A"
        if t.get('next_run_at'):
            try:
                nr_dt = datetime.fromisoformat(str(t['next_run_at']))
                next_run = f"<t:{int(nr_dt.timestamp())}:R>"
            except Exception:
                next_run = str(t['next_run_at'])

        embed.add_field(
            name=f"{active} {label} (`...{hint}`)",
            value=(
                f"Lần chạy cuối: {last_run}\n"
                f"Lần chạy tiếp: {next_run}"
            ),
            inline=False,
        )

    embed.set_footer(text=f"Tổng: {len(tokens)} token")
    return embed


def error_embed(message: str) -> discord.Embed:
    return discord.Embed(
        title="❌ Lỗi",
        description=message,
        color=COLOR_ERROR,
    )


def success_embed(message: str) -> discord.Embed:
    return discord.Embed(
        title="✅ Thành công",
        description=message,
        color=COLOR_SUCCESS,
    )


def warning_embed(message: str) -> discord.Embed:
    return discord.Embed(
        title="⚠️ Cảnh báo",
        description=message,
        color=COLOR_WARNING,
    )
