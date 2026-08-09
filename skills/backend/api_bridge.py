"""
API Bridge — Puente entre agentes externos y el sistema local.
Permite que otros dispositivos se comuniquen con Máximun.
"""
import json
import logging
import subprocess
from typing import Dict, Optional

logger = logging.getLogger("maximun.bridge")


class APIBridge:
    """Puente de comunicación multi-dispositivo."""

    def __init__(self, config: dict):
        self.config = config
        self.endpoints = config.get("bridge", {}).get("endpoints", {})

    def send_to_device(self, device: str, message: str) -> Dict:
        """Envía un mensaje a otro dispositivo en la red."""
        endpoint = self.endpoints.get(device)
        if not endpoint:
            return {"error": f"Device {device} not configured"}

        try:
            import urllib.request
            data = json.dumps({"message": message}).encode()
            req = urllib.request.Request(
                endpoint,
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except Exception as e:
            return {"error": str(e)}

    def broadcast(self, message: str) -> Dict:
        """Envía un mensaje a todos los dispositivos configurados."""
        results = {}
        for device in self.endpoints:
            results[device] = self.send_to_device(device, message)
        return results

    def register_device(self, name: str, endpoint: str):
        """Registra un nuevo dispositivo."""
        self.endpoints[name] = endpoint
        logger.info(f"Device registered: {name} -> {endpoint}")
