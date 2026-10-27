"""Self-contained tablet assistant UI; no CDN or browser-side API credentials."""

ASSISTANT_STYLE = """
    #assistant-launch { position:fixed; right:16px; bottom:16px; z-index:110;
      background:#126f62; border-color:#39b79b; padding:12px 18px; font-weight:600; }
    #quick-eraser { position:fixed; left:16px; bottom:16px; z-index:110; padding:12px 18px;
      background:#28323d; border-color:#718399; font-weight:600; }
    #quick-eraser.active, #quick-eraser.pen-button-active, #btn-eraser.pen-button-active {
      background:#986529; border-color:#fbbf24; color:#fff; }
    #assistant-panel { display:none; position:fixed; right:0; top:0; bottom:0; width:360px;
      z-index:105; background:#191d22; color:#eef2f6; border-left:1px solid #343b44;
      flex-direction:column; padding:20px; gap:14px; box-shadow:-8px 0 30px #0004; }
    body.assistant-open #assistant-panel { display:flex; }
    body.assistant-open #stage { width:calc(100vw - 360px); }
    body.assistant-open #ui-container { left:calc((100vw - 360px) / 2); max-width:calc(100vw - 376px); }
    body.assistant-open #assistant-launch { display:none; }
    .assistant-heading { display:flex; align-items:center; justify-content:space-between; gap:8px; }
    .assistant-heading h2 { font-size:19px; font-weight:600; }
    #assistant-status, .assistant-hint { color:#a6b3c3; font-size:12px; line-height:1.6; }
    #assistant-messages { flex:1; min-height:60px; overflow-y:auto; display:flex;
      flex-direction:column; gap:12px; touch-action:pan-y; }
    #assistant-messages * { touch-action:pan-y; -webkit-user-select:text !important; user-select:text !important; }
    .assistant-message { white-space:pre-wrap; overflow-wrap:anywhere; font-size:14px; line-height:1.75;
      padding:12px 14px; border-radius:12px; background:#252c34; }
    .assistant-message.question { background:#173f39; border:1px solid #28665b; }
    .assistant-message.error { color:#ffc4bd; border:1px solid #7f4642; }
    .assistant-empty { margin:auto 0; color:#a6b3c3; font-size:14px; line-height:1.9; }
    #assistant-form { display:flex; flex-direction:column; gap:10px; }
    #assistant-question { width:100%; min-height:88px; max-height:180px; resize:vertical;
      background:#101419; border:1px solid #46515f; border-radius:12px; padding:12px;
      color:#eef2f6; font:inherit; font-size:14px; line-height:1.5; outline:none;
      -webkit-user-select:text !important; user-select:text !important; touch-action:manipulation; }
    #assistant-question:focus { border-color:#39b79b; }
    #assistant-form label { font-size:13px; }
    .assistant-actions { display:flex; gap:8px; }
    #assistant-send { flex:1; justify-content:center; background:#126f62; border-color:#39b79b; padding:10px; }
    #assistant-panel button:disabled { opacity:.45; cursor:default; }
    @media(max-width:700px) {
      #assistant-panel { width:100%; height:55dvh; top:auto; border-left:0; border-top:1px solid #343b44;
        padding:12px 16px; gap:8px; }
      body.assistant-open #stage { width:100vw; height:45dvh; }
      body.assistant-open #quick-eraser { bottom:calc(55dvh + 12px); }
      body.assistant-open #ui-container { left:50%; max-width:calc(100vw - 16px); }
      #assistant-question { min-height:56px; }
      .assistant-hint { font-size:11px; }
    }
    #pen-button-mode { color:#eee; background:#28323d; font-size:12px; }
    #pen-button-mode option { color:#eee; background:#28323d; }
"""

ASSISTANT_STYLE += '#assistant-launch{right:90px;bottom:17px;padding:10px 15px;border-radius:30px;border:0;background:#323e57;color:#fff;font-size:12px;box-shadow:0 4px 12px #0001}#assistant-panel{width:360px;background:#fbfbfd;color:#353b49;border-color:#dedfe7;box-shadow:-10px 0 40px #00000008;padding:22px}#assistant-panel .btn{border:1px solid #e1e3ec;border-radius:10px;padding:8px 12px;background:white;color:#5b6275}#assistant-panel #assistant-send{background:#465979;color:white;border:0}#assistant-messages .assistant-message{background:#f0f1f5;color:#41495a}#assistant-messages .question{background:#eaf0f8;border:1px solid #d8e1ef}#assistant-question{background:white;color:#3a4254;border:1px solid #d9dde8}#assistant-status,.assistant-hint{color:#8a91a1}#assistant-panel h2{margin:0}#assistant-question::placeholder{color:#a2a8b6}\nbody.assistant-open #stage{right:436px;width:auto;height:auto}body.assistant-open #tool-rail{right:360px}body.assistant-open #page-footer{right:460px}\n@media(max-width:900px){#assistant-launch{right:72px;bottom:18px;font-size:11px}body.assistant-open #stage{width:auto;right:58px;bottom:calc(55dvh + 20px);height:auto}body.assistant-open #tool-rail{right:0;bottom:55dvh}body.assistant-open #assistant-panel{width:100%;height:55dvh;top:auto;bottom:0;right:0;padding:14px;border-left:0;border-top:1px solid #dedfe7}}'

ASSISTANT_MARKUP = """
  <button type="button" class="btn" id="assistant-launch" aria-expanded="false" aria-controls="assistant-panel">✦ Claudeに聞く</button>
  <aside id="assistant-panel" aria-label="ノートについてClaudeに質問">
    <div class="assistant-heading">
      <h2>ノートと考える</h2>
      <button type="button" class="btn" id="assistant-close" aria-label="質問パネルを閉じる">閉じる</button>
    </div>
    <div id="assistant-status" role="status">PCに接続してください</div>
    <div id="assistant-messages" role="log" aria-live="polite" aria-relevant="additions text">
      <p class="assistant-empty">式や図を書いて、気になったところを質問できます。<br>「この変形は合ってる？」<br>「次の一手のヒントを教えて」</p>
    </div>
    <form id="assistant-form">
      <label for="assistant-question">今のノートについて質問</label>
      <textarea id="assistant-question" maxlength="4000" placeholder="この式の変形を説明して" enterkeyhint="send"></textarea>
      <div class="assistant-actions">
        <button type="submit" class="btn" id="assistant-send" disabled>今のノートを送って質問</button>
        <button type="button" class="btn" id="assistant-reset" disabled>新しい会話</button>
      </div>
      <p class="assistant-hint">今のノート画像と質問をAnthropicへ送ります。同じノートでは会話を続けられます。回答はこの端末に表示されます。</p>
    </form>
  </aside>
"""

ASSISTANT_SCRIPT = r"""
    const assistantPanel = document.getElementById('assistant-panel');
    const assistantLaunch = document.getElementById('assistant-launch');
    const assistantMessages = document.getElementById('assistant-messages');
    const assistantStatus = document.getElementById('assistant-status');
    const assistantQuestion = document.getElementById('assistant-question');
    const assistantSend = document.getElementById('assistant-send');
    const assistantReset = document.getElementById('assistant-reset');
    let assistantConnected = false;
    let assistantConfigured = false;
    let assistantPending = null;
    let assistantAnswer = null;
    let assistantContext = null;
    let assistantModel = '';

    function updateAssistantControls() {
      assistantSend.disabled = !assistantConnected || !assistantConfigured || !!assistantPending;
      assistantReset.disabled = !assistantConnected || !!assistantPending;
      assistantSend.textContent = assistantPending ? '回答を受信中…' : '今のノートを送って質問';
      assistantStatus.textContent = !assistantConnected ? 'PCとの接続を待っています' :
        !assistantConfigured ? 'PCの「NoteTutor設定」でAPIキーを設定してください' :
        assistantPending ? 'ノートを見ながら考えています…' : `質問できます · ${assistantModel}`;
    }

    function updateExtensionConnection(connected) {
      assistantConnected = connected;
      if (!connected) {
        assistantConfigured = false;
        if (assistantPending && assistantAnswer) {
          assistantAnswer.textContent += '\n接続が切れました。回答は未完了です。再接続後に再送してください。';
          assistantAnswer.classList.add('error');
        }
        assistantPending = null;
        // Server conversation state belongs to one authenticated connection.
        assistantContext = null;
      }
      updateAssistantControls();
    }

    function appendAssistantMessage(text, className) {
      const empty = assistantMessages.querySelector('.assistant-empty');
      if (empty) empty.remove();
      const bubble = document.createElement('div');
      bubble.className = `assistant-message ${className || ''}`;
      bubble.textContent = text; // Model output is never interpreted as HTML.
      assistantMessages.appendChild(bubble);
      assistantMessages.scrollTop = assistantMessages.scrollHeight;
      return bubble;
    }

    function handleTutorMessage(msg) {
      if (msg.type === 'ai_status') {
        assistantConfigured = !!msg.configured;
        assistantModel = msg.model || '';
        updateAssistantControls();
        return;
      }
      if (msg.requestId !== assistantPending || !assistantAnswer) return;
      if (msg.type === 'ai_delta') {
        if (assistantAnswer.dataset.waiting) {
          assistantAnswer.textContent = '';
          delete assistantAnswer.dataset.waiting;
        }
        assistantAnswer.textContent += msg.delta;
        assistantMessages.scrollTop = assistantMessages.scrollHeight;
      } else if (msg.type === 'ai_done' || msg.type === 'ai_error') {
        if (msg.type === 'ai_error') {
          const partial = assistantAnswer.dataset.waiting ? '' : assistantAnswer.textContent + '\n\n';
          assistantAnswer.textContent = partial + msg.message;
          assistantAnswer.classList.add('error');
        }
        delete assistantAnswer.dataset.waiting;
        assistantPending = null;
        updateAssistantControls();
      }
    }

    function setAssistantOpen(open) {
      finishActiveInput();
      document.body.classList.toggle('assistant-open', open);
      assistantLaunch.setAttribute('aria-expanded', String(open));
      adjustLayout();
    }
    assistantLaunch.addEventListener('click', () => setAssistantOpen(true));
    document.getElementById('assistant-close').addEventListener('click', () => setAssistantOpen(false));
    assistantPanel.addEventListener('pointerdown', e => e.stopPropagation());
    assistantPanel.addEventListener('touchstart', e => e.stopPropagation(), {passive:true});

    function captureNotebook() {
      if (!currentDocumentId) throw new Error('ノートの接続を待ってください。');
      const image = document.createElement('canvas');
      const ratio = slideWrapper.clientHeight / Math.max(1, slideWrapper.clientWidth);
      image.width = Math.round(1600 / Math.max(1, ratio));
      image.height = Math.round(image.width * ratio);
      const ctx = image.getContext('2d');
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, image.width, image.height);
      if (typeof paintNotebookPaper === 'function') paintNotebookPaper(ctx, image.width, image.height);
      if (isSketchVisible) ctx.drawImage(committedCanvas, 0, 0, image.width, image.height);
      return image.toDataURL('image/jpeg', 0.9);
    }

    document.getElementById('assistant-form').addEventListener('submit', e => {
      e.preventDefault();
      const question = assistantQuestion.value.trim();
      if (!question || assistantSend.disabled || !ws || ws.readyState !== WebSocket.OPEN) return;
      finishActiveInput();
      let image;
      try { image = captureNotebook(); }
      catch (error) { showToast(error.message); return; }
      const context = `${currentDocumentId}:${isSketchbook ? 'sketchbook' : currentPage}`;
      if (context !== assistantContext) {
        assistantMessages.replaceChildren();
        assistantContext = context;
      }
      const label = document.getElementById('note-title')?.value || 'ノート';
      appendAssistantMessage(`${label}\n${question}`, 'question');
      assistantAnswer = appendAssistantMessage('ノートを送信しています…', '');
      assistantAnswer.dataset.waiting = 'true';
      assistantPending = `q_${Date.now()}_${Math.random().toString(36).slice(2)}`;
      sendWS({type:'ai_ask', requestId:assistantPending, question, context, image});
      assistantQuestion.value = '';
      updateAssistantControls();
    });
    assistantQuestion.addEventListener('keydown', e => {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && !e.isComposing) {
        e.preventDefault();
        document.getElementById('assistant-form').requestSubmit();
      }
    });
    assistantReset.addEventListener('click', () => {
      if (assistantPending) return;
      sendWS({type:'ai_reset'});
      assistantMessages.replaceChildren();
      appendAssistantMessage('新しい会話を始めます。今のノートについて質問してください。', '');
      assistantContext = null;
    });
    updateAssistantControls();

function handleExtensionMessage(msg){if(!msg.type.startsWith('ai_'))return false;handleTutorMessage(msg);return true;}
"""
