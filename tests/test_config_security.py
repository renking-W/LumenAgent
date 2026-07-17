"""Configuration credential logging tests."""

import unittest

from lumen_agent.application.service.common.config_service import (
    _loggable_config_value,
)


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
