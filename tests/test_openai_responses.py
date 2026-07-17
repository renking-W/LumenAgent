"""OpenAI Responses API adapter tests."""

import json
import unittest

from lumen_agent.infrastructure.http_pool import StreamHandle
from lumen_agent.model_adapters import get_model_adapter
from lumen_agent.model_adapters.openai import OpenAIAdapter
from lumen_agent.model_adapters.client.openai_responses_client import (
    OpenAIResponsesHttpClient,
    response_content_blocks,
    to_responses_input,
    to_responses_tools,
)


class FakeSettings:
    def __init__(self, values=None):
        self.values = values or {}

    def get(self, key, default=None):
        return self.values.get(key, default)


class FakeStreamResponse:
    def __init__(self, events):
        self.events = events

    async def aiter_lines(self):
        for event in self.events:
            yield f"data: {json.dumps(event)}"


class TestOpenAIResponsesConversion(unittest.TestCase):
    def test_factory_selects_openai_adapter(self):
        adapter = get_model_adapter(FakeSettings({"LLM_PROVIDER": "openai"}))
        self.assertIsInstance(adapter, OpenAIAdapter)

    def test_converts_messages_tools_and_images(self):
        messages = [
            {
                "role": "system",
                "content": [{"type": "text", "text": "Be useful"}],
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Inspect this"},
                    {
                        "type": "image_url",
                        "image_url": {"url": "https://example.com/a.png"},
                    },
                ],
            },
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "call_1",
                        "name": "read",
                        "input": {"path": "a.py"},
                    },
                    {
                        "type": "tool_result",
                        "tool_use_id": "call_1",
                        "content": "print('ok')",
                    },
                ],
            },
        ]
        converted = to_responses_input(messages)
        self.assertEqual(
            converted[0], {"role": "system", "content": "Be useful"}
        )
        self.assertEqual(converted[1]["content"][1]["type"], "input_image")
        self.assertEqual(converted[2]["type"], "function_call")
        self.assertEqual(converted[3]["type"], "function_call_output")

        tools = to_responses_tools(
            [
                {
                    "name": "read",
                    "description": "Read a file",
                    "input_schema": {"type": "object"},
                }
            ]
        )
        self.assertEqual(tools[0]["name"], "read")
        self.assertNotIn("function", tools[0])

    def test_builds_responses_payload(self):
        client = OpenAIResponsesHttpClient(
            FakeSettings(
                {
                    "LLM_MODEL": "gpt-5.6",
                    "LLM_MAX_TOKENS": 2048,
                    "LLM_ENABLE_THINKING": True,
                    "AGENT_TOOL_CHOICE": "auto",
                }
            )
        )
        payload = client._payload(
            [{"role": "user", "content": [{"type": "text", "text": "hello"}]}],
            temperature=None,
            stream=True,
            tools=[{"name": "read", "input_schema": {"type": "object"}}],
        )
        self.assertEqual(payload["model"], "gpt-5.6")
        self.assertEqual(payload["max_output_tokens"], 2048)
        self.assertEqual(payload["reasoning"], {"summary": "auto"})
        self.assertTrue(payload["stream"])

    def test_extracts_text_and_reasoning_summary(self):
        blocks = response_content_blocks(
            {
                "output": [
                    {
                        "type": "reasoning",
                        "summary": [{"type": "summary_text", "text": "Checked."}],
                    },
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "Done."}],
                    },
                ]
            }
        )
        self.assertEqual(
            blocks[0], {"type": "thinking", "thinking": "Checked."}
        )
        self.assertEqual(blocks[1], {"type": "text", "text": "Done."})


class TestOpenAIResponsesStream(unittest.IsolatedAsyncioTestCase):
    async def test_parses_stream_events(self):
        handle = StreamHandle("POST", "https://example.test", protocol="responses")
        handle._state = "STREAMING"
        handle._response = FakeStreamResponse(
            [
                {
                    "type": "response.reasoning_summary_text.delta",
                    "delta": "Checking",
                },
                {"type": "response.output_text.delta", "delta": "Hello"},
                {
                    "type": "response.output_item.done",
                    "item": {
                        "type": "function_call",
                        "call_id": "call_1",
                        "name": "read",
                        "arguments": "{\"path\":\"a.py\"}",
                    },
                },
            ]
        )
        events = [event async for event in handle.receive()]
        self.assertEqual(events[0], ("reasoning_content", "Checking"))
        self.assertEqual(events[1], ("content", "Hello"))
        self.assertEqual(events[2][1]["input"], {"path": "a.py"})


if __name__ == "__main__":
    unittest.main()
