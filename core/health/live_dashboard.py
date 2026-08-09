"""Dashboard de salud en vivo — métricas del sistema."""
import time, json, os
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger("maximun.health")

class LiveDashboard:
    def __init__(self, project_root: str = "."):
        self.root = Path(project_root)
        self.metrics_file = self.root / "data" / "health_metrics.jsonl"

    def collect_metrics(self) -> dict:
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "uptime": self._get_uptime(),
            "ram": self._get_ram(),
            "disk": self._get_disk(),
            "cpu_temp": self._get_temp(),
            "load_avg": self._get_load(),
        }
        
        # Append to log
        with open(self.metrics_file, "a") as f:
            f.write(json.dumps(metrics) + "\n")
        
        return metrics

    def _get_uptime(self):
        try:
            with open("/proc/uptime") as f:
                return float(f.read().split()[0])
        except: return 0

    def _get_ram(self):
        try:
            with open("/proc/meminfo") as f:
                lines = f.readlines()
            mem = {}
            for l in lines:
                parts = l.split()
                if parts[0] in ("MemTotal:", "MemAvailable:"):
                    mem[parts[0]] = int(parts[1])
            total = mem.get("MemTotal:", 1)
            avail = mem.get("MemAvailable:", 0)
            return {"total_mb": total//1024, "used_mb": (total-avail)//1024, "percent": round((total-avail)/total*100, 1)}
        except: return {"total_mb": 0, "used_mb": 0, "percent": 0}

    def _get_disk(self):
        try:
            st = os.statvfs("/")
            total = st.f_blocks * st.f_frsize
            free = st.f_bavail * st.f_frsize
            used = total - free
            return {"total_gb": round(total/1073741824, 1), "used_gb": round(used/1073741824, 1), "percent": round(used/total*100, 1)}
        except: return {"total_gb": 0, "used_gb": 0, "percent": 0}

    def _get_temp(self):
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                return int(f.read().strip()) / 1000
        except: return None

    def _get_load(self):
        try:
            with open("/proc/loadavg") as f:
                return f.read().strip().split()[:3]
        except: return []

    def get_recent_metrics(self, count: int = 20) -> list:
        if not self.metrics_file.exists():
            return []
        lines = self.metrics_file.read_text().strip().split("\n")
        return [json.loads(l) for l in lines[-count:]]

    def generate_report(self) -> str:
        m = self.collect_metrics()
        report = f"""═══ SALUD DEL SISTEMA ═══
Hora: {m['timestamp']}
Uptime: {m['uptime']/3600:.1f} horas
RAM: {m['ram']['used_mb']}/{m['ram']['total_mb']} MB ({m['ram']['percent']}%)
Disco: {m['disk']['used_gb']}/{m['disk']['total_gb']} GB ({m['disk']['percent']}%)"""
        if m['cpu_temp']:
            report += f"\nTemp CPU: {m['cpu_temp']:.1f}°C"
        report += f"\nLoad: {' '.join(m['load_avg'])}"
        return report
