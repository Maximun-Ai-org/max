#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
#  Máximun Agent — Script de Despliegue
#  Descarga modelos, instala dependencias, configura el entorno
# ═══════════════════════════════════════════════════════════════════

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; }
info() { echo -e "${BLUE}[i]${NC} $1"; }

echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Máximun Agent — Despliegue Completo${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo ""

cd "$PROJECT_DIR"

# ─── 1. System Dependencies ───────────────────────────────────
info "Verificando dependencias del sistema..."

if command -v apt-get &>/dev/null; then
    apt-get update -qq 2>/dev/null || true
    apt-get install -y -qq python3-dev python3-pip build-essential cmake 2>/dev/null || true
fi

# ─── 2. Python venv ───────────────────────────────────────────
VENV_DIR="$PROJECT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
    info "Creando entorno virtual..."
    python3 -m venv "$VENV_DIR"
    log "Entorno virtual creado: $VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
log "Entorno virtual activado"

# ─── 3. Python Dependencies ───────────────────────────────────
info "Instalando dependencias Python..."
pip install --upgrade pip -q 2>/dev/null
pip install -r "$PROJECT_DIR/requirements.txt" -q 2>/dev/null
log "Dependencias instaladas"

# ─── 4. Verify llama-cpp-python ───────────────────────────────
info "Verificando llama-cpp-python..."
python3 -c "import llama_cpp; print('  llama-cpp-python version:', llama_cpp.__version__)" 2>/dev/null || {
    warn "Recompilando llama-cpp-python sin GPU..."
    pip install llama-cpp-python --force-reinstall --no-cache-dir -q 2>/dev/null
    log "llama-cpp-python instalado"
}

# ─── 5. Download Models ───────────────────────────────────────
info "Descargando modelos GGUF cuantizados..."

download_hf() {
    local repo=$1
    local filename=$2
    local target_dir=$3
    local target_path="$target_dir/$filename"

    if [ -f "$target_path" ]; then
        log "Ya existe: $filename"
        return
    fi

    local url="https://huggingface.co/$repo/resolve/main/$filename"
    info "Descargando: $filename"
    
    mkdir -p "$target_dir"
    
    if command -v wget &>/dev/null; then
        wget -q --show-progress -O "$target_path" "$url" || {
            err "Fallo descarga: $filename"
            rm -f "$target_path"
            return 1
        }
    elif command -v curl &>/dev/null; then
        curl -L --progress-bar -o "$target_path" "$url" || {
            err "Fallo descarga: $filename"
            rm -f "$target_path"
            return 1
        }
    else
        err "No hay wget ni curl disponible"
        return 1
    fi

    local size=$(du -h "$target_path" | cut -f1)
    log "Descargado: $filename ($size)"
}

# Planner: Qwen 2.5 1.5B Q4_K_M (~1.0 GB)
download_hf "bartowski/Qwen2.5-1.5B-Instruct-GGUF" \
    "qwen2.5-1.5b-instruct-q4_k_m.gguf" \
    "$PROJECT_DIR/models/primary"

# Reasoner: SmolLM2 1.7B Q4_K_M (~1.0 GB)
download_hf "HuggingFaceTB/SmolLM2-1.7B-Instruct-GGUF" \
    "smollm2-1.7b-instruct-q4_k_m.gguf" \
    "$PROJECT_DIR/models/primary"

# Worker: TinyLlama 1.1B Q4_K_M (~0.7 GB)
download_hf "TheTinyLlama/TinyLlama-1.1B-Chat-v1.0-GGUF" \
    "tinyllama-1.1b-chat-q4_k_m.gguf" \
    "$PROJECT_DIR/models/primary"

# ─── 6. Download Embeddings ───────────────────────────────────
info "Descargando modelo de embeddings..."
python3 -c "
from sentence_transformers import SentenceTransformer
import os
os.environ['TRANSFORMERS_CACHE'] = '$PROJECT_DIR/models/embeddings'
model = SentenceTransformer('all-MiniLM-L6-v2')
print('  Embeddings descargados correctamente')
" 2>/dev/null || warn "Embeddings se descargarán al primer uso"

# ─── 7. Create directories ────────────────────────────────────
info "Creando estructura de directorios..."
mkdir -p "$PROJECT_DIR"/{logs,data/{sessions,knowledge,cache},memory/{short_term,long_term/{episodic,semantic},vector_store/chroma}}

# ─── 8. Verify Installation ──────────────────────────────────
echo ""
info "Verificando instalación..."

python3 -c "
import yaml, json
from pathlib import Path

project = Path('$PROJECT_DIR')
config = yaml.safe_load(open(project / 'config/agent.yaml'))

models = project / 'models/primary'
available = []
for f in models.glob('*.gguf'):
    size_mb = f.stat().st_size / 1024 / 1024
    available.append((f.name, size_mb))

print()
print('Modelos disponibles:')
for name, size in available:
    print(f'  ✓ {name} ({size:.1f} MB)')
    
if not available:
    print('  ✗ No hay modelos descargados')
print()

# Check dependencies
deps_ok = True
for dep in ['llama_cpp', 'sentence_transformers', 'chromadb', 'yaml', 'rich']:
    try:
        __import__(dep)
        print(f'  ✓ {dep}')
    except ImportError:
        print(f'  ✗ {dep} — FALTA')
        deps_ok = False

print()
if deps_ok and available:
    print('═══════════════════════════════════════════════════')
    print('  ✓ DESPLIEGUE COMPLETADO EXITOSAMENTE')
    print('═══════════════════════════════════════════════════')
    print()
    print('  Ejecutar: python3 maximun.py --chat')
else:
    print('  ⚠ Despliegue incompleto — revisar errores arriba')
"
