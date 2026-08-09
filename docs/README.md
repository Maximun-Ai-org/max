# Documentación — Máximun Hermes Agent

## Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│                    MÁXIMUN AGENT                        │
│                 Arquitectura HRM Híbrida                │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐         │
│  │ PLANNER  │───▶│ REASONER │───▶│  WORKER  │         │
│  │ Qwen 2.5 │    │ SmolLM2  │    │TinyLlama │         │
│  │  1.5B    │    │  1.7B    │    │  1.1B    │         │
│  └──────────┘    └──────────┘    └──────────┘         │
│       │               │               │                │
│       └───────────────┼───────────────┘                │
│                       │                                │
│              ┌────────▼────────┐                       │
│              │   MEMORY MGR    │                       │
│              ├─────────────────┤                       │
│              │ Working Memory  │ ← RAM (activa)        │
│              │ Short-term      │ ← JSONL (sesiones)    │
│              │ Long-term       │ ← SQLite (conocimiento)│
│              │ RAG             │ ← ChromaDB + Embeddings│
│              └─────────────────┘                       │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  HARDWARE: Android ARM64, 4 cores, 5.5GB RAM           │
│  MODELOS: GGUF Q4_K_M (total ~2.8 GB)                 │
│  MODO: 100% Local / Offline                            │
└─────────────────────────────────────────────────────────┘
```

## Modelos

| Rol | Modelo | Cuantización | Tamaño | RAM | Uso |
|-----|--------|-------------|--------|-----|-----|
| Planner | Qwen 2.5 1.5B Instruct | Q4_K_M | ~1.0 GB | ~1.2 GB | Planificación, razonamiento complejo |
| Reasoner | SmolLM2 1.7B Instruct | Q4_K_M | ~1.0 GB | ~1.3 GB | Análisis, síntesis |
| Worker | TinyLlama 1.1B Chat | Q4_K_M | ~0.7 GB | ~0.9 GB | Respuestas rápidas |
| Embeddings | all-MiniLM-L6-v2 | FP16 | ~90 MB | ~180 MB | Búsqueda semántica RAG |

## Uso

```bash
# Chat interactivo
python3 maximun.py --chat

# Mensaje único
python3 maximun.py --process "¿Qué hora es?"

# CLI
python3 cli/main.py chat
python3 cli/main.py status
python3 cli/main.py models
python3 cli/main.py index /path/to/docs

# API Server
python3 api/server.py
```
