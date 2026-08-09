"""
Motor TTS offline — espeak-ng / piper / fallback flite.
Convierte texto a audio WAV para salida por Jack.
"""
import os
import subprocess
import tempfile
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("maximun.voice.tts")


class TTSEngine:
    """
    Motor TTS multi-backend offline.
    Prioridad: piper > espeak-ng > flite
    Sin dependencias de servicios cloud.
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.backend = self._detect_backend()
        self.voice = self.config.get("voice", "es")
        self.rate = self.config.get("rate", 160)
        self.pitch = self.config.get("pitch", 50)
        self.output_dir = Path(tempfile.gettempdir()) / "maximun_tts"
        self.output_dir.mkdir(exist_ok=True)

    def _detect_backend(self) -> str:
        """Detecta el backend TTS disponible."""
        backends = ["piper", "espeak-ng", "espeak", "flite"]
        for backend in backends:
            try:
                subprocess.run(
                    [backend, "--version"],
                    capture_output=True, timeout=5
                )
                logger.info(f"TTS backend detectado: {backend}")
                return backend
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        logger.warning("No TTS backend encontrado")
        return "none"

    def synthesize(self, text: str, output_path: Optional[str] = None) -> str:
        """
        Sintetiza texto a audio WAV.
        Retorna la ruta del archivo de audio generado.
        """
        if self.backend == "none":
            logger.error("No hay backend TTS disponible")
            return ""

        if not output_path:
            output_path = str(self.output_dir / f"tts_{hash(text) & 0xFFFFFF:06x}.wav")

        try:
            if self.backend == "piper":
                return self._synthesize_piper(text, output_path)
            elif self.backend in ("espeak-ng", "espeak"):
                return self._synthesize_espeak(text, output_path)
            elif self.backend == "flite":
                return self._synthesize_flite(text, output_path)
        except Exception as e:
            logger.error(f"TTS synthesis error: {e}")
            return ""

        return ""

    def _synthesize_espeak(self, text: str, output_path: str) -> str:
        """Sintetiza con espeak-ng."""
        cmd = [
            self.backend,
            "-v", self.voice,
            "-s", str(self.rate),
            "-p", str(self.pitch),
            "-w", output_path,
            text,
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode == 0 and os.path.exists(output_path):
            logger.info(f"TTS generado: {output_path}")
            return output_path
        logger.error(f"espeak error: {result.stderr.decode()}")
        return ""

    def _synthesize_piper(self, text: str, output_path: str) -> str:
        """Sintetiza con piper."""
        model_path = self.config.get("piper_model", "")
        if not model_path:
            logger.error("Piper model not configured")
            return ""
        cmd = ["piper", "--model", model_path, "--output_file", output_path]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate(input=text.encode("utf-8"), timeout=60)
        if proc.returncode == 0 and os.path.exists(output_path):
            return output_path
        return ""

    def _synthesize_flite(self, text: str, output_path: str) -> str:
        """Sintetiza con flite."""
        cmd = ["flite", "-o", output_path, "-t", text]
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode == 0 and os.path.exists(output_path):
            return output_path
        return ""

    def speak(self, text: str) -> bool:
        """Sintetiza y reproduce directamente."""
        audio_path = self.synthesize(text)
        if not audio_path:
            return False
        try:
            subprocess.run(
                ["aplay", "-q", audio_path],
                capture_output=True, timeout=30
            )
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # Fallback a aplay alternativo
            try:
                subprocess.run(
                    ["paplay", audio_path],
                    capture_output=True, timeout=30
                )
                return True
            except Exception:
                return False

    def speak_jack(self, text: str) -> bool:
        """Sintetiza y reproduce por Jack audio."""
        audio_path = self.synthesize(text)
        if not audio_path:
            return False
        try:
            subprocess.run(
                ["jack_playfile", audio_path],
                capture_output=True, timeout=30
            )
            return True
        except FileNotFoundError:
            # Fallback a aplay con设备 Jack
            try:
                subprocess.run(
                    ["aplay", "-D", "jack", audio_path],
                    capture_output=True, timeout=30
                )
                return True
            except Exception:
                return self.speak(text)

    def get_status(self) -> dict:
        return {
            "backend": self.backend,
            "voice": self.voice,
            "rate": self.rate,
            "available": self.backend != "none",
        }
