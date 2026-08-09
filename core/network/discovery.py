"""Descubrimiento de red local — encuentra dispositivos en la LAN."""
import socket, subprocess, json, os
from pathlib import Path
from typing import List, Dict
import logging

logger = logging.getLogger("maximun.network")

class NetworkDiscovery:
    def __init__(self, project_root: str = "."):
        self.root = Path(project_root)
        self.known_devices = self.root / "data" / "known_devices.json"
        self.devices = self._load()

    def _load(self):
        if self.known_devices.exists():
            return json.loads(self.known_devices.read_text())
        return []

    def _save(self):
        self.known_devices.write_text(json.dumps(self.devices, indent=2, ensure_ascii=False))

    def get_local_ip(self) -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def scan_network(self, subnet: str = None) -> List[Dict]:
        if not subnet:
            ip = self.get_local_ip()
            subnet = ".".join(ip.split(".")[:3])
        
        found = []
        # Quick ping sweep
        for i in range(1, 255):
            ip = f"{subnet}.{i}"
            try:
                result = subprocess.run(
                    ["ping", "-c", "1", "-W", "1", ip],
                    capture_output=True, timeout=2
                )
                if result.returncode == 0:
                    hostname = socket.getfqdn(ip) if ip != self.get_local_ip() else "localhost"
                    device = {"ip": ip, "hostname": hostname, "discovered": True}
                    found.append(device)
            except Exception:
                pass
        
        self.devices = found
        self._save()
        return found

    def register_device(self, ip: str, name: str, port: int = 8080):
        device = {"ip": ip, "name": name, "port": port, "registered": True}
        self.devices.append(device)
        self._save()

    def send_to_device(self, ip: str, message: str, port: int = 8080) -> Dict:
        import urllib.request
        try:
            data = json.dumps({"message": message}).encode()
            req = urllib.request.Request(
                f"http://{ip}:{port}/api/chat",
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read())
        except Exception as e:
            return {"error": str(e)}
