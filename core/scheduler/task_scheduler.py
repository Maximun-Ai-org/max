"""Scheduler de tareas interno — funciona sin cron del sistema."""
import time, json, threading
from pathlib import Path
from datetime import datetime, timedelta
import logging

logger = logging.getLogger("maximun.scheduler")

class TaskScheduler:
    def __init__(self, project_root: str):
        self.root = Path(project_root)
        self.tasks_file = self.root / "data" / "scheduled_tasks.json"
        self.tasks = self._load()
        self._active = False
        self._callbacks = {}

    def _load(self):
        if self.tasks_file.exists():
            return json.loads(self.tasks_file.read_text())
        return []

    def _save(self):
        self.tasks_file.write_text(json.dumps(self.tasks, indent=2, ensure_ascii=False))

    def add_task(self, name: str, action: str, interval_seconds: int = 3600, once: bool = False):
        task = {
            "name": name, "action": action,
            "interval": interval_seconds, "once": once,
            "enabled": True, "last_run": None,
            "created": datetime.now().isoformat(),
        }
        self.tasks.append(task)
        self._save()
        logger.info(f"Task scheduled: {name} (every {interval_seconds}s)")

    def register_callback(self, action_name: str, callback):
        self._callbacks[action_name] = callback

    def start(self):
        self._active = True
        while self._active:
            now = time.time()
            for task in self.tasks:
                if not task["enabled"]:
                    continue
                last = task.get("last_run")
                if last is None or (now - last) >= task["interval"]:
                    self._execute(task)
                    task["last_run"] = now
                    if task.get("once"):
                        task["enabled"] = False
            self._save()
            time.sleep(10)

    def _execute(self, task):
        action = task["action"]
        logger.info(f"Executing: {task['name']}")
        if action in self._callbacks:
            try:
                self._callbacks[action]()
            except Exception as e:
                logger.error(f"Task error: {e}")

    def stop(self):
        self._active = False

    def get_tasks(self):
        return self.tasks
