"""
Enrutador de tareas — clasifica y delega al nivel HRM correcto.
"""
import logging
import re
from typing import Dict, Tuple
from enum import Enum

logger = logging.getLogger("maximun.router")


class TaskComplexity(Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


class TaskRouter:
    """Enruta tareas al modelo apropiado según complejidad."""

    COMPLEX_KEYWORDS = {
        "planifica", "analiza", "razona", "compara", "evalúa", "diseña",
        "arquitectura", "estrategia", "optimiza", "refactoriza", "explica_detalladamente",
        "step by step", "paso a paso", "cadena de pensamiento", "think",
        "investiga", "profundiza", "sintetiza", "argumenta",
    }

    MEDIUM_KEYWORDS = {
        "resuelve", "calcula", "traduce", "resume", "genera", "escribe",
        "crea", "modifica", "busca", "ordena", "filtra", "transforma",
        "code", "código", "script", "función", "implementa",
    }

    SIMPLE_KEYWORDS = {
        "qué", "cuál", "cuánto", "cuándo", "dónde", "quién",
        "define", "lista", "muestra", "status", "estado", "ayuda",
        "hola", "gracias", "ok", "sí", "no",
    }

    def __init__(self, config: dict):
        self.config = config
        self.hrm_cfg = config.get("hrm", {})
        self.strategy = self.hrm_cfg.get("routing", {}).get("strategy", "cascade")
        self.confidence_threshold = self.hrm_cfg.get("routing", {}).get("confidence_threshold", 0.7)
        self.escalation_threshold = self.hrm_cfg.get("routing", {}).get("escalation_threshold", 0.5)

    def classify(self, task: str) -> Tuple[TaskComplexity, float, str]:
        """
        Clasifica una tarea por complejidad.
        Retorna: (complejidad, confianza, modelo sugerido)
        """
        task_lower = task.lower().strip()
        words = set(task_lower.split())

        # Score each level
        complex_score = len(words & self.COMPLEX_KEYWORDS)
        medium_score = len(words & self.MEDIUM_KEYWORDS)
        simple_score = len(words & self.SIMPLE_KEYWORDS)

        # Heuristics for length and complexity
        if len(task) > 200 or task.count("?") > 2:
            complex_score += 2
        if len(task) > 100:
            complex_score += 1
        if "y " in task_lower or "también" in task_lower:
            medium_score += 1
        if "primero" in task_lower or "luego" in task_lower or "después" in task_lower:
            complex_score += 1

        # Determine level
        total = complex_score + medium_score + simple_score + 1
        if complex_score >= medium_score and complex_score >= simple_score and complex_score > 0:
            confidence = complex_score / total
            return TaskComplexity.COMPLEX, confidence, self.hrm_cfg.get("delegation", {}).get("complex_tasks", "planner")
        elif medium_score >= simple_score and medium_score > 0:
            confidence = medium_score / total
            return TaskComplexity.MEDIUM, confidence, self.hrm_cfg.get("delegation", {}).get("medium_tasks", "reasoner")
        else:
            confidence = max(simple_score / total, 0.4)
            return TaskComplexity.SIMPLE, confidence, self.hrm_cfg.get("delegation", {}).get("simple_tasks", "worker")

    def should_escalate(self, current_level: str, confidence: float) -> bool:
        """Decide si escalar al siguiente nivel del HRM."""
        if confidence < self.escalation_threshold:
            return True
        hierarchy = self.hrm_cfg.get("hierarchy", {})
        levels = ["worker", "reasoner", "planner"]
        current_idx = levels.index(current_level) if current_level in levels else 0
        return current_idx < len(levels) - 1 and confidence < self.confidence_threshold
