"""Tests del core del agente."""
import sys
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.orchestrator.router import TaskRouter, TaskComplexity


class TestTaskRouter:
    """Tests del enrutador de tareas."""

    def setup_method(self):
        self.config = {
            "hrm": {
                "routing": {
                    "strategy": "cascade",
                    "confidence_threshold": 0.7,
                    "escalation_threshold": 0.5,
                },
                "delegation": {
                    "simple_tasks": "worker",
                    "medium_tasks": "reasoner",
                    "complex_tasks": "planner",
                },
            }
        }
        self.router = TaskRouter(self.config)

    def test_simple_task(self):
        """Tareas simples van al worker."""
        complexity, confidence, model = self.router.classify("¿Qué hora es?")
        assert model == "worker"
        assert complexity == TaskComplexity.SIMPLE

    def test_medium_task(self):
        """Tareas medianas van al reasoner."""
        complexity, confidence, model = self.router.classify("Escribe una función que calcule fibonacci")
        assert model == "reasoner"
        assert complexity == TaskComplexity.MEDIUM

    def test_complex_task(self):
        """Tareas complejas van al planner."""
        complexity, confidence, model = self.router.classify(
            "Analiza la arquitectura de este sistema y diseña un plan de optimización paso a paso"
        )
        assert model == "planner"
        assert complexity == TaskComplexity.COMPLEX

    def test_escalation(self):
        """Verifica escalación por baja confianza."""
        assert self.router.should_escalate("worker", 0.3) == True
        assert self.router.should_escalate("planner", 0.9) == False

    def test_long_input_is_complex(self):
        """Inputs largos se clasifican como complejos."""
        long_input = "Necesito que " + " ".join(["analices", "razones", "evalúes", "comparas"] * 5)
        complexity, confidence, model = self.router.classify(long_input)
        assert model == "planner"

    def test_spanish_keywords(self):
        """Keywords en español son detectados."""
        complexity, _, model = self.router.classify("hola")
        assert model == "worker"

        complexity, _, model = self.router.classify("genera un script de python")
        assert model in ("reasoner", "planner")


class TestShortTermMemory:
    """Tests de memoria a corto plazo."""

    def setup_method(self):
        self.config = {
            "memory": {
                "short_term": {
                    "max_sessions": 5,
                    "max_tokens_per_session": 1000,
                    "storage": "/tmp/test_stm.jsonl",
                }
            }
        }

    def test_session_lifecycle(self):
        """Ciclo de vida de una sesión."""
        from memory.short_term import ShortTermMemory
        
        stm = ShortTermMemory(self.config, "/tmp")
        session_id = stm.start_session()
        assert session_id.startswith("session_")

        stm.add_message("user", "Hola")
        stm.add_message("assistant", "¡Hola!")

        messages = stm.get_messages()
        assert len(messages) == 2
        assert messages[0]["content"] == "Hola"

        stm.end_session()


class TestLongTermMemory:
    """Tests de memoria a largo plazo."""

    def setup_method(self):
        self.config = {
            "memory": {
                "long_term": {
                    "storage": "/tmp/test_ltm.db",
                    "decay_rate": 0.01,
                }
            }
        }
        Path("/tmp/test_ltm.db").unlink(missing_ok=True)

    def teardown_method(self):
        Path("/tmp/test_ltm.db").unlink(missing_ok=True)

    def test_store_and_retrieve(self):
        """Almacenar y recuperar conocimiento."""
        from memory.long_term import LongTermMemory
        
        ltm = LongTermMemory(self.config, "/tmp")
        
        entry_id = ltm.store("test", "key1", "Este es un contenido de prueba")
        assert entry_id > 0

        results = ltm.retrieve(category="test")
        assert len(results) == 1
        assert results[0]["key"] == "key1"
        
        ltm.close()

    def test_search(self):
        """Búsqueda de conocimiento."""
        from memory.long_term import LongTermMemory
        
        ltm = LongTermMemory(self.config, "/tmp")
        
        ltm.store("test", "python", "Python es un lenguaje de programación")
        ltm.store("test", "rust", "Rust es un lenguaje de programación")
        
        results = ltm.search_knowledge("lenguaje")
        assert len(results) == 2
        
        ltm.close()

    def test_interactions(self):
        """Almacenar y recuperar interacciones."""
        from memory.long_term import LongTermMemory
        
        ltm = LongTermMemory(self.config, "/tmp")
        
        ltm.store_interaction("Hola", "¡Hola!", "worker", "simple", 0.9)
        
        interactions = ltm.get_interactions()
        assert len(interactions) == 1
        assert interactions[0]["user_message"] == "Hola"
        
        ltm.close()


class TestMemoryManager:
    """Tests del gestor de memoria unificado."""

    def setup_method(self):
        self.config = {
            "memory": {
                "short_term": {
                    "max_sessions": 5,
                    "max_tokens_per_session": 1000,
                    "storage": "/tmp/test_mm_stm.jsonl",
                },
                "long_term": {
                    "storage": "/tmp/test_mm_ltm.db",
                    "decay_rate": 0.01,
                },
                "rag": {
                    "enabled": False,
                },
            }
        }
        Path("/tmp/test_mm_ltm.db").unlink(missing_ok=True)
        Path("/tmp/test_mm_stm.jsonl").unlink(missing_ok=True)

    def teardown_method(self):
        Path("/tmp/test_mm_ltm.db").unlink(missing_ok=True)
        Path("/tmp/test_mm_stm.jsonl").unlink(missing_ok=True)

    def test_process_input(self):
        """Procesamiento de entrada del usuario."""
        from memory.memory_manager import MemoryManager
        
        mm = MemoryManager(self.config, "/tmp")
        
        result = mm.process_input("¿Qué sabes de Python?")
        assert "user_input" in result
        assert result["user_input"] == "¿Qué sabes de Python?"
        
        mm.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
