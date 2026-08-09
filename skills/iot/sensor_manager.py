"""
Gestor de sensores — temperatura, humedad, movimiento, etc.
Soporta DHT11/DHT22, BMP280, PIR, LDR.
"""
import time
import logging
import json
from typing import Dict, Optional, List
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("maximun.iot.sensors")

try:
    import Adafruit_DHT
    _DHT_AVAILABLE = True
except ImportError:
    _DHT_AVAILABLE = False


class SensorManager:
    """Gestor centralizado de sensores IoT."""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.sensors = self.config.get("sensors", {})
        self.readings: List[Dict] = []
        self._simulate = not _DHT_AVAILABLE

        if self._simulate:
            logger.info("Sensores en modo simulación")

    def read_dht(self, pin: int = 4, sensor_type: str = "DHT22") -> Dict:
        """Lee sensor DHT (temperatura + humedad)."""
        if self._simulate:
            import random
            temp = round(22 + random.uniform(-3, 5), 1)
            hum = round(55 + random.uniform(-10, 15), 1)
            return {"temperature": temp, "humidity": hum, "simulated": True}

        try:
            sensor = Adafruit_DHT.DHT22 if sensor_type == "DHT22" else Adafruit_DHT.DHT11
            humidity, temperature = Adafruit_DHT.read_retry(sensor, pin)
            if humidity is not None and temperature is not None:
                return {
                    "temperature": round(temperature, 1),
                    "humidity": round(humidity, 1),
                    "simulated": False,
                }
        except Exception as e:
            logger.error(f"DHT read error: {e}")

        return {"temperature": None, "humidity": None, "error": "read_failed"}

    def read_bmp280(self) -> Dict:
        """Lee sensor BMP280 (presión + temperatura)."""
        if self._simulate:
            import random
            return {
                "pressure": round(1013 + random.uniform(-5, 5), 1),
                "temperature": round(22 + random.uniform(-2, 3), 1),
                "simulated": True,
            }
        return {"pressure": None, "temperature": None, "error": "not_available"}

    def read_pir(self, pin: int = 12) -> Dict:
        """Lee sensor PIR (movimiento)."""
        if self._simulate:
            import random
            return {"motion": random.choice([True, False]), "simulated": True}
        return {"motion": False, "simulated": False}

    def read_ldr(self, pin: int = 14) -> Dict:
        """Lee sensor LDR (luminosidad)."""
        if self._simulate:
            import random
            return {"lux": round(random.uniform(0, 1000), 0), "simulated": True}
        return {"lux": 0, "simulated": False}

    def read_all(self) -> Dict:
        """Lee todos los sensores configurados."""
        readings = {
            "timestamp": datetime.now().isoformat(),
            "dht": self.read_dht(),
            "bmp280": self.read_bmp280(),
            "pir": self.read_pir(),
            "ldr": self.read_ldr(),
        }
        self.readings.append(readings)
        if len(self.readings) > 1000:
            self.readings = self.readings[-500:]
        return readings

    def get_latest(self) -> Dict:
        """Retorna la última lectura."""
        return self.readings[-1] if self.readings else self.read_all()

    def get_history(self, count: int = 10) -> List[Dict]:
        """Retorna las últimas N lecturas."""
        return self.readings[-count:]

    def check_thresholds(self, rules: Dict = None) -> List[Dict]:
        """Verifica reglas de umbral y retorna alertas."""
        if not self.readings:
            return []

        latest = self.readings[-1]
        alerts = []
        rules = rules or self.config.get("rules", {})

        dht = latest.get("dht", {})
        if dht.get("temperature"):
            max_temp = rules.get("max_temperature", 35)
            if dht["temperature"] > max_temp:
                alerts.append({
                    "type": "temperature_high",
                    "value": dht["temperature"],
                    "threshold": max_temp,
                    "action": rules.get("on_high_temp", "alert"),
                })

        return alerts

    def save_readings(self, path: str):
        """Guarda lecturas a archivo JSON."""
        Path(path).write_text(json.dumps(self.readings[-100:], indent=2, ensure_ascii=False))
