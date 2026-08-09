#!/usr/bin/env python3
"""Benchmark del sistema de memoria."""
import sys
import time
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.long_term import LongTermMemory


def benchmark_memory():
    config = {
        "memory": {
            "long_term": {
                "storage": "/tmp/bench_memory.db",
                "decay_rate": 0.01,
            }
        }
    }

    Path("/tmp/bench_memory.db").unlink(missing_ok=True)
    ltm = LongTermMemory(config, "/tmp")

    print("═══ Benchmark Long-term Memory ═══")

    # Benchmark writes
    start = time.perf_counter()
    for i in range(100):
        ltm.store("benchmark", f"key_{i}", f"Contenido de prueba número {i} con información relevante")
    write_time = time.perf_counter() - start
    print(f"Escrituras: 100 entradas en {write_time*1000:.1f}ms ({100/write_time:.0f} ops/s)")

    # Benchmark reads
    start = time.perf_counter()
    for i in range(100):
        ltm.retrieve(category="benchmark", limit=10)
    read_time = time.perf_counter() - start
    print(f"Lecturas: 100 consultas en {read_time*1000:.1f}ms ({100/read_time:.0f} ops/s)")

    # Benchmark search
    start = time.perf_counter()
    for i in range(50):
        ltm.search_knowledge("prueba", limit=5)
    search_time = time.perf_counter() - start
    print(f"Búsquedas: 50 queries en {search_time*1000:.1f}ms ({50/search_time:.0f} ops/s)")

    # Benchmark interactions
    start = time.perf_counter()
    for i in range(100):
        ltm.store_interaction(f"Mensaje {i}", f"Respuesta {i}", "worker", "simple", 0.8)
    interaction_time = time.perf_counter() - start
    print(f"Interacciones: 100 guardadas en {interaction_time*1000:.1f}ms ({100/interaction_time:.0f} ops/s)")

    ltm.close()
    Path("/tmp/bench_memory.db").unlink(missing_ok=True)

    print()
    print("Benchmark completado")


if __name__ == "__main__":
    benchmark_memory()
