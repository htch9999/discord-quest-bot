"""Quick verification of all bot modules."""
import asyncio


async def test_db():
    from bot.db.database import Database
    db = Database(":memory:")
    await db.init()
    tid = await db.save_token("uid1", "main", b"enc_data", "hint", None)
    tokens = await db.get_tokens("uid1")
    assert len(tokens) == 1
    assert tokens[0]["label"] == "main"
    ok = await db.rename_token("uid1", "main", "alt")
    assert ok
    t = await db.get_token_by_label("uid1", "alt")
    assert t is not None
    ok = await db.remove_token("uid1", "alt")
    assert ok
    tokens = await db.get_tokens("uid1")
    assert len(tokens) == 0
    await db.close()
    print("DB: ALL TESTS PASSED")


def test_imports():
    from bot.config import BOT_TOKEN, VERSION, SUPPORTED_TASKS
    from bot.db.database import Database
    from bot.db.models import SCHEMA_SQL
    from bot.services.crypto import encrypt_token, decrypt_token, get_token_hint
    from bot.services.rate_limiter import RateLimiter
    from bot.core.discord_api import DiscordAPI, fetch_latest_build_number, make_super_properties
    from bot.core.quest_engine import QuestEngine, get_quest_name, is_enrolled, is_completed
    from bot.core.task_manager import TaskManager
    from bot.utils.token_mask import mask_token, mask_in_text
    from bot.utils.logger import get_logger
    from bot.utils.formatter import info_embed, token_list_embed, error_embed, success_embed
    print("IMPORTS: ALL PASSED")


def test_rate_limiter():
    from bot.services.rate_limiter import RateLimiter
    rl = RateLimiter()
    ok, _ = rl.can_run("user1")
    assert ok
    rl.record_run("user1")
    ok, _ = rl.can_run("user1")
    assert ok
    ok, _ = rl.can_command("user1")
    assert ok
    rl.record_command("user1")
    ok, msg = rl.can_command("user1")
    assert not ok
    print("RATE LIMITER: ALL TESTS PASSED")


def test_token_mask():
    from bot.utils.token_mask import mask_token, mask_in_text
    assert mask_token("abcdefghij") == "...ghij"
    assert mask_token("ab") == "ab"
    print("TOKEN MASK: ALL TESTS PASSED")


if __name__ == "__main__":
    test_imports()
    asyncio.run(test_db())
    test_rate_limiter()
    test_token_mask()
    print("\n=== ALL VERIFICATION TESTS PASSED ===")
