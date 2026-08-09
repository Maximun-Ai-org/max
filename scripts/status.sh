#!/bin/bash
# Verificar estado del agente
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "═══════════════════════════════════"
echo "  Estado — Máximun Agent"
echo "═══════════════════════════════════"
echo ""

echo "Sistema:"
uname -a
echo ""

echo "Almacenamiento:"
du -sh "$PROJECT_DIR"/core/ 2>/dev/null || echo "  core/: vacío"
du -sh "$PROJECT_DIR"/data/ 2>/dev/null || echo "  data/: vacío"
du -sh "$PROJECT_DIR"/logs/ 2>/dev/null || echo "  logs/: vacío"
echo ""

echo "Skills:"
ls "$PROJECT_DIR/skills/plugins/" 2>/dev/null || echo "  Ningún plugin instalado"
echo ""

echo "Memoria:"
ls "$PROJECT_DIR/core/memory/" 2>/dev/null || echo "  Sin datos de memoria"
echo ""

echo "Últimos logs:"
tail -5 "$PROJECT_DIR/logs/"*.log 2>/dev/null || echo "  Sin logs"
