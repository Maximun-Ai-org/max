"""
Memoria a corto plazo — sesiones de conversación recientes.
Almacenamiento en JSONL para persistencia ligera.
"""
import json
import time
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger("maximun.memory.short_term")


class ShortTermMemory:
    """Gestiona memoria de conversaciones recientes y contexto activo."""

    def __init__(self, config: dict, project_root: str):
        self.config = config
        self.project_root = Path(project_root)
        self.storage_file = self.project_root / config.get("memory", {}).get(
            "short_term", {}
        ).get("storage", "memory/short_term/sessions.jsonl")
        self.max_sessions = config.get("memory", {}).get("short_term", {}).get("max_sessions", 20)
        self.max_tokens = config.get("memory", {}).get("short_term", {}).get("max_tokens_per_session", 8192)
        self._working_memory: List[Dict] = []
        self._current_session: Optional[Dict] = None
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)

    def start_session(self) -> str:
        """Inicia una nueva sesión de conversación."""
        session_id = f"session_{int(time.time())}"
        self._current_session = {
            "id": session_id,
            "started_at": datetime.now().isoformat(),
            "messages": [],
            "metadata": {},
        }
        self._working_memory.clear()
        logger.info(f"Started session: {session_id}")
        return session_id

    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None):
        """Agrega un mensaje a la sesión actual."""
        if not self._current_session:
            self.start_session()

        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
        }

        self._current_session["messages"].append(message)
        self._working_memory.append(message)

        # Trim working memory
        while len(self._working_memory) > 20:
            self._working_memory.pop(0)

    def get_context(self, max_messages: int = 10) -> str:
        """Retorna contexto de conversación para el LLM."""
        messages = self._working_memory[-max_messages:]
        if not messages:
            return ""

        context_parts = []
        for msg in messages:
            prefix = "Usuario" if msg["role"] == "user" else "Asistente"
            context_parts.append(f"{prefix}: {msg['content'][:500]}")

        return "\n".join(context_parts)

    def get_messages(self, limit: int = 20) -> List[Dict]:
        """Retorna los últimos mensajes."""
        return self._working_memory[-limit:]

    def end_session(self):
        """Finaliza la sesión actual y persiste."""
        if self._current_session:
            self._current_session["ended_at"] = datetime.now().isoformat()
            self._persist_session(self._current_session)
            self._current_session = None

    def _persist_session(self, session: Dict):
        """Persiste la sesión al archivo JSONL."""
        try:
            with open(self.storage_file, "a") as f:
                f.write(json.dumps(session, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to persist session: {e}")

    def load_recent_sessions(self, count: int = 5) -> List[Dict]:
        """Carga las sesiones más recientes del archivo."""
        if not self.storage_file.exists():
            return []

        sessions = []
        try:
            with open(self.storage_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        sessions.append(json.loads(line))
        except Exception as e:
            logger.error(f"Failed to load sessions: {e}")

        return sessions[-count:]

    def search_messages(self, query: str, limit: int = 10) -> List[Dict]:
        """Busca mensajes por contenido."""
        results = []
        if not self.storage_file.exists():
            return results

        query_lower = query.lower()
        try:
            with open(self.storage_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    session = json.loads(line)
                    for msg in session.get("messages", []):
                        if query_lower in msg.get("content", "").lower():
                            results.append(msg)
                            if len(results) >= limit:
                                return results
        except Exception as e:
            logger.error(f"Failed to search messages: {e}")

        return results

    def get_stats(self) -> dict:
        """Estadísticas de memoria a corto plazo."""
        total_messages = 0
        total_sessions = 0
        if self.storage_file.exists():
            try:
                with open(self.storage_file, "r") as f:
                    for line in f:
                        if line.strip():
                            session = json.loads(line)
                            total_sessions += 1
                            total_messages += len(session.get("messages", []))
            except Exception:
                pass

        return {
            "working_memory_size": len(self._working_memory),
            "current_session": self._current_session["id"] if self._current_session else None,
            "total_sessions": total_sessions,
            "total_messages": total_messages,
        }
