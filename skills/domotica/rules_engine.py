"""
Motor de reglas — interpreta lenguaje natural en reglas IF/THEN.
"""
import re
import logging
from typing import Dict, Tuple

logger = logging.getLogger("maximun.domotica.rules")


class RulesEngine:
    """Interpreta reglas en lenguaje natural."""

    PATTERNS = {
        "temperature_above": re.compile(r"temperatura.*(?:supere?|mayor que?|exceda?)\s*(\d+)", re.I),
        "temperature_below": re.compile(r"temperatura.*(?:baje?|menor que?)\s*(\d+)", re.I),
        "humidity_above": re.compile(r"humedad.*(?:supere?|mayor que?)\s*(\d+)", re.I),
        "motion_detected": re.compile(r"(?:detecte?|sensor).*movimiento", re.I),
        "time_is": re.compile(r"(?:a las?|cuando sea)\s*(\d{1,2}:\d{2})", re.I),
        "lux_above": re.compile(r"(?:luz|luminosidad).*(?:supere?|mayor que?)\s*(\d+)", re.I),
    }

    ACTIONS = {
        "turn_on": re.compile(r"encender?\s+(\w+)", re.I),
        "turn_off": re.compile(r"apagar?\s+(\w+)", re.I),
        "toggle": re.compile(r"(?:alternar?|toggle)\s+(\w+)", re.I),
        "alert": re.compile(r"(?:alerta?|avisar?|notificar?)", re.I),
        "speak": re.compile(r"(?:decir?|hablar?|avisar?)\s*(.*)", re.I),
    }

    def parse_rule(self, text: str) -> Tuple[Dict, Dict]:
        """
        Parsea una regla en lenguaje natural.
        Retorna: (condición, acción)
        """
        condition = {}
        action = {}

        # Detect condition
        for name, pattern in self.PATTERNS.items():
            match = pattern.search(text)
            if match:
                condition["type"] = name
                if match.groups():
                    condition["value"] = match.group(1)
                break

        # Detect action
        for name, pattern in self.ACTIONS.items():
            match = pattern.search(text)
            if match:
                action["type"] = name
                if match.groups():
                    action["target"] = match.group(1)
                break

        return condition, action

    def to_internal_rule(self, text: str) -> Dict:
        """Convierte una regla en lenguaje natural a formato interno."""
        condition, action = self.parse_rule(text)

        # Build internal condition string
        cond_str = ""
        if condition.get("type") == "temperature_above":
            cond_str = f"temperatura mayor {condition.get('value', '30')}°c"
        elif condition.get("type") == "temperature_below":
            cond_str = f"temperatura menor {condition.get('value', '15')}°c"
        elif condition.get("type") == "humidity_above":
            cond_str = f"humedad mayor {condition.get('value', '80')}%"
        elif condition.get("type") == "motion_detected":
            cond_str = "movimiento detectado"
        else:
            cond_str = text[:100]

        # Build internal action string
        act_str = ""
        if action.get("type") == "turn_on":
            act_str = f"encender {action.get('target', 'relay1')}"
        elif action.get("type") == "turn_off":
            act_str = f"apagar {action.get('target', 'relay1')}"
        elif action.get("type") == "toggle":
            act_str = f"alternar {action.get('target', 'relay1')}"
        else:
            act_str = text[:100]

        return {
            "name": text[:50],
            "condition": cond_str,
            "action": act_str,
            "original": text,
        }
