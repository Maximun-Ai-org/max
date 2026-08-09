# Migración

## Perfiles
- **mobile_low**: 2GB RAM → TinyLlama 1.1B (todos)
- **mobile_medium**: 4-6GB → Qwen 2.5 1.5B + SmolLM2 1.7B + TinyLlama (ACTUAL)
- **mobile_high**: 8GB+ → Qwen 2.5 3B + Phi-3 Mini 3.8B + SmolLM2
- **desktop**: 16GB+ → Qwen 2.5 7B + Phi-3 Medium 14B + SmolLM2

```bash
python3 migrations/migrate.py --list
python3 migrations/migrate.py mobile_high
```
