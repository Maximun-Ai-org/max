#!/usr/bin/env python3
"""
CLI — Interfaz de línea de comandos para Máximun Agent.
"""
import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import click
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.markdown import Markdown
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

console = Console() if RICH_AVAILABLE else None


def print_rich(text, style=None):
    if console:
        console.print(text, style=style)
    else:
        print(text)


@click.group()
@click.version_option(version="0.1.0", prog_name="maximun")
def cli():
    """Máximun Hermes Agent — CLI"""
    pass


@cli.command()
@click.option("--no-download", is_flag=True, help="No descargar modelos")
def setup(no_download):
    """Configurar el agente (descargar modelos, instalar dependencias)"""
    print_rich("[bold blue]Configurando Máximun Agent...[/bold blue]" if RICH_AVAILABLE else "Configurando...")
    import subprocess
    subprocess.run(["bash", str(Path(__file__).parent.parent / "scripts" / "deploy.sh")], cwd=str(Path(__file__).parent.parent))


@cli.command()
def chat():
    """Iniciar chat interactivo"""
    from maximun import MaximunAgent, load_config
    config = load_config()
    agent = MaximunAgent(config)
    agent.setup(download_models=True)
    agent.chat()


@cli.command()
@click.argument("message")
def ask(message):
    """Enviar un mensaje al agente"""
    from maximun import MaximunAgent, load_config
    config = load_config()
    agent = MaximunAgent(config)
    agent.setup(download_models=False)
    response = agent.process(message)
    print_rich(response)
    agent.shutdown()


@cli.command()
def status():
    """Mostrar estado del agente"""
    from maximun import MaximunAgent, load_config
    config = load_config()
    agent = MaximunAgent(config)
    agent.setup(download_models=False)
    
    status_data = agent.hrm.get_status()
    
    if RICH_AVAILABLE:
        table = Table(title="Máximun Agent Status")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")
        for key, value in status_data.items():
            table.add_row(key, str(value))
        console.print(table)
    else:
        print(json.dumps(status_data, indent=2, ensure_ascii=False))
    
    agent.shutdown()


@cli.command()
def models():
    """Listar modelos disponibles"""
    from maximun import MaximunAgent, load_config
    config = load_config()
    agent = MaximunAgent(config)
    agent.setup(download_models=False)
    
    model_list = agent.model_manager.list_models()
    loaded = agent.engine.get_loaded_models() if agent.engine else []
    
    if RICH_AVAILABLE:
        table = Table(title="Modelos")
        table.add_column("Rol", style="cyan")
        table.add_column("Archivo")
        table.add_column("Tamaño", style="green")
        table.add_column("Cargado", style="yellow")
        for m in model_list:
            table.add_row(m["role"], m["filename"], f"{m['size_mb']:.1f} MB", "✓" if m["role"] in loaded else "✗")
        console.print(table)
    else:
        for m in model_list:
            loaded_mark = "✓" if m["role"] in loaded else "✗"
            print(f"  {loaded_mark} {m['role']}: {m['filename']} ({m['size_mb']:.1f} MB)")
    
    agent.shutdown()


@cli.command()
def memory():
    """Mostrar estadísticas de memoria"""
    from maximun import MaximunAgent, load_config
    config = load_config()
    agent = MaximunAgent(config)
    agent.setup(download_models=False)
    
    stats = agent.memory.get_stats()
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    agent.shutdown()


@cli.command()
@click.argument("directory")
def index(directory):
    """Indexar directorio en RAG"""
    from maximun import MaximunAgent, load_config
    config = load_config()
    agent = MaximunAgent(config)
    agent.setup(download_models=False)
    agent.memory.initialize_rag()
    
    result = agent.memory.index_knowledge_base(directory)
    print(json.dumps(result, indent=2))
    agent.shutdown()


@cli.command()
@click.argument("profile")
def migrate(profile):
    """Migrar a perfil de hardware más potente"""
    from maximun import MaximunAgent, load_config
    config = load_config()
    agent = MaximunAgent(config)
    agent.setup(download_models=False)
    
    migrated = agent.model_manager.migrate_models(profile)
    print(f"Migrated: {migrated}")
    agent.shutdown()


@cli.command()
def download():
    """Descargar todos los modelos"""
    from maximun import MaximunAgent, load_config
    config = load_config()
    agent = MaximunAgent(config)
    
    results = agent.model_manager.download_all_models()
    for role, path in results.items():
        if path:
            print(f"  ✓ {role}: {path.name} ({path.stat().st_size / 1024 / 1024:.1f} MB)")
        else:
            print(f"  ✗ {role}: FAILED")
    
    agent.shutdown()


if __name__ == "__main__":
    cli()
