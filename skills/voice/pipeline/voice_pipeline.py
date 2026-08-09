"""
Voice Pipeline — Flujo completo de interacción por voz.

Flujo HRM de reflexión:
1. ESCUCHAR (STT) → Captura audio del usuario
2. REFLEXIONAR (HRM) → Procesa con planner/reasoner/worker
3. AUDITAR (Evaluator) → Verifica calidad de la respuesta
4. COMPROBAR (Validator) → Ejecuta validaciones lógicas
5. HABLAR (TTS) → Genera y reproduce respuesta por voz
"""
import time
import logging
from typing import Optional, Dict, Any
from ..tts.engine import TTSEngine
from ..stt.engine import STTEngine

logger = logging.getLogger("maximun.voice.pipeline")


class VoicePipeline:
    """
    Pipeline de interacción por voz con ciclo de reflexión HRM.
    
    Ciclo: Listen → Reflect → Audit → Verify → Speak
    """

    def __init__(self, config: dict, hrm_orchestrator=None, memory_manager=None):
        self.config = config
        self.hrm = hrm_orchestrator
        self.memory = memory_manager

        voice_cfg = config.get("voice", {})
        tts_cfg = voice_cfg.get("tts", {})
        stt_cfg = voice_cfg.get("stt", {})

        self.tts = TTSEngine(tts_cfg)
        self.stt = STTEngine(stt_cfg)
        self.active = False
        self._reflection_log = []

    def process_voice_input(self, duration: int = 5, source: str = "mic") -> Dict[str, Any]:
        """
        Procesa una entrada de voz completa a través del ciclo HRM.
        
        Returns:
            {
                "user_text": str,       # Lo que dijo el usuario
                "reflection": str,      # Análisis del planner
                "audit": str,           # Auditoría del reasoner
                "verification": str,    # Resultado de comprobación
                "response_text": str,   # Respuesta final
                "audio_path": str,      # Ruta del audio generado
                "cycle_time": float,    # Tiempo total del ciclo
                "stages": list,         # Etapas completadas
            }
        """
        start_time = time.time()
        stages = []
        result = {
            "user_text": "",
            "reflection": "",
            "audit": "",
            "verification": "",
            "response_text": "",
            "audio_path": "",
            "cycle_time": 0,
            "stages": stages,
        }

        # ═══ ETAPA 1: ESCUCHAR (STT) ═══
        logger.info("🎤 Etapa 1: Escuchando...")
        if source == "jack":
            user_text = self.stt.transcribe_jack(duration)
        else:
            user_text = self.stt.transcribe_mic(duration)

        if not user_text:
            result["response_text"] = "No pude escuchar lo que dijiste"
            result["audio_path"] = self.tts.synthesize(result["response_text"])
            return result

        result["user_text"] = user_text
        stages.append("listen")
        logger.info(f"  Texto: {user_text}")

        # ═══ ETAPA 2: REFLEXIONAR (HRM) ═══
        logger.info("🧠 Etapa 2: Reflexionando...")
        if self.hrm:
            enriched = {}
            if self.memory:
                enriched = self.memory.process_input(user_text)
            hrm_result = self.hrm.process(user_text, enriched)
            result["reflection"] = hrm_result.get("response", "")
            result["response_text"] = hrm_result["response"]
            stages.append("reflect")
            logger.info(f"  Modelo usado: {hrm_result['model_used']}")
        else:
            result["reflection"] = f"Procesando: {user_text}"
            result["response_text"] = f"Entendido: {user_text}"
            stages.append("reflect")

        # ═══ ETAPA 3: AUDITAR (Evaluator) ═══
        logger.info("🔍 Etapa 3: Auditando respuesta...")
        audit = self._audit_response(user_text, result["reflection"])
        result["audit"] = audit
        stages.append("audit")
        logger.info(f"  Audit: {'PASS' if audit['passed'] else 'FAIL'}")

        # Si la auditoría falla, reintentar con nivel superior
        if not audit["passed"] and self.hrm:
            logger.info("  Reintentando con nivel superior...")
            retry_result = self.hrm.process(
                f"Corrige y mejora: {user_text}\n\nRespuesta anterior: {result['reflection']}\n\nProblemas: {audit['issues']}",
            )
            result["reflection"] = retry_result.get("response", result["reflection"])
            result["response_text"] = retry_result["response"]
            stages.append("retry")

        # ═══ ETAPA 4: COMPROBAR (Validator) ═══
        logger.info("✅ Etapa 4: Comprobando...")
        verification = self._verify_response(result["response_text"])
        result["verification"] = verification
        stages.append("verify")
        logger.info(f"  Verify: {'PASS' if verification['valid'] else 'WARNING'}")

        # ═══ ETAPA 5: HABLAR (TTS) ═══
        logger.info("🔊 Etapa 5: Generando audio...")
        audio_path = self.tts.synthesize(result["response_text"])
        result["audio_path"] = audio_path
        stages.append("speak")

        # Reproducir si hay audio
        if audio_path:
            self.tts.speak_jack(result["response_text"])

        # Guardar en memoria
        if self.memory:
            self.memory.process_response(
                result["response_text"],
                model_used="voice_pipeline",
                task_level="voice",
                confidence=audit.get("confidence", 0.7),
            )

        result["cycle_time"] = time.time() - start_time
        self._reflection_log.append(result)

        logger.info(f"Ciclo completado en {result['cycle_time']:.2f}s")
        return result

    def process_text_input(self, text: str) -> Dict[str, Any]:
        """
        Procesa entrada de texto (sin STT) pero genera respuesta por voz.
        """
        start_time = time.time()
        stages = []
        result = {
            "user_text": text,
            "reflection": "",
            "audit": "",
            "verification": "",
            "response_text": "",
            "audio_path": "",
            "cycle_time": 0,
            "stages": stages,
        }

        # REFLEXIONAR
        if self.hrm:
            enriched = {}
            if self.memory:
                enriched = self.memory.process_input(text)
            hrm_result = self.hrm.process(text, enriched)
            result["reflection"] = hrm_result.get("response", "")
            result["response_text"] = hrm_result["response"]
        else:
            result["response_text"] = f"Procesando: {text}"
        stages.append("reflect")

        # AUDITAR
        audit = self._audit_response(text, result["reflection"])
        result["audit"] = audit
        stages.append("audit")

        if not audit["passed"] and self.hrm:
            retry = self.hrm.process(
                f"Corrige: {text}\nProblemas: {audit['issues']}"
            )
            result["response_text"] = retry.get("response", result["response_text"])
            stages.append("retry")

        # COMPROBAR
        verification = self._verify_response(result["response_text"])
        result["verification"] = verification
        stages.append("verify")

        # HABLAR
        audio_path = self.tts.synthesize(result["response_text"])
        result["audio_path"] = audio_path
        stages.append("speak")

        if audio_path:
            self.tts.speak_jack(result["response_text"])

        if self.memory:
            self.memory.process_response(
                result["response_text"],
                model_used="voice_text_pipeline",
                task_level="text_voice",
                confidence=audit.get("confidence", 0.7),
            )

        result["cycle_time"] = time.time() - start_time
        return result

    def _audit_response(self, question: str, answer: str) -> Dict[str, Any]:
        """
        Auditoría de la respuesta:
        - ¿Responde a la pregunta?
        - ¿Es coherente?
        - ¿Tiene contenido suficiente?
        """
        issues = []
        confidence = 0.8

        if not answer or len(answer.strip()) < 5:
            issues.append("Respuesta demasiado corta o vacía")
            confidence -= 0.3

        if answer.startswith("[Error"):
            issues.append("Error en la generación")
            confidence -= 0.5

        # Check if answer addresses question keywords
        q_words = set(question.lower().split())
        a_words = set(answer.lower().split())
        overlap = len(q_words & a_words)
        if overlap == 0 and len(q_words) > 3:
            issues.append("Baja relevancia semántica")
            confidence -= 0.2

        # Check length appropriateness
        if len(answer) > 2000:
            issues.append("Respuesta excesivamente larga")
            confidence -= 0.1

        return {
            "passed": len(issues) == 0,
            "confidence": max(0.1, min(1.0, confidence)),
            "issues": issues,
        }

    def _verify_response(self, response: str) -> Dict[str, Any]:
        """Comprobación lógica básica de la respuesta."""
        warnings = []
        valid = True

        if not response:
            valid = False
            warnings.append("Respuesta vacía")

        if response.count("[Error") > 0:
            valid = False
            warnings.append("Contiene marcadores de error")

        if response.count("undefined") > 2 or response.count("None") > 2:
            warnings.append("Posibles valores nulos")

        return {"valid": valid, "warnings": warnings}

    def start_continuous(self, duration_per_turn: int = 5):
        """Inicia modo de escucha continua."""
        self.active = True
        logger.info("Modo voz continua activado")
        
        turn = 0
        while self.active:
            turn += 1
            logger.info(f"\n═══ Turno {turn} ═══")
            try:
                result = self.process_voice_input(duration_per_turn, source="jack")
                print(f"Tú: {result['user_text']}")
                print(f"Máximun: {result['response_text']}")
                print(f"Tiempo: {result['cycle_time']:.2f}s")
            except KeyboardInterrupt:
                self.active = False
            except Exception as e:
                logger.error(f"Error en turno {turn}: {e}")

    def stop(self):
        """Detiene el modo continuo."""
        self.active = False

    def get_status(self) -> dict:
        return {
            "tts": self.tts.get_status(),
            "stt": self.stt.get_status(),
            "active": self.active,
            "total_turns": len(self._reflection_log),
        }
