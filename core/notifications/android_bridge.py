"""Puente a notificaciones Android — usa termux-notification si disponible."""
import subprocess, logging

logger = logging.getLogger("maximun.notifications")

class NotificationBridge:
    def __init__(self):
        self.available = self._check()

    def _check(self) -> bool:
        try:
            result = subprocess.run(
                ["which", "termux-notification"],
                capture_output=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def send(self, title: str, content: str, id: str = "maximun"):
        if not self.available:
            logger.debug(f"Notification (no termux): {title}: {content}")
            return False
        try:
            subprocess.run(
                ["termux-notification", "-t", title, "-c", content, "--id", id],
                capture_output=True, timeout=10
            )
            return True
        except Exception:
            return False

    def clear(self, id: str = "maximun"):
        if self.available:
            try:
                subprocess.run(
                    ["termux-notification-remove", id],
                    capture_output=True, timeout=5
                )
            except Exception:
                pass
