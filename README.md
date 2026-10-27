# NoteTutor

NoteSyncの手書きノートを、CodexなどMCP対応の会話から見ながら学ぶための拡張です。ノートの余白へ式やヒントを書き、必要に応じて別ページも参照できます。普段の家庭教師にはClaude APIキーは不要です。

ノートの保存・描画・同期はNoteSync、課題提出はKulmsSubmitが担当します。Claudeへの直接質問と手書きの先読み転記は、明示的に有効化した場合だけ使える追加機能です。
## インストールと起動

```bash
# NoteSyncの環境へ追加する
../NoteSync/.venv/bin/python -m pip install -e .
../NoteSync/.venv/bin/notetutor
```

`notesync.extensions` のエントリーポイントを使うので、インストール後は通常の `notesync` 起動でも読み込まれます。取り外すには `../NoteSync/.venv/bin/python -m pip uninstall note-tutor`、一時的に無効にするには `NOTESYNC_DISABLE_EXTENSIONS=1` を指定します。ソースとGit履歴は独立していますが、ウィンドウ内の拡張なので実行時はNoteSyncと同じPython環境を使います。

## 普段の使い方

NoteSyncを起動し、MCPを読み込んだCodexなどからノートを共有します。「今のノートを見て、次の一手を教えて」と頼めば、表示中のページを確認して、必要な式や短いヒントをノートの余白に書けます。画像の読み取り・指導は接続中の会話が担当します。会話サービス側の利用枠は別途使います。

## 任意: Claudeによる直接質問と先読み

既定ではClaude機能は無効で、設定ボタン・質問パネル・先読みツールバーは表示されず、Claude APIへの通信も行いません。使いたいときは `.env.example` を `.env` にコピーし、`NOTETUTOR_CLAUDE_ENABLED=1` とAPIキーを設定してNoteSyncとMCPを再起動します。既存の `.env` はそのまま使えます。`NOTETUTOR_CLAUDE_ENABLED=0` または未設定なら無効です。

| 設定 | 用途 |
| --- | --- |
| `NOTETUTOR_CLAUDE_ENABLED` | `1`でClaude機能を表示・有効化。既定はOFF |
| `ANTHROPIC_API_KEY` | AnthropicのAPIキー |
| `NOTETUTOR_CLAUDE_MODEL` | 質問応答のモデル |
| `NOTETUTOR_VISION_MODEL` | 転記専用モデル。省略時は質問応答と同じ |
| `NOTETUTOR_VISION_ENABLED` | Claude機能が有効な場合、`1`で起動時から転記をON |
| `NOTETUTOR_ENV_FILE` | 別の設定ファイルの絶対パス |

環境変数は`.env`より優先し、旧 `BEAMERPLUS_*` のモデル・先読み設定も受け付けます。`.env` はGit除外です。Claudeに質問すると現在のノート画像と質問を送信し、先読みをONにすると変更した手書き領域を送信します。どちらもAnthropic APIの料金が発生します。先読み結果は近似であり、解答の正しさを判定しません。

先読み結果は `read_note_context` から取得でき、無効時は `unavailable` を返します。書き込み前や図・判読困難な箇所の確認には `read_current_note` を使います。

## 拡張境界と開発

実装の入口は `note_tutor/plugin.py`、公開APIはNoteSyncの `notesync.api`（version 1）です。公開ホスト経由でスナップショット・変更通知・ボタン・追加ツールバー・MCP操作を使います。描画は公開の `Stroke` と `paint_ink` を使います。NoteSyncはNoteTutorを直接importしません。

```bash
NOTETUTOR_CLAUDE_ENABLED=1 NOTETUTOR_VISION_ENABLED=0 QT_QPA_PLATFORM=offscreen ../NoteSync/.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

テストではモデルAPIを模擬します。転記の差分・更新競合、エラー・中断、接続ごとの履歴、実loopback経由の画像不要の読み取りを検証します。

## ライセンス

MIT。BeamerPlus由来のノートプロジェクトから学習支援部分を分離しました。元の著作権表示は [LICENSE](LICENSE) に保持しています。
