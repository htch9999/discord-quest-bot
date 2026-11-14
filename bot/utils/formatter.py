"""
Discord embed template builders.
"""

import discord
import platform
import psutil
from datetime import datetime

from bot.config import VERSION
from bot.utils.i18n import tr, mode_text


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
    language: str = "en",
) -> discord.Embed:
    """Build the /info embed."""
    # Uptime
    days, rem = divmod(uptime_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    mins, _ = divmod(rem, 60)
    uptime_str = f"{days}d {hours}h {mins}m"

    # System info
    cpu_pct = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    os_info = f"{platform.system()} {platform.release()}"

    embed = discord.Embed(
        title=tr(language, "info_title"),
        color=COLOR_INFO,
    )
    embed.add_field(name=tr(language, "total_users"), value=str(total_users), inline=True)
    embed.add_field(name=tr(language, "quests_done"), value=str(total_quests_done), inline=True)
    embed.add_field(name=tr(language, "servers"), value=str(guild_count), inline=True)
    embed.add_field(name=tr(language, "ping"), value=f"{latency_ms:.0f}ms", inline=True)
    embed.add_field(name=tr(language, "uptime"), value=uptime_str, inline=True)
    embed.add_field(
        name=tr(language, "system"),
        value=f"{os_info}\nCPU: {cpu_pct}% | RAM: {mem.used // (1024**3)}/{mem.total // (1024**3)}GB",
        inline=False,
    )
    embed.add_field(
        name=tr(language, "storage"),
        value=f"{disk.used // (1024**3)}/{disk.total // (1024**3)}GB",
        inline=True,
    )
    embed.add_field(name="Version", value=f"v{VERSION}", inline=True)
    embed.set_footer(text="Discord Quest Bot")
    return embed


def token_list_embed(tokens: list[dict], language: str = "en") -> discord.Embed:
    """Build the /autoquests list embed."""
    embed = discord.Embed(
        title=tr(language, "token_list_title"),
        color=COLOR_INFO,
    )

    if not tokens:
        embed.description = tr(language, "token_list_empty")
        return embed

    for t in tokens:
        hint = t.get("token_hint", "????")
        label = t.get("label", "default")
        active = tr(language, "active") if t.get("is_active") else tr(language, "paused")

        last_run = tr(language, "never")
        if t.get('last_run_at'):
            try:
                lr_dt = datetime.fromisoformat(str(t['last_run_at']))
                last_run = f"<t:{int(lr_dt.timestamp())}:R>"
            except Exception:
                last_run = str(t['last_run_at'])

        next_run = tr(language, "not_available")
        if t.get('next_run_at'):
            try:
                nr_dt = datetime.fromisoformat(str(t['next_run_at']))
                next_run = f"<t:{int(nr_dt.timestamp())}:R>"
            except Exception:
                next_run = str(t['next_run_at'])

        embed.add_field(
            name=f"{active} · {label} (`...{hint}`)",
            value=(
                f"{tr(language, 'last_run')}: {last_run}\n"
                f"{tr(language, 'next_run_short')}: {next_run}"
            ),
            inline=False,
        )

    embed.set_footer(text=f"{len(tokens)} token(s)")
    return embed


def error_embed(message: str, language: str = "en") -> discord.Embed:
    return discord.Embed(
        title=tr(language, "error"),
        description=message,
        color=COLOR_ERROR,
    )


def success_embed(message: str, language: str = "en") -> discord.Embed:
    return discord.Embed(
        title="Thành công" if language == "vi" else "Success",
        description=message,
        color=COLOR_SUCCESS,
    )


def warning_embed(message: str, language: str = "en") -> discord.Embed:
    return discord.Embed(
        title="Cảnh báo" if language == "vi" else "Warning",
        description=message,
        color=COLOR_WARNING,
    )


def auto_run_embed(
    label: str,
    hint: str,
    completed: int,
    quest_names: list[str] | None,
    next_run: datetime | None,
    startup: bool = False,
    language: str = "en",
    quest_mode: str = "multi",
) -> discord.Embed:
    """Build a compact completion summary that respects Discord field limits."""
    title = tr(language, "startup_run_title" if startup else "auto_run_title")
    embed = discord.Embed(title=title, color=COLOR_SUCCESS if completed else COLOR_WARNING)
    embed.description = (
        tr(language, "auto_run_summary", label=label, hint=hint, count=completed)
        if completed else tr(language, "no_quests_completed")
    )
    if quest_names:
        details = "\n".join(f"• {name}" for name in quest_names)
        if len(details) > 1024:
            details = details[:1021].rsplit("\n", 1)[0] + "..."
        embed.add_field(name=tr(language, "quest_details"), value=details or tr(language, "no_quests"), inline=False)
    if next_run:
        embed.add_field(
            name=tr(language, "next_run"),
            value=f"<t:{int(next_run.timestamp())}:R>",
            inline=False,
        )
    embed.add_field(
        name=tr(language, "mode_label"),
        value=mode_text(language, quest_mode, include_hint=True),
        inline=False,
    )
    return embed


def token_invalid_embed(label: str, hint: str, failures: int, max_failures: int, language: str = "en") -> discord.Embed:
    return discord.Embed(
        title=tr(language, "token_invalid_title"),
        description=tr(language, "token_invalid_dm", label=label, hint=hint, failures=failures, maximum=max_failures),
        color=COLOR_WARNING,
    )


def token_deleted_embed(label: str, hint: str, reason: str = "", language: str = "en") -> discord.Embed:
    return discord.Embed(
        title=tr(language, "token_deleted_title"),
        description=tr(language, "token_deleted_dm", label=label, hint=hint) + (f"\n{reason}" if reason else ""),
        color=COLOR_ERROR,
    )
