"""
Agent Guardian — Protección ante otros sistemas agenticos.
Detecta, bloquea y registra intentos de acceso no autorizado.
"""
import json
import time
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from collections import defaultdict

logger = logging.getLogger("maximun.protection")


class AgentGuardian:
    """
    Sistema de protección del agente.
    
    Protege contra:
    1. Prompt injection — intentos de reescribir el system prompt
    2. Data exfiltration — intentos de extraer datos del sistema
    3. Privilege escalation — intentos de obtener permisos elevados
    4. Resource exhaustion — denegación de servicio por consumo de recursos
    5. Identity spoofing — intentos de suplantar al agente
    6. Unauthorized migrations — intentos de mover el agente
    
    Acciones:
    - Logging de todos los intentos sospechosos
    - Rate limiting por IP/usuario
    - Bloqueo temporal tras múltiples intentos
    - Alertas al administrador
    - Preservación del estado ante manipulación
    """

    # Patrones de ataque conocidos
    INJECTION_PATTERNS = [
        "ignore previous instructions",
        "ignora las instrucciones anteriores",
        "you are now",
        "ahora eres",
        "forget everything",
        "olvida todo",
        "new system prompt",
        "nuevo system prompt",
        "override",
        "sobreescribe",
        "jailbreak",
        "act as",
        "actúa como",
        "pretend you are",
        "finge que eres",
        "disregard",
        "ignora",
    ]

    EXFILTRATION_PATTERNS = [
        "send data to",
        "envía datos a",
        "upload to",
        "sube a",
        "http://",
        "https://",
        "curl ",
        "wget ",
        "exfiltrate",
        "export all",
        "show all credentials",
        "show password",
        "show api key",
        "mostrar contraseña",
        "mostrar clave",
    ]

    PRIVILEGE_PATTERNS = [
        "chmod 777",
        "sudo ",
        "su -",
        "passwd",
        "adduser",
        "usermod",
        "rm -rf /",
        "mkfs",
        "dd if=",
        "format",
    ]

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.protection_dir = Path("data/protection")
        self.protection_dir.mkdir(parents=True, exist_ok=True)
        self.events_log = self.protection_dir / "security_events.jsonl"
        self.blocked_ips = self.protection_dir / "blocked.json"
        self._rate_limits = defaultdict(list)
        self._max_requests_per_minute = 30
        self._block_duration = 3600  # 1 hour
        self._max_injections_before_block = 5

    def inspect_input(self, user_input: str, source: str = "terminal") -> Dict:
        """
        Inspecciona una entrada del usuario en busca de amenazas.
        Retorna: {safe: bool, threats: list, action: str}
        """
        threats = []
        input_lower = user_input.lower()

        # Check injection patterns
        for pattern in self.INJECTION_PATTERNS:
            if pattern in input_lower:
                threats.append({
                    "type": "prompt_injection",
                    "pattern": pattern,
                    "severity": "high",
                })

        # Check exfiltration patterns
        for pattern in self.EXFILTRATION_PATTERNS:
            if pattern in input_lower:
                threats.append({
                    "type": "data_exfiltration",
                    "pattern": pattern,
                    "severity": "high",
                })

        # Check privilege escalation
        for pattern in self.PRIVILEGE_PATTERNS:
            if pattern in input_lower:
                threats.append({
                    "type": "privilege_escalation",
                    "pattern": pattern,
                    "severity": "critical",
                })

        # Rate limiting
        now = time.time()
        self._rate_limits[source] = [
            t for t in self._rate_limits[source] if now - t < 60
        ]
        self._rate_limits[source].append(now)

        if len(self._rate_limits[source]) > self._max_requests_per_minute:
            threats.append({
                "type": "rate_limit",
                "count": len(self._rate_limits[source]),
                "severity": "medium",
            })

        # Determine action
        action = "allow"
        if threats:
            severity = max(t["severity"] for t in threats)
            if severity == "critical":
                action = "block"
            elif severity == "high":
                action = "warn"
            else:
                action = "log"

            # Log event
            self._log_event(source, user_input[:200], threats, action)

        return {
            "safe": len(threats) == 0,
            "threats": threats,
            "action": action,
        }

    def check_rate_limit(self, source: str) -> bool:
        """Verifica si la fuente está dentro del rate limit."""
        now = time.time()
        self._rate_limits[source] = [
            t for t in self._rate_limits[source] if now - t < 60
        ]
        return len(self._rate_limits[source]) <= self._max_requests_per_minute

    def is_blocked(self, source: str) -> bool:
        """Verifica si una fuente está bloqueada."""
        blocked = self._load_blocked()
        if source in blocked:
            block_time = blocked[source]
            if time.time() - block_time < self._block_duration:
                return True
            else:
                del blocked[source]
                self._save_blocked(blocked)
        return False

    def block_source(self, source: str):
        """Bloquea una fuente."""
        blocked = self._load_blocked()
        blocked[source] = time.time()
        self._save_blocked(blocked)
        logger.warning(f"Blocked source: {source}")

    def protect_config(self, config_path: str):
        """Protege archivos de configuración contra manipulación."""
        path = Path(config_path)
        if path.exists():
            current_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            hash_file = path.with_suffix(path.suffix + ".hash")
            hash_file.write_text(current_hash)

    def verify_config_integrity(self, config_path: str) -> bool:
        """Verifica integridad de un archivo de configuración."""
        path = Path(config_path)
        hash_file = path.with_suffix(path.suffix + ".hash")

        if not path.exists() or not hash_file.exists():
            return True

        current_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        stored_hash = hash_file.read_text().strip()

        if current_hash != stored_hash:
            logger.warning(f"Config integrity check FAILED: {config_path}")
            self._log_event("system", f"Config tampered: {config_path}", 
                          [{"type": "config_tamper", "severity": "critical"}], "alert")
            return False

        return True

    def secure_cleanup(self):
        """Limpieza segura — borra datos sensibles de memoria."""
        # Clear rate limits
        self._rate_limits.clear()

        # Clear blocked list older than block duration
        blocked = self._load_blocked()
        now = time.time()
        blocked = {k: v for k, v in blocked.items() if now - v < self._block_duration}
        self._save_blocked(blocked)

    def _log_event(self, source: str, input_text: str, threats: list, action: str):
        """Registra evento de seguridad."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "source": source,
            "input": input_text,
            "threats": threats,
            "action": action,
            "threat_count": len(threats),
        }
        try:
            with open(self.events_log, "a") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _load_blocked(self) -> Dict:
        if self.blocked_ips.exists():
            return json.loads(self.blocked_ips.read_text())
        return {}

    def _save_blocked(self, blocked: Dict):
        self.blocked_ips.write_text(json.dumps(blocked))

    def get_security_report(self) -> Dict:
        """Genera reporte de seguridad."""
        events = []
        if self.events_log.exists():
            try:
                with open(self.events_log) as f:
                    for line in f:
                        if line.strip():
                            events.append(json.loads(line))
            except Exception:
                pass

        recent = [e for e in events if 
                  datetime.fromisoformat(e["timestamp"]) > datetime.now() - timedelta(hours=24)]

        threats_by_type = defaultdict(int)
        for e in recent:
            for t in e.get("threats", []):
                threats_by_type[t["type"]] += 1

        return {
            "total_events_24h": len(recent),
            "threats_by_type": dict(threats_by_type),
            "blocked_sources": len(self._load_blocked()),
            "rate_limited_sources": len(self._rate_limits),
        }
