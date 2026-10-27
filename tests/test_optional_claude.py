import asyncio
import os
import unittest
from unittest.mock import Mock, patch
from note_tutor.plugin import TutorExtension


class OptionalClaudeTests(unittest.TestCase):
    def test_default_keeps_tutoring_instructions_without_provider_or_controls(self):
        with patch.dict(os.environ, {}, clear=True), patch('note_tutor.plugin.load_local_settings'), \
             patch('note_tutor.plugin.NoteAssistant') as assistant, patch('note_tutor.plugin.TutorControls') as controls:
            extension = TutorExtension()
            assistant.assert_not_called()
            self.assertFalse(extension.claude_enabled)
            self.assertIsNone(extension.attach_window(Mock()))
            controls.assert_not_called()
            css, html, script = extension.tablet_assets()
            self.assertEqual((css, html), ('', ''))
            self.assertIn('handleExtensionMessage', script)
            self.assertIn('read_current_note', extension.mcp_instructions())
            self.assertNotIn('first use read_note_context', extension.mcp_instructions())
            session = extension.connection(None, Mock())
            async def no_provider_calls():
                await session.connected()
                self.assertFalse(await session.handle({'type': 'ai_ask'}))
                await session.close()
            asyncio.run(no_provider_calls())

    def test_explicit_enable_restores_claude_features(self):
        with patch.dict(os.environ, {'NOTETUTOR_CLAUDE_ENABLED': '1'}, clear=True), \
             patch('note_tutor.plugin.load_local_settings'), patch('note_tutor.plugin.NoteAssistant') as assistant:
            extension = TutorExtension()
            assistant.assert_called_once()
            self.assertTrue(extension.claude_enabled)
            self.assertIn('assistant-panel', extension.tablet_assets()[1])
            self.assertIn('first use read_note_context', extension.mcp_instructions())
            self.assertIsNotNone(extension.connection(None, Mock()))
