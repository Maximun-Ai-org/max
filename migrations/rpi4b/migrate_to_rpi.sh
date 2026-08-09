#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
#  Migración completa a Raspberry Pi 4B + openSUSE MicroOS
#  Incluye: SO, configuración, IoT, audio Jack, servicios 24/7
# ═══════════════════════════════════════════════════════════════════

set -e
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; }
info() { echo -e "${BLUE}[i]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_SRC="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Máximun Agent — Migración a Raspberry Pi 4B${NC}"
echo -e "${BLUE}  SO: openSUSE MicroOS (inmutable, 24/7)${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# ─── 1. Download openSUSE MicroOS Image ───────────────
info "Paso 1: Verificando openSUSE MicroOS para RPi4B..."

MICROOS_URL="https://download.opensuse.org/ports/aarch64/tumbleweed/images/openSUSE-MicroOS.aarch64-RaspberryPi4-Current.raw.xz"
MICROOS_IMG="$SCRIPT_DIR/opensuse/openSUSE-MicroOS-RPi4.raw.xz"

mkdir -p "$SCRIPT_DIR/opensuse"

if [ ! -f "$MICROOS_IMG" ]; then
    info "Descargando openSUSE MicroOS para RPi4B..."
    info "URL: $MICROOS_URL"
    info "Esto puede tardar 10-30 minutos..."
    
    curl -L --progress-bar -o "$MICROOS_IMG" "$MICROOS_URL" || {
        err "Error descargando MicroOS"
        warn "Descarga manualmente:"
        warn "  $MICROOS_URL"
        warn "  Coloca en: $MICROOS_IMG"
    }
fi

if [ -f "$MICROOS_IMG" ]; then
    SIZE=$(du -h "$MICROOS_IMG" | awk '{print $1}')
    log "MicroOS descargado: $SIZE"
fi

# ─── 2. Prepare SD Card Script ───────────────────────
info "Paso 2: Generando script de grabación de SD..."

cat > "$SCRIPT_DIR/opensuse/flash_sd.sh" << 'FLASHEOF'
#!/bin/bash
# Flash openSUSE MicroOS to SD Card for RPi4B
# ⚠ Esto borrará toda la SD

set -e
IMG="$(dirname "$0")/openSUSE-MicroOS-RPi4.raw.xz"

if [ ! -f "$IMG" ]; then
    echo "Error: Imagen no encontrada en $IMG"
    exit 1
fi

echo "╔══════════════════════════════════════╗"
echo "║  Flash openSUSE MicroOS to SD Card  ║"
echo "║  Target: Raspberry Pi 4B            ║"
echo "╚══════════════════════════════════════╝"
echo ""

# Detect SD card
echo "SD Cards disponibles:"
lsblk -d -o NAME,SIZE,MODEL | grep -E "mmcblk|sd[b-z]"
echo ""
read -p "Dispositivo SD (ej: /dev/mmcblk1): " SD_DEV

if [ ! -b "$SD_DEV" ]; then
    echo "Error: $SD_DEV no es un dispositivo válido"
    exit 1
fi

echo ""
echo "⚠️  Esto BORRARÁ TODO en $SD_DEV"
read -p "¿Confirmar? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Cancelado"
    exit 0
fi

echo ""
echo "Flashing..."
xzcat "$IMG" | sudo dd of="$SD_DEV" bs=4M status=progress conv=fsync
sync

echo ""
echo "✓ Flash completado"
echo ""
echo "Pasos siguientes:"
echo "  1. Insertar SD en RPi4B"
echo "  2. Conectar: Ethernet, Jack audio, disipador de aluminio"
echo "  3. Encender y esperar a que MicroOS arranque"
echo "  4. Conectar por SSH: ssh root@<ip-de-la-rpi>"
echo "  5. Ejecutar: bash /root/Máximun_proyect/migrations/rpi4b/opensuse/setup_rpi.sh"
FLASHEOF
chmod +x "$SCRIPT_DIR/opensuse/flash_sd.sh"

# ─── 3. RPi4B Setup Script (runs ON the RPi) ─────────
info "Paso 3: Generando script de configuración RPi4B..."

cat > "$SCRIPT_DIR/opensuse/setup_rpi.sh" << 'SETUPEOF'
#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
#  Configuración de Máximun Agent en RPi4B + openSUSE MicroOS
#  Ejecutar DESPUÉS de flashear la SD y arrancar
# ═══════════════════════════════════════════════════════════════════
set -e

echo "═══ Configurando Máximun en RPi4B ═══"

# ─── MicroOS is immutable (read-only) ─────────────────
# Use transactional-update for system packages
echo "Instalando dependencias del sistema..."
transactional-update pkg install -y \
    python312 python312-pip \
    gcc gcc-c++ cmake make \
    espeak-ng \
    alsa-utils jack \
    libasound2-dev \
    git wget curl \
    i2c-tools \
    python3-RPi.GPIO \
    python3-gpiozero

# ─── Python packages ──────────────────────────────────
echo "Instalando dependencias Python..."
pip3 install --break-system-packages \
    llama-cpp-python \
    sentence-transformers \
    chromadb \
    pyyaml rich click \
    aiohttp aiofiles \
    RPi.GPIO gpiozero

# ─── Audio Jack Configuration ─────────────────────────
echo "Configurando audio Jack..."
cat > /etc/asound.conf << 'ASOUND'
pcm.!default {
    type jack
    playback_ports {
        0 maximun:output_0
    }
    capture_ports {
        0 maximun:input_0
    }
}
ctl.!default {
    type jack
}
ASOUND

# Start Jack audio server
systemctl enable jackd || true
cat > /etc/systemd/system/jackd.service << 'JACKEOF'
[Unit]
Description=JACK Audio Server for Máximun
After=sound.target

[Service]
Type=simple
ExecStartPre=/usr/bin/jackd -R -d alsa -d hw:0 -r 48000 -p 1024 -n 2
ExecStart=/bin/sleep 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
JACKEOF

systemctl daemon-reload
systemctl enable jackd

# ─── I2C for sensors ──────────────────────────────────
echo "Habilitando I2C..."
echo "dtparam=i2c_arm=on" >> /boot/config.txt 2>/dev/null || true
modprobe i2c-dev 2>/dev/null || true

# ─── GPIO Permissions ─────────────────────────────────
echo "Configurando permisos GPIO..."
usermod -a -G gpio,input,audio root 2>/dev/null || true

# ─── Thermal management (disipador de aluminio) ───────
echo "Configurando gestión térmica..."
cat > /etc/systemd/system/thermal-monitor.service << 'THERMALEOF'
[Unit]
Description=Thermal Monitor for Máximun RPi4B
After=multi-user.target

[Service]
Type=simple
ExecStart=/usr/local/bin/thermal_monitor.sh
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
THERMALEOF

cat > /usr/local/bin/thermal_monitor.sh << 'THERMSHEOF'
#!/bin/bash
# Monitorea temperatura y ajusta rendimiento
while true; do
    TEMP=$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo "45000")
    TEMP_C=$((TEMP / 1000))
    
    if [ "$TEMP_C" -gt 75 ]; then
        echo "performance" > /sys/devices/system/cpu/cpufreq/policy0/scaling_governor 2>/dev/null || true
        echo "⚠ Temperatura alta: ${TEMP_C}°C"
    elif [ "$TEMP_C" -lt 50 ]; then
        echo "ondemand" > /sys/devices/system/cpu/cpufreq/policy0/scaling_governor 2>/dev/null || true
    fi
    
    sleep 30
done
THERMSHEOF
chmod +x /usr/local/bin/thermal_monitor.sh
systemctl enable thermal-monitor

# ─── Máximun Agent Service ───────────────────────────
echo "Creando servicio systemd del agente..."
cat > /etc/systemd/system/maximun-agent.service << 'AGENTEOF'
[Unit]
Description=Máximun Hermes Agent
After=network-online.target jackd.service
Wants=network-online.target
Requires=jackd.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/Máximun_proyect
ExecStart=/usr/bin/python3 /root/Máximun_proyect/maximun.py --chat
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
AGENTEOF

# ─── API Server Service ──────────────────────────────
cat > /etc/systemd/system/maximun-api.service << 'APIEOF'
[Unit]
Description=Máximun API Server
After=maximun-agent.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/Máximun_proyect
ExecStart=/usr/bin/python3 /root/Máximun_proyect/api/server.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
APIEOF

# ─── Home Automation Service ─────────────────────────
cat > /etc/systemd/system/maximun-domotica.service << 'DOMEOF'
[Unit]
Description=Máximun Home Automation
After=maximun-agent.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/Máximun_proyect
ExecStart=/usr/bin/python3 -c "
from skills.iot import GPIOController, SensorManager
from skills.domotica import HomeAutomation
gpio = GPIOController()
sensors = SensorManager()
auto = HomeAutomation(gpio, sensors)
auto.start()
"
Restart=always
RestartSec=15

[Install]
WantedBy=multi-user.target
DOMEOF

# ─── Enable all services ─────────────────────────────
echo "Habilitando servicios..."
systemctl daemon-reload
systemctl enable maximun-agent.service
systemctl enable maximun-api.service
systemctl enable maximun-domotica.service

echo ""
echo "═══════════════════════════════════════════════════"
echo "  ✓ Configuración RPi4B completada"
echo "═══════════════════════════════════════════════════"
echo ""
echo "Servicios:"
echo "  systemctl start jackd"
echo "  systemctl start maximun-agent"
echo "  systemctl start maximun-api"
echo "  systemctl start maximun-domotica"
echo ""
echo "Acceso:"
echo "  SSH: ssh root@$(hostname -I | awk '{print $1}')"
echo "  Web: http://$(hostname -I | awk '{print $1}'):8080"
echo "  Audio: Jack en puerto nativo"
SETUPEOF
chmod +x "$SCRIPT_DIR/opensuse/setup_rpi.sh"

# ─── 4. Sync project to SD ───────────────────────────
info "Paso 4: Preparando sincronización del proyecto..."

cat > "$SCRIPT_DIR/sync_to_rpi.sh" << 'SYNCEOF'
#!/bin/bash
# Sincroniza el proyecto completo al RPi4B
set -e

RPI_IP="${1:-192.168.1.100}"
RPI_USER="${2:-root}"
PROJECT_SRC="$(cd "$(dirname "$0")/../.." && pwd)"

echo "Sincronizando Máximun a RPi4B ($RPI_USER@$RPI_IP)..."

# Sync with rsync
rsync -avz --progress \
    --exclude='__pycache__' \
    --exclude='.pytest_cache' \
    --exclude='*.pyc' \
    --exclude='.venv' \
    --exclude='logs/*.log' \
    --exclude='data/cache/*' \
    "$PROJECT_SRC/" "$RPI_USER@$RPI_IP:/root/Máximun_proyect/"

echo "Sincronización completada"
echo ""
echo "En el RPi4B ejecuta:"
echo "  cd /root/Máximun_proyect && bash scripts/deploy.sh"
echo "  systemctl start maximun-agent"
SYNCEOF
chmod +x "$SCRIPT_DIR/sync_to_rpi.sh"

# ─── 5. Create complete archive ──────────────────────
info "Paso 5: Creando archivo de migración completa..."

ARCHIVE="$SCRIPT_DIR/máximun_rpi4b_migration.tar.gz"
tar -czf "$ARCHIVE" \
    -C "$SCRIPT_DIR/.." \
    --exclude='__pycache__' \
    --exclude='.pytest_cache' \
    --exclude='*.pyc' \
    .

ARCHIVE_SIZE=$(du -h "$ARCHIVE" | awk '{print $1}')
log "Archivo de migración: $ARCHIVE ($ARCHIVE_SIZE)"

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✓ MIGRACIÓN RPi4B LISTA${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo "Pasos para completar la migración:"
echo ""
echo "  1. Flashear MicroOS a la SD:"
echo "     bash $SCRIPT_DIR/opensuse/flash_sd.sh"
echo ""
echo "  2. Insertar SD en RPi4B y arrancar"
echo ""
echo "  3. Copiar el proyecto al RPi4B:"
echo "     bash $SCRIPT_DIR/sync_to_rpi.sh <ip-del-rpi>"
echo ""
echo "  4. Configurar el RPi4B:"
echo "     ssh root@<ip-del-rpi>"
echo "     bash /root/Máximun_proyect/migrations/rpi4b/opensuse/setup_rpi.sh"
echo ""
echo "  5. Iniciar servicios:"
echo "     systemctl start jackd maximun-agent maximun-api maximun-domotica"
echo ""
echo "  Hardware recomendado:"
echo "    - Raspberry Pi 4B (4GB+ RAM)"
echo "    - Disipador de aluminio pasivo"
echo "    - SD Card 32GB+ (clase A2)"
echo "    - Cable Ethernet (preferido sobre WiFi)"
echo "    - Altavoz/auriculares en Jack 3.5mm"
