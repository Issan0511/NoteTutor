import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from note_tutor.LocalSettings import load_local_settings


class LocalSettingsTests(unittest.TestCase):
    def test_dotenv_quotes_existing_environment_and_literal_values(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            path = Path(folder) / '.env'
            path.write_text('ANTHROPIC_API_KEY="placeholder-${UNSET}"\n'
                            'BEAMERPLUS_CLAUDE_MODEL=file-model\n'
                            'BEAMERPLUS_VISION_MODEL=vision-model\n'
                            'BEAMERPLUS_VISION_ENABLED=1\nUNRELATED=ignored\n')
            os.environ['BEAMERPLUS_CLAUDE_MODEL'] = 'existing-model'
            load_local_settings(path)
            self.assertEqual(os.environ['ANTHROPIC_API_KEY'], 'placeholder-${UNSET}')
            self.assertEqual(os.environ['BEAMERPLUS_CLAUDE_MODEL'], 'existing-model')
            self.assertEqual(os.environ['BEAMERPLUS_VISION_MODEL'], 'vision-model')
            self.assertEqual(os.environ['BEAMERPLUS_VISION_ENABLED'], '1')
            self.assertNotIn('UNRELATED', os.environ)

    def test_explicit_file_missing_file_and_empty_key(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            path = Path(folder) / '.env'
            os.environ['BEAMERPLUS_ENV_FILE'] = str(path)
            load_local_settings()
            self.assertNotIn('ANTHROPIC_API_KEY', os.environ)
            path.write_text('ANTHROPIC_API_KEY=\n')
            load_local_settings()
            self.assertNotIn('ANTHROPIC_API_KEY', os.environ)

    def test_new_settings_and_legacy_environment_precedence(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            path = Path(folder) / '.env'
            path.write_text('NOTETUTOR_CLAUDE_MODEL=file-model\nNOTETUTOR_VISION_ENABLED=1\n')
            os.environ['BEAMERPLUS_CLAUDE_MODEL'] = 'legacy-shell'
            os.environ['NOTETUTOR_VISION_ENABLED'] = '0'
            load_local_settings(path)
            self.assertEqual(os.environ['NOTETUTOR_CLAUDE_MODEL'], 'legacy-shell')
            self.assertEqual(os.environ['NOTETUTOR_VISION_ENABLED'], '0')
