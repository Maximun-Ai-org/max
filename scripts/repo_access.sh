#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
#  Máximun Agent — Script de Acceso al Repo
#  Crea repo, establece permisos, y prepara para migración
# ═══════════════════════════════════════════════════════════════════

set -e
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; }
info() { echo -e "${BLUE}[i]${NC} $1"; }

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Máximun Agent — Configuración de Repo${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo ""

cd "$PROJECT_DIR"

# ─── 1. Initialize Git if not done ────────────────────
if [ ! -d ".git" ]; then
    info "Inicializando repositorio Git..."
    git init
    git config user.name "Máximun Agent"
    git config user.email "maximun@local"
    log "Repositorio inicializado"
fi

# ─── 2. Create .gitignore ─────────────────────────────
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.pyc
*.pyo
.venv/
venv/

# Models (too large for git)
models/primary/*.gguf
models/embeddings/*
models/cache/*
models/migrated/*
!models/.gitkeep

# Runtime
logs/*.log
data/cache/*
data/sessions/*.jsonl
memory/vector_store/chroma/*
memory/long_term/*.db
memory/short_term/*.jsonl

# OS
.DS_Store
Thumbs.db
*.swp
*.swo

# IDE
.vscode/
.idea/

# Build
*.egg-info/
dist/
build/

# Migration archives
migrations/*.tar.gz
migrations/rpi4b/opensuse/*.xz
migrations/rpi4b/opensuse/*.img

# Pytest
.pytest_cache/
EOF

# ─── 3. Create .gitkeep files ─────────────────────────
for dir in models/primary models/embeddings models/cache models/migrated \
           logs data/cache data/sessions memory/vector_store/chroma \
           memory/long_term memory/short_term; do
    mkdir -p "$dir"
    touch "$dir/.gitkeep"
done

# ─── 4. Set permissions ──────────────────────────────
info "Estableciendo permisos..."
chmod +x scripts/*.sh
chmod +x migrations/sdcard/*.sh 2>/dev/null || true
chmod +x migrations/rpi4b/*.sh 2>/dev/null || true
chmod +x migrations/rpi4b/opensuse/*.sh 2>/dev/null || true
chmod +x maximun.py
chmod 644 config/agent.yaml
chmod 644 config/agent.yaml
chmod 644 requirements.txt

# Create admin group
groupadd -f maximun_admin 2>/dev/null || true
chown -R root:maximun_admin "$PROJECT_DIR"
chmod -R 775 "$PROJECT_DIR"
chmod 777 "$PROJECT_DIR/logs" 2>/dev/null || true

log "Permisos establecados (root:maximun_admin)"

# ─── 5. Initial commit ────────────────────────────────
info "Creando commit inicial..."
git add -A
git commit -m "Máximun Agent v0.1.0 — HRM Multi-LLM + RAG + Voice + IoT + RPi4B Migration" 2>/dev/null || {
    warn "Commit ya existe o nothing to commit"
}

# ─── 6. Generate repo info ────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════"
echo "  REPO CONFIGURADO"
echo "═══════════════════════════════════════════════════"
echo ""
echo "Ruta del proyecto:"
echo "  $PROJECT_DIR"
echo ""
echo "Comandos de acceso:"
echo "  cd $PROJECT_DIR"
echo "  git log --oneline"
echo ""
echo "Para copiar a SD Card:"
echo "  bash migrations/sdcard/migrate_to_sd.sh"
echo ""
echo "Para migrar a RPi4B:"
echo "  bash migrations/rpi4b/migrate_to_rpi.sh"
echo ""
echo "Permisos:"
echo "  Owner: root"
echo "  Group: maximun_admin"
echo "  Mode: 775 (admin read/write, others read)"
echo ""
echo "Archivos totales:"
find . -type f -not -path './.git/*' -not -name '.gitkeep' | wc -l
echo ""

# ─── 7. Full project archive ─────────────────────────
info "Generando archivo completo del proyecto..."
ARCHIVE="/tmp/máximun_complete_$(date +%Y%m%d).tar.gz"
tar -czf "$ARCHIVE" \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='.pytest_cache' \
    --exclude='*.pyc' \
    --exclude='.venv' \
    --exclude='logs/*.log' \
    --exclude='data/cache/*' \
    --exclude='memory/vector_store/chroma/*' \
    --exclude='migrations/*.tar.gz' \
    --exclude='migrations/rpi4b/opensuse/*.xz' \
    --exclude='migrations/rpi4b/opensuse/*.img' \
    .

ARCHIVE_SIZE=$(du -h "$ARCHIVE" | awk '{print $1}')
log "Archivo completo: $ARCHIVE ($ARCHIVE_SIZE)"

echo ""
echo "Para extraer en otra máquina:"
echo "  tar -xzf $ARCHIVE -C /ruta/destino/"
echo ""
echo "Para copiar al RPi4B:"
echo "  scp -r $PROJECT_DIR root@<ip-rpi>:/root/Máximun_proyect/"
echo "  # o"
echo "  rsync -avz $PROJECT_DIR/ root@<ip-rpi>:/root/Máximun_proyect/"
