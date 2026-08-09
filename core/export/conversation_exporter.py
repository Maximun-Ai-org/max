"""Export de conversaciones — JSON, Markdown, TXT."""
import json
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger("maximun.export")

class ConversationExporter:
    def __init__(self, project_root: str = "."):
        self.export_dir = Path(project_root) / "data" / "exports"
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export_session(self, messages: list, format: str = "markdown") -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format == "markdown":
            path = self.export_dir / f"session_{ts}.md"
            content = f"# Conversación — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            for msg in messages:
                role = "👤 Usuario" if msg.get("role") == "user" else "🤖 Máximun"
                content += f"### {role}\n{msg.get('content', '')}\n\n"
            path.write_text(content)
        elif format == "json":
            path = self.export_dir / f"session_{ts}.json"
            path.write_text(json.dumps(messages, indent=2, ensure_ascii=False))
        else:  # txt
            path = self.export_dir / f"session_{ts}.txt"
            content = ""
            for msg in messages:
                role = "User" if msg.get("role") == "user" else "Maximun"
                content += f"[{role}]: {msg.get('content', '')}\n\n"
            path.write_text(content)
        
        return str(path)

    def export_all_knowledge(self) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.export_dir / f"knowledge_export_{ts}.json"
        # Would export from SQLite long-term memory
        return str(path)

    def list_exports(self) -> list:
        return [f.name for f in self.export_dir.glob("*") if f.is_file()]
