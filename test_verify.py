"""Quick verification of all bot modules."""
import asyncio


async def test_db():
    from bot.db.database import Database
    db = Database(":memory:")
    await db.init()
    assert await db.get_user_language("uid1") == "en"
    assert await db.get_user_quest_mode("uid1") == "multi"
    await db.set_user_language("uid1", "vi")
    await db.set_user_quest_mode("uid1", "single")
    assert await db.get_user_language("uid1") == "vi"
    assert await db.get_user_quest_mode("uid1") == "single"
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


async def test_token_hygiene():
    from datetime import datetime, timezone, timedelta
    from bot.db.database import Database

    db = Database(":memory:")
    await db.init()

    # Failure counter increments and resets
    tid = await db.save_token("uid1", "main", b"enc_data", "hint", None)
    assert await db.record_token_failure(tid) == 1
    assert await db.record_token_failure(tid) == 2
    await db.reset_token_failures(tid)
    token = await db.get_token_by_id(tid)
    assert token["fail_count"] == 0

    # Dead by repeated failures
    tid2 = await db.save_token("uid2", "dead", b"enc_data", "hint", None)
    for _ in range(3):
        await db.record_token_failure(tid2)
    dead_ids = [d["id"] for d in await db.get_dead_tokens(3, 30)]
    assert tid2 in dead_ids and tid not in dead_ids

    # Stale by inactivity (inactive + old dates)
    tid3 = await db.save_token("uid3", "old", b"enc_data", "hint", None)
    await db.set_token_active(tid3, False)
    old = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    await db._db.execute(
        "UPDATE saved_tokens SET created_at = ?, last_run_at = ? WHERE id = ?",
        (old, old, tid3),
    )
    await db._db.commit()
    dead_ids = [d["id"] for d in await db.get_dead_tokens(3, 30)]
    assert tid3 in dead_ids

    # Active tokens are never considered stale, delete works
    assert await db.delete_token_by_id(tid3)
    assert await db.get_token_by_id(tid3) is None
    assert tid not in [d["id"] for d in await db.get_dead_tokens(3, 30)]

    await db.close()
    print("TOKEN HYGIENE: ALL TESTS PASSED")


async def test_quest_start_and_completion_callbacks():
    from bot.core.quest_engine import QuestEngine

    quest = {
        "id": "quest-1",
        "userStatus": {"enrolledAt": "2026-01-01T00:00:00+00:00"},
        "config": {
            "messages": {"questName": "Example quest"},
            "taskConfig": {"tasks": {"PLAY_ON_DESKTOP": {"target": 10}}},
        },
    }
    events = []
    engine = QuestEngine(api=object(), on_start=lambda quests: _record_start(events, quests))
    async def no_op_process(item):
        events.append(("process", item["id"]))
    engine.fetch_quests = _return_value([quest])
    engine.auto_accept = _return_value([quest])
    engine.process_quest = no_op_process
    await engine.run_once()
    assert events[0][0] == "start" and events[1] == ("process", "quest-1")

    events.clear()
    completed_quest = {
        **quest,
        "userStatus": {"enrolledAt": "2026-01-01T00:00:00+00:00", "completedAt": "2026-01-02T00:00:00+00:00"},
    }
    engine.fetch_quests = _return_value([completed_quest])
    engine.auto_accept = _return_value([completed_quest])
    await engine.run_once()
    assert not events, "on_start must not fire when there are no actionable quests"

    failed_engine = QuestEngine(api=object())
    async def fail_completion(item):
        return False
    failed_engine.complete_heartbeat = fail_completion
    await failed_engine.process_quest(quest)
    await failed_engine.wait_all()
    assert "quest-1" not in failed_engine.completed_ids

    from datetime import datetime, timezone

    class FakeResponse:
        def __init__(self, status, body):
            self.status = status
            self.body = body
        async def json(self):
            return self.body
        async def text(self):
            return "mock response"

    class FakeAPI:
        def __init__(self, responses):
            self.responses = iter(responses)
        async def post(self, *_args, **_kwargs):
            return next(self.responses)

    async def make_quest(task, target=5):
        return {
            "id": "quest-1",
            "userStatus": {"enrolledAt": datetime.now(timezone.utc).isoformat()},
            "config": {
                "messages": {"questName": "Example quest"},
                "taskConfig": {"tasks": {task: {"target": target}}},
            },
        }

    # The video handler must only report completion when Discord accepts it.
    video_quest = await make_quest("WATCH_VIDEO")
    video_engine = QuestEngine(api=FakeAPI([
        FakeResponse(200, {"completed_at": "now"}),
    ]))
    assert await video_engine.complete_video(video_quest)

    failed_video = QuestEngine(api=FakeAPI([
        FakeResponse(500, {}), FakeResponse(500, {}),
    ]))
    assert not await failed_video.complete_video(video_quest)

    heartbeat_quest = await make_quest("PLAY_ON_DESKTOP")
    heartbeat_engine = QuestEngine(api=FakeAPI([
        FakeResponse(200, {"progress": {"PLAY_ON_DESKTOP": {"value": 5}}}),
    ]))
    assert await heartbeat_engine.complete_heartbeat(heartbeat_quest)

    # Activity completion should remain true when finalization is rejected,
    # because Discord already confirmed the target in the progress response.
    activity_quest = await make_quest("PLAY_ACTIVITY")
    activity_engine = QuestEngine(api=FakeAPI([
        FakeResponse(200, {"progress": {"PLAY_ACTIVITY": {"value": 5}}}),
        FakeResponse(500, {}),
    ]))
    assert await activity_engine.complete_activity(activity_quest)

    print("QUEST CALLBACKS: ALL TESTS PASSED")


async def test_single_mode_is_sequential():
    from bot.core.quest_engine import QuestEngine

    def make_quest(qid):
        return {
            "id": qid,
            "userStatus": {"enrolledAt": "2026-01-01T00:00:00+00:00"},
            "config": {
                "messages": {"questName": qid},
                "taskConfig": {"tasks": {"WATCH_VIDEO": {"target": 1}}},
            },
        }

    running = 0
    max_running = 0
    start_order = []

    async def complete_video(_quest):
        nonlocal running, max_running
        running += 1
        max_running = max(max_running, running)
        await asyncio.sleep(0)
        running -= 1
        return True

    async def on_quest_start(qid, _name, _task_type):
        start_order.append(qid)

    engine = QuestEngine(
        api=object(), run_mode="single", on_quest_start=on_quest_start
    )
    engine.single_mode_delay = 0
    engine.fetch_quests = _return_value([make_quest("q1"), make_quest("q2")])
    engine.auto_accept = _return_value([make_quest("q1"), make_quest("q2")])
    engine.complete_video = complete_video

    summary = await engine.run_once()
    assert summary["run_mode"] == "single"
    assert summary["actionable_total"] == 2
    assert start_order == ["q1", "q2"]
    assert max_running == 1
    assert engine.active_quest_count == 0
    print("SINGLE MODE: SEQUENTIAL TEST PASSED")


async def _record_start(events, quests):
    events.append(("start", [q["id"] for q in quests]))


def _return_value(value):
    async def _callback(*args, **kwargs):
        return value
    return _callback


def test_formatters():
    from datetime import datetime, timezone, timedelta
    from bot.utils.formatter import (
        auto_run_embed,
        token_invalid_embed,
        token_deleted_embed,
    )

    next_run = datetime.now(timezone.utc) + timedelta(days=2)
    embed = auto_run_embed(
        "main", "abcd", 2, ["Quest A [WATCH_VIDEO]", "Quest B"], next_run
    )
    assert embed.title == "Auto-run summary"
    names = [f.name for f in embed.fields]
    assert "Quest details" in names and "Next scheduled run" in names

    startup_embed = auto_run_embed("main", "abcd", 1, None, None, startup=True)
    assert startup_embed.title == "Startup auto-run summary"

    empty_run = auto_run_embed("main", "abcd", 0, None, None, startup=True)
    assert empty_run.description == "No quests completed"

    invalid = token_invalid_embed("main", "abcd", 2, 3)
    assert invalid.title == "Invalid token"

    deleted = token_deleted_embed("main", "abcd", "test reason")
    assert deleted.title == "Token removed"

    # Long quest lists must stay inside Discord's 1024-char field limit
    many = [f"Quest {i} " + "x" * 60 for i in range(30)]
    long_embed = auto_run_embed("main", "abcd", 30, many, None)
    assert len(long_embed.fields[0].value) <= 1024

    print("FORMATTERS: ALL TESTS PASSED")


def test_progress_embeds():
    from bot.services.progress_message import ProgressMessage

    progress = ProgressMessage(channel=None, token_hint="abcd", language="en")
    progress._quests = {
        str(i): {
            "name": f"Quest {i} " + ("x" * 80),
            "task_type": "PLAY_ON_DESKTOP",
            "done": 0,
            "total": 100,
            "status": "running",
        }
        for i in range(30)
    }
    embed = progress._build_embed()
    assert all(len(field.value) <= 1024 for field in embed.fields)

    final = progress._build_final_embed({"total": 30, "completed_now": 0})
    assert final.title == "No quests completed"
    print("PROGRESS EMBEDS: ALL TESTS PASSED")


async def test_progress_message_lifecycle():
    from bot.services.progress_message import ProgressMessage

    class FakeMessage:
        def __init__(self, embed):
            self.id = 1
            self.embeds = [embed]
        async def edit(self, *, embed):
            self.embeds.append(embed)

    class FakeChannel:
        def __init__(self):
            self.message = None
        async def send(self, *, embed):
            self.message = FakeMessage(embed)
            return self.message

    channel = FakeChannel()
    progress = ProgressMessage(channel=channel, language="en", run_mode="startup")
    progress.update_quest("q1", "Quest 1", "PLAY_ON_DESKTOP", 0, 30)
    await progress.start()
    assert any(
        field.name == "Quest progress (0/1)" and "Quest 1" in field.value
        for field in channel.message.embeds[0].fields
    )

    progress.mark_complete("q1", "Quest 1", "PLAY_ON_DESKTOP", 30)
    await progress.finish({"total": 1, "completed_now": 1})
    assert channel.message.embeds[-1].title == "Startup auto-run summary"
    print("PROGRESS LIFECYCLE: ALL TESTS PASSED")


if __name__ == "__main__":
    test_imports()
    asyncio.run(test_db())
    asyncio.run(test_token_hygiene())
    asyncio.run(test_quest_start_and_completion_callbacks())
    asyncio.run(test_single_mode_is_sequential())
    test_rate_limiter()
    test_token_mask()
    test_formatters()
    test_progress_embeds()
    asyncio.run(test_progress_message_lifecycle())
    print("\n=== ALL VERIFICATION TESTS PASSED ===")
