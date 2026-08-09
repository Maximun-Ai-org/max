"""
Motor de inferencia — wrapper sobre llama-cpp-python.
Soporta múltiples modelos con hot-swap y gestión de contexto.
"""
import os
import gc
import logging
from typing import Optional, Dict, Generator, List
from pathlib import Path

logger = logging.getLogger("maximun.inference")

# Lazy import — llama_cpp only needed at runtime
_llama_cpp = None


def _get_llama_cpp():
    global _llama_cpp
    if _llama_cpp is None:
        try:
            import llama_cpp
            _llama_cpp = llama_cpp
        except ImportError:
            raise ImportError(
                "llama-cpp-python not installed. Run: pip install llama-cpp-python"
            )
    return _llama_cpp


class InferenceEngine:
    """Motor de inferencia local con soporte multi-modelo."""

    def __init__(self, config: dict, model_paths: Dict[str, Path]):
        self.config = config
        self.model_paths = model_paths
        self._models: Dict[str, object] = {}
        self._active_role: Optional[str] = None
        self._context: List[Dict] = []
        self._max_context = config.get("memory", {}).get("working", {}).get("max_tokens", 4096)

    def load_model(self, role: str) -> bool:
        """Carga un modelo en memoria."""
        if role in self._models:
            logger.info(f"Model {role} already loaded")
            return True

        path = self.model_paths.get(role)
        if not path or not path.exists():
            logger.error(f"Model not found for role: {role}")
            return False

        model_cfg = self.config.get("models", {}).get(role, {})
        n_threads = model_cfg.get("n_threads", 4)
        n_ctx = model_cfg.get("context_length", 4096)
        n_gpu = model_cfg.get("n_gpu_layers", 0)

        logger.info(f"Loading {role} model: {path.name} (ctx={n_ctx}, threads={n_threads})")

        try:
            Llama = _get_llama_cpp().Llama
            model = Llama(
                model_path=str(path),
                n_ctx=n_ctx,
                n_threads=n_threads,
                n_gpu_layers=n_gpu,
                verbose=False,
                use_mmap=True,
                use_mlock=False,
            )
            self._models[role] = model
            logger.info(f"✓ Loaded {role}: {path.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to load {role}: {e}")
            return False

    def unload_model(self, role: str):
        """Descarga un modelo de memoria."""
        if role in self._models:
            del self._models[role]
            gc.collect()
            logger.info(f"Unloaded model: {role}")

    def unload_all(self):
        """Descarga todos los modelos."""
        for role in list(self._models.keys()):
            self.unload_model(role)

    def generate(
        self,
        role: str,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 40,
        stop: Optional[List[str]] = None,
        stream: bool = False,
    ) -> str:
        """Genera texto con un modelo específico."""
        if role not in self._models:
            if not self.load_model(role):
                return f"[Error: No se pudo cargar modelo {role}]"

        model = self._models[role]
        model_cfg = self.config.get("models", {}).get(role, {})

        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Add context
        messages.extend(self._context[-10:])  # Last 10 exchanges
        messages.append({"role": "user", "content": prompt})

        try:
            response = model.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens or model_cfg.get("max_tokens", 512),
                temperature=temperature or model_cfg.get("temperature", 0.7),
                top_p=top_p,
                top_k=top_k,
                stop=stop or [],
                stream=stream,
            )

            if stream:
                return self._stream_response(response)

            content = response["choices"][0]["message"]["content"]

            # Update context
            self._context.append({"role": "user", "content": prompt})
            self._context.append({"role": "assistant", "content": content})
            self._trim_context()

            return content

        except Exception as e:
            logger.error(f"Generation error ({role}): {e}")
            return f"[Error de generación: {e}]"

    def _stream_response(self, response) -> Generator[str, None, None]:
        """Procesa respuesta streaming."""
        for chunk in response:
            delta = chunk["choices"][0].get("delta", {})
            content = delta.get("content", "")
            if content:
                yield content

    def _trim_context(self):
        """Mantiene el contexto dentro del límite de tokens."""
        while len(self._context) > 20:
            self._context.pop(0)

    def clear_context(self):
        """Limpia el contexto de conversación."""
        self._context.clear()

    def get_loaded_models(self) -> List[str]:
        """Retorna lista de modelos cargados."""
        return list(self._models.keys())

    def get_status(self) -> dict:
        """Estado del motor de inferencia."""
        return {
            "loaded_models": self.get_loaded_models(),
            "context_size": len(self._context),
            "max_context": self._max_context,
            "available_models": {
                role: str(path) if path else None
                for role, path in self.model_paths.items()
            },
        }
