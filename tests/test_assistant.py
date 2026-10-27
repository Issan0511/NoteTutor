import asyncio
import base64
import io
import json
import os
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from PIL import Image

from note_tutor.Assistant import AssistantError, NoteAssistant, validate_question
from notesync.WebServer import WebBridge, WebServer


def snapshot(size=(32, 32)):
    buf = io.BytesIO()
    Image.new("RGB", size, "white").save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def sse(*events):
    return io.BytesIO(b": keep-alive\n\n" + b"".join(
        ("data: " + json.dumps(event) + "\n\n").encode() for event in events
    ))


class AssistantTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-placeholder", "BEAMERPLUS_CLAUDE_MODEL": "claude-sonnet-5-5"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.assistant = NoteAssistant()
        self.image = snapshot()

    def run_stream(self, events):
        chunks = []
        with patch("note_tutor.Assistant.urlopen", return_value=sse(*events)) as request:
            answer = self.assistant.stream("説明して", self.image, [], chunks.append, threading.Event())
        return answer, chunks, request.call_args[0][0]

    def test_image_validation(self):
        self.assertEqual(validate_question({"question": " 式は？ ", "context": "doc:0", "image": self.image}),
                         ("式は？", "doc:0", self.image))

    def test_malformed_or_oversized_image_rejected(self):
        for image in ("https://example.com/private.png", "data:image/png;base64,%%%", snapshot((2049, 1)),
                      self.image.replace("image/png", "image/jpeg")):
            with self.subTest(image=image[:40]), self.assertRaises(AssistantError):
                validate_question({"question": "式は？", "context": "doc:0", "image": image})

    def test_stream_assembles_text_and_keeps_credentials_out_of_payload(self):
        answer, chunks, request = self.run_stream([
            {"type": "message_start", "message": {"stop_reason": None}},
            {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
            {"type": "ping"},
            {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "式を"}},
            {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "確認します。"}},
            {"type": "content_block_stop", "index": 0},
            {"type": "message_delta", "delta": {"stop_reason": "end_turn"}},
            {"type": "message_stop"},
        ])
        self.assertEqual(answer, "式を確認します。")
        self.assertEqual(chunks, ["式を", "確認します。"])
        payload = json.loads(request.data)
        self.assertTrue(payload["stream"])
        self.assertEqual(payload["max_tokens"], 4096)
        image = payload["messages"][-1]["content"][0]
        self.assertEqual(image["type"], "image")
        self.assertEqual(image["source"]["type"], "base64")
        self.assertEqual(image["source"]["media_type"], "image/png")
        self.assertEqual(image["source"]["data"], self.image.split(",", 1)[1])
        self.assertEqual(payload["messages"][-1]["content"][1], {"type": "text", "text": "説明して"})
        self.assertIn("system", payload)
        self.assertNotIn("test-placeholder", request.data.decode())
        self.assertEqual(request.get_header("X-api-key"), "test-placeholder")
        self.assertEqual(request.get_header("Anthropic-version"), "2023-06-01")
        self.assertEqual(request.full_url, "https://api.anthropic.com/v1/messages")

    def test_truncated_stream_is_not_success(self):
        with self.assertRaisesRegex(AssistantError, "途中"):
            self.run_stream([{"type": "content_block_delta", "delta": {"type": "text_delta", "text": "部分的な回答"}}])

    def test_incomplete_and_failed_streams_are_not_success(self):
        for stop_reason in (None, "max_tokens", "model_context_window_exceeded", "tool_use", "pause_turn"):
            with self.subTest(stop_reason=stop_reason), self.assertRaises(AssistantError):
                self.run_stream([
                    {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "途中の回答"}},
                    {"type": "message_delta", "delta": {"stop_reason": stop_reason}},
                    {"type": "message_stop"},
                ])

    def test_api_error_event_is_not_success(self):
        with self.assertRaises(AssistantError):
            self.run_stream([{"type": "error", "error": {"type": "overloaded_error", "message": "secret"}}])

    def test_thinking_and_unknown_events_are_not_shown_as_answer(self):
        answer, chunks, _ = self.run_stream([
            {"type": "content_block_delta", "delta": {"type": "thinking_delta", "thinking": "internal"}},
            {"type": "future_event"},
            {"type": "content_block_start", "content_block": {"type": "text", "text": "回答"}},
            {"type": "message_delta", "delta": {"stop_reason": "end_turn"}},
            {"type": "message_stop"},
        ])
        self.assertEqual(answer, "回答")
        self.assertEqual(chunks, ["回答"])

    def test_refusal_text_is_displayed(self):
        answer, _, _ = self.run_stream([
            {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "回答できません"}},
            {"type": "message_delta", "delta": {"stop_reason": "refusal"}},
            {"type": "message_stop"},
        ])
        self.assertEqual(answer, "回答できません")

    def test_empty_completion_is_not_success(self):
        with self.assertRaises(AssistantError):
            self.run_stream([
                {"type": "message_delta", "delta": {"stop_reason": "end_turn"}},
                {"type": "message_stop"},
            ])

    def test_missing_key_does_not_call_api(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}), patch("note_tutor.Assistant.urlopen") as request:
            with self.assertRaisesRegex(AssistantError, "Claude設定"):
                self.assistant.stream("説明して", self.image, [], lambda _: None, threading.Event())
            request.assert_not_called()

    def test_cancelled_request_does_not_call_api(self):
        cancelled = threading.Event()
        cancelled.set()
        with patch("note_tutor.Assistant.urlopen") as request:
            self.assertEqual(self.assistant.stream("説明して", self.image, [], lambda _: None, cancelled), "")
            request.assert_not_called()

    def test_upstream_errors_do_not_expose_credentials(self):
        for status in (400, 401, 403, 404, 429, 500, 529):
            with self.subTest(status=status), patch("note_tutor.Assistant.urlopen", side_effect=HTTPError(
                "https://api.anthropic.com/v1/messages", status, "secret-test-placeholder", {}, None
            )):
                with self.assertRaises(AssistantError) as failure:
                    self.assistant.stream("説明して", self.image, [], lambda _: None, threading.Event())
                self.assertNotIn("test-placeholder", str(failure.exception))

    def test_concurrent_requests_are_bounded(self):
        self.assistant._slots.acquire()
        self.assistant._slots.acquire()
        try:
            with self.assertRaisesRegex(AssistantError, "回答中"):
                self.assistant.stream("説明して", self.image, [], lambda _: None, threading.Event())
        finally:
            self.assistant._slots.release()
            self.assistant._slots.release()


class FakeSocket:
    def __init__(self):
        self.messages = []

    async def send(self, message):
        self.messages.append(json.loads(message))


class ConversationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.server = WebServer(WebBridge(), lambda _: None, lambda: {})
        from note_tutor.plugin import TutorExtension, TutorConnection
        self.extension = TutorExtension()
        self.connection = TutorConnection(self.extension, None)
        self.socket = FakeSocket()
        self.session = {"context": None, "history": []}
        self.request = {"requestId": "test_1", "question": "説明して", "context": "doc:0", "image": snapshot()}

    async def ask(self):
        await self.connection._respond_to_ai(self.socket, self.request, self.session, threading.Event())

    async def test_stream_is_private_and_history_tracks_only_successful_turns(self):
        other_socket = FakeSocket()
        self.server.connected_clients = {self.socket, other_socket}
        def stream(question, image, history, emit, cancelled):
            emit("回答")
            return "回答"
        with patch.object(self.extension.assistant, "stream", side_effect=stream):
            await self.ask()
        self.assertEqual([item["type"] for item in self.socket.messages], ["ai_delta", "ai_done"])
        self.assertEqual(other_socket.messages, [])
        self.assertEqual(len(self.session["history"]), 2)
        self.assertNotIn("image", json.dumps(self.session))

    async def test_followup_keeps_history_but_new_page_discards_it(self):
        with patch.object(self.extension.assistant, "stream", return_value="回答") as stream:
            await self.ask()
            await self.ask()
            self.assertEqual(len(stream.call_args.args[2]), 2)
            self.request["context"] = "doc:1"
            await self.ask()
            self.assertEqual(stream.call_args.args[2], [])
            self.request["context"] = "another-doc:1"
            await self.ask()
            self.assertEqual(stream.call_args.args[2], [])

    async def test_failure_preserves_previous_history_and_reports_error(self):
        self.session.update(context="doc:0", history=[{"role": "user", "content": "前の質問"}])
        with patch.object(self.extension.assistant, "stream", side_effect=AssistantError("通信失敗")):
            await self.ask()
        self.assertEqual(len(self.session["history"]), 1)
        self.assertEqual(self.socket.messages[-1]["type"], "ai_error")

    async def test_ink_messages_continue_while_api_waits(self):
        started, release = threading.Event(), threading.Event()
        def stream(*args):
            started.set()
            release.wait(2)
            return "回答"
        with patch.object(self.extension.assistant, "stream", side_effect=stream):
            task = asyncio.create_task(self.ask())
            await asyncio.to_thread(started.wait, 2)
            with patch.object(self.server.bridge, "stroke_moved") as signal:
                self.server._handle_client_message({"type": "stroke_move", "normX": 0.5, "normY": 0.5})
                signal.emit.assert_called_once()
            release.set()
            await task


if __name__ == "__main__":
    unittest.main()
