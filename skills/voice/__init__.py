"""Sistema de voz — TTS/STT offline para Máximun Agent."""
from .tts.engine import TTSEngine
from .stt.engine import STTEngine
from .pipeline.voice_pipeline import VoicePipeline

__all__ = ["TTSEngine", "STTEngine", "VoicePipeline"]
