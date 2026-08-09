# Sistema de Memoria

## Capas
1. **Working Memory** (RAM) — contexto activo, ~20 intercambios
2. **Short-term** (JSONL) — sesiones recientes, 20 sesiones
3. **Long-term** (SQLite) — conocimiento acumulado, 10K entradas
4. **RAG** (ChromaDB + embeddings) — búsqueda semántica

## Auto-aprendizaje
- Almacena interacciones completas
- Respuestas de alta confianza como conocimiento
- Decaimiento temporal de prioridad
