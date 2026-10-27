"""PC-only settings. The key is kept in process memory, never in notebook files."""

import os
import re

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QMessageBox, QVBoxLayout,
)


class AssistantSettings(QDialog):
    def __init__(self, model: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NoteTutor設定")
        self.setMinimumWidth(440)
        layout = QVBoxLayout(self)
        description = QLabel("Anthropic APIで質問・視覚の先読みを利用できます。APIの利用料金が発生します。\n"
                             "この画面で入力したキーはPCのメモリ内だけで使い、端末やノートには保存しません。")
        description.setWordWrap(True)
        layout.addWidget(description)
        form = QFormLayout()
        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.setPlaceholderText("設定済み（空欄なら変更しません）" if os.environ.get("ANTHROPIC_API_KEY") else "Anthropic APIキー")
        form.addRow("APIキー", self.key_input)
        self.model_input = QLineEdit(model)
        self.model_input.setMaxLength(100)
        form.addRow("モデル", self.model_input)
        layout.addLayout(form)
        layout.addWidget(QLabel("ここで入力したキーは今回の起動中だけ有効です。\n"
                               "起動時はNoteTutorの.envからも設定を読み込みます。"))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self):
        model = self.model_input.text().strip()
        if not re.fullmatch(r"[a-zA-Z0-9_.:-]+", model):
            QMessageBox.warning(self, "モデル", "有効なモデル名を入力してください。")
            return
        key = self.key_input.text().strip()
        if key:
            os.environ["ANTHROPIC_API_KEY"] = key
        self.key_input.clear()
        self.accept()
