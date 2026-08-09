#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
#  Migración completa a SD Card — Máximun Agent
#  Migra el proyecto, modelos, configuración y permisos
# ═══════════════════════════════════════════════════════════════════

set -e
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; }
info() { echo -e "${BLUE}[i]${NC} $1"; }

# ─── Detectar SD Card ──────────────────────────────────
detect_sd() {
    for dev in /dev/mmcblk1 /dev/mmcblk0 /dev/sdb /dev/sdc; do
        if [ -b "$dev" ]; then
            SD_DEV="$dev"
            SD_MOUNT="/mnt/sd_migration"
            return 0
        fi
    done
    # Check if already mounted
    for mount_point in /mnt/sd /media/sd /storage; do
        if mountpoint -q "$mount_point" 2>/dev/null; then
            SD_DEV=""
            SD_MOUNT="$mount_point"
            return 0
        fi
    done
    return 1
}

# ─── Main ──────────────────────────────────────────────
PROJECT_SRC="$(cd "$(dirname "$0")/../.." && pwd)"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Máximun Agent — Migración a SD Card${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo ""

# Detect SD
info "Detectando SD Card..."
if detect_sd; then
    log "SD detectada: ${SD_DEV:-'montada en'} -> $SD_MOUNT"
else
    warn "No se detectó SD Card"
    warn "Ingresa la ruta de destino manualmente:"
    read -p "Ruta destino: " SD_MOUNT
    mkdir -p "$SD_MOUNT"
fi

# Check space
info "Verificando espacio..."
SD_TOTAL=$(df -B1 "$SD_MOUNT" 2>/dev/null | tail -1 | awk '{print $2}' || echo "0")
PROJECT_SIZE=$(du -sb "$PROJECT_SRC" 2>/dev/null | awk '{print $1}' || echo "0")

if [ "$SD_TOTAL" -gt 0 ] && [ "$PROJECT_SIZE" -gt 0 ]; then
    SD_AVAIL_HR=$(df -h "$SD_MOUNT" 2>/dev/null | tail -1 | awk '{print $4}')
    PROJECT_HR=$(du -sh "$PROJECT_SRC" 2>/dev/null | awk '{print $1}')
    info "Proyecto: $PROJECT_HR | SD disponible: $SD_AVAIL_HR"
fi

# ─── Create destination ────────────────────────────────
DEST="$SD_MOUNT/Máximun_proyect"
info "Creando estructura en destino..."
mkdir -p "$DEST"

# ─── Sync project ──────────────────────────────────────
info "Sincronizando proyecto..."

# Sync code (exclude heavy/temp files)
rsync -av --progress \
    --exclude='__pycache__' \
    --exclude='.pytest_cache' \
    --exclude='*.pyc' \
    --exclude='.venv' \
    --exclude='logs/*.log' \
    --exclude='data/cache/*' \
    --exclude='memory/vector_store/chroma/*' \
    "$PROJECT_SRC/" "$DEST/" 2>&1 | tail -5

# ─── Sync models (critical!) ──────────────────────────
info "Sincronizando modelos (puede tardar)..."
mkdir -p "$DEST/models/primary"
rsync -av --progress "$PROJECT_SRC/models/primary/" "$DEST/models/primary/"

# ─── Set permissions ──────────────────────────────────
info "Configurando permisos..."
chmod -R 755 "$DEST"
chmod +x "$DEST/scripts/"*.sh
chmod +x "$DEST/migrations/"*/*.sh 2>/dev/null || true
chmod +x "$DEST/maximun.py"

# Create admin group if needed
groupadd -f maximun_admin
chown -R root:maximun_admin "$DEST"

# ─── Generate migration marker ─────────────────────────
cat > "$DEST/.migration_info" << EOF
source: $(hostname)
source_path: $PROJECT_SRC
migrated_at: $(date -Iseconds)
migration_target: sdcard
total_size: $(du -sh "$DEST" | awk '{print $1}')
EOF

# ─── Verify ───────────────────────────────────────────
echo ""
info "Verificación de migración..."

MISSING=0
for f in maximun.py config/agent.yaml scripts/deploy.sh; do
    if [ -f "$DEST/$f" ]; then
        log "$f"
    else
        err "$f MISSING"
        MISSING=$((MISSING + 1))
    fi
done

for m in models/primary/*.gguf; do
    if [ -f "$DEST/$m" ]; then
        log "$(basename $m)"
    else
        err "$(basename $m) MISSING"
        MISSING=$((MISSING + 1))
    fi
done

echo ""
if [ "$MISSING" -eq 0 ]; then
    echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  ✓ MIGRACIÓN A SD COMPLETADA${NC}"
    echo -e "${GREEN}  Destino: $DEST${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
else
    echo -e "${YELLOW}  ⚠ Migración completada con $MISSING archivos faltantes${NC}"
fi

echo ""
echo "Para ejecutar en la SD:"
echo "  cd $DEST && bash scripts/deploy.sh"
echo "  cd $DEST && python3 maximun.py --chat"
