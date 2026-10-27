"""Desktop controls and text-only tutor access to background transcription."""

import os

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QPushButton, QToolBar

from note_tutor.NotebookVision import NotebookVision


class TutorControls:
    def __init__(self, host, assistant):
        self.host, self.assistant = host, assistant
        self.vision_toolbar = host.add_toolbar('視覚の先読み')
        self.vision = NotebookVision(
            host.snapshot,
            host.metadata,
            lambda: (os.environ.get('NOTETUTOR_VISION_MODEL') or os.environ.get('BEAMERPLUS_VISION_MODEL', '')).strip() or self.assistant.model,
            host.parent)
        host.on_ink_change(self.vision.source_changed)
        host.register_operation('read_note_context', lambda args: self.vision.read(args.get('since_revision')))
        host.add_action('✦ NoteTutor設定', self.show_ai_settings)
        self.vision_button = QPushButton('視覚の先読み OFF')
        self.vision_button.setCheckable(True)
        self.vision_button.setStyleSheet('QPushButton:checked {background:#e8f0ff; border-color:#8ba9d2; color:#274a80;}')
        self.vision_button.setToolTip('ONの間、変更した手書きをClaude APIへ送り、数式の転記を先に用意します。API利用料金が発生します。')
        self.vision_button.toggled.connect(self.vision.set_enabled)
        self.vision_toolbar.addWidget(self.vision_button)
        self.vision_label = QLabel('先読み OFF')
        self.vision_toolbar.addWidget(self.vision_label)
        self.vision_retry = QPushButton('先読みを再試行')
        self.vision_retry.clicked.connect(lambda: self.vision.set_enabled(True))
        self.vision_retry.setVisible(False)
        self.vision_toolbar.addWidget(self.vision_retry)
        self.vision.changed.connect(self._update_vision_status)
        self.vision_status_timer = QTimer(host.parent)
        self.vision_status_timer.setInterval(1000)
        self.vision_status_timer.timeout.connect(self._update_vision_status)
        self.vision_status_timer.start()
        if (os.environ.get('NOTETUTOR_VISION_ENABLED') or os.environ.get('BEAMERPLUS_VISION_ENABLED')) == '1':
            self.vision_button.setChecked(True)

    def _update_vision_status(self):
        self.vision_button.setText('視覚の先読み ON' if self.vision.enabled else '視覚の先読み OFF')
        if not self.vision.enabled:
            self.vision_label.setText('先読み OFF')
            self.vision_retry.setVisible(False)
            return
        context = self.vision.read()
        state = context['status']
        seconds = context['recognition_lag_ms'] / 1000
        if state == 'ready':
            duration = context['metrics'].get('api_ms', 0) / 1000
            label = f'先読み済み {context["ready_count"]}/{context["block_count"]} · API {duration:.1f}秒'
        elif state == 'no_api_key':
            label = 'Claude設定でAPIキーを入力'
        elif state == 'error':
            label = '先読みエラー · 再試行できます'
        elif context['pen_active']:
            label = '筆記中 · 続きを待っています'
        else:
            label = f'先読み {context["ready_count"]}/{context["block_count"]} · 未反映 {seconds:.1f}秒'
        self.vision_label.setText(label)
        errors = [block['error'] for block in context['blocks'] if block['status'] == 'error']
        self.vision_label.setToolTip(context.get('error') or '\n'.join(errors) or
                                   '筆記から認識完了までの遅れです。音声会話全体の応答時間は含みません。')
        self.vision_retry.setVisible(state == 'error')

    def show_ai_settings(self):
        from .AssistantSettings import AssistantSettings
        before = (self.vision.model(), os.environ.get('ANTHROPIC_API_KEY'))
        dialog = AssistantSettings(self.assistant.model, self.host.parent)
        if dialog.exec() == AssistantSettings.DialogCode.Accepted:
            self.assistant.model = dialog.model_input.text().strip()
            self.host.broadcast(dict(type='ai_status', configured=self.assistant.configured, model=self.assistant.model))
        if before != (self.vision.model(), os.environ.get('ANTHROPIC_API_KEY')):
            self.vision.configuration_changed()

    def stop(self):
        self.vision.stop()
        self.vision_status_timer.stop()
