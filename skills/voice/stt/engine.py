"""
Motor STT offline — whisper.cpp / vosk / fallback pocketsphinx.
Captura audio del micrófono o Jack y lo convierte a texto.
"""
import os
import subprocess
import tempfile
import json
import wave
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("maximun.voice.stt")


class STTEngine:
    """
    Motor STT multi-backend offline.
    Prioridad: whisper (local) > vosk > pocketsphinx
    Sin dependencias de servicios cloud.
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.backend = self._detect_backend()
        self.language = self.config.get("language", "es")
        self.model_path = self.config.get("model_path", "")
        self.sample_rate = 16000
        self.record_dir = Path(tempfile.gettempdir()) / "maximun_stt"
        self.record_dir.mkdir(exist_ok=True)

    def _detect_backend(self) -> str:
        """Detecta el backend STT disponible."""
        # Check whisper
        for cmd in ["whisper", "whisper-cli", "main"]:
            try:
                result = subprocess.run(
                    [cmd, "--help"],
                    capture_output=True, timeout=5
                )
                if result.returncode == 0 or b"whisper" in result.stderr.lower():
                    logger.info(f"STT backend detectado: whisper ({cmd})")
                    return f"whisper:{cmd}"
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue

        # Check vosk
        try:
            import vosk
            logger.info("STT backend detectado: vosk")
            return "vosk"
        except ImportError:
            pass

        # Check pocketsphinx
        try:
            subprocess.run(["pocketsphinx_continuous", "--help"],
                          capture_output=True, timeout=5)
            logger.info("STT backend detectado: pocketsphinx")
            return "pocketsphinx"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        logger.warning("No STT backend encontrado")
        return "none"

    def transcribe_file(self, audio_path: str) -> str:
        """Transcribe un archivo de audio a texto."""
        if self.backend == "none":
            logger.error("No hay backend STT disponible")
            return ""

        try:
            if "whisper" in self.backend:
                return self._transcribe_whisper(audio_path)
            elif self.backend == "vosk":
                return self._transcribe_vosk(audio_path)
            elif self.backend == "pocketsphinx":
                return self._transcribe_pocketsphinx(audio_path)
        except Exception as e:
            logger.error(f"STT transcription error: {e}")
            return ""

        return ""

    def transcribe_mic(self, duration: int = 5) -> str:
        """Graba del micrófono y transcribe."""
        audio_path = str(self.record_dir / "recording.wav")
        try:
            subprocess.run(
                ["arecord", "-d", str(duration), "-r", str(self.sample_rate),
                 "-f", "S16_LE", "-c", "1", audio_path],
                capture_output=True, timeout=duration + 5
            )
            return self.transcribe_file(audio_path)
        except Exception as e:
            logger.error(f"Mic recording error: {e}")
            return ""

    def transcribe_jack(self, duration: int = 5) -> str:
        """Captura del Jack y transcribe."""
        audio_path = str(self.record_dir / "jack_recording.wav")
        try:
            subprocess.run(
                ["jack_capture", "--format", "wav", "--channels", "1",
                 "--rate", str(self.sample_rate), "--seconds", str(duration),
                 audio_path],
                capture_output=True, timeout=duration + 10
            )
            if os.path.exists(audio_path):
                return self.transcribe_file(audio_path)
        except FileNotFoundError:
            # Fallback a arecord con device Jack
            try:
                subprocess.run(
                    ["arecord", "-d", str(duration), "-r", str(self.sample_rate),
                     "-f", "S16_LE", "-c", "1", "-D", "jack", audio_path],
                    capture_output=True, timeout=duration + 5
                )
                return self.transcribe_file(audio_path)
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Jack capture error: {e}")
        return ""

    def _transcribe_whisper(self, audio_path: str) -> str:
        """Transcribe con whisper."""
        whisper_cmd = self.backend.split(":")[1] if ":" in self.backend else "whisper"
        model = self.config.get("whisper_model", "tiny")
        cmd = [
            whisper_cmd,
            audio_path,
            "--language", self.language,
            "--model", model,
            "--output_format", "txt",
            "--output_dir", str(self.record_dir),
        ]
        if self.model_path:
            cmd.extend(["--model", self.model_path])

        result = subprocess.run(cmd, capture_output=True, timeout=120)

        # Read output txt
        txt_path = Path(audio_path).with_suffix(".txt")
        if txt_path.exists():
            text = txt_path.read_text().strip()
            txt_path.unlink()
            return text

        # Fallback: parse stdout
        return result.stdout.decode().strip()

    def _transcribe_vosk(self, audio_path: str) -> str:
        """Transcribe con vosk."""
        import vosk
        import numpy as np

        model_path = self.model_path or f"vosk-model-{self.language}"
        if not os.path.exists(model_path):
            # Try to find installed vosk model
            for d in Path("/usr/share/vosk").glob("model-*"):
                model_path = str(d)
                break

        model = vosk.Model(model_path)
        wf = wave.open(audio_path, "rb")
        rec = vosk.KaldiRecognizer(model, wf.getframerate())
        rec.SetWords(True)

        results = []
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                if result.get("text"):
                    results.append(result["text"])

        final = json.loads(rec.FinalResult())
        if final.get("text"):
            results.append(final["text"])

        return " ".join(results)

    def _transcribe_pocketsphinx(self, audio_path: str) -> str:
        """Transcribe con pocketsphinx."""
        result = subprocess.run(
            ["pocketsphinx_continuous", "-infile", audio_path,
             "-lang", self.language],
            capture_output=True, timeout=60
        )
        return result.stdout.decode().strip()

    def get_status(self) -> dict:
        return {
            "backend": self.backend,
            "language": self.language,
            "available": self.backend != "none",
        }
