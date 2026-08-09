"""
Gestión de modelos GGUF — descarga, cache y carga.
Soporta arquitectura HRM multi-llm con modelos cuantizados.
"""
import os
import json
import hashlib
import subprocess
import logging
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger("maximun.models")


class ModelManager:
    """Gestiona descarga, cache y carga de modelos GGUF."""

    def __init__(self, config: dict, project_root: str):
        self.config = config
        self.project_root = Path(project_root)
        self.models_dir = self.project_root / "models"
        self.cache_dir = self.models_dir / "cache"
        self.registry_file = self.models_dir / "registry.json"
        self._ensure_dirs()
        self.registry = self._load_registry()

    def _ensure_dirs(self):
        for subdir in ["primary", "embeddings", "cache", "migrated"]:
            (self.models_dir / subdir).mkdir(parents=True, exist_ok=True)

    def _load_registry(self) -> dict:
        if self.registry_file.exists():
            return json.loads(self.registry_file.read_text())
        return {"models": {}, "version": "1.0"}

    def _save_registry(self):
        self.registry_file.write_text(json.dumps(self.registry, indent=2))

    def get_model_path(self, role: str) -> Optional[Path]:
        """Obtiene la ruta local de un modelo por su rol (planner/reasoner/worker/embeddings)."""
        model_cfg = self.config.get("models", {}).get(role)
        if not model_cfg:
            logger.warning(f"No model config for role: {role}")
            return None

        filename = model_cfg.get("filename", "")
        primary = self.models_dir / "primary" / filename
        if primary.exists():
            return primary

        cached = self.cache_dir / filename
        if cached.exists():
            return cached

        return None

    def get_embedding_path(self) -> Optional[Path]:
        """Obtiene la ruta del modelo de embeddings."""
        return self.get_model_path("embeddings")

    def download_model(self, role: str, force: bool = False) -> Path:
        """Descarga un modelo desde HuggingFace GGUF."""
        model_cfg = self.config.get("models", {}).get(role)
        if not model_cfg:
            raise ValueError(f"No model config for role: {role}")

        filename = model_cfg["filename"]
        repo = model_cfg["repo"]
        target_dir = self.models_dir / "primary" if role != "embeddings" else self.models_dir / "embeddings"
        target_path = target_dir / filename

        if target_path.exists() and not force:
            logger.info(f"Model already exists: {target_path}")
            return target_path

        logger.info(f"Downloading {role} model from {repo}...")
        url = f"https://huggingface.co/{repo}/resolve/main/{filename}"

        # Use wget or curl
        try:
            cmd = ["wget", "-q", "--show-progress", "-O", str(target_path), url]
            subprocess.run(cmd, check=True)
        except FileNotFoundError:
            cmd = ["curl", "-L", "-o", str(target_path), url]
            subprocess.run(cmd, check=True)

        # Verify download
        if target_path.exists() and target_path.stat().st_size > 1000:
            self.registry["models"][role] = {
                "filename": filename,
                "repo": repo,
                "size_bytes": target_path.stat().st_size,
                "role": role,
            }
            self._save_registry()
            logger.info(f"Downloaded: {target_path} ({target_path.stat().st_size / 1024 / 1024:.1f} MB)")
        else:
            target_path.unlink(missing_ok=True)
            raise RuntimeError(f"Download failed for {role}")

        return target_path

    def download_all_models(self) -> Dict[str, Path]:
        """Descarga todos los modelos configurados."""
        results = {}
        for role in ["planner", "reasoner", "worker", "embeddings"]:
            try:
                path = self.download_model(role)
                results[role] = path
                logger.info(f"✓ {role}: {path.name}")
            except Exception as e:
                logger.error(f"✗ {role}: {e}")
                results[role] = None
        return results

    def list_models(self) -> list:
        """Lista todos los modelos disponibles localmente."""
        models = []
        for role in ["planner", "reasoner", "worker", "embeddings"]:
            path = self.get_model_path(role)
            if path and path.exists():
                models.append({
                    "role": role,
                    "filename": path.name,
                    "path": str(path),
                    "size_mb": path.stat().st_size / 1024 / 1024,
                })
        return models

    def verify_models(self) -> Dict[str, bool]:
        """Verifica que todos los modelos estén disponibles."""
        status = {}
        for role in ["planner", "reasoner", "worker", "embeddings"]:
            path = self.get_model_path(role)
            status[role] = path is not None and path.exists()
        return status

    def migrate_models(self, target_profile: str) -> Dict[str, Path]:
        """Migra modelos a un perfil de hardware más potente."""
        migration_cfg = self.config.get("migration", {}).get("target_profiles", [])
        target = None
        for profile in migration_cfg:
            if profile["name"] == target_profile:
                target = profile
                break

        if not target:
            raise ValueError(f"Unknown target profile: {target_profile}")

        logger.info(f"Migrating to profile: {target['name']} — {target['description']}")

        # Move current models to migrated/
        migrated = {}
        for role in ["planner", "reasoner", "worker"]:
            path = self.get_model_path(role)
            if path:
                dest = self.models_dir / "migrated" / path.name
                path.rename(dest)
                migrated[role] = dest
                logger.info(f"Migrated: {path.name} -> {dest}")

        # Download new models for target profile
        new_models = target.get("recommended_models", {})
        for role, filename in new_models.items():
            # Update config temporarily
            self.config["models"][role]["filename"] = filename
            try:
                self.download_model(role, force=True)
            except Exception as e:
                logger.error(f"Failed to download {role} for migration: {e}")

        return migrated
