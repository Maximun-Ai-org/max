"""Recuperación ante corrupción de bases de datos."""
import sqlite3, shutil, json, os
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger("maximun.recovery")

class DatabaseRecovery:
    def __init__(self, project_root: str = "."):
        self.root = Path(project_root)
        self.backup_dir = self.root / "data" / "recovery"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def check_integrity(self, db_path: str) -> dict:
        path = Path(db_path)
        if not path.exists():
            return {"status": "missing", "path": db_path}
        
        try:
            conn = sqlite3.connect(str(path))
            result = conn.execute("PRAGMA integrity_check").fetchone()
            conn.close()
            
            if result[0] == "ok":
                return {"status": "ok", "path": db_path}
            else:
                return {"status": "corrupted", "error": result[0], "path": db_path}
        except Exception as e:
            return {"status": "error", "error": str(e), "path": db_path}

    def auto_repair(self, db_path: str) -> bool:
        path = Path(db_path)
        if not path.exists():
            return False
        
        # Try VACUUM repair
        try:
            conn = sqlite3.connect(str(path))
            conn.execute("VACUUM")
            conn.close()
            logger.info(f"VACUUM repair successful: {db_path}")
            return True
        except Exception:
            pass
        
        # Try export/import repair
        try:
            backup_path = self.backup_dir / f"recovery_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            shutil.copy2(path, backup_path)
            
            conn = sqlite3.connect(str(path))
            new_conn = sqlite3.connect(str(path) + ".new")
            
            for line in conn.iterdump():
                new_conn.execute(line)
            
            conn.close()
            new_conn.close()
            
            os.replace(str(path) + ".new", str(path))
            logger.info(f"Export/import repair successful: {db_path}")
            return True
        except Exception as e:
            logger.error(f"Repair failed: {e}")
            return False

    def check_all_databases(self) -> list:
        databases = [
            self.root / "memory" / "long_term" / "knowledge.db",
        ]
        results = []
        for db in databases:
            if db.exists():
                results.append(self.check_integrity(str(db)))
        return results
