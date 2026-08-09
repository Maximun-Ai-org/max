"""Backup automático de datos críticos de Maximun."""
import shutil, json, os, time
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger("maximun.backup")

class BackupManager:
    def __init__(self, project_root: str):
        self.root = Path(project_root)
        self.backup_dir = self.root / "data" / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.critical_files = [
            "config/agent.yaml",
            "data/identity/identity.json",
            "data/identity/learned.json",
            "memory/long_term/knowledge.db",
            "memory/short_term/sessions.jsonl",
        ]

    def create_backup(self, label: str = "") -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"backup_{label}_{ts}" if label else f"backup_{ts}"
        dest = self.backup_dir / name
        dest.mkdir(parents=True, exist_ok=True)
        
        for f in self.critical_files:
            src = self.root / f
            if src.exists():
                dst = dest / f.replace("/", "_")
                shutil.copy2(src, dst)
        
        # Create manifest
        manifest = {"created": datetime.now().isoformat(), "label": label, "files": len(list(dest.glob("*")))}
        (dest / "manifest.json").write_text(json.dumps(manifest))
        
        logger.info(f"Backup creado: {dest}")
        return str(dest)

    def list_backups(self) -> list:
        backups = []
        for d in sorted(self.backup_dir.iterdir()):
            if d.is_dir() and (d / "manifest.json").exists():
                m = json.loads((d / "manifest.json").read_text())
                backups.append({"name": d.name, "created": m["created"], "files": m["files"]})
        return backups

    def restore_backup(self, backup_name: str) -> bool:
        src = self.backup_dir / backup_name
        if not src.exists():
            return False
        
        restore_map = {
            "config_agent.yaml": "config/agent.yaml",
            "data_identity_identity.json": "data/identity/identity.json",
            "data_identity_learned.json": "data/identity/learned.json",
            "memory_long_term_knowledge.db": "memory/long_term/knowledge.db",
        }
        
        for backup_file, target_path in restore_map.items():
            src_file = src / backup_file
            if src_file.exists():
                dst = self.root / target_path
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst)
                logger.info(f"Restaurado: {target_path}")
        
        return True

    def auto_backup(self):
        """Backup automático — mantener últimos 10."""
        self.create_backup("auto")
        backups = sorted(self.backup_dir.glob("backup_auto_*"))
        for old in backups[:-10]:
            shutil.rmtree(old)
