"""上下文组装的用户消息持久化回归测试。"""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lumen_agent.application.common.context_assembly import assemble_for_llm
from lumen_agent.application.service.chat.chat_service import _build_user_blocks


class _FakeRepository:
    """提供上下文组装所需的最小只读会话仓库。"""

    def __init__(self, messages: list[dict]) -> None:
        self._messages = messages

    async def get_session(self, session_id: str) -> dict:
        return {"id": session_id, "summary": ""}

    async def list_recent_messages(self, session_id: str, limit: int) -> list[dict]:
        return self._messages[-limit:]


class _FakeCounter:
    """测试只关注消息结构，不执行真实 Token 计算。"""

    def count_messages(self, messages: list[dict]) -> int:
        return 1


class ContextAssemblyTest(unittest.TestCase):
    def test_current_user_message_is_added_once_from_database(self) -> None:
        """当前用户消息只从数据库进入模型上下文一次。"""
        messages = [
            {"role": "user", "content": [{"type": "text", "text": "测试消息"}]}
        ]

        result = asyncio.run(
            assemble_for_llm(
                _FakeRepository(messages),
                object(),
                {
                    "SUMMARY_THRESHOLD_TURNS": 6,
                    "CONTEXT_FORCE_COMPRESS_RATIO": 0.5,
                },
                session_id="session-1",
                system_content=None,
                counter=_FakeCounter(),
                context_window=1000,
            )
        )

        self.assertEqual(result.messages, messages)

    def test_persisted_file_and_image_are_prepared_for_llm(self) -> None:
        """文件元数据和图片引用落库后仍能转换成模型输入格式。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "sample.png"
            image_path.write_bytes(b"image-bytes")
            blocks = _build_user_blocks(
                "查看附件",
                [
                    {
                        "name": "report.pdf",
                        "path": "D:/report.pdf",
                        "extension": ".pdf",
                        "size": 12,
                    }
                ],
                ["/v1/files/sample.png"],
            )
            messages = [{"role": "user", "content": blocks}]

            with patch(
                "lumen_agent.application.common.context_assembly.DirGuide.tmp_dir",
                return_value=Path(temp_dir),
            ):
                result = asyncio.run(
                    assemble_for_llm(
                        _FakeRepository(messages),
                        object(),
                        {
                            "SUMMARY_THRESHOLD_TURNS": 6,
                            "CONTEXT_FORCE_COMPRESS_RATIO": 0.5,
                        },
                        session_id="session-2",
                        system_content=None,
                        counter=_FakeCounter(),
                        context_window=1000,
                    )
                )

        content = result.messages[-1]["content"]
        self.assertEqual(content[0], {"type": "text", "text": "查看附件"})
        self.assertEqual(content[1]["type"], "text")
        self.assertIn("D:/report.pdf", content[1]["text"])
        self.assertTrue(
            content[2]["image_url"]["url"].startswith("data:image/png;base64,")
        )


if __name__ == "__main__":
    unittest.main()
