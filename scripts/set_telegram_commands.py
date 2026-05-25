#!/usr/bin/env python3
"""Register slash commands for the Bri Telegram bot."""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from kadrix.telegram_bot import set_commands

if __name__ == "__main__":
    print("🤖 Registrando comandos slash de Bri en Telegram...")
    result = set_commands()
    if result.get("ok"):
        print("✅ Comandos registrados exitosamente.")
        print("\n📋 Lista de comandos:")
        print("  /start     — Vincular tu cuenta de Cadrex")
        print("  /help      — Ver lista de comandos")
        print("  /tareas    — Ver tus tareas pendientes")
        print("  /agregar   — Crear tarea por lenguaje natural")
        print("  /done      — Marcar tarea como completada")
        print("  /stats     — Estadísticas del dashboard")
    else:
        print(f"❌ Error: {result}")
        sys.exit(1)
