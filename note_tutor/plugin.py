"""Optional NoteSync extension: all tutoring UI, policy and paid calls live here."""
import asyncio
import json
import re
import threading
import websockets
from .Assistant import NoteAssistant, AssistantError, validate_question
from .LocalSettings import load_local_settings
from .NotebookVisionUI import TutorControls
from .TabletAssistant import ASSISTANT_STYLE, ASSISTANT_MARKUP, ASSISTANT_SCRIPT

class TutorExtension:
    def __init__(self):
        load_local_settings()
        self.assistant = NoteAssistant()
    def mcp_instructions(self):
        from .instructions import TUTOR_INSTRUCTIONS
        return TUTOR_INSTRUCTIONS
    def tablet_assets(self): return ASSISTANT_STYLE, ASSISTANT_MARKUP, ASSISTANT_SCRIPT
    def attach_window(self, host): return TutorControls(host, self.assistant)
    def connection(self, server, websocket): return TutorConnection(self, websocket)

class TutorConnection:
    def __init__(self, extension, websocket):
        self.extension, self.websocket = extension, websocket
        self.task = None
        self.cancelled = threading.Event()
        self.session = dict(context=None, history=[])
    async def connected(self):
        assistant = self.extension.assistant
        await self.websocket.send(json.dumps(dict(type='ai_status',configured=assistant.configured,model=assistant.model)))
    async def handle(self, data):
        kind = data.get('type')
        if kind == 'ai_reset':
            if self.task is None or self.task.done(): self.session.update(context=None, history=[])
            return True
        if kind != 'ai_ask': return False
        identifier = data.get('requestId', '')
        if not isinstance(identifier,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}',identifier): return True
        if self.task is not None and not self.task.done():
            await self.websocket.send(json.dumps(dict(type='ai_error',requestId=identifier,message='前の質問に回答中です。少し待ってください。')))
            return True
        self.cancelled = threading.Event()
        self.task = asyncio.create_task(self._respond_to_ai(self.websocket,data,self.session,self.cancelled))
        return True
    async def close(self):
        self.cancelled.set()
        if self.task is not None and not self.task.done():
            self.task.cancel()
            try: await self.task
            except asyncio.CancelledError: pass

    async def _respond_to_ai(self, websocket, data, session, cancelled):
        """Stream only to the requester; keep network work off Qt and WS threads."""
        request_id = data["requestId"]
        loop = asyncio.get_running_loop()

        def emit(delta):
            if cancelled.is_set():
                return
            future = asyncio.run_coroutine_threadsafe(websocket.send(json.dumps({
                "type": "ai_delta", "requestId": request_id, "delta": delta,
            })), loop)
            try:
                future.result(timeout=5)
            except Exception:
                cancelled.set()

        try:
            question, context, image = validate_question(data)
            history = list(session["history"]) if session["context"] == context else []
            answer = await asyncio.to_thread(self.extension.assistant.stream, question, image, history, emit, cancelled)
            if cancelled.is_set():
                return
            session.update(context=context, history=(history + [
                {"role": "user", "content": question},
                {"role": "assistant", "content": answer[:16000]},
            ])[-12:])
            await websocket.send(json.dumps({"type": "ai_done", "requestId": request_id}))
        except AssistantError as exc:
            await websocket.send(json.dumps({"type": "ai_error", "requestId": request_id, "message": str(exc)}))
        except asyncio.CancelledError:
            cancelled.set()
            raise
        except websockets.exceptions.ConnectionClosed:
            cancelled.set()
        except Exception:
            await websocket.send(json.dumps({
                "type": "ai_error", "requestId": request_id,
                "message": "回答の取得に失敗しました。再接続してお試しください。",
            }))
