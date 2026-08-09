#!/bin/bash
# Iniciar Máximun Agent
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "═══════════════════════════════════"
echo "  Máximun Hermes Agent v0.1.0"
echo "═══════════════════════════════════"
echo ""
echo "Directorio: $PROJECT_DIR"
echo ""

# Verificar entorno
echo "▶ Verificando entorno..."
if command -v termux-device-info &>/dev/null; then
    echo "  ✓ termux disponible"
else
    echo "  ✗ termux no encontrado"
fi

if command -v shizuku &>/dev/null; then
    echo "  ✓ shizuku disponible"
else
    echo "  ✗ shizuku no disponible"
fi

if command -v bsh &>/dev/null; then
    echo "  ✓ bsh disponible"
else
    echo "  ✗ bsh no encontrado"
fi

# Cargar configuración
echo ""
echo "▶ Cargando configuración..."
if [ -f "$PROJECT_DIR/core/config/settings.json" ]; then
    echo "  ✓ settings.json encontrado"
else
    echo "  ✗ settings.json no encontrado"
fi

# Cargar skills
echo ""
echo "▶ Cargando skills..."
PLUGIN_COUNT=$(ls -d "$PROJECT_DIR/skills/plugins/"*/ 2>/dev/null | wc -l)
BUILTIN_COUNT=$(ls "$PROJECT_DIR/skills/builtin/"*.md 2>/dev/null | wc -l)
echo "  Plugins: $PLUGIN_COUNT"
echo "  Built-in: $BUILTIN_COUNT"

# Estado
echo ""
echo "▶ Estado del agente:"
echo "  Nombre: Máximun"
echo "  Tipo: Hermes"
echo "  Plataforma: Android (proot)"
echo "  PID: $$"
echo ""
echo "Agente listo."
