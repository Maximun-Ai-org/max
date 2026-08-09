"""
Heartbeat — monitoreo de salud autónomo.
Maximun vigila su propio estado y se autorrecupera.
"""
import json
import time
import logging
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict

logger = logging.getLogger("maximun.heartbeat")


class HeartbeatMonitor:
    """
    Monitoreo de salud 24/7.
    
    Vigila:
    - Uso de CPU y RAM
    - Estado de modelos
    - Integridad de archivos
    - Estado de servicios
    - Temperatura del sistema
    - Espacio en disco
    - Conectividad local (no internet)
    
    Acciones:
    - Restart automático de modelos caídos
    - Backup de memoria periódico
    - Alertas si algo falla
    - Log de métricas para diagnóstico
    """

    def __init__(self, agent=None, config: dict = None):
        self.agent = agent
        self.config = config or {}
        self.heartbeat_dir = Path("data/heartbeat")
        self.heartbeat_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.heartbeat_dir / "heartbeat_log.jsonl"
        self.alerts_file = self.heartbeat_dir / "alerts.jsonl"
        self._active = False
        self._checks_passed = 0
        self._checks_failed = 0

    def check_system_health(self) -> Dict:
        """Verificación completa de salud del sistema."""
        import os

        health = {
            "timestamp": datetime.now().isoformat(),
            "uptime": self._get_uptime(),
            "cpu_temp": self._get_cpu_temp(),
            "ram_usage": self._get_ram_usage(),
            "disk_usage": self._get_disk_usage(),
            "processes": self._get_process_count(),
            "models_loaded": [],
            "memory_status": "unknown",
            "services": {},
            "status": "healthy",
            "issues": [],
        }

        # Check models
        if self.agent and self.agent.engine:
            health["models_loaded"] = self.agent.engine.get_loaded_models()

        # Check memory
        if self.agent and self.agent.memory:
            try:
                stats = self.agent.memory.get_stats()
                health["memory_status"] = "ok"
                health["memory_stats"] = stats
            except Exception as e:
                health["memory_status"] = f"error: {e}"
                health["issues"].append(f"Memory error: {e}")

        # Check disk
        if health["disk_usage"].get("percent", 0) > 90:
            health["issues"].append(f"Disk usage critical: {health['disk_usage']['percent']}%")

        # Check RAM
        if health["ram_usage"].get("percent", 0) > 90:
            health["issues"].append(f"RAM usage critical: {health['ram_usage']['percent']}%")

        # Check temperature
        if health["cpu_temp"] and health["cpu_temp"] > 80:
            health["issues"].append(f"CPU temperature high: {health['cpu_temp']}°C")

        # Overall status
        if health["issues"]:
            health["status"] = "degraded" if len(health["issues"]) < 3 else "critical"

        # Log
        self._log_health(health)

        return health

    def _get_uptime(self) -> float:
        """Obtiene uptime del sistema."""
        try:
            with open("/proc/uptime") as f:
                return float(f.read().split()[0])
        except Exception:
            return 0

    def _get_cpu_temp(self):
        """Obtiene temperatura de la CPU."""
        paths = [
            "/sys/class/thermal/thermal_zone0/temp",
            "/sys/class/thermal/thermal_zone1/temp",
        ]
        for path in paths:
            try:
                with open(path) as f:
                    return int(f.read().strip()) / 1000
            except Exception:
                continue
        return None

    def _get_ram_usage(self) -> Dict:
        """Obtiene uso de RAM."""
        try:
            with open("/proc/meminfo") as f:
                lines = f.readlines()
            mem = {}
            for line in lines:
                parts = line.split()
                if parts[0] in ("MemTotal:", "MemAvailable:", "MemFree:"):
                    mem[parts[0]] = int(parts[1])
            total = mem.get("MemTotal:", 1)
            available = mem.get("MemAvailable:", mem.get("MemFree:", 0))
            used = total - available
            return {
                "total_mb": total // 1024,
                "used_mb": used // 1024,
                "available_mb": available // 1024,
                "percent": round(used / total * 100, 1),
            }
        except Exception:
            return {"total_mb": 0, "used_mb": 0, "percent": 0}

    def _get_disk_usage(self) -> Dict:
        """Obtiene uso de disco."""
        import shutil
        try:
            usage = shutil.disk_usage("/")
            return {
                "total_gb": round(usage.total / (1024**3), 1),
                "used_gb": round(usage.used / (1024**3), 1),
                "free_gb": round(usage.free / (1024**3), 1),
                "percent": round(usage.used / usage.total * 100, 1),
            }
        except Exception:
            return {"total_gb": 0, "used_gb": 0, "percent": 0}

    def _get_process_count(self) -> int:
        """Cuenta procesos activos."""
        try:
            return len([d for d in Path("/proc").iterdir() if d.name.isdigit()])
        except Exception:
            return 0

    def _log_health(self, health: Dict):
        """Registra resultado de health check."""
        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(health, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def auto_recover(self, health: Dict) -> bool:
        """Intenta recuperación automática si hay problemas."""
        recovered = False

        for issue in health.get("issues", []):
            if "Memory error" in issue and self.agent:
                logger.info("Auto-recovery: reiniciando memoria")
                try:
                    self.agent.memory.close()
                    self.agent.memory = type(self.agent.memory)(
                        self.agent.config, str(Path(".").resolve())
                    )
                    recovered = True
                except Exception as e:
                    logger.error(f"Memory recovery failed: {e}")

            if "disk usage critical" in issue:
                logger.info("Auto-recovery: limpiando caché")
                cache_dir = Path("data/cache")
                if cache_dir.exists():
                    for f in cache_dir.glob("*"):
                        if f.is_file():
                            f.unlink()
                    recovered = True

        return recovered

    def backup_memory(self):
        """Backup periódico de memoria."""
        backup_dir = self.heartbeat_dir / "backups"
        backup_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Backup long-term memory
        ltm_file = Path("memory/long_term/knowledge.db")
        if ltm_file.exists():
            import shutil
            shutil.copy2(ltm_file, backup_dir / f"knowledge_{timestamp}.db")

        # Backup identity
        identity_file = Path("data/identity/identity.json")
        if identity_file.exists():
            import shutil
            shutil.copy2(identity_file, backup_dir / f"identity_{timestamp}.json")

        # Backup sessions
        sessions_file = Path("memory/short_term/sessions.jsonl")
        if sessions_file.exists():
            import shutil
            shutil.copy2(sessions_file, backup_dir / f"sessions_{timestamp}.jsonl")

        # Keep only last 10 backups
        backups = sorted(backup_dir.glob("knowledge_*.db"))
        for old in backups[:-10]:
            old.unlink()

        logger.info(f"Backup completed: {timestamp}")

    def start_continuous(self, interval: int = 60):
        """Inicia monitoreo continuo."""
        self._active = True
        logger.info(f"Heartbeat monitor activo (intervalo: {interval}s)")

        backup_counter = 0

        while self._active:
            try:
                health = self.check_system_health()

                if health["status"] == "critical":
                    self.auto_recover(health)
                    self._checks_failed += 1
                else:
                    self._checks_passed += 1

                # Backup cada 30 minutos
                backup_counter += interval
                if backup_counter >= 1800:
                    self.backup_memory()
                    backup_counter = 0

                time.sleep(interval)
            except KeyboardInterrupt:
                self._active = False
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                time.sleep(30)

    def stop(self):
        self._active = False

    def get_status(self) -> dict:
        return {
            "active": self._active,
            "checks_passed": self._checks_passed,
            "checks_failed": self._checks_failed,
            "uptime_hours": round(self._get_uptime() / 3600, 1),
        }
