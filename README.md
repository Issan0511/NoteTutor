# NoteTutor

NoteSyncのノートを使う、任意のチューター拡張です。質問応答、手書きの先読み転記、学習支援用のMCP指示を管理します。ノートの保存・描画・同期はNoteSync、大学への提出はKulmsSubmitが担当します。

## インストールと起動

```bash
# NoteSyncの環境へ追加する
../NoteSync/.venv/bin/python -m pip install -e .
../NoteSync/.venv/bin/notetutor
```

`notesync.extensions` のエントリーポイントを使うので、インストール後は通常の `notesync` 起動でも読み込まれます。取り外すには `../NoteSync/.venv/bin/python -m pip uninstall note-tutor`、一時的に無効にするには `NOTESYNC_DISABLE_EXTENSIONS=1` を指定します。ソースとGit履歴は独立していますが、ウィンドウ内の拡張なので実行時はNoteSyncと同じPython環境を使います。

## 設定

このリポジトリの `.env.example` を `.env` にコピーして記入するか、PCの「NoteTutor設定」を使います。GUIのキーはメモリ内のみ、`.env` はGit除外です。キーはブラウザやノートに送りません。設定は環境変数をファイルより優先し、シェル展開をしません。

| 設定 | 用途 |
| --- | --- |
| `ANTHROPIC_API_KEY` | AnthropicのAPIキー |
| `NOTETUTOR_CLAUDE_MODEL` | 質問応答のモデル |
| `NOTETUTOR_VISION_MODEL` | 転記専用モデル。省略時は質問応答と同じ |
| `NOTETUTOR_VISION_ENABLED` | `1`で起動時から転記を有効化。既定はOFF |
| `NOTETUTOR_ENV_FILE` | 別の設定ファイルの絶対パス |

旧 `BEAMERPLUS_CLAUDE_MODEL`・`BEAMERPLUS_VISION_MODEL`・`BEAMERPLUS_VISION_ENABLED`・`BEAMERPLUS_ENV_FILE` も移行用に受け付けます。この端末の既存 `.env` はNoteTutorへ移しています。

タブレットの「Claudeに聞く」から今のノート画像と質問を送れます。履歴は接続ごとに分かれ、回答は質問した端末へだけ届きます。同期だけの利用ではモデルを呼びません。質問と有効化した転記にはAPI料金が発生します。

## 視覚の先読み

PCで「視覚の先読み」をONにすると、変更した手書き領域を転記し、LaTeX・文章・不確かな箇所をメモリに保持します。筆跡への書き込みはしません。800msの筆休めを待ち、開始間隔は最低2秒、同時1件・最大4領域に制限します。変更のない領域とUndoした領域はキャッシュを再利用します。

ページ・筆跡・モデルが変わった場合に古い結果を最新版として返しません。エラー時は自動送信を停止し、再試行ボタンで再開します。OFF後に新たな送信は始めませんが、送信済みのリクエストは完了する場合があります。転記は近似で、解答の正しさを判定する機能ではありません。

NoteSyncのMCPで `read_note_context` を呼ぶと、画像再送・API待ちなしで先読み結果を取得できます。`fresh`、領域ごとの状態、`uncertain` を確認し、変更取得には `since_revision` を使います。未導入時は `unavailable` になり、`read_current_note` で画像を読めます。

## 拡張境界と開発

実装の入口は `note_tutor/plugin.py`、公開APIはNoteSyncの `notesync.api`（version 1）です。公開ホスト経由でスナップショット・変更通知・ボタン・追加ツールバー・MCP操作を使います。描画は公開の `Stroke` と `paint_ink` を使います。NoteSyncはNoteTutorを直接importしません。

```bash
NOTETUTOR_VISION_ENABLED=0 QT_QPA_PLATFORM=offscreen ../NoteSync/.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

テストではモデルAPIを模擬します。転記の差分・更新競合、エラー・中断、接続ごとの履歴、実loopback経由の画像不要の読み取りを検証します。

## ライセンス

MIT。BeamerPlus由来のノートプロジェクトから学習支援部分を分離しました。元の著作権表示は [LICENSE](LICENSE) に保持しています。
