#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
#  Máximun Agent — Daemon Autónomo
#  Se ejecuta 24/7 sin intervención humana
#  Auto-monitoreo, auto-recuperación, backup
# ═══════════════════════════════════════════════════════════════════

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"
PID_FILE="$PROJECT_DIR/data/maximun.pid"
LOCK_FILE="$PROJECT_DIR/data/maximun.lock"

mkdir -p "$LOG_DIR" "$PROJECT_DIR/data"

# ─── Preventar múltiples instancias ──────────────────
if [ -f "$LOCK_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE" 2>/dev/null)
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        echo "Máximun ya está ejecutándose (PID: $OLD_PID)"
        exit 1
    fi
    rm -f "$LOCK_FILE" "$PID_FILE"
fi

echo $$ > "$PID_FILE"
echo "running" > "$LOCK_FILE"

cleanup() {
    echo "Deteniendo Máximun..."
    rm -f "$LOCK_FILE" "$PID_FILE"
    exit 0
}
trap cleanup SIGTERM SIGINT

# ─── Start services ──────────────────────────────────
echo "═══ Máximun Daemon Autónomo ═══"
echo "PID: $$"
echo "Directorio: $PROJECT_DIR"
echo ""

cd "$PROJECT_DIR"

# Start heartbeat monitor in background
echo "Iniciando heartbeat monitor..."
python3 -c "
import sys
sys.path.insert(0, '.')
from core.communication.heartbeat import HeartbeatMonitor
monitor = HeartbeatMonitor()
monitor.start_continuous(interval=60)
" >> "$LOG_DIR/heartbeat.log" 2>&1 &

# Start file listener for communication
echo "Iniciando file listener..."
python3 -c "
import sys
sys.path.insert(0, '.')
from core.communication.local_channel import LocalChannel
channel = LocalChannel()
channel.file_listener(poll_interval=2)
" >> "$LOG_DIR/file_listener.log" 2>&1 &

# Start API server
echo "Iniciando API server..."
python3 api/server.py >> "$LOG_DIR/api.log" 2>&1 &

echo ""
echo "Todos los servicios iniciados"
echo "Logs en: $LOG_DIR"
echo ""

# ─── Watchdog loop ────────────────────────────────────
while true; do
    sleep 300  # Check every 5 minutes
    
    # Verify Python processes are alive
    if ! pgrep -f "HeartbeatMonitor" > /dev/null 2>&1; then
        echo "[$(date)] Heartbeat died, restarting..."
        python3 -c "
import sys; sys.path.insert(0, '.')
from core.communication.heartbeat import HeartbeatMonitor
HeartbeatMonitor().start_continuous(60)
" >> "$LOG_DIR/heartbeat.log" 2>&1 &
    fi
    
    # Verify API server
    if ! pgrep -f "api/server.py" > /dev/null 2>&1; then
        echo "[$(date)] API server died, restarting..."
        python3 api/server.py >> "$LOG_DIR/api.log" 2>&1 &
    fi
    
    # Disk space check
    DISK_USE=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
    if [ "$DISK_USE" -gt 90 ]; then
        echo "[$(date)] WARNING: Disk usage at ${DISK_USE}%"
        find "$LOG_DIR" -name "*.log" -size +10M -exec truncate -s 1M {} \;
    fi
done
