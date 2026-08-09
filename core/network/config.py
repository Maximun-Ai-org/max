"""Configuración de red — IP estática, proxy, DNS."""
import subprocess, json
from pathlib import Path
import logging

logger = logging.getLogger("maximun.network.config")

class NetworkConfig:
    def __init__(self, project_root: str = "."):
        self.config_file = Path(project_root) / "data" / "network_config.json"
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.config = self._load()

    def _load(self):
        if self.config_file.exists():
            return json.loads(self.config_file.read_text())
        return {"mode": "dhcp", "ip": "", "gateway": "", "dns": "8.8.8.8"}

    def _save(self):
        self.config_file.write_text(json.dumps(self.config, indent=2))

    def set_static(self, ip: str, gateway: str, dns: str = "8.8.8.8"):
        self.config.update({"mode": "static", "ip": ip, "gateway": gateway, "dns": dns})
        self._save()

    def get_status(self) -> dict:
        try:
            result = subprocess.run(["ip", "addr", "show"], capture_output=True, text=True, timeout=5)
            return {"interfaces": result.stdout[:500], "config": self.config}
        except Exception:
            return {"config": self.config}
