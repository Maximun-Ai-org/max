#!/bin/bash
# ═══════════════════════════════════════════════════════
#  Backup a Google Drive — requiere rclone instalado
#  Primera vez: rclone config (sigue el wizard)
# ═══════════════════════════════════════════════════════
set -e
PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE="gdrive"
REMOTE_DIR="Máximun_proyect"

echo "═══ Backup a Google Drive ═══"

# Check rclone
if ! command -v rclone &>/dev/null; then
    echo "Instalando rclone..."
    curl -sSL https://rclone.org/install.sh | bash
fi

# Check config
if ! rclone listremotes 2>/dev/null | grep -q "^${REMOTE}:"; then
    echo "Configura rclone primero:"
    echo "  rclone config"
    echo "  Crea un remote llamado 'gdrive' con Google Drive"
    exit 1
fi

echo "Sincronizando..."
rclone sync "$PROJECT" "${REMOTE}:${REMOTE_DIR}" \
    --exclude ".git/*" \
    --exclude "__pycache__/*" \
    --exclude "*.pyc" \
    --exclude "logs/*.log" \
    --exclude "data/cache/*" \
    --exclude "memory/vector_store/chroma/*" \
    --progress

echo "✓ Backup completado a Google Drive: ${REMOTE_DIR}/"
