"""
Canal de comunicación local — sin dependencia de red externa.
Sirve por: terminal, WebSocket local, audio Jack.
"""
import json
import os
import signal
import sys
import logging
import threading
import time
from pathlib import Path
from typing import Optional, Callable

logger = logging.getLogger("maximun.comm.local")

try:
    from aiohttp import web
    AIOHTTP = True
except ImportError:
    AIOHTTP = False


class LocalChannel:
    """
    Canal de comunicación que funciona 100% offline.
    
    Canales disponibles:
    1. Terminal interactivo (default)
    2. WebSocket local (ws://localhost:9090)
    3. HTTP API local (http://localhost:8080)
    4. Archivo compartido (polling)
    5. Audio Jack (TTS bidireccional)
    """

    def __init__(self, agent=None, config: dict = None):
        self.agent = agent
        self.config = config or {}
        self.comm_dir = Path(self.config.get("comm_dir", "data/communication"))
        self.comm_dir.mkdir(parents=True, exist_ok=True)
        self.inbox = self.comm_dir / "inbox.jsonl"
        self.outbox = self.comm_dir / "outbox.jsonl"
        self._active = False
        self._callbacks = []

    # ─── Terminal Channel ──────────────────────────────
    def terminal_chat(self):
        """Canal principal — chat por terminal, sin internet."""
        print("╔═══════════════════════════════════════════════════╗")
        print("║  MÁXIMUN — Canal Local (sin conexión)           ║")
        print("║  Escribe 'ayuda' para comandos                  ║")
        print("╚═══════════════════════════════════════════════════╝")
        print()

        self._active = True
        session_id = None

        if self.agent:
            session_id = self.agent.memory.short_term.start_session()
            print(f"Sesión: {session_id}\n")

        while self._active:
            try:
                user_input = input("Tú > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nSesión guardada.")
                break

            if not user_input:
                continue

            # Special commands
            if user_input.startswith("/"):
                self._handle_command(user_input)
                continue

            if user_input.lower() in ("salir", "exit", "quit", "q"):
                break

            # Process
            print("\nMáximun > ", end="", flush=True)
            try:
                if self.agent:
                    response = self.agent.process(user_input)
                else:
                    response = f"[Agente no disponible] Recibido: {user_input}"
                print(response)

                # Record interaction
                if self.agent and hasattr(self.agent, 'identity'):
                    self.agent.identity.record_interaction(user_input, response)

            except Exception as e:
                print(f"[Error: {e}]")

            print()

        if self.agent:
            self.agent.memory.short_term.end_session()
            self.agent.shutdown()

        print("Hasta pronto.")

    # ─── File Channel (for communication without terminal) ──
    def file_listener(self, poll_interval: int = 2):
        """
        Escucha archivos en inbox/ para comunicación asincrónica.
        Útil cuando no hay terminal pero hay archivos compartidos.
        """
        self._active = True
        logger.info(f"File listener activo en {self.comm_dir}")

        while self._active:
            try:
                if self.inbox.exists():
                    lines = self.inbox.read_text().strip().split("\n")
                    new_lines = []

                    for line in lines:
                        if not line.strip():
                            continue
                        try:
                            msg = json.loads(line)
                            if not msg.get("processed", False):
                                response = self._process_message(msg)
                                self._write_outbox(msg.get("id", ""), response)
                                msg["processed"] = True
                            new_lines.append(json.dumps(msg, ensure_ascii=False))
                        except json.JSONDecodeError:
                            new_lines.append(line)

                    self.inbox.write_text("\n".join(new_lines) + "\n")

                time.sleep(poll_interval)
            except KeyboardInterrupt:
                self._active = False
            except Exception as e:
                logger.error(f"File listener error: {e}")
                time.sleep(5)

    def send_message(self, to: str, message: str, msg_type: str = "text"):
        """Envía un mensaje al outbox."""
        msg = {
            "id": f"msg_{int(time.time()*1000)}",
            "to": to,
            "from": "maximun",
            "type": msg_type,
            "content": message,
            "timestamp": time.time(),
            "processed": False,
        }
        with open(self.outbox, "a") as f:
            f.write(json.dumps(msg, ensure_ascii=False) + "\n")

    def _process_message(self, msg: dict) -> str:
        """Procesa un mensaje recibido por canal de archivos."""
        content = msg.get("content", "")
        if self.agent:
            return self.agent.process(content)
        return f"Recibido: {content}"

    def _write_outbox(self, reply_to: str, response: str):
        """Escribe respuesta en outbox."""
        msg = {
            "id": f"reply_{int(time.time()*1000)}",
            "reply_to": reply_to,
            "from": "maximun",
            "content": response,
            "timestamp": time.time(),
        }
        with open(self.outbox, "a") as f:
            f.write(json.dumps(msg, ensure_ascii=False) + "\n")

    # ─── WebSocket Channel ─────────────────────────────
    def start_websocket_server(self, host: str = "127.0.0.1", port: int = 9090):
        """Inicia servidor WebSocket local para comunicación."""
        if not AIOHTTP:
            logger.error("aiohttp no disponible para WebSocket")
            return

        import asyncio

        async def ws_handler(request):
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            async for msg in ws:
                if msg.type == 1:  # TEXT
                    data = json.loads(msg.data)
                    content = data.get("message", "")
                    if self.agent:
                        response = self.agent.process(content)
                    else:
                        response = f"Echo: {content}"
                    await ws.send_json({"response": response})
            return ws

        app = web.Application()
        app.router.add_get("/ws", ws_handler)
        logger.info(f"WebSocket server en ws://{host}:{port}")
        web.run_app(app, host=host, port=port)

    def _handle_command(self, cmd: str):
        """Maneja comandos especiales."""
        cmd = cmd.lower().strip()
        commands = {
            "/status": lambda: print(json.dumps(
                self.agent.hrm.get_status() if self.agent else {},
                indent=2, ensure_ascii=False
            )),
            "/identidad": lambda: print(json.dumps(
                self.agent.identity.get_stats() if self.agent and hasattr(self.agent, 'identity') else {},
                indent=2, ensure_ascii=False
            )),
            "/memoria": lambda: print(json.dumps(
                self.agent.memory.get_stats() if self.agent else {},
                indent=2, ensure_ascii=False
            )),
            "/ayuda": lambda: print("""
Comandos:
  /status     Estado del sistema
  /identidad  Identidad de Maximun
  /memoria    Estadísticas de memoria
  /heartbeat  Estado de salud
  /ayuda      Esta ayuda
  salir       Terminar
            """),
        }

        if cmd in commands:
            commands[cmd]()
        else:
            print(f"Comando desconocido: {cmd}")

    def shutdown(self):
        self._active = False
