"""
Memoria a largo plazo — conocimiento acumulado con SQLite.
Soporta decaimiento temporal y búsqueda semántica.
"""
import sqlite3
import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger("maximun.memory.long_term")


class LongTermMemory:
    """Almacén de conocimiento a largo plazo con prioridad y decaimiento."""

    def __init__(self, config: dict, project_root: str):
        self.config = config
        self.project_root = Path(project_root)
        db_path = self.project_root / config.get("memory", {}).get(
            "long_term", {}
        ).get("storage", "memory/long_term/knowledge.db")
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(db_path))
        self.decay_rate = config.get("memory", {}).get("long_term", {}).get("decay_rate", 0.01)
        self._init_db()

    def _init_db(self):
        """Inicializa las tablas de la base de datos."""
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                key TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                priority REAL DEFAULT 1.0,
                access_count INTEGER DEFAULT 0,
                last_accessed TEXT,
                created_at TEXT NOT NULL,
                embedding_id TEXT
            );
            
            CREATE INDEX IF NOT EXISTS idx_category ON knowledge(category);
            CREATE INDEX IF NOT EXISTS idx_key ON knowledge(key);
            CREATE INDEX IF NOT EXISTS idx_priority ON knowledge(priority DESC);
            
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT DEFAULT 'default',
                user_message TEXT NOT NULL,
                agent_response TEXT NOT NULL,
                model_used TEXT,
                task_level TEXT,
                confidence REAL,
                feedback TEXT,
                timestamp TEXT NOT NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_interactions_timestamp ON interactions(timestamp DESC);
        """)
        self.db.commit()

    def store(self, category: str, key: str, content: str, metadata: Optional[Dict] = None, embedding_id: Optional[str] = None) -> int:
        """Almacena conocimiento nuevo."""
        cursor = self.db.execute(
            """INSERT INTO knowledge (category, key, content, metadata, priority, last_accessed, created_at, embedding_id)
               VALUES (?, ?, ?, ?, 1.0, ?, ?, ?)""",
            (
                category,
                key,
                content,
                json.dumps(metadata or {}),
                datetime.now().isoformat(),
                datetime.now().isoformat(),
                embedding_id,
            ),
        )
        self.db.commit()
        logger.info(f"Stored knowledge: [{category}] {key}")
        return cursor.lastrowid

    def retrieve(self, category: Optional[str] = None, key: Optional[str] = None, limit: int = 10) -> List[Dict]:
        """Recupera conocimiento por categoría o clave."""
        query = "SELECT * FROM knowledge WHERE 1=1"
        params = []

        if category:
            query += " AND category = ?"
            params.append(category)
        if key:
            query += " AND key LIKE ?"
            params.append(f"%{key}%")

        query += " ORDER BY priority DESC, last_accessed DESC LIMIT ?"
        params.append(limit)

        rows = self.db.execute(query, params).fetchall()
        columns = [desc[0] for desc in self.db.execute("SELECT * FROM knowledge LIMIT 0").description]

        results = []
        for row in rows:
            entry = dict(zip(columns, row))
            entry["metadata"] = json.loads(entry.get("metadata", "{}"))
            
            # Update access count and timestamp
            self.db.execute(
                "UPDATE knowledge SET access_count = access_count + 1, last_accessed = ? WHERE id = ?",
                (datetime.now().isoformat(), entry["id"]),
            )
            results.append(entry)

        self.db.commit()
        return results

    def update_priority(self, knowledge_id: int, new_priority: float):
        """Actualiza la prioridad de un conocimiento."""
        self.db.execute(
            "UPDATE knowledge SET priority = ? WHERE id = ?",
            (new_priority, knowledge_id),
        )
        self.db.commit()

    def apply_decay(self):
        """Aplica decaimiento temporal a las prioridades."""
        self.db.execute(
            """UPDATE knowledge SET priority = priority * (1.0 - ?)
               WHERE julianday('now') - julianday(last_accessed) > 30""",
            (self.decay_rate,),
        )
        self.db.commit()
        logger.info("Applied memory decay")

    def store_interaction(self, user_message: str, agent_response: str, model_used: str = "", task_level: str = "", confidence: float = 0.0, user_id: str = "default"):
        """Almacena una interacción completa."""
        self.db.execute(
            """INSERT INTO interactions (user_id, user_message, agent_response, model_used, task_level, confidence, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, user_message, agent_response, model_used, task_level, confidence, datetime.now().isoformat()),
        )
        self.db.commit()

    def get_interactions(self, user_id: str = "default", limit: int = 20) -> List[Dict]:
        """Recupera interacciones recientes."""
        rows = self.db.execute(
            "SELECT * FROM interactions WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        columns = [desc[0] for desc in self.db.execute("SELECT * FROM interactions LIMIT 0").description]
        return [dict(zip(columns, row)) for row in rows]

    def search_knowledge(self, query: str, limit: int = 10) -> List[Dict]:
        """Búsqueda de texto en conocimiento."""
        rows = self.db.execute(
            "SELECT * FROM knowledge WHERE content LIKE ? OR key LIKE ? ORDER BY priority DESC LIMIT ?",
            (f"%{query}%", f"%{query}%", limit),
        ).fetchall()
        columns = [desc[0] for desc in self.db.execute("SELECT * FROM knowledge LIMIT 0").description]
        return [dict(zip(columns, row)) for row in rows]

    def get_stats(self) -> dict:
        """Estadísticas de memoria a largo plazo."""
        count = self.db.execute("SELECT COUNT(*) FROM knowledge").fetchone()[0]
        interactions = self.db.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]
        categories = self.db.execute("SELECT DISTINCT category FROM knowledge").fetchall()
        return {
            "total_knowledge": count,
            "total_interactions": interactions,
            "categories": [c[0] for c in categories],
        }

    def export_data(self, path: str):
        """Exporta todos los datos a JSON."""
        knowledge = self.db.execute("SELECT * FROM knowledge").fetchall()
        interactions = self.db.execute("SELECT * FROM interactions").fetchall()
        
        export = {
            "knowledge": knowledge,
            "interactions": interactions,
            "exported_at": datetime.now().isoformat(),
        }
        
        Path(path).write_text(json.dumps(export, indent=2, ensure_ascii=False))

    def close(self):
        """Cierra la conexión a la base de datos."""
        self.db.close()
