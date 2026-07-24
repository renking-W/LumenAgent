"""配置凭据保护与 JWT Secret 初始化测试。"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lumen_agent.application.service.common.config_service import (
    _SYSTEM_PROTECTED_KEYS,
    _loggable_config_value,
)
from lumen_agent.infrastructure.start_need import config_loader


class TestConfigLogRedaction(unittest.TestCase):
    def test_redacts_credentials(self):
        for key in (
            "LLM_API_KEY",
            "EMBEDDING_API_KEY",
            "SERVICE_TOKEN",
            "CLIENT_SECRET",
            "DB_PASSWORD",
        ):
            self.assertEqual(_loggable_config_value(key, "secret"), "[REDACTED]")

    def test_keeps_non_sensitive_values(self):
        self.assertEqual(_loggable_config_value("LLM_MODEL", "gpt-5.6"), "gpt-5.6")


class TestJwtSecretInitialization(unittest.TestCase):
    """验证 JWT Secret 只在首次创建 config.json 时生成。"""

    def _load_with_files(self, config: dict, env_text: str = "") -> tuple[dict, dict]:
        """在临时配置文件上执行真实加载流程，并返回合并配置与落盘内容。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "config.json"
            env_path = root / ".env"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            env_path.write_text(env_text, encoding="utf-8")
            with (
                patch.object(config_loader, "_CONFIG_JSON_PATH", config_path),
                patch.object(config_loader, "_ENV_PATH", env_path),
            ):
                loaded = config_loader.load_and_merge()
            persisted = json.loads(config_path.read_text(encoding="utf-8"))
        return loaded, persisted

    def test_generates_secret_when_config_file_does_not_exist(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "config.json"
            env_path = root / ".env"
            env_path.write_text("", encoding="utf-8")
            with (
                patch.object(config_loader, "_CONFIG_JSON_PATH", config_path),
                patch.object(config_loader, "_ENV_PATH", env_path),
            ):
                loaded = config_loader.load_and_merge()

            persisted = json.loads(config_path.read_text(encoding="utf-8"))

        self.assertEqual(loaded["AUTH_JWT_SECRET"], persisted["AUTH_JWT_SECRET"])
        self.assertGreaterEqual(len(persisted["AUTH_JWT_SECRET"]), 64)

    def test_reuses_existing_config_secret(self):
        loaded, persisted = self._load_with_files(
            {"AUTH_JWT_SECRET": "existing-secret"},
            "AUTH_JWT_SECRET=\n",
        )

        self.assertEqual(loaded["AUTH_JWT_SECRET"], "existing-secret")
        self.assertEqual(persisted["AUTH_JWT_SECRET"], "existing-secret")

    def test_non_empty_env_secret_keeps_highest_priority(self):
        loaded, persisted = self._load_with_files(
            {"AUTH_JWT_SECRET": "config-secret"},
            "AUTH_JWT_SECRET=env-secret\n",
        )

        self.assertEqual(loaded["AUTH_JWT_SECRET"], "env-secret")
        self.assertEqual(persisted["AUTH_JWT_SECRET"], "config-secret")

    def test_secret_is_hidden_from_config_management(self):
        self.assertIn("AUTH_JWT_SECRET", _SYSTEM_PROTECTED_KEYS)
