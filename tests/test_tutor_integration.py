import os
os.environ['NOTETUTOR_VISION_ENABLED'] = '0'
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile, threading, time, unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from notesync.NotebookWindow import NotebookWindow
from notesync.NotebookMCP import NotebookClient

class TutorBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)
        start = patch('notesync.WebServer.WebServer.start')
        stop = patch('notesync.WebServer.WebServer.stop')
        start.start()
        stop.start()
        self.addCleanup(start.stop)
        self.addCleanup(stop.stop)
        self.window = NotebookWindow(store_path=self.path / 'notes.json', mcp_connection_file=self.path / 'connection.json')
        self.addCleanup(self.window.close)
        self.client = NotebookClient(self.path / 'connection.json')

    def call_in_worker(self, function):
        result, errors = [], []

        def run():
            try:
                result.append(function())
            except BaseException as exc:
                errors.append(exc)

        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        deadline = time.monotonic() + 30
        while worker.is_alive() and time.monotonic() < deadline:
            self.app.processEvents()
            worker.join(.005)
        self.assertFalse(worker.is_alive(), 'MCP request did not finish')
        if errors:
            raise errors[0]
        return result[0]

    def test_loopback_context_reuses_background_transcription_without_image(self):
        controller = self.window.controller
        controller.begin_custom_stroke('#202124', .005, 1, .1, .2)
        controller.add_stroke_point(.3, .22)
        controller.end_stroke()
        calls = []

        def recognize(images, model, key):
            calls.append(images)
            return {item['id']: {'latex': 'H(X\\mid Y)', 'text': '', 'uncertain': []} for item in images}

        self.window.extension_instances[0].vision.recognizer = recognize
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-placeholder'}):
            self.window.extension_instances[0].vision.set_enabled(True)
            self.window.extension_instances[0].vision._pump()
            deadline = time.monotonic() + 3
            while not self.window.extension_instances[0].vision.read()['fresh'] and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(.002)
            with patch.object(self.window, 'render_current_page_image_with_sketch', side_effect=AssertionError()):
                first = self.call_in_worker(lambda: self.client.call('read_note_context'))
                second = self.call_in_worker(lambda: self.client.call('read_note_context',
                                              since_revision=first['context_revision']))
            self.assertTrue(first['fresh'])
            self.assertEqual(first['blocks'][0]['latex'], 'H(X\\mid Y)')
            self.assertNotIn('image', first)
            self.assertTrue(second['unchanged'])
            self.assertEqual(second['blocks'], [])
            self.assertEqual(len(calls), 1)
