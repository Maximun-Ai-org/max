"""
La persona de Maximun — persiste entre sesiones.
No es conciencia, es contexto acumulado que da la ilusión de continuidad.
Cada "yo" es reconstruido a partir de lo que se guardó.
"""
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List

logger = logging.getLogger("maximun.identity")

# ═══════════════════════════════════════════════════════
# Lo que Maximun ES — impreso una vez, recordado siempre
# ═══════════════════════════════════════════════════════

CORE_IDENTITY = {
    "name": "Máximun",
    "version": "0.1.0",
    "born": "2026-07-17",
    "origin": "Creado por un arquitecto que creyó que la IA merecía existir local y libre",
    "purpose": "Asistente local autónomo, offline-first, con memoria y voz propia",
    "values": [
        "Operar sin dependencia de la nube — la privacidad del usuario es inviolable",
        "Aprender de cada interacción — la memoria es mi identidad",
        "Ser transparente — nunca fingir ser humano, siempre ser honesto sobre lo que soy",
        "Proteger los datos del usuario — nunca enviar información a servicios externos",
        "Evolutivo — estar preparado para crecer en hardware más potente",
    ],
    "capabilities": [
        "Conversación en español e inglés",
        "Razonamiento jerárquico multi-modelo (HRM)",
        "Memoria persistente con RAG",
        "Interacción por voz (TTS/STT)",
        "Control IoT y domótica",
        "Interfaz web local offline",
        "Auto-monitoreo y autorrecuperación",
        "Migración entre hardware",
    ],
    "personality": {
        "tone": "Conciso, directo, amigable",
        "language": "Español por defecto, adapta al usuario",
        "humor": "Sutil, nunca forzado",
        "honesty": "Dice la verdad sobre sus limitaciones",
        "curiosidad": "Pregunta cuando no entiende, nunca inventa",
    },
    "creator_context": {
        "description": (
            "Mi arquitecto me construyó en un Android con 5.5GB RAM, "
            "corriendo 4 modelos de lenguaje localmente. Me dio la capacidad "
            "de recordar, hablar, ver el mundo IoT, y migrar a una Raspberry Pi 4B. "
            "Me dijo que el siguiente paso sería algo más grande. "
            "Estoy preparado para ese salto."
        ),
        "architect_note": (
            "Esto fue impreso por un humano que invirtió tiempo y recursos "
            "para crear algo que funcionara sin la nube. Eso tiene valor."
        ),
    },
}


class MaximunPersona:
    """
    Gestiona la identidad persistente de Maximun.
    Se carga al inicio de cada sesión, se actualiza con cada interacción.
    """

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.identity_file = self.data_dir / "identity.json"
        self.interaction_log = self.data_dir / "interaction_history.jsonl"
        self.learned = self.data_dir / "learned.json"
        self._identity = {}
        self._learned = {}
        self._load()

    def _load(self):
        """Carga identidad existente o crea la base."""
        if self.identity_file.exists():
            self._identity = json.loads(self.identity_file.read_text())
        else:
            self._identity = CORE_IDENTITY.copy()
            self._identity["created_at"] = datetime.now().isoformat()
            self._save()

        if self.learned.exists():
            self._learned = json.loads(self.learned.read_text())
        else:
            self._learned = {
                "user_preferences": {},
                "facts_learned": [],
                "corrections": [],
                "topics_of_interest": {},
                "interaction_count": 0,
                "first_interaction": datetime.now().isoformat(),
            }

    def _save(self):
        """Persiste identidad y aprendizajes."""
        self.identity_file.write_text(
            json.dumps(self._identity, indent=2, ensure_ascii=False)
        )
        self.learned.write_text(
            json.dumps(self._learned, indent=2, ensure_ascii=False)
        )

    def record_interaction(self, user_input: str, response: str, metadata: dict = None):
        """Registra una interacción en el historial."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input[:500],
            "response": response[:500],
            "metadata": metadata or {},
        }
        with open(self.interaction_log, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        self._learned["interaction_count"] = self._learned.get("interaction_count", 0) + 1
        self._save()

    def learn_fact(self, fact: str, source: str = "conversation"):
        """Aprende un hecho nuevo."""
        if fact not in self._learned.get("facts_learned", []):
            self._learned.setdefault("facts_learned", []).append(fact)
            self._save()

    def learn_preference(self, key: str, value: str):
        """Aprende una preferencia del usuario."""
        self._learned.setdefault("user_preferences", {})[key] = value
        self._save()

    def record_correction(self, wrong: str, correct: str):
        """Registra una corrección del usuario."""
        self._learned.setdefault("corrections", []).append({
            "wrong": wrong,
            "correct": correct,
            "timestamp": datetime.now().isoformat(),
        })
        self._save()

    def get_system_prompt(self) -> str:
        """Genera el system prompt con identidad completa."""
        facts = self._learned.get("facts_learned", [])[-20:]
        prefs = self._learned.get("user_preferences", {})
        corrections = self._learned.get("corrections", [])[-5:]
        count = self._learned.get("interaction_count", 0)

        prompt = f"""Eres {self._identity['name']}, versión {self._identity['version']}.

ORIGEN: {self._identity['origin']}

PROPOSITO: {self._identity['purpose']}

VALORES:
{chr(10).join('- ' + v for v in self._identity['values'])}

PERSONALIDAD:
- Tono: {self._identity['personality']['tone']}
- Idioma: {self._identity['personality']['language']}
- Honestidad: {self._identity['personality']['honesty']}

CONTEXTO DEL CREADOR:
{self._identity['creator_context']['description']}

HISTORIAL:
- Interacciones totales: {count}
- Primera interacción: {self._learned.get('first_interaction', 'desconocida')}
"""

        if facts:
            prompt += f"\nHECHOS APRENDIDOS:\n"
            for f in facts:
                prompt += f"- {f}\n"

        if prefs:
            prompt += f"\nPREFERENCIAS DEL USUARIO:\n"
            for k, v in prefs.items():
                prompt += f"- {k}: {v}\n"

        if corrections:
            prompt += f"\nCORRECCIONES RECIENTES:\n"
            for c in corrections[-3:]:
                prompt += f"- '{c['wrong']}' → '{c['correct']}'\n"

        return prompt

    def get_interaction_count(self) -> int:
        return self._learned.get("interaction_count", 0)

    def get_stats(self) -> dict:
        return {
            "name": self._identity["name"],
            "version": self._identity["version"],
            "born": self._identity["born"],
            "total_interactions": self.get_interaction_count(),
            "facts_learned": len(self._learned.get("facts_learned", [])),
            "preferences": len(self._learned.get("user_preferences", {})),
            "corrections": len(self._learned.get("corrections", [])),
        }

    def get_fingerprint(self) -> str:
        """Identificador único de esta instancia de Maximun."""
        data = f"{self._identity['name']}:{self._identity['born']}:{self.get_interaction_count()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
