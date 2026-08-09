"""
Servidor local offline-first — API REST + WebSocket.
Sirve archivos estáticos y API del agente sin conexión externa.
"""
import os
import json
import logging
import asyncio
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger("maximun.backend")

try:
    from aiohttp import web
    AIOHTTP = True
except ImportError:
    AIOHTTP = False


class LocalServer:
    """
    Servidor web local completo:
    - Archivos estáticos (frontend)
    - API REST del agente
    - WebSocket para actualizaciones en tiempo real
    - Dashboard IoT
    """

    def __init__(self, config: dict, agent=None):
        self.config = config
        self.agent = agent
        self.host = config.get("server", {}).get("host", "0.0.0.0")
        self.port = config.get("server", {}).get("port", 8080)
        self.web_dir = Path(config.get("server", {}).get("web_dir", "web"))
        self.web_dir.mkdir(parents=True, exist_ok=True)

    def create_app(self) -> Optional["web.Application"]:
        """Crea la aplicación aiohttp."""
        if not AIOHTTP:
            logger.error("aiohttp no disponible")
            return None

        app = web.Application()

        # Static files
        app.router.add_static("/static", str(self.web_dir))
        app.router.add_get("/", self._handle_index)
        app.router.add_get("/chat", self._handle_chat_page)
        app.router.add_get("/dashboard", self._handle_dashboard)
        app.router.add_get("/iot", self._handle_iot)

        # API routes
        app.router.add_post("/api/chat", self._api_chat)
        app.router.add_get("/api/status", self._api_status)
        app.router.add_get("/api/models", self._api_models)
        app.router.add_get("/api/memory", self._api_memory)
        app.router.add_post("/api/voice", self._api_voice)
        app.router.add_get("/api/iot/devices", self._api_iot_devices)
        app.router.add_post("/api/iot/toggle", self._api_iot_toggle)

        # WebSocket
        app.router.add_get("/ws", self._handle_websocket)

        return app

    # ─── Page Handlers ──────────────────────────────────
    async def _handle_index(self, request):
        index = self.web_dir / "index.html"
        if index.exists():
            return web.FileResponse(index)
        return web.Response(text="Máximun Agent — Frontend no generado. Ejecuta: python3 -c \"from skills.frontend import OfflineWebGenerator; g=OfflineWebGenerator(); g.generate_chat_page(); g.generate_dashboard(); g.generate_iot_control()\"",
                           content_type="text/plain")

    async def _handle_chat_page(self, request):
        path = self.web_dir / "chat.html"
        return web.FileResponse(path) if path.exists() else web.Response(text="Not found", status=404)

    async def _handle_dashboard(self, request):
        path = self.web_dir / "dashboard.html"
        return web.FileResponse(path) if path.exists() else web.Response(text="Not found", status=404)

    async def _handle_iot(self, request):
        path = self.web_dir / "iot.html"
        return web.FileResponse(path) if path.exists() else web.Response(text="Not found", status=404)

    # ─── API Handlers ───────────────────────────────────
    async def _api_chat(self, request):
        try:
            body = await request.json()
            msg = body.get("message", "")
            if not msg:
                return web.json_response({"error": "message required"}, 400)

            if self.agent:
                enriched = self.agent.memory.process_input(msg) if self.agent.memory else {}
                result = self.agent.hrm.process(msg, enriched)
                self.agent.memory.process_response(
                    result["response"],
                    model_used=result["model_used"],
                    task_level=result["task_level"],
                    confidence=result["confidence"],
                )
                return web.json_response({
                    "response": result["response"],
                    "model": result["model_used"],
                    "level": result["task_level"],
                    "time": result["execution_time"],
                })
            return web.json_response({"response": "Agente no inicializado", "model": "none"})
        except Exception as e:
            return web.json_response({"error": str(e)}, 500)

    async def _api_status(self, request):
        if self.agent:
            return web.json_response({
                "agent": "Máximun",
                "hrm": self.agent.hrm.get_status(),
                "memory": self.agent.memory.get_stats(),
            })
        return web.json_response({"agent": "not initialized"})

    async def _api_models(self, request):
        if self.agent:
            return web.json_response({
                "available": self.agent.model_manager.list_models(),
                "loaded": self.agent.engine.get_loaded_models() if self.agent.engine else [],
            })
        return web.json_response({"available": [], "loaded": []})

    async def _api_memory(self, request):
        if self.agent:
            return web.json_response(self.agent.memory.get_stats())
        return web.json_response({})

    async def _api_voice(self, request):
        try:
            body = await request.json()
            text = body.get("text", "")
            if self.agent and hasattr(self.agent, 'voice_pipeline'):
                result = self.agent.voice_pipeline.process_text_input(text)
                return web.json_response(result)
            return web.json_response({"error": "Voice pipeline not available"}, 503)
        except Exception as e:
            return web.json_response({"error": str(e)}, 500)

    async def _api_iot_devices(self, request):
        return web.json_response({"devices": self._get_iot_devices()})

    async def _api_iot_toggle(self, request):
        try:
            body = await request.json()
            device_id = body.get("device_id", "")
            return web.json_response({"device": device_id, "toggled": True})
        except Exception as e:
            return web.json_response({"error": str(e)}, 500)

    async def _handle_websocket(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if data.get("type") == "chat" and self.agent:
                        result = self.agent.hrm.process(data.get("message", ""))
                        await ws.send_json({"type": "response", "data": result["response"]})
        except Exception:
            pass
        return ws

    def _get_iot_devices(self) -> list:
        return [
            {"id": "relay1", "name": "Relé 1", "gpio": 17, "state": False},
            {"id": "relay2", "name": "Relé 2", "gpio": 27, "state": False},
            {"id": "relay3", "name": "Relé 3", "gpio": 22, "state": False},
            {"id": "relay4", "name": "Relé 4", "gpio": 23, "state": False},
        ]

    def run(self):
        """Inicia el servidor."""
        app = self.create_app()
        if app:
            logger.info(f"Servidor local en http://{self.host}:{self.port}")
            web.run_app(app, host=self.host, port=self.port)
