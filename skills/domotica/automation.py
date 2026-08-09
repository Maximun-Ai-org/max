"""
Automatización del hogar — orquesta sensores + actuadores.
Reglas en lenguaje natural → ejecución en GPIO.
"""
import logging
import time
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger("maximun.domotica")


class HomeAutomation:
    """
    Motor de automatización domótica.
    
    Soporta:
    - Reglas IF/THEN simples
    - Temporizadores
    - Horarios (amanecer/atardecer)
    - Modos (noche, ausente,经济)
    - Respuesta a eventos de sensores
    """

    def __init__(self, gpio_controller=None, sensor_manager=None):
        self.gpio = gpio_controller
        self.sensors = sensor_manager
        self.rules: List[Dict] = []
        self.schedules: List[Dict] = []
        self.modes = {
            "home": {"description": "Modo normal"},
            "away": {"description": "Ausente"},
            "night": {"description": "Modo noche"},
            "eco": {"description": "Modo económico"},
        }
        self.current_mode = "home"
        self._active = False

    def add_rule(self, name: str, condition: str, action: str, enabled: bool = True):
        """Agrega una regla de automatización."""
        rule = {
            "name": name,
            "condition": condition,
            "action": action,
            "enabled": enabled,
            "created_at": datetime.now().isoformat(),
            "last_triggered": None,
            "trigger_count": 0,
        }
        self.rules.append(rule)
        logger.info(f"Rule added: {name}")

    def add_schedule(self, name: str, time_str: str, action: str, days: str = "daily"):
        """Agrega un temporizado."""
        schedule = {
            "name": name,
            "time": time_str,
            "action": action,
            "days": days,
            "enabled": True,
        }
        self.schedules.append(schedule)
        logger.info(f"Schedule added: {name} at {time_str}")

    def set_mode(self, mode: str):
        """Cambia el modo de automatización."""
        if mode in self.modes:
            self.current_mode = mode
            logger.info(f"Mode changed to: {mode}")
            self._apply_mode_rules()

    def _apply_mode_rules(self):
        """Aplica reglas del modo actual."""
        if self.current_mode == "night":
            # Apagar luces, activar sensor de movimiento
            if self.gpio:
                self.gpio.set_pin("led1", False)
                self.gpio.set_pin("led2", False)
        elif self.current_mode == "away":
            # Apagar todo, activar alarma
            if self.gpio:
                for pin in ["relay1", "relay2", "relay3", "relay4"]:
                    self.gpio.set_pin(pin, False)
        elif self.current_mode == "eco":
            # Reducir consumo
            if self.gpio:
                self.gpio.set_pin("relay3", False)
                self.gpio.set_pin("relay4", False)

    def evaluate_rules(self) -> List[str]:
        """Evalúa todas las reglas activas y retorna acciones tomadas."""
        if not self.sensors or not self.gpio:
            return []

        actions_taken = []
        readings = self.sensors.read_all()

        for rule in self.rules:
            if not rule["enabled"]:
                continue

            if self._check_condition(rule["condition"], readings):
                self._execute_action(rule["action"])
                rule["last_triggered"] = datetime.now().isoformat()
                rule["trigger_count"] += 1
                actions_taken.append(f"Executed: {rule['name']}")

        return actions_taken

    def _check_condition(self, condition: str, readings: Dict) -> bool:
        """Evalúa una condición contra las lecturas de sensores."""
        cond = condition.lower()
        dht = readings.get("dht", {})

        if "temperatura" in cond and "mayor" in cond:
            try:
                threshold = float(cond.split("mayor")[1].strip().replace("°c", "").strip())
                return dht.get("temperature", 0) > threshold
            except (ValueError, IndexError):
                pass

        if "temperatura" in cond and "menor" in cond:
            try:
                threshold = float(cond.split("menor")[1].strip().replace("°c", "").strip())
                return dht.get("temperature", 999) < threshold
            except (ValueError, IndexError):
                pass

        if "humedad" in cond and "mayor" in cond:
            try:
                threshold = float(cond.split("mayor")[1].strip().replace("%", "").strip())
                return dht.get("humidity", 0) > threshold
            except (ValueError, IndexError):
                pass

        if "movimiento" in cond:
            pir = readings.get("pir", {})
            return pir.get("motion", False)

        if "luz" in cond or "luminosidad" in cond:
            ldr = readings.get("ldr", {})
            return ldr.get("lux", 0) > 500

        return False

    def _execute_action(self, action: str):
        """Ejecuta una acción en los dispositivos."""
        act = action.lower()

        if not self.gpio:
            return

        if "encender" in act:
            for pin in ["relay1", "relay2", "relay3", "relay4", "led1", "led2"]:
                if pin in act:
                    self.gpio.set_pin(pin, True)
                    return
            self.gpio.set_pin("relay1", True)

        if "apagar" in act:
            for pin in ["relay1", "relay2", "relay3", "relay4", "led1", "led2"]:
                if pin in act:
                    self.gpio.set_pin(pin, False)
                    return
            self.gpio.set_pin("relay1", False)

        if "alternar" in act or "toggle" in act:
            for pin in ["relay1", "relay2", "relay3", "relay4"]:
                if pin in act:
                    self.gpio.toggle_pin(pin)
                    return

    def check_schedules(self) -> List[str]:
        """Verifica temporizados contra la hora actual."""
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        actions = []

        for schedule in self.schedules:
            if not schedule["enabled"]:
                continue
            if schedule["time"] == current_time:
                self._execute_action(schedule["action"])
                actions.append(f"Scheduled: {schedule['name']}")

        return actions

    def start(self):
        """Inicia el bucle de automatización."""
        self._active = True
        logger.info("Home automation started")

        while self._active:
            try:
                self.evaluate_rules()
                self.check_schedules()
                time.sleep(10)
            except KeyboardInterrupt:
                self.stop()
            except Exception as e:
                logger.error(f"Automation error: {e}")
                time.sleep(30)

    def stop(self):
        self._active = False
        logger.info("Home automation stopped")

    def get_rules(self) -> List[Dict]:
        return self.rules

    def get_status(self) -> dict:
        return {
            "mode": self.current_mode,
            "active": self._active,
            "rules_count": len(self.rules),
            "schedules_count": len(self.schedules),
            "rules": self.rules,
        }
