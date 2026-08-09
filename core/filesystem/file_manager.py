"""Operaciones de archivos — leer, escribir, buscar, listar."""
import os, shutil, glob
from pathlib import Path
from typing import List, Optional

class FileManager:
    def __init__(self, project_root: str = ".", sandbox: bool = True):
        self.root = Path(project_root).resolve()
        self.sandbox = sandbox

    def _check_path(self, path: str) -> Path:
        p = (self.root / path).resolve()
        if self.sandbox and not str(p).startswith(str(self.root)):
            raise ValueError("Path outside sandbox")
        return p

    def read_file(self, path: str) -> str:
        p = self._check_path(path)
        if p.exists() and p.is_file():
            return p.read_text(encoding="utf-8", errors="replace")
        return ""

    def write_file(self, path: str, content: str) -> bool:
        try:
            p = self._check_path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return True
        except Exception:
            return False

    def list_dir(self, path: str = ".") -> List[dict]:
        p = self._check_path(path)
        if not p.exists():
            return []
        items = []
        for item in sorted(p.iterdir()):
            items.append({
                "name": item.name,
                "type": "dir" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else 0,
            })
        return items

    def search_files(self, pattern: str, path: str = ".") -> List[str]:
        p = self._check_path(path)
        return [str(f.relative_to(self.root)) for f in p.rglob(pattern)]

    def file_info(self, path: str) -> dict:
        p = self._check_path(path)
        if not p.exists():
            return {"error": "not found"}
        stat = p.stat()
        return {
            "name": p.name, "size": stat.st_size,
            "modified": stat.st_mtime, "is_dir": p.is_dir(),
        }
