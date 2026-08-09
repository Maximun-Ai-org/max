#!/usr/bin/env python3
"""Benchmark del TaskRouter — mide precisión de clasificación."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.orchestrator.router import TaskRouter, TaskComplexity


def benchmark_classification():
    config = {
        "hrm": {
            "routing": {
                "strategy": "cascade",
                "confidence_threshold": 0.7,
                "escalation_threshold": 0.5,
            },
            "delegation": {
                "simple_tasks": "worker",
                "medium_tasks": "reasoner",
                "complex_tasks": "planner",
            },
        }
    }
    router = TaskRouter(config)

    test_cases = [
        ("hola", "worker"),
        ("¿Qué hora es?", "worker"),
        ("define machine learning", "worker"),
        ("escribe una función en python", "reasoner"),
        ("genera un script de bash", "reasoner"),
        ("calcula fibonacci", "reasoner"),
        ("analiza la arquitectura de este sistema", "planner"),
        ("diseña un plan de optimización paso a paso", "planner"),
        ("evalúa y compara diferentes aproximaciones", "planner"),
        ("investiga y sintetiza los hallazgos", "planner"),
    ]

    print("═══ Benchmark TaskRouter ═══")
    print(f"Test cases: {len(test_cases)}")
    print()

    correct = 0
    total_time = 0

    for task, expected_model in test_cases:
        start = time.perf_counter()
        complexity, confidence, model = router.classify(task)
        elapsed = time.perf_counter() - start
        total_time += elapsed

        is_correct = model == expected_model
        correct += is_correct
        icon = "✓" if is_correct else "✗"

        print(f"  {icon} [{complexity.value:8s}] {model:8s} | {task[:50]}")

    accuracy = correct / len(test_cases) * 100
    avg_time = total_time / len(test_cases) * 1000

    print()
    print(f"Precisión: {correct}/{len(test_cases)} ({accuracy:.0f}%)")
    print(f"Tiempo promedio: {avg_time:.2f}ms por clasificación")
    print(f"Throughput: {1000/avg_time:.0f} clasificaciones/segundo")


if __name__ == "__main__":
    benchmark_classification()
