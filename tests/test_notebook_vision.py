"""Incremental transcription, stale-result races and bounded API failures."""

from copy import deepcopy
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from note_tutor.NotebookVision import NotebookVision, VisionError, ink_regions, recognize_regions, render_region
from notesync.NotebookWindow import NotebookWindow


def stroke(y=.2, x=.15):
    return dict(points=[(x, y, 1), (x + .15, y + .025, 1)], width_ratio=.005,
                color='#202124', opacity=1, brush='pen')


def transcription(images, model, key):
    return {item['id']: dict(latex='H(X\\mid Y)', text='', uncertain=[]) for item in images}


class RegionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_adjacent_scripts_group_and_unmodified_line_keeps_its_id(self):
        a, b = stroke(.2), stroke(.6)
        initial = ink_regions([a, b])
        self.assertEqual(len(initial), 2)
        script = stroke(.18, .32)
        changed = ink_regions([a, b, script])
        self.assertEqual(len(changed), 2)
        self.assertNotEqual(changed[0].id, initial[0].id)
        self.assertEqual(changed[1].id, initial[1].id)
        self.assertEqual(ink_regions([b])[0].id, initial[1].id)
        moved = deepcopy(b)
        moved['points'][0] = (.1, .6, 1)
        self.assertNotEqual(ink_regions([moved])[0].id, initial[1].id)

    def test_crop_contains_ink_and_is_smaller_than_page(self):
        region = ink_regions([stroke()])[0]
        rendered = render_region(region, 4 / 3)
        image = QImage.fromData(rendered['png'])
        self.assertFalse(image.isNull())
        self.assertLess(image.width() * image.height(), 1600 * 1200 / 10)
        self.assertTrue(any(image.pixelColor(x, y).red() < 100 for x in range(image.width())
                            for y in range(image.height())))


class ProviderTests(unittest.TestCase):
    def response(self, regions, reason='end_turn'):
        return io.BytesIO(json.dumps({'stop_reason': reason,
                         'content': [{'type': 'text', 'text': json.dumps({'regions': regions})}]}).encode())

    def test_short_batch_transcription_and_key_not_in_body(self):
        images = [dict(id='one', png=b'png'), dict(id='two', png=b'png2')]
        results = [dict(id=item['id'], latex='x=y', text='', uncertain=[]) for item in images]
        with patch('note_tutor.NotebookVision.urlopen', return_value=self.response(results)) as network:
            result = recognize_regions(images, 'configured-model', 'private-placeholder')
        self.assertEqual(set(result), {'one', 'two'})
        request = network.call_args.args[0]
        body = json.loads(request.data)
        self.assertEqual(body['max_tokens'], 2048)
        self.assertNotIn('tools', body)
        self.assertNotIn('private-placeholder', request.data.decode())
        self.assertEqual(request.get_header('X-api-key'), 'private-placeholder')
        self.assertEqual(len([part for part in body['messages'][0]['content'] if part['type'] == 'image']), 2)

    def test_missing_duplicate_and_truncated_results_are_rejected(self):
        item = dict(id='one', latex='x', text='', uncertain=[])
        for regions, reason in [([], 'end_turn'), ([item, item], 'end_turn'),
                                ([dict(item, id='other')], 'end_turn'), ([item], 'max_tokens'),
                                ([dict(item, uncertain='guess')], 'end_turn')]:
            with self.subTest(regions=regions, reason=reason), patch(
                    'note_tutor.NotebookVision.urlopen', return_value=self.response(regions, reason)):
                with self.assertRaises(VisionError):
                    recognize_regions([dict(id='one', png=b'png')], 'model', 'placeholder')

    def test_api_error_is_safe(self):
        with patch('note_tutor.NotebookVision.urlopen', side_effect=HTTPError(
                'https://api.anthropic.com/v1/messages', 401, 'private-placeholder', {}, None)):
            with self.assertRaises(VisionError) as error:
                recognize_regions([dict(id='one', png=b'png')], 'model', 'private-placeholder')
        self.assertNotIn('private-placeholder', str(error.exception))


class VisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        env = patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-placeholder'})
        env.start()
        self.addCleanup(env.stop)
        self.meta = dict(note_id='note', page_id='page', revision='0', aspect=4 / 3,
                         pen_active=False, title='test', page_index=0, page_count=1, texts=[])
        self.ink = [stroke(.2), stroke(.6)]
        self.calls = []
        self.model = 'model'

        def recognize(images, model, key):
            self.calls.append(deepcopy(images))
            return transcription(images, model, key)

        self.vision = NotebookVision(lambda: (dict(self.meta), deepcopy(self.ink)),
                                    lambda: dict(self.meta), lambda: self.model,
                                    recognizer=recognize, debounce_ms=20, min_interval_ms=0)
        self.addCleanup(self.vision.stop)

    def wait_for(self, predicate):
        deadline = time.monotonic() + 3
        while not predicate() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(.002)
        self.assertTrue(predicate(), 'background transcription did not finish')

    def start(self):
        self.vision.set_enabled(True)
        self.vision.timer.stop()
        self.vision._pump()

    def change(self):
        self.meta['revision'] = str(int(self.meta['revision']) + 1)
        self.vision.source_changed()

    def test_only_changed_region_is_recognized_and_context_reads_are_cached(self):
        self.start()
        self.wait_for(lambda: self.vision.read()['fresh'])
        first = self.vision.read()
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(len(self.calls[0]), 2)
        with patch('note_tutor.NotebookVision.render_region', side_effect=AssertionError('must use cache')):
            unchanged = self.vision.read(first['context_revision'])
        self.assertTrue(unchanged['unchanged'])
        self.assertEqual(unchanged['blocks'], [])
        self.ink.append(stroke(.21, .4))
        self.change()
        pending = self.vision.read(first['context_revision'])
        self.assertFalse(pending['fresh'])
        self.assertEqual(len(pending['removed_block_ids']), 1)
        self.assertEqual(len(pending['blocks']), 1)
        self.assertNotIn('latex', pending['blocks'][0])
        self.wait_for(lambda: self.vision.read()['fresh'])
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(len(self.calls[-1]), 1)
        # Undo reuses the cached original transcription without another API call.
        self.ink.pop()
        self.change()
        self.assertTrue(self.vision.read()['fresh'])
        self.assertEqual(len(self.calls), 2)
        self.assertGreater(self.vision.read()['metrics']['cache_hits'], 0)

    def test_deleted_ink_never_returns_old_transcription_and_clear_is_free(self):
        self.start()
        self.wait_for(lambda: self.vision.read()['fresh'])
        first = self.vision.read()
        self.ink.clear()
        self.change()
        cleared = self.vision.read(first['context_revision'])
        self.assertTrue(cleared['fresh'])
        self.assertEqual(cleared['blocks'], [])
        self.assertEqual(len(cleared['removed_block_ids']), 2)
        self.assertEqual(len(self.calls), 1)

    def test_page_switch_and_inflight_edit_cannot_publish_stale_result(self):
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)

        def blocked(images, model, key):
            self.calls.append(deepcopy(images))
            entered.set()
            release.wait(3)
            return transcription(images, model, key)

        self.vision.recognizer = blocked
        self.start()
        self.assertTrue(entered.wait(1))
        self.meta['page_id'] = 'other-page'
        self.ink = [stroke(.3)]
        self.change()
        before = self.vision.read()
        self.assertFalse(before['fresh'])
        self.assertTrue(all('latex' not in block for block in before['blocks']))
        self.assertEqual(len(self.calls), 1)  # Only one request can be in flight.
        release.set()
        self.wait_for(lambda: self.vision.read()['fresh'])
        current = self.vision.read()
        self.assertEqual(current['page_id'], 'other-page')
        self.assertEqual(current['block_count'], 1)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.calls[-1][0]['id'], current['blocks'][0]['id'])

    def test_pen_down_disables_freshness_and_does_not_send_requests(self):
        self.meta['pen_active'] = True
        self.start()
        self.assertFalse(self.vision.read()['fresh'])
        self.assertEqual(self.calls, [])
        self.meta['pen_active'] = False
        self.change()
        self.wait_for(lambda: self.vision.read()['fresh'])
        self.assertEqual(len(self.calls), 1)

    def test_model_change_rerecognizes_and_unknown_delta_is_full_snapshot(self):
        self.start()
        self.wait_for(lambda: self.vision.read()['fresh'])
        self.model = 'other-model'
        self.vision.configuration_changed()
        self.assertFalse(self.vision.read()['fresh'])
        self.wait_for(lambda: self.vision.read()['fresh'])
        self.assertEqual(len(self.calls), 2)
        self.assertTrue(self.vision.read('unknown')['full_snapshot'])

    def test_inflight_same_page_rewrite_discards_old_expression(self):
        release = threading.Event()
        self.addCleanup(release.set)
        original = self.vision.recognizer

        def blocked(images, model, key):
            self.calls.append(deepcopy(images))
            release.wait(3)
            return transcription(images, model, key)

        self.vision.recognizer = blocked
        self.start()
        old_id = ink_regions(self.ink)[0].id
        self.ink[0] = stroke(.2, .4)
        self.change()
        # Replan while the old API request is still running.
        pending = self.vision.read()
        self.assertNotIn(old_id, [block['id'] for block in pending['blocks']])
        self.vision.recognizer = original
        release.set()
        self.wait_for(lambda: self.vision.read()['fresh'])
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(len(self.calls[-1]), 1)
        self.assertNotIn(old_id, [block['id'] for block in self.vision.read()['blocks']])

    def test_disabled_inflight_result_cannot_reappear_without_new_request(self):
        release = threading.Event()
        self.addCleanup(release.set)

        def blocked(images, model, key):
            self.calls.append(images)
            release.wait(3)
            return transcription(images, model, key)

        self.vision.recognizer = blocked
        self.start()
        self.vision.set_enabled(False)
        release.set()
        self.wait_for(lambda: not self.vision._busy)
        self.assertFalse(self.vision.read()['fresh'])
        self.assertEqual(len(self.calls), 1)
        self.vision.set_enabled(True)
        self.wait_for(lambda: self.vision.read()['fresh'])
        self.assertEqual(len(self.calls), 2)

    def test_continuous_writing_is_not_perpetually_debounced_and_rate_limit_holds(self):
        self.vision.set_enabled(True)
        self.vision._scheduled_since = time.monotonic() - 3
        self.vision.source_changed()
        self.assertLessEqual(self.vision.timer.remainingTime(), 1)
        self.vision.timer.stop()
        self.vision.min_interval_ms = 2000
        self.vision._last_request = time.monotonic()
        self.vision._pump()
        self.assertEqual(self.calls, [])
        self.assertGreater(self.vision.timer.remainingTime(), 1000)
        self.vision.timer.stop()
        self.vision._last_request -= 3
        self.vision._pump()
        self.wait_for(lambda: self.vision.read()['fresh'])
        self.assertEqual(len(self.calls), 1)

    def test_failures_pause_all_requests_until_explicit_retry(self):
        self.ink = [stroke(index / 10) for index in range(1, 9)]
        self.vision.recognizer = lambda *args: (_ for _ in ()).throw(VisionError('API unavailable'))
        self.start()
        self.wait_for(lambda: self.vision.read()['status'] == 'error')
        self.vision._pump()
        self.assertEqual(self.vision.request_count, 1)
        self.assertFalse(self.vision.read()['fresh'])
        self.vision.recognizer = transcription
        self.vision.set_enabled(True)
        self.wait_for(lambda: self.vision.read()['fresh'])
        self.assertEqual(self.vision.request_count, 3)  # Retry two bounded batches.

    def test_missing_key_disabled_and_stopped_never_call_api(self):
        self.assertEqual(self.vision.read()['status'], 'disabled')
        self.vision._pump()
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': ''}):
            self.start()
            self.assertEqual(self.vision.read()['status'], 'no_api_key')
        self.vision.stop()
        self.vision._pump()
        self.assertEqual(self.calls, [])


class VisionWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_window_toggle_and_text_only_mcp_do_not_render_or_write_ink(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'BEAMERPLUS_VISION_ENABLED': '0'}), patch(
                'notesync.WebServer.WebServer.start'), patch('notesync.WebServer.WebServer.stop'), patch(
                'notesync.NotebookWindow.NotebookBridge', return_value=None):
            window = NotebookWindow(store_path=Path(folder) / 'notes.json')
            controls = window.extension_instances[0]
            try:
                window.controller.begin_custom_stroke('#202124', .005, 1, .1, .2)
                window.controller.add_stroke_point(.3, .22)
                window.controller.end_stroke()
                controls.vision.recognizer = transcription
                with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'placeholder'}):
                    controls.vision_button.setChecked(True)
                    controls.vision._pump()
                    deadline = time.monotonic() + 3
                    while not controls.vision.read()['fresh'] and time.monotonic() < deadline:
                        self.app.processEvents()
                        time.sleep(.002)
                    with patch.object(window, 'render_current_page_image_with_sketch', side_effect=AssertionError()):
                        result = window._handle_mcp_call('read_note_context', {})
                    self.assertTrue(result['fresh'])
                    self.assertIn('latex', result['blocks'][0])
                    self.assertNotIn('image', result)
                    self.assertEqual(len(window.controller.serialized_ink()), 1)
                    self.assertEqual(window.controller.serialized_texts(), [])
                    controls._update_vision_status()
                    self.assertIn('先読み済み', controls.vision_label.text())
            finally:
                window.close()
