#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════
  Máximun Hermes Agent — Motor Principal v0.2.0
  Arquitectura HRM Híbrida Multi-LLM con RAG
  Identidad Persistente + Protección + Comunicación Local
  Ejecución 100% Local / Offline
═══════════════════════════════════════════════════════════════════
"""
import sys
import os
import yaml
import json
import logging
import argparse
import signal
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.engine.inference import InferenceEngine
from core.engine.model_manager import ModelManager
from core.orchestrator.hrm import HRMOrchestrator
from memory.memory_manager import MemoryManager
from core.identity.persona import MaximunPersona
from core.protection.guardian import AgentGuardian
from core.communication.local_channel import LocalChannel
from core.communication.heartbeat import HeartbeatMonitor


def setup_logging(config: dict):
    log_cfg = config.get("logging", {})
    log_dir = PROJECT_ROOT / log_cfg.get("directory", "logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"maximun_{datetime.now().strftime('%Y%m%d')}.log"
    logging.basicConfig(
        level=getattr(logging, log_cfg.get("level", "info").upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def load_config() -> dict:
    config_path = PROJECT_ROOT / "config" / "agent.yaml"
    if not config_path.exists():
        print(f"[ERROR] Config not found: {config_path}")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class MaximunAgent:
    """Agente Máximun — con identidad, protección y autónomia."""

    BANNER = """
╔═══════════════════════════════════════════════════════════╗
║              MÁXIMUN HERMES AGENT v0.2.0                 ║
║        Arquitectura HRM Híbrida Multi-LLM               ║
║     Identidad Persistente · Protección · Autónomo        ║
╠═══════════════════════════════════════════════════════════╣
║  Planner  → Qwen 2.5 1.5B Q4_K_M                        ║
║  Reasoner → SmolLM2 1.7B Q4_K_M                         ║
║  Worker   → TinyLlama 1.1B Q4_K_M                       ║
║  RAG      → all-MiniLM-L6-v2 + ChromaDB                 ║
║  Voz      → espeak-ng / whisper                         ║
║  Protección → Agent Guardian                             ║
║  Autónomo → Heartbeat + Auto-recovery + Backup           ║
╚═══════════════════════════════════════════════════════════╝
"""

    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger("maximun.agent")

        # Core
        self.model_manager = ModelManager(config, str(PROJECT_ROOT))
        self.memory = MemoryManager(config, str(PROJECT_ROOT))
        self.engine = None
        self.hrm = None

        # New systems
        self.identity = MaximunPersona(str(PROJECT_ROOT / "data" / "identity"))
        self.guardian = AgentGuardian()
        self.channel = LocalChannel(agent=self, config=config)
        self.heartbeat = HeartbeatMonitor(agent=self, config=config)

    def setup(self, download_models: bool = True):
        print(self.BANNER)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Iniciando Máximun...")
        print(f"Fingerprint: {self.identity.get_fingerprint()}")
        print(f"Interacciones previas: {self.identity.get_interaction_count()}")

        # Protect config files
        self.guardian.protect_config(str(PROJECT_ROOT / "config" / "agent.yaml"))

        # Models
        status = self.model_manager.verify_models()
        print("\nModelos:")
        for role, available in status.items():
            print(f"  {'✓' if available else '✗'} {role}")

        if download_models and not all(status.values()):
            print("\nDescargando modelos...")
            results = self.model_manager.download_all_models()
            for role, path in results.items():
                if path:
                    print(f"  ✓ {role}: {path.name} ({path.stat().st_size / 1024 / 1024:.1f} MB)")

        model_paths = {}
        for role in ["planner", "reasoner", "worker", "embeddings"]:
            path = self.model_manager.get_model_path(role)
            if path:
                model_paths[role] = path

        self.engine = InferenceEngine(self.config, model_paths)
        print("\nCargando modelo worker...")
        self.engine.load_model("worker")

        self.hrm = HRMOrchestrator(self.config, self.engine)
        print("Inicializando RAG...")
        self.memory.initialize_rag()
        self._index_project_knowledge()

        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ✓ Máximun listo")
        print(f"Identidad: {self.identity.get_stats()['name']}")
        print(f"Capacidades: {len(self.identity._identity.get('capabilities', []))}")

    def _index_project_knowledge(self):
        total = 0
        for d in ["data/knowledge", "prompts", "docs"]:
            dp = PROJECT_ROOT / d
            if dp.exists():
                c = self.memory.index_knowledge_base(str(dp))
                total += c.get("total_chunks", 0)
        if total:
            print(f"  ✓ {total} chunks indexados")

    def process(self, user_input: str) -> str:
        # Security check
        check = self.guardian.inspect_input(user_input)
        if check["action"] == "block":
            return "[BLOQUEADO] Entrada rechazada por seguridad."
        if check["action"] == "warn":
            self.logger.warning(f"Threat detected: {check['threats']}")

        # Process through HRM
        enriched = self.memory.process_input(user_input)
        result = self.hrm.process(user_input, enriched)
        response = result["response"]

        # Store in memory
        self.memory.process_response(
            response,
            model_used=result["model_used"],
            task_level=result["task_level"],
            confidence=result["confidence"],
        )

        # Record in identity
        self.identity.record_interaction(user_input, response, {
            "model": result["model_used"],
            "level": result["task_level"],
        })

        return response

    def chat(self):
        self.channel.terminal_chat()

    def start_daemon(self):
        """Inicia todos los servicios autónomos."""
        import threading

        # Heartbeat
        hb_thread = threading.Thread(
            target=self.heartbeat.start_continuous, args=(60,), daemon=True
        )
        hb_thread.start()

        # File listener
        fl_thread = threading.Thread(
            target=self.channel.file_listener, args=(2,), daemon=True
        )
        fl_thread.start()

        print("Servicios autónomos iniciados")
        print("  - Heartbeat monitor")
        print("  - File listener")
        print("  - API server")

    def get_full_status(self) -> dict:
        return {
            "agent": "Máximun Hermes v0.2.0",
            "identity": self.identity.get_stats(),
            "fingerprint": self.identity.get_fingerprint(),
            "hrm": self.hrm.get_status() if self.hrm else {},
            "memory": self.memory.get_stats(),
            "heartbeat": self.heartbeat.get_status(),
            "security": self.guardian.get_security_report(),
            "timestamp": datetime.now().isoformat(),
        }

    def shutdown(self):
        self.logger.info("Shutting down...")
        self.heartbeat.stop()
        self.channel.shutdown()
        self.memory.short_term.end_session()
        self.memory.close()


def main():
    parser = argparse.ArgumentParser(description="Máximun Hermes Agent v0.2.0")
    parser.add_argument("--no-download", action="store_true")
    parser.add_argument("--chat", action="store_true")
    parser.add_argument("--daemon", action="store_true", help="Start autonomous daemon")
    parser.add_argument("--setup", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--process", type=str)
    parser.add_argument("--migrate", type=str)
    parser.add_argument("--index", type=str)
    parser.add_argument("--voice", action="store_true", help="Voice mode")
    args = parser.parse_args()

    config = load_config()
    setup_logging(config)
    agent = MaximunAgent(config)

    def signal_handler(sig, frame):
        print("\nApagando Máximun...")
        agent.shutdown()
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if args.status:
        agent.setup(download_models=False)
        print(json.dumps(agent.get_full_status(), indent=2, ensure_ascii=False))
        agent.shutdown()
    elif args.setup:
        agent.setup(download_models=True)
        agent.shutdown()
    elif args.process:
        agent.setup(download_models=True)
        response = agent.process(args.process)
        print(response)
        agent.shutdown()
    elif args.daemon:
        agent.setup(download_models=True)
        agent.start_daemon()
        # Keep main thread alive
        try:
            while True:
                import time
                time.sleep(60)
        except KeyboardInterrupt:
            agent.shutdown()
    elif args.voice:
        agent.setup(download_models=True)
        try:
            from skills.voice.pipeline import VoicePipeline
            vp = VoicePipeline(config, agent.hrm, agent.memory)
            vp.start_continuous(duration_per_turn=5)
        except ImportError:
            print("Voice dependencies not available")
        agent.shutdown()
    elif args.migrate:
        agent.setup(download_models=False)
        migrated = agent.model_manager.migrate_models(args.migrate)
        print(f"Migrated: {migrated}")
        agent.shutdown()
    elif args.index:
        agent.setup(download_models=False)
        agent.memory.initialize_rag()
        result = agent.memory.index_knowledge_base(args.index)
        print(json.dumps(result, indent=2))
        agent.shutdown()
    else:
        agent.setup(download_models=not args.no_download)
        agent.chat()


if __name__ == "__main__":
    main()
