# Máximun Proyect — Hermes Agent Base

Agente tipo Hermes ejecutándose en Android (proot).

## Estructura

```
core/           — Núcleo del agente (config, memoria, contexto)
skills/         — Habilidades y plugins del agente
tools/          — Herramientas de interacción (device, api, web, fs)
prompts/        — System prompts y plantillas
data/           — Datos persistentes (sesiones, conocimiento, caché)
logs/           — Logs del agente
scripts/        — Scripts de automatización y utilidades
storage/        — Almacenamiento compartido con sdcard
.config/        — Configuración interna del agente
```

## Ejecución

```bash
# Iniciar agente
./scripts/start.sh

# Verificar estado
./scripts/status.sh
```

## Notas

- Ejecuta como root en proot (Android)
- Shizuku/termux disponibles para acceso al dispositivo
- Memoria persistente en `core/memory/`
- Datos de sesión en `data/sessions/`
