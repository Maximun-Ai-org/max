"""
Controlador GPIO — gestiona pines de entrada/salida.
Soporta RPi4B (RPi.GPIO / gpiozero) y Arduino (serial).
"""
import logging
import json
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger("maximun.iot.gpio")

# Try importing GPIO libraries
_RPI_GPIO = False
_GPIOZERO = False
try:
    import RPi.GPIO as GPIO
    _RPI_GPIO = True
except (ImportError, RuntimeError):
    pass
try:
    import gpiozero
    _GPIOZERO = True
except ImportError:
    pass


class GPIOController:
    """
    Controlador de GPIO multi-plataforma.
    - RPi4B: RPi.GPIO / gpiozero
    - Simulación: cuando no hay hardware real
    """

    # Mapeo de pines estándar para RPi4B
    PIN_MAP = {
        "relay1": 17,
        "relay2": 27,
        "relay3": 22,
        "relay4": 23,
        "led1": 5,
        "led2": 6,
        "button1": 12,
        "button2": 16,
        "sensor_data": 4,
        "sensor_clk": 14,
    }

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.pin_config = {**self.PIN_MAP, **self.config.get("pins", {})}
        self.states = {pin: False for pin in self.pin_config.values()}
        self.is_real_hardware = _RPI_GPIO or _GPIOZERO
        self._initialized = False

        if self.is_real_hardware:
            self._init_real()
        else:
            logger.info("GPIO: Modo simulación (sin hardware real)")

    def _init_real(self):
        """Inicializa GPIO real."""
        if _RPI_GPIO:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            for name, pin in self.pin_config.items():
                GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
            self._initialized = True
            logger.info("GPIO real inicializado (RPi.GPIO)")

    def set_pin(self, pin_name: str, state: bool) -> bool:
        """Enciende/apaga un pin."""
        pin = self.pin_config.get(pin_name)
        if pin is None:
            logger.warning(f"Pin no encontrado: {pin_name}")
            return False

        if self.is_real_hardware and _RPI_GPIO:
            try:
                GPIO.output(pin, GPIO.HIGH if state else GPIO.LOW)
                self.states[pin] = state
                logger.info(f"GPIO {pin_name} (pin {pin}) -> {'ON' if state else 'OFF'}")
                return True
            except Exception as e:
                logger.error(f"GPIO error: {e}")
                return False
        else:
            self.states[pin] = state
            logger.info(f"GPIO simulado {pin_name} -> {'ON' if state else 'OFF'}")
            return True

    def get_pin(self, pin_name: str) -> bool:
        """Lee el estado de un pin."""
        pin = self.pin_config.get(pin_name)
        if pin is None:
            return False

        if self.is_real_hardware and _RPI_GPIO:
            try:
                return GPIO.input(pin) == GPIO.HIGH
            except Exception:
                return False
        return self.states.get(pin, False)

    def toggle_pin(self, pin_name: str) -> bool:
        """Alterna el estado de un pin."""
        current = self.get_pin(pin_name)
        return self.set_pin(pin_name, not current)

    def get_all_states(self) -> Dict[str, bool]:
        """Retorna el estado de todos los pines."""
        return {
            name: self.get_pin(name)
            for name in self.pin_config
        }

    def cleanup(self):
        """Limpia GPIO al cerrar."""
        if self.is_real_hardware and _RPI_GPIO:
            GPIO.cleanup()
            logger.info("GPIO cleanup completado")

    def get_status(self) -> dict:
        return {
            "hardware": self.is_real_hardware,
            "pins": len(self.pin_config),
            "states": self.get_all_states(),
        }
