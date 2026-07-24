"""摘要压缩并发状态与记忆幂等写入测试。"""

from __future__ import annotations

import asyncio
import re
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from lumen_agent.agent.memory.memory_utils import MemoryFileUtils
from lumen_agent.infrastructure.data_base.sqlite_conversation import (
    SqliteConversationRepository,
)


class SummaryCompactionRepositoryTest(unittest.IsolatedAsyncioTestCase):
    """验证同一会话只能被一个摘要任务抢占。"""

    async def test_claim_once_and_preserve_new_round_count(self) -> None:
        """提交时只扣已压缩轮数，不覆盖运行期间新增的轮次。"""
        with tempfile.TemporaryDirectory() as directory:
            repo = SqliteConversationRepository(Path(directory) / "conversation.db")
            await repo.ensure_session("session-1")
            for index in range(3):
                await repo.append_message("session-1", "user", f"问题 {index}")
                await repo.append_message("session-1", "assistant", f"回答 {index}")
                await repo.increment_round_counter("session-1")

            first, second = await asyncio.gather(
                repo.claim_summary_compaction("session-1", stale_after_seconds=60),
                repo.claim_summary_compaction("session-1", stale_after_seconds=60),
            )
            claims = [claim for claim in (first, second) if claim is not None]
            self.assertEqual(len(claims), 1)
            claim = claims[0]

            # 模拟摘要生成期间又完成了一轮对话。
            await repo.append_message("session-1", "user", "新问题")
            await repo.append_message("session-1", "assistant", "新回答")
            await repo.increment_round_counter("session-1")

            committed = await repo.complete_summary_compaction(
                "session-1",
                compaction_started_at=str(claim["compaction_started_at"]),
                new_summary="新摘要",
                summary_cursor_seq=3,
                compressed_turns=2,
            )
            self.assertTrue(committed)
            session = await repo.get_session("session-1")
            self.assertIsNotNone(session)
            assert session is not None
            self.assertEqual(session["count"], 2)
            self.assertEqual(session["summary_cursor_seq"], 3)
            self.assertEqual(session["compaction_in_progress"], 0)


class MemoryFileIdempotencyTest(unittest.TestCase):
    """验证相同消息区间不会在每日记忆中重复追加。"""

    def test_same_entry_id_replaces_existing_block(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            memory = MemoryFileUtils(Path(directory))
            entry_id = "session:session-1:seq:0-3"
            memory.append_daily_summary("session-1", "第一次内容", entry_id=entry_id)
            memory.append_daily_summary("session-1", "第二次内容", entry_id=entry_id)

            content = memory.daily_file_path().read_text(encoding="utf-8")
            self.assertEqual(content.count(f"entry_id={entry_id}"), 1)
            self.assertNotIn("第一次内容", content)
            self.assertIn("第二次内容", content)


    def test_entry_id_uses_exact_boundary_and_searches_old_files(self) -> None:
        """短 ID 不误命中长 ID，跨日期重试仍覆盖原文件。"""
        with tempfile.TemporaryDirectory() as directory:
            memory = MemoryFileUtils(Path(directory))
            memory.ensure_dir()
            old_date = date.today() - timedelta(days=1)
            old_path = memory.daily_file_path(old_date)
            short_id = "session:session-1:seq:0-3"
            long_id = "session:session-1:seq:0-30"
            old_path.write_text(
                "## 2026-01-01 00:00:00  session=session-1  "
                f"entry_id={long_id}\n\n长区间\n\n---\n\n"
                "## 2026-01-01 00:01:00  session=session-1  "
                f"entry_id={short_id}\n\n旧短区间\n\n---\n\n",
                encoding="utf-8",
            )

            result = memory.append_daily_summary(
                "session-1",
                "新短区间",
                entry_id=short_id,
            )

            self.assertIsNotNone(result)
            assert result is not None
            self.assertEqual(result[0], old_path)
            content = old_path.read_text(encoding="utf-8")
            short_matches = re.findall(
                rf"entry_id={re.escape(short_id)}(?:\s|$)", content
            )
            long_matches = re.findall(
                rf"entry_id={re.escape(long_id)}(?:\s|$)", content
            )
            self.assertEqual(len(short_matches), 1)
            self.assertEqual(len(long_matches), 1)
            self.assertIn("长区间", content)
            self.assertNotIn("旧短区间", content)
            self.assertIn("新短区间", content)

if __name__ == "__main__":
    unittest.main()
