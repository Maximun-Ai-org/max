"""
Memory Manager — Coordinador unificado de memoria.
Integra short-term, long-term y RAG en un sistema cohesivo.
"""
import logging
from typing import Dict, Optional, List
from pathlib import Path

from .short_term import ShortTermMemory
from .long_term import LongTermMemory
from .rag_engine import RAGEngine

logger = logging.getLogger("maximun.memory")


class MemoryManager:
    """
    Gestor central de memoria para el agente Máximun.
    
    Capas:
    1. Working Memory — contexto activo en RAM
    2. Short-term — sesiones recientes (JSONL)
    3. Long-term — conocimiento acumulado (SQLite)
    4. RAG — búsqueda semántica (ChromaDB + embeddings)
    """

    def __init__(self, config: dict, project_root: str):
        self.config = config
        self.project_root = Path(project_root)

        # Initialize memory layers
        self.short_term = ShortTermMemory(config, project_root)
        self.long_term = LongTermMemory(config, project_root)
        self.rag = RAGEngine(config, project_root)

        # Try to initialize RAG (needs sentence-transformers)
        self._rag_initialized = False

    def initialize_rag(self) -> bool:
        """Inicializa el motor RAG."""
        if not self._rag_initialized:
            self._rag_initialized = self.rag.initialize()
        return self._rag_initialized

    def process_input(self, user_input: str, user_id: str = "default") -> Dict:
        """
        Procesa una entrada del usuario a través de todas las capas de memoria.
        Retorna contexto enriquecido para el LLM.
        """
        # 1. Add to working memory
        self.short_term.add_message("user", user_input)

        # 2. Get short-term context
        st_context = self.short_term.get_context(max_messages=10)

        # 3. Search long-term memory
        lt_results = self.long_term.search_knowledge(user_input, limit=5)
        lt_context = "\n".join([
            f"- [{r['category']}] {r['key']}: {r['content'][:200]}"
            for r in lt_results
        ]) if lt_results else ""

        # 4. RAG search
        rag_context = ""
        if self._rag_initialized:
            rag_context = self.rag.get_rag_context(user_input, top_k=3)

        # 5. Build enriched context
        enriched_context = {
            "user_input": user_input,
            "short_term": st_context,
            "long_term": lt_context,
            "rag_context": rag_context,
            "has_rag": bool(rag_context),
        }

        return enriched_context

    def process_response(self, response: str, model_used: str = "", task_level: str = "", confidence: float = 0.0):
        """Procesa la respuesta del agente para almacenar en memoria."""
        self.short_term.add_message("assistant", response, {
            "model": model_used,
            "level": task_level,
            "confidence": confidence,
        })

        # Auto-learn: store interesting responses in long-term
        if confidence > 0.6 and len(response) > 50:
            self.long_term.store(
                category="learned",
                key=response[:100],
                content=response,
                metadata={"model": model_used, "level": task_level},
            )

        # Store interaction
        self.long_term.store_interaction(
            user_message=self.short_term.get_messages(limit=1)[-2]["content"] if len(self.short_term.get_messages()) >= 2 else "",
            agent_response=response,
            model_used=model_used,
            task_level=task_level,
            confidence=confidence,
        )

    def index_knowledge(self, text: str, source: str = "manual", category: str = "general") -> Dict:
        """Indexa nuevo conocimiento en todas las capas."""
        result = {"stored": False, "indexed": False, "chunks": 0}

        # Store in long-term
        entry_id = self.long_term.store(category, source, text)
        result["stored"] = True
        result["entry_id"] = entry_id

        # Index in RAG
        if self._rag_initialized:
            chunks = self.rag.index_document(text, {"source": source, "category": category})
            result["indexed"] = True
            result["chunks"] = chunks

            # Link embedding
            if chunks > 0:
                self.long_term.update_priority(entry_id, 1.5)

        return result

    def index_file(self, file_path: str) -> Dict:
        """Indexa un archivo en todas las capas."""
        path = Path(file_path)
        if not path.exists():
            return {"error": f"File not found: {file_path}"}

        text = path.read_text(encoding="utf-8", errors="ignore")
        return self.index_knowledge(text, source=str(path), category=path.suffix.lstrip("."))

    def index_knowledge_base(self, directory: str) -> Dict:
        """Indexa un directorio completo de conocimiento."""
        if self._rag_initialized:
            chunks = self.rag.index_directory(directory)
            return {"directory": directory, "total_chunks": chunks}
        return {"error": "RAG not initialized"}

    def search(self, query: str, limit: int = 10) -> Dict:
        """Búsqueda unificada en todas las capas de memoria."""
        results = {
            "short_term": self.short_term.search_messages(query, limit),
            "long_term": self.long_term.search_knowledge(query, limit),
            "rag": self.rag.query(query, limit) if self._rag_initialized else [],
        }
        return results

    def get_full_context(self, user_input: str) -> str:
        """Genera contexto completo para el LLM."""
        ctx = self.process_input(user_input)
        parts = []

        if ctx.get("rag_context"):
            parts.append(ctx["rag_context"])
        if ctx.get("long_term"):
            parts.append(f"=== CONOCIMIENTO ALMACENADO ===\n{ctx['long_term']}")
        if ctx.get("short_term"):
            parts.append(f"=== CONVERSACIÓN RECIENTE ===\n{ctx['short_term']}")

        return "\n\n".join(parts) if parts else ""

    def get_stats(self) -> dict:
        """Estadísticas completas de memoria."""
        return {
            "short_term": self.short_term.get_stats(),
            "long_term": self.long_term.get_stats(),
            "rag": self.rag.get_stats(),
            "rag_initialized": self._rag_initialized,
        }

    def clear_working_memory(self):
        """Limpia la memoria de trabajo."""
        self.short_term._working_memory.clear()

    def close(self):
        """Cierra recursos."""
        self.long_term.close()
