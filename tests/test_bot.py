import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bot


def youtube_item(vid, title, age_hours=1, duration="PT5M", live="none"):
    published = (datetime.now(timezone.utc) - timedelta(hours=age_hours)).isoformat().replace("+00:00", "Z")
    return {"id": vid, "snippet": {"title": title, "publishedAt": published,
            "liveBroadcastContent": live,
            "thumbnails": {"high": {"url": f"https://img.test/{vid}.jpg"}}},
            "contentDetails": {"duration": duration}, "status": {"privacyStatus": "public"}}


class Response:
    def __init__(self, data, status=200):
        self._data, self.status_code, self.ok, self.text = data, status, status < 400, ""
    def json(self): return self._data


class FakeHTTP:
    def __init__(self, videos):
        self.videos = videos
        self.sent = []
        self.fail_after = None
    def get(self, url, params=None, **kwargs):
        if url.endswith("/channels"):
            return Response({"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UUabc"}}}]})
        if url.endswith("/playlistItems"):
            return Response({"items": [{"contentDetails": {"videoId": v["id"]}} for v in self.videos]})
        if url.endswith("/videos"):
            return Response({"items": self.videos})
        raise AssertionError(url)
    def post(self, url, json=None, **kwargs):
        method = url.rsplit("/", 1)[-1]
        if method == "sendPhoto" and self.fail_after == 0:
            self.fail_after = None
            raise bot.requests.Timeout("simulated timeout")
        if method == "sendPhoto" and self.fail_after is not None:
            self.fail_after -= 1
        self.sent.append((method, json))
        return Response({"ok": True, "result": {"message_id": len(self.sent)}})


class BotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state_file = Path(self.temp.name) / "state.json"
        self.env = patch.dict(os.environ, {
            "YOUTUBE_API_KEY": "test-key", "TELEGRAM_BOT_TOKEN": "123:test",
            "TELEGRAM_CHAT_ID": "@testchannel", "YOUTUBE_HANDLE": "Sir_Mr_yellow138",
            "INITIAL_POST_LIMIT": "2", "MAX_POSTS_PER_RUN": "5", "MAX_AGE_DAYS": "14",
        }, clear=False)
        self.env.start()
        self.state_patch = patch.object(bot, "STATE_FILE", self.state_file)
        self.state_patch.start()
        self.config_patch = patch.multiple(bot, INITIAL_POST_LIMIT=2, MAX_POSTS_PER_RUN=5, MAX_AGE_DAYS=14, MAX_ITEMS=15)
        self.config_patch.start()
    def tearDown(self):
        self.config_patch.stop()
        self.state_patch.stop()
        self.env.stop()
        self.temp.cleanup()
    def use_fake(self, videos):
        fake = FakeHTTP(videos)
        self.http_patch = patch.object(bot, "HTTP", fake)
        self.http_patch.start()
        self.addCleanup(self.http_patch.stop)
        return fake

    def test_first_run_posts_in_order_and_deduplicates(self):
        fake = self.use_fake([youtube_item("v3", "newest"), youtube_item("v2", "middle", 2), youtube_item("v1", "oldest", 3)])
        bot.main()
        posts = [payload for method, payload in fake.sent if method == "sendPhoto"]
        self.assertEqual(len(posts), 2)
        self.assertIn("middle", posts[0]["caption"])
        self.assertIn("newest", posts[1]["caption"])
        self.assertEqual(posts[0]["reply_markup"]["inline_keyboard"][0][0]["text"], "🍿 پخشش کن!")
        state = json.loads(self.state_file.read_text())
        self.assertTrue(state["initialized"])
        self.assertEqual(set(state["posted_ids"]), {"v1", "v2", "v3"})
        fake.sent.clear()
        bot.main()
        self.assertFalse(fake.sent)

    def test_failure_preserves_success_and_retries_remaining(self):
        fake = self.use_fake([youtube_item("v3", "newest"), youtube_item("v2", "middle", 2), youtube_item("v1", "oldest", 3)])
        fake.fail_after = 1
        with self.assertRaises(bot.BotError):
            bot.main()
        state = json.loads(self.state_file.read_text())
        self.assertFalse(state["initialized"])
        self.assertIn("v1", state["posted_ids"])
        fake.sent.clear()
        bot.main()
        final = json.loads(self.state_file.read_text())
        self.assertTrue(final["initialized"])
        self.assertTrue({"v1", "v2", "v3"}.issubset(set(final["posted_ids"])))

    def test_live_and_upcoming_are_excluded(self):
        fake = self.use_fake([youtube_item("live", "live", live="live"), youtube_item("up", "upcoming", live="upcoming"), youtube_item("ok", "normal")])
        bot.main()
        captions = [p.get("caption", "") for m, p in fake.sent if m == "sendPhoto"]
        self.assertEqual(len(captions), 1)
        self.assertIn("normal", captions[0])

    def test_short_heuristic_and_caption_html_are_safe(self):
        short = youtube_item("short", "#Shorts <b>title</b>", duration="PT50S")
        self.assertTrue(bot.is_probable_short(short))
        self.assertTrue(bot.video_url(short).endswith("/shorts/short"))
        short["snippet"]["title"] = "x & <" * 1000
        caption = bot.build_caption(short)
        self.assertEqual(caption.count("<b>"), 1)
        self.assertEqual(caption.count("</b>"), 1)
        self.assertLessEqual(len(caption), 1024)

    def test_state_preserves_order_and_unique_ids(self):
        state = bot.default_state()
        for vid in ("a", "b", "a"):
            bot.append_seen(state, vid)
        bot.save_state(state)
        self.assertEqual(json.loads(self.state_file.read_text())["posted_ids"], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
