"""Testes isolados da leitura de .env (usam somente chaves fictícias)."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fase4.config import load_project_environment
from fase4.interfaces.cli import doctor


class EnvironmentConfigTests(unittest.TestCase):
    def test_reads_local_dotenv_without_exposing_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text(
                "AZURE_SPEECH_KEY=FAKE_SPEECH_TEST_KEY\n"
                "AZURE_SPEECH_REGION=brazilsouth\n"
                "AZURE_LANGUAGE_KEY=FAKE_LANGUAGE_TEST_KEY\n"
                "AZURE_LANGUAGE_ENDPOINT=https://fake.example.test/\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                self.assertTrue(load_project_environment(env_file))
                # Não lemos um eventual .env real durante o teste.
                with patch("fase4.interfaces.cli.load_project_environment", return_value=True):
                    status = doctor()
                self.assertTrue(status["azure_speech_configured"])
                self.assertTrue(status["azure_language_configured"])
                serialized = repr(status)
                self.assertNotIn("FAKE_SPEECH_TEST_KEY", serialized)
                self.assertNotIn("FAKE_LANGUAGE_TEST_KEY", serialized)

    def test_environment_variables_take_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("AZURE_SPEECH_KEY=DOTENV_FAKE_VALUE\n", encoding="utf-8")
            with patch.dict(os.environ, {"AZURE_SPEECH_KEY": "EXPORTED_FAKE_VALUE"}, clear=True):
                load_project_environment(env_file)
                self.assertEqual(os.environ["AZURE_SPEECH_KEY"], "EXPORTED_FAKE_VALUE")

    def test_missing_dotenv_is_optional(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            with patch.dict(os.environ, {}, clear=True):
                self.assertFalse(load_project_environment(env_file))
                self.assertNotIn("AZURE_SPEECH_KEY", os.environ)


if __name__ == "__main__":
    unittest.main()
