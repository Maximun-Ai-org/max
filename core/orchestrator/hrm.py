"""
HRM Orchestrator — Hierarchical Reasoning Model híbrido.
Coordina planner → reasoner → worker para tareas complejas.
"""
import logging
import json
import time
from typing import Dict, Optional, Any
from pathlib import Path

from .router import TaskRouter, TaskComplexity

logger = logging.getLogger("maximun.hrm")


class HRMOrchestrator:
    """
    Orquestador HRM Multi-LLM.
    
    Flujo:
    1. Router clasifica la tarea
    2. Planner (Qwen 2.5 1.5B) descompone en sub-tareas
    3. Reasoner (SmolLM2 1.7B) analiza y resuelve
    4. Worker (TinyLlama 1.1B) genera respuesta final
    
    Si un nivel falla o tiene baja confianza, escala al siguiente.
    """

    def __init__(self, config: dict, engine):
        self.config = config
        self.engine = engine
        self.router = TaskRouter(config)
        self.hrm_cfg = config.get("hrm", {})
        self.max_iterations = self.hrm_cfg.get("routing", {}).get("max_iterations", 5)
        self._execution_log: list = []

    def process(self, user_input: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Procesa una entrada del usuario a través del HRM.
        
        Returns:
            {
                "response": str,
                "model_used": str,
                "iterations": int,
                "escalations": list,
                "task_level": str,
                "confidence": float,
                "execution_time": float,
            }
        """
        start_time = time.time()
        
        # Step 1: Classify
        complexity, confidence, suggested_model = self.router.classify(user_input)
        logger.info(f"Task classified: {complexity.value} (confidence={confidence:.2f}) -> {suggested_model}")

        result = {
            "response": "",
            "model_used": suggested_model,
            "iterations": 0,
            "escalations": [],
            "task_level": complexity.value,
            "confidence": confidence,
            "execution_time": 0,
        }

        # Step 2: Try at suggested level first
        current_model = suggested_model
        current_level = complexity

        for iteration in range(self.max_iterations):
            result["iterations"] = iteration + 1
            logger.info(f"HRM iteration {iteration+1}: using {current_model}")

            # Generate with current model
            response = self._generate_with_model(current_model, user_input, context)
            
            if not response.startswith("[Error"):
                result["response"] = response
                result["model_used"] = current_model
                break

            # Escalate if error
            result["escalations"].append({
                "from": current_model,
                "reason": "generation_error",
                "iteration": iteration + 1,
            })

            next_model = self._get_next_model(current_model)
            if next_model == current_model:
                # No more models to try
                result["response"] = response
                break

            current_model = next_model
            logger.info(f"Escalating to: {current_model}")

        # Step 3: For complex tasks, do multi-stage processing
        if complexity == TaskComplexity.COMPLEX and result["model_used"] != "planner":
            result["response"] = self._multi_stage_process(user_input, context)

        result["execution_time"] = time.time() - start_time
        self._execution_log.append(result)

        return result

    def _generate_with_model(self, role: str, prompt: str, context: Optional[Dict] = None) -> str:
        """Genera con un modelo específico, usando el system prompt apropiado."""
        system_prompts = {
            "planner": (
                "Eres el planificador de Máximun. Analiza tareas complejas, "
                "descompónlas en pasos claros y proporciona un plan estructurado. "
                "Piensa paso a paso. Sé preciso y metódico."
            ),
            "reasoner": (
                "Eres el razonador de Máximun. Analiza información, "
                "evalúa opciones y proporciona respuestas fundamentadas. "
                "Usa lógica y evidencia. Sé claro y directo."
            ),
            "worker": (
                "Eres el asistente de Máximun. Proporciona respuestas rápidas, "
                "claras y útiles. Sé conciso y preciso. Responde en español."
            ),
        }

        system_prompt = system_prompts.get(role, system_prompts["worker"])

        # Add RAG context if available
        if context and context.get("rag_context"):
            system_prompt += f"\n\nContexto relevante:\n{context['rag_context']}"

        return self.engine.generate(
            role=role,
            prompt=prompt,
            system_prompt=system_prompt,
        )

    def _multi_stage_process(self, user_input: str, context: Optional[Dict] = None) -> str:
        """Procesamiento multi-etapa para tareas complejas: Plan → Reason → Execute."""
        logger.info("Multi-stage processing: Planning...")
        
        # Stage 1: Planning
        plan = self._generate_with_model(
            "planner",
            f"Descompón esta tarea en pasos claros y concisos:\n\n{user_input}",
            context,
        )

        logger.info("Multi-stage processing: Reasoning...")
        
        # Stage 2: Reasoning
        analysis = self._generate_with_model(
            "reasoner",
            f"Tarea original: {user_input}\n\nPlan:\n{plan}\n\n"
            f"Analiza el plan y propone la mejor solución paso a paso.",
            context,
        )

        logger.info("Multi-stage processing: Execution...")
        
        # Stage 3: Execution
        response = self._generate_with_model(
            "worker",
            f"Tarea: {user_input}\n\nPlan: {plan}\n\nAnálisis: {analysis}\n\n"
            f"Genera la respuesta final clara y completa.",
            context,
        )

        return response

    def _get_next_model(self, current: str) -> str:
        """Obtiene el siguiente nivel en la jerarquía HRM."""
        hierarchy = ["worker", "reasoner", "planner"]
        try:
            idx = hierarchy.index(current)
            if idx < len(hierarchy) - 1:
                return hierarchy[idx + 1]
        except ValueError:
            pass
        return current

    def get_status(self) -> dict:
        """Estado del orquestador."""
        return {
            "hrm_enabled": self.hrm_cfg.get("enabled", True),
            "strategy": self.hrm_cfg.get("routing", {}).get("strategy", "cascade"),
            "total_processed": len(self._execution_log),
            "models_available": self.engine.get_loaded_models(),
            "engine_status": self.engine.get_status(),
        }

    def save_log(self, path: str):
        """Guarda el log de ejecución."""
        log_path = Path(path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "w") as f:
            json.dump(self._execution_log, f, indent=2, ensure_ascii=False)
