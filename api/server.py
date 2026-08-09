"""
API Server — Interfaz HTTP para el agente Máximun.
Endpoint local en 127.0.0.1:8080
"""
import json
import logging
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from aiohttp import web
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

logger = logging.getLogger("maximun.api")


class MaximunAPI:
    """Servidor API para el agente."""

    def __init__(self, agent, host="127.0.0.1", port=8080):
        self.agent = agent
        self.host = host
        self.port = port

    def _json_response(self, data: dict, status: int = 200) -> web.Response:
        return web.json_response(data, status=status, dumps=lambda x: json.dumps(x, ensure_ascii=False, default=str))

    async def handle_chat(self, request: web.Request) -> web.Response:
        """POST /chat — Procesa un mensaje del usuario."""
        try:
            body = await request.json()
            user_input = body.get("message", "")
            user_id = body.get("user_id", "default")

            if not user_input:
                return self._json_response({"error": "message is required"}, 400)

            # Process through HRM
            enriched = self.agent.memory.process_input(user_input, user_id)
            result = self.agent.hrm.process(user_input, enriched)

            # Store in memory
            self.agent.memory.process_response(
                result["response"],
                model_used=result["model_used"],
                task_level=result["task_level"],
                confidence=result["confidence"],
            )

            return self._json_response({
                "response": result["response"],
                "model_used": result["model_used"],
                "task_level": result["task_level"],
                "confidence": result["confidence"],
                "iterations": result["iterations"],
                "execution_time": result["execution_time"],
            })

        except Exception as e:
            logger.exception("Chat error")
            return self._json_response({"error": str(e)}, 500)

    async def handle_status(self, request: web.Request) -> web.Response:
        """GET /status — Estado del agente."""
        return self._json_response({
            "agent": "Máximun Hermes",
            "version": "0.1.0",
            "hrm": self.agent.hrm.get_status(),
            "memory": self.agent.memory.get_stats(),
            "timestamp": datetime.now().isoformat(),
        })

    async def handle_models(self, request: web.Request) -> web.Response:
        """GET /models — Modelos disponibles."""
        models = self.agent.model_manager.list_models()
        loaded = self.agent.engine.get_loaded_models()
        return self._json_response({
            "available": models,
            "loaded": loaded,
        })

    async def handle_memory(self, request: web.Request) -> web.Response:
        """GET /memory — Estadísticas de memoria."""
        return self._json_response(self.agent.memory.get_stats())

    async def handle_index(self, request: web.Request) -> web.Response:
        """POST /index — Indexar contenido."""
        try:
            body = await request.json()
            text = body.get("text", "")
            source = body.get("source", "api")
            category = body.get("category", "general")

            result = self.agent.memory.index_knowledge(text, source, category)
            return self._json_response(result)
        except Exception as e:
            return self._json_response({"error": str(e)}, 500)

    async def handle_search(self, request: web.Request) -> web.Response:
        """GET /search?q=... — Buscar en memoria."""
        query = request.query.get("q", "")
        if not query:
            return self._json_response({"error": "q parameter required"}, 400)
        
        results = self.agent.memory.search(query)
        return self._json_response(results)

    def create_app(self) -> web.Application:
        app = web.Application()
        app.router.add_post("/chat", self.handle_chat)
        app.router.add_get("/status", self.handle_status)
        app.router.add_get("/models", self.handle_models)
        app.router.add_get("/memory", self.handle_memory)
        app.router.add_post("/index", self.handle_index)
        app.router.add_get("/search", self.handle_search)
        return app

    def run(self):
        """Inicia el servidor."""
        if not AIOHTTP_AVAILABLE:
            print("aiohttp not installed. Run: pip install aiohttp")
            return

        app = self.create_app()
        print(f"Máximun API server en http://{self.host}:{self.port}")
        web.run_app(app, host=self.host, port=self.port)


def main():
    """Standalone API server."""
    import yaml
    config_path = Path(__file__).parent.parent / "config" / "agent.yaml"
    config = yaml.safe_load(open(config_path))

    from maximun import MaximunAgent
    agent = MaximunAgent(config)
    agent.setup(download_models=False)

    server = MaximunAPI(
        agent,
        host=config.get("server", {}).get("host", "127.0.0.1"),
        port=config.get("server", {}).get("port", 8080),
    )
    server.run()


if __name__ == "__main__":
    main()
