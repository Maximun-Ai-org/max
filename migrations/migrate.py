#!/usr/bin/env python3
"""
Script de migración — Mueve el agente a un perfil de hardware más potente.
"""
import sys
import json
import yaml
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.engine.model_manager import ModelManager


PROFILES = {
    "mobile_low": {
        "description": "Dispositivo básico (2GB RAM, 2 cores)",
        "models": {
            "planner": "tinyllama-1.1b-chat-q4_k_m.gguf",
            "reasoner": "tinyllama-1.1b-chat-q4_k_m.gguf",
            "worker": "tinyllama-1.1b-chat-q4_k_m.gguf",
        },
        "threads": 2,
        "context": 1024,
    },
    "mobile_medium": {
        "description": "Dispositivo medio (4-6GB RAM, 4 cores) — ACTUAL",
        "models": {
            "planner": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
            "reasoner": "smollm2-1.7b-instruct-q4_k_m.gguf",
            "worker": "tinyllama-1.1b-chat-q4_k_m.gguf",
        },
        "threads": 4,
        "context": 4096,
    },
    "mobile_high": {
        "description": "Flagship (8GB+ RAM, 8 cores) — Snapdragon 8 Gen 2+",
        "models": {
            "planner": "qwen2.5-3b-instruct-q4_k_m.gguf",
            "reasoner": "phi-3-mini-4k-q4_k_m.gguf",
            "worker": "smollm2-1.7b-instruct-q4_k_m.gguf",
        },
        "threads": 8,
        "context": 8192,
    },
    "desktop": {
        "description": "Desktop (16GB+ RAM, x86_64)",
        "models": {
            "planner": "qwen2.5-7b-instruct-q4_k_m.gguf",
            "reasoner": "phi-3-medium-4k-q4_k_m.gguf",
            "worker": "smollm2-1.7b-instruct-q4_k_m.gguf",
        },
        "threads": 16,
        "context": 16384,
    },
}


def migrate(target_profile: str):
    """Migra el agente a un nuevo perfil de hardware."""
    if target_profile not in PROFILES:
        print(f"Perfil desconocido: {target_profile}")
        print(f"Perfiles disponibles: {', '.join(PROFILES.keys())}")
        return

    profile = PROFILES[target_profile]
    print(f"\nMigrando a: {target_profile}")
    print(f"Descripción: {profile['description']}")
    print(f"Modelos:")
    for role, model in profile["models"].items():
        print(f"  {role}: {model}")

    # Backup current config
    config_path = PROJECT_ROOT / "config" / "agent.yaml"
    backup_path = PROJECT_ROOT / "config" / "agent.yaml.bak"
    shutil.copy2(config_path, backup_path)
    print(f"\nConfiguración respaldada: {backup_path}")

    # Update config
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    for role, model_file in profile["models"].items():
        if role in config["models"]:
            config["models"][role]["filename"] = model_file
            config["models"][role]["n_threads"] = profile["threads"]
            config["models"][role]["context_length"] = profile["context"]

    config["hardware"]["profile"] = target_profile

    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    print(f"Configuración actualizada para {target_profile}")

    # Download new models
    print("\nDescargando modelos del nuevo perfil...")
    manager = ModelManager(config, str(PROJECT_ROOT))
    results = manager.download_all_models()

    for role, path in results.items():
        if path:
            print(f"  ✓ {role}: {path.name} ({path.stat().st_size / 1024 / 1024:.1f} MB)")
        else:
            print(f"  ✗ {role}: FALLÓ")

    print(f"\n✓ Migración a {target_profile} completada")


def list_profiles():
    """Lista perfiles de hardware disponibles."""
    print("\nPerfiles de hardware disponibles:\n")
    for name, profile in PROFILES.items():
        marker = " ← ACTUAL" if name == "mobile_medium" else ""
        print(f"  {name}{marker}")
        print(f"    {profile['description']}")
        print(f"    Modelos: {', '.join(profile['models'].values())}")
        print()


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "--list":
        list_profiles()
    else:
        migrate(sys.argv[1])
