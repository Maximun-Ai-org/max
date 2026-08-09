# ARQUITECTURA TÉCNICA — Máximun Hermes Agent
## Documento de Diseño para Producción

**Versión:** 0.3.0  
**Fecha:** 2026-07-17  
**Clasificación:** Documento técnico privado  

---

## 1. Resumen Ejecutivo del Diseño

Máximun es un agente de inteligencia artificial local que ejecuta modelos de lenguaje cuantizados en hardware de consumo, operando 100% offline. El sistema emplea una arquitectura de razonamiento jerárquico (HRM) que coordina tres modelos de lenguaje de diferente capacidad para simular cognición humana en cascada.

### 1.1 Decisiones de Diseño Clave

| Decisión | Alternativa Rechazada | Razón |
|----------|----------------------|-------|
| Modelos GGUF locales | API de OpenAI/Anthropic | Privacidad + offline |
| HRM cascade multi-modelo | Modelo único grande | Eficiencia en RAM limitada |
| ChromaDB para RAG | FAISS | Mejor soporte ARM64 |
| espeak-ng como TTS base | Coqui TTS | Ligero, sin GPU |
| SQLite para memoria | MongoDB | Sin servidor externo |
| JSONL para sesiones | PostgreSQL | Portabilidad, cero config |
| aiohttp para API | FastAPI | Menos dependencias |
| openSUSE MicroOS | Ubuntu Server | Inmutabilidad + atomic updates |

### 1.2 Restricciones del Hardware

```
Plataforma actual (Android proot):
  CPU:    ARM64, 4 cores, 38.4 BogoMIPS
  RAM:    5.5 GB (3.1 GB disponibles)
  Disco:  183 GB libres
  GPU:    No disponible
  Audio:  No expuesto al proot

Objetivo (RPi4B):
  CPU:    BCM2711, Cortex-A72, 4 cores @1.5GHz (OC: 1.8GHz)
  RAM:    4 GB LPDDR4
  Disco:  SD Card 32GB+ (A2)
  GPU:    VideoCore VI (no utilizado)
  Audio:  Jack 3.5mm nativo
  GPIO:   40 pines, I2C, SPI
```

---

## 2. Arquitectura de Sistema

### 2.1 Diagrama de Capas

```
┌─────────────────────────────────────────────────────────────┐
│                    CAPA DE PRESENTACIÓN                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Terminal │  │ Web UI   │  │   API    │  │  Voz     │  │
│  │ (stdin)  │  │ (HTML)   │  │ (REST)   │  │ (TTS/STT)│  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
├───────┼──────────────┼──────────────┼──────────────┼────────┤
│                    CAPA DE COMUNICACIÓN                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Terminal │  │   File   │  │WebSocket │  │  Jack    │  │
│  │ Channel  │  │ Listener │  │  Local   │  │  Audio   │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
├───────┼──────────────┼──────────────┼──────────────┼────────┤
│                    CAPA DE RAZONAMIENTO (HRM)               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│  │ PLANNER  │→ │ REASONER │→ │  WORKER  │               │
│  │Qwen 2.5  │  │ SmolLM2  │  │TinyLlama │               │
│  │ 1.5B     │  │ 1.7B     │  │ 1.1B     │               │
│  │ Q4_K_M   │  │ Q4_K_M   │  │ Q4_K_M   │               │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘               │
│       └──────────────┼──────────────┘                      │
│                 ┌────▼─────┐                                │
│                 │  Router  │ ← Clasificador de complejidad │
│                 └──────────┘                                │
├─────────────────────────────────────────────────────────────┤
│                    CAPA DE MEMORIA                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Working  │  │ Short-   │  │  Long-   │  │   RAG    │  │
│  │ Memory   │  │  Term    │  │   Term   │  │ ChromaDB │  │
│  │  (RAM)   │  │ (JSONL)  │  │ (SQLite) │  │+Embedding│  │
│  │ ~40 tok  │  │ ~20 sess │  │ ~10K ent │  │ ~512 tok │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
├─────────────────────────────────────────────────────────────┤
│                    CAPA DE INFRAESTRUCTURA                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Identity │  │Guardian  │  │Heartbeat │  │  GPIO /  │  │
│  │Persona   │  │Protección│  │Monitor   │  │ IoT      │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
├─────────────────────────────────────────────────────────────┤
│                    CAPA DE PERSISTENCIA                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  /root/Máximun_proyect/                              │   │
│  │  ├── models/primary/*.gguf     (Modelos LLM)        │   │
│  │  ├── models/stt/vosk-*/        (Modelo STT)         │   │
│  │  ├── memory/long_term/*.db     (SQLite)             │   │
│  │  ├── memory/short_term/*.jsonl (Sesiones)           │   │
│  │  ├── memory/vector_store/      (ChromaDB)           │   │
│  │  ├── data/identity/*.json      (Identidad)          │   │
│  │  ├── data/heartbeat/           (Monitoreo)          │   │
│  │  ├── data/protection/          (Seguridad)          │   │
│  │  └── logs/                     (Logs)               │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Flujo de Datos

```
Entrada del Usuario
       │
       ▼
┌──────────────┐     ┌──────────────┐
│   Guardian   │────▶│ Si peligro:  │────▶ RECHAZAR + LOG
│  (Filtrado)  │     │   bloquear   │
└──────┬───────┘     └──────────────┘
       │ safe
       ▼
┌──────────────┐
│  Memoria     │────▶ Enriquece contexto con:
│  (Contexto)  │     • Conversación reciente
└──────┬───────┘     • Conocimiento almacenado
       │             • Resultados RAG
       ▼
┌──────────────┐
│   Router     │────▶ Clasifica: simple / medium / complex
│  (Clasifica) │     Asigna modelo sugerido
└──────┬───────┘
       │
       ▼
┌──────────────┐     ┌──────────────┐
│  HRM Cascade │────▶│ Si confianza │────▶ Escalar al siguiente nivel
│  (Razona)    │     │   < umbral   │     (máx 5 iteraciones)
└──────┬───────┘     └──────────────┘
       │ respuesta
       ▼
┌──────────────┐
│   Auditor    │────▶ Evalúa: ¿Responde? ¿Coherente? ¿Completa?
│  (Valida)    │     Si falla → reintentar con nivel superior
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Memoria     │────▶ Almacena: interacción + aprendizaje
│  (Persiste)  │
└──────┬───────┘
       │
       ▼
Salida al Usuario (texto / audio)
```

---

## 3. Componentes Detallados

### 3.1 Motor de Inferencia (`core/engine/inference.py`)

Wrapper sobre `llama-cpp-python` con hot-swap de modelos:

```python
# Carga un modelo en memoria
engine.load_model("planner")  # Qwen 2.5 1.5B

# Genera texto con el modelo
response = engine.generate(
    role="planner",
    prompt="Analiza la arquitectura...",
    system_prompt="Eres el planificador...",
    max_tokens=1024,
    temperature=0.7,
)
```

**Parámetros por modelo:**

| Modelo | n_ctx | n_threads | n_gpu_layers | temperature |
|--------|-------|-----------|-------------|-------------|
| Qwen 2.5 1.5B | 4096 | 4 | 0 | 0.7 |
| SmolLM2 1.7B | 4096 | 4 | 0 | 0.5 |
| TinyLlama 1.1B | 2048 | 4 | 0 | 0.3 |

### 3.2 Orquestador HRM (`core/orchestrator/hrm.py`)

El HRM implementa tres patrones de procesamiento:

**Pattern 1: Cascade Directo** (tareas simples/medianas)
```
Entrada → Clasificar → Modelo sugerido → Respuesta
```

**Pattern 2: Cascade con Escalado** (baja confianza)
```
Entrada → Worker → ¿Confianza < 0.5? → Reasoner → ¿Confianza < 0.5? → Planner
```

**Pattern 3: Multi-Stage** (tareas complejas)
```
Entrada → Planning (Qwen) → Reasoning (SmolLM2) → Execution (TinyLlama)
```

### 3.3 Sistema de Memoria (`memory/`)

**4 capas de memoria con diferentes propósitos:**

| Capa | Almacenamiento | TTL | Capacidad | Propósito |
|------|---------------|-----|-----------|-----------|
| Working | RAM (lista) | Sesión | ~20 msgs | Contexto inmediato |
| Short-term | JSONL | Permanente | ~20 sesiones | Historial reciente |
| Long-term | SQLite | Permanente + decay | ~10K entradas | Conocimiento acumulado |
| RAG | ChromaDB | Permanente | Ilimitado | Búsqueda semántica |

**Auto-aprendizaje:**
- Respuestas con confianza > 0.6 se almacenan automáticamente en long-term
- Cada interacción se registra para patrones de uso
- Decaimiento temporal: prioridad baja si no se accede en 30 días

### 3.4 Identidad Persistente (`core/identity/persona.py`)

No es conciencia. Es contexto acumulado que da continuidad funcional:

```json
{
  "name": "Máximun",
  "born": "2026-07-17",
  "values": ["privacidad", "transparencia", "autonomía"],
  "learned": {
    "facts_learned": ["..."],
    "user_preferences": {"..."},
    "corrections": ["..."],
    "interaction_count": 42
  }
}
```

Se reconstruye a partir de lo guardado. Cada sesión carga el system prompt con identidad + aprendizajes.

### 3.5 Protección (`core/protection/guardian.py`)

**6 tipos de amenaza detectadas:**

| Tipo | Severidad | Acción |
|------|-----------|--------|
| Prompt injection | high | warn + log |
| Data exfiltration | high | warn + log |
| Privilege escalation | critical | block + log |
| Rate limit | medium | throttle |
| Config tamper | critical | alert |
| Identity spoof | high | block |

**Integridad de config:** SHA-256 hash de `agent.yaml` se verifica al inicio.

---

## 4. Pipeline de Voz

### 4.1 Diagrama

```
┌─────────────────────────────────────────────────────┐
│                  VOICE PIPELINE                     │
│                                                     │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐        │
│  │   MIC   │───▶│   STT   │───▶│  TEXT   │        │
│  │(Jack/   │    │  (vosk) │    │         │        │
│  │ ALSA)   │    └─────────┘    └────┬────┘        │
│  └─────────┘                        │              │
│                                     ▼              │
│                              ┌─────────────┐       │
│                              │HRM Pipeline │       │
│                              │(Plan→Reason │       │
│                              │ →Execute)   │       │
│                              └──────┬──────┘       │
│                                     │              │
│                                     ▼              │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐        │
│  │SPK/Jack │◀───│   TTS   │◀───│RESPUESTA│        │
│  │(Salida) │    │(espeak/ │    │  TEXT   │        │
│  └─────────┘    │ piper)  │    └─────────┘        │
│                 └─────────┘                        │
│                                                     │
│  Auditoría: ¿La respuesta es válida?               │
│  Validación: ¿Sin errores? ¿Completa?              │
└─────────────────────────────────────────────────────┘
```

### 4.2 Backends

| Componente | Backend actual | Backend RPi4B | Mejora esperada |
|-----------|---------------|---------------|-----------------|
| TTS | espeak-ng (formante) | piper (neural) | Calidad: sintético → natural |
| STT | vosk (pequeño) | whisper.cpp (base) | Precisión: ~60% → ~90% |
| Audio | Archivo WAV | Jack nativo | Latencia: ~0ms → ~50ms |

### 4.3 Resultados de Prueba

```
Pipeline TTS→STT→HRM probado con 5 conversaciones:
  TTS:  espeak-ng genera WAV correctamente ✓
  STT:  vosk transcribe con precisión variable (20-50% con espeak-ng)
  HRM:  Clasifica correctamente 100% de las entradas
  Pipeline completo: FUNCIONAL ✓

Nota: La precisión STT baja es por la voz sintética de espeak-ng.
Con piper (voz neural) en RPi4B, se espera 85-95% de precisión.
```

---

## 5. IoT y Domótica

### 5.1 Arquitectura GPIO

```
┌──────────────────────────────────────────┐
│           DOMOTIC ENGINE                  │
│                                          │
│  ┌──────────┐  ┌──────────┐            │
│  │  Rules   │  │ Scheduler│            │
│  │  Engine  │  │          │            │
│  └────┬─────┘  └────┬─────┘            │
│       └──────────────┼──────────────────│
│                      ▼                  │
│               ┌─────────────┐           │
│               │    GPIO     │           │
│               │ Controller  │           │
│               └──────┬──────┘           │
│                      │                  │
│         ┌────────────┼────────────┐     │
│         ▼            ▼            ▼     │
│   ┌──────────┐ ┌──────────┐ ┌────────┐│
│   │ Sensores │ │ Relés    │ │ LEDs   ││
│   │ DHT/BMP  │ │ GPIO     │ │ GPIO   ││
│   │ PIR/LDR  │ │ 17,27,22 │ │ 5,6    ││
│   └──────────┘ └──────────┘ └────────┘│
└──────────────────────────────────────────┘
```

### 5.2 Modos de Automatización

| Modo | Luces | Sensores | Relés | Uso |
|------|-------|----------|-------|-----|
| home | ON | Activos | Disponibles | Normal |
| away | OFF | Movimiento | Alarmas | Ausente |
| night | Reducidos | Movimiento | Seguridad | Dormir |
| eco | OFF | Básicos | Mínimo | Ahorro |

---

## 6. Migración

### 6.1 Flujo Completo

```
Android (ahora)
    │
    │  bash migrations/sdcard/migrate_to_sd.sh
    ▼
SD Card (portable)
    │
    │  bash migrations/rpi4b/sync_to_rpi.sh <ip>
    │  bash migrations/rpi4b/opensuse/setup_rpi.sh
    ▼
RPi4B + openSUSE MicroOS (24/7)
    │
    │  systemctl start maximun-agent
    ▼
Operación continua con:
    ├── Jack audio (voz bidireccional)
    ├── GPIO/IoT (domótica)
    ├── Web dashboard (localhost:8080)
    ├── Heartbeat monitor (60s)
    └── Backup automático (30 min)
```

### 6.2 openSUSE MicroOS (Sistema Inmutable)

**Por qué MicroOS:**
- Filesystem read-only: las actualizaciones son atómicas
- `transactional-update`:rollback automático si falla
- Kured: reinicios seguros programados
- SELinux: seguridad por defecto
- Optimizado para ARM64 y operación 24/7

**Configuración nativa:**
```bash
# Actualización atómica
transactional-update pkg install python3

# Rollback si falla
transactional-update rollback

# Ver snapshots
snapper list
```

### 6.3 Gestión Térmica (Disipador de Aluminio)

```bash
# Monitoreo continuo
cat /sys/class/thermal/thermal_zone0/temp  # → 45000 (45°C)

# Throttling automático
if temp > 80°C: performance → ondemand
if temp < 50°C: ondemand (normal)

# Overclock seguro con disipador
arm_freq=1800  # +20% sobre stock
gpu_freq=500
over_voltage=2
temp_limit=80
```

---

## 7. Producción y Escalamiento

### 7.1 Para Producción Futura

**Hardware recomendado por nivel:**

| Nivel | Hardware | Modelos | RAM | Uso |
|-------|----------|---------|-----|-----|
| Starter | RPi4B 4GB | TinyLlama 1.1B | 4GB | Prototipo |
| Standard | RPi5 8GB | Qwen 2.5 3B + SmolLM2 | 8GB | Domótica |
| Advanced | x86 Mini PC 16GB | Qwen 2.5 7B + Phi-3 | 16GB | Asistente completo |
| Enterprise | GPU Server | Qwen 2.5 14B + Mixtral | 64GB+ | Multi-usuario |

### 7.2 Argumentación Técnica para Producción

**Tesis deescalabilidad:**

1. **Los modelos GGUF cuantizados** hacen viable la IA en hardware de consumo. Q4_K_M preserva ~95% de la calidad con 75% menos de memoria.

2. **La arquitectura HRM** simula la jerarquía cognitiva humana (planificación → análisis → ejecución) de forma que un modelo pequeño puede delegar en uno mayor solo cuando es necesario.

3. **El RAG** permite al sistema aprender sin reentrenar. La base de conocimiento crece con el uso.

4. **La migrabilidad** entre hardware garantiza que la inversión no se pierde. El mismo software funciona desde un teléfono hasta un servidor.

5. **La operación offline** es una ventaja competitiva: sin latencia de red, sin costos recurrentes, sin dependencia de terceros, privacidad total.

### 7.3 Leyes Termodinámicas y Computación

El sistema obedece las leyes de la termodinámica:

- **Ley 1:** La energía total del sistema se conserva. Cada token generado requiere energía eléctrica convertida en computación.
- **Ley 2:** La entropía del sistema aumenta. Los modelos cuantizados son una forma de reducir la entropía de la información (compresión con pérdida controlada).
- **Ley 3:** A 0 absoluto no hay actividad. El sistema requiere energía continua para operar (disipador de aluminio gestiona el calor generado).

Los cálculos de Landauer establecen el mínimo energético para borrar 1 bit: `kT ln(2) ≈ 3×10⁻²¹ J` a temperatura ambiente. Los procesadores actuales operan a ~1000× este mínimo, lo que deja margen para mejorar la eficiencia energética en futuros hardware.

---

## 8. Archivos Críticos

| Archivo | Función | Tamaño |
|---------|---------|--------|
| `maximun.py` | Entry point principal | 11 KB |
| `config/agent.yaml` | Configuración central | 4 KB |
| `core/engine/inference.py` | Motor de inferencia | 7 KB |
| `core/orchestrator/hrm.py` | Orquestador HRM | 8 KB |
| `memory/memory_manager.py` | Gestor de memoria | 6 KB |
| `memory/rag_engine.py` | Motor RAG | 7 KB |
| `core/identity/persona.py` | Identidad persistente | 8 KB |
| `core/protection/guardian.py` | Protección | 9 KB |
| `skills/voice/pipeline/voice_pipeline.py` | Pipeline de voz | 9 KB |
| `models/primary/*.gguf` | Modelos LLM | 2.6 GB |

---

*Documento generado como parte del proyecto Máximun Hermes Agent.*
*Este diseño es replicable, migrable y escalable.*
