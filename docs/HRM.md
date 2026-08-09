# Arquitectura HRM

```
Nivel 3: PLANNER (Qwen 2.5 1.5B) — planificación profunda
Nivel 2: REASONER (SmolLM2 1.7B) — análisis y resolución  
Nivel 1: WORKER (TinyLlama 1.1B) — respuestas rápidas
```

Cascade: intenta nivel → escala si confianza baja → máx 5 iteraciones.
Multi-stage: Planning → Reasoning → Execution para tareas complejas.
