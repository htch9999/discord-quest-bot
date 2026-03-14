"""
Discord API client — async HTTP helper for user-token based requests.

Ported from original main.py DiscordAPI class, converted to aiohttp.
"""

import re
import json
import base64
import aiohttp
from typing import Optional

from bot.config import API_BASE
from bot.utils.logger import get_logger

logger = get_logger("discord_api")


# ── Build number fetcher ─────────────────────────────────────────────────────

async def fetch_latest_build_number() -> int:
    """Scrape Discord web app to get the latest client_build_number."""
    FALLBACK = 504649
    ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    )
    try:
        logger.info("Đang lấy build number mới nhất từ Discord...")
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://discord.com/app",
                headers={"User-Agent": ua},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as r:
                if r.status != 200:
                    logger.warning(
                        "Không lấy được trang Discord (%s), dùng fallback", r.status
                    )
                    return FALLBACK
                text = await r.text()

            scripts = re.findall(r"/assets/([a-f0-9]+)\.js", text)
            if not scripts:
                scripts_alt = re.findall(r'src="(/assets/[^"]+\.js)"', text)
                scripts = [
                    s.split("/")[-1].replace(".js", "") for s in scripts_alt
                ]

            if not scripts:
                logger.warning("Không tìm thấy JS assets, dùng fallback")
                return FALLBACK

            for asset_hash in scripts[-5:]:
                try:
                    async with session.get(
                        f"https://discord.com/assets/{asset_hash}.js",
                        headers={"User-Agent": ua},
                        timeout=aiohttp.ClientTimeout(total=15),
                    ) as ar:
                        js_text = await ar.text()
                        m = re.search(
                            r'buildNumber["\s:]+["\s]*(\d{5,7})', js_text
                        )
                        if m:
                            bn = int(m.group(1))
                            logger.info("Build number: %d", bn)
                            return bn
                except Exception:
                    continue

        logger.warning("Không tìm thấy build number, dùng fallback %d", FALLBACK)
        return FALLBACK
    except Exception as e:
        logger.warning("Lỗi lấy build number: %s, dùng fallback %d", e, FALLBACK)
        return FALLBACK


def make_super_properties(build_number: int) -> str:
    """Create base64-encoded X-Super-Properties header."""
    obj = {
        "os": "Windows",
        "browser": "Discord Client",
        "release_channel": "stable",
        "client_version": "1.0.9175",
        "os_version": "10.0.26100",
        "os_arch": "x64",
        "app_arch": "x64",
        "system_locale": "en-US",
        "browser_user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "discord/1.0.9175 Chrome/128.0.6613.186 "
            "Electron/32.2.7 Safari/537.36"
        ),
        "browser_version": "32.2.7",
        "client_build_number": build_number,
        "native_build_number": 59498,
        "client_event_source": None,
    }
    return base64.b64encode(json.dumps(obj).encode()).decode()


class DiscordAPI:
    """
    Async HTTP client for Discord API using a user token.
    """

    def __init__(self, token: str, build_number: int):
        self.token = token
        self.build_number = build_number
        self._session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self):
        if self._session is None or self._session.closed:
            ua = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "discord/1.0.9175 Chrome/128.0.6613.186 "
                "Electron/32.2.7 Safari/537.36"
            )
            sp = make_super_properties(self.build_number)
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": self.token,
                    "Content-Type": "application/json",
                    "Accept": "*/*",
                    "Accept-Language": "en-US,en;q=0.9",
                    "User-Agent": ua,
                    "X-Super-Properties": sp,
                    "X-Discord-Locale": "en-US",
                    "X-Discord-Timezone": "Asia/Ho_Chi_Minh",
                    "Origin": "https://discord.com",
                    "Referer": "https://discord.com/channels/@me",
                }
            )

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def get(self, path: str, **kwargs) -> aiohttp.ClientResponse:
        await self._ensure_session()
        url = f"{API_BASE}{path}"
        logger.debug("GET %s", path)
        r = await self._session.get(url, **kwargs)
        logger.debug("  -> %s", r.status)
        return r

    async def post(
        self, path: str, payload: Optional[dict] = None, **kwargs
    ) -> aiohttp.ClientResponse:
        await self._ensure_session()
        url = f"{API_BASE}{path}"
        logger.debug("POST %s", path)
        r = await self._session.post(url, json=payload, **kwargs)
        logger.debug("  -> %s", r.status)
        return r

    async def validate_token(self) -> bool:
        """Validate the user token by calling /users/@me."""
        try:
            r = await self.get("/users/@me")
            if r.status == 200:
                user = await r.json()
                name = user.get("username", "?")
                logger.info("Đăng nhập: %s (ID: %s)", name, user["id"])
                return True
            else:
                logger.error("Token không hợp lệ (status %s)", r.status)
                return False
        except Exception as e:
            logger.error("Không thể kết nối tới Discord: %s", e)
            return False
