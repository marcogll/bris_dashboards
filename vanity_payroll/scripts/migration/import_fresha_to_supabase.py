"""
Script para migrar datos de Fresha de SQLite a Supabase usando REST API.
Usa el UUID de la cita (ref_cita) como primary key.

Author: @marcogll
Date: 2026-05-23
"""

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    from dotenv import load_dotenv
    load_dotenv('/Users/marco/Documents/code/vanity_hq/vanity_payroll/.env.migration')
except ImportError:
    print("❌ dotenv not installed")
    sys.exit(1)


# RAW_COLUMNS - Mapeo de columnas del CSV de Fresha
RAW_COLUMNS = {
    "Ref. cita": "ref_cita",
    "Cliente": "client_name",
    "Miembro del equipo": "staff_name",
    "Recurso": "resource",
    "Estado": "status",
    "Creada el día": "created_at_source",
    "Fecha programada": "scheduled_at",
    "Fecha de cancelación": "cancelled_at",
    "Categoría": "category",
    "Servicio": "service",
    "Duración (min)": "duration_original",
    "Franja horaria cita": "time_slot",
    "Creada por": "created_by",
    "Cancelado por": "cancelled_by",
    "Centro": "center_name",
    "Ventas netas": "net_sales",
    "Motivo de cancelación": "cancellation_reason",
    "Recargos aplicados": "surcharges",
    "Pagos por adelantado": "prepayments",
}


def normalize_name(value: str) -> str:
    """Normaliza nombres a minúsculas y sin espacios dobles"""
    value = (value or "").strip().lower()
    value = re.sub(r"\s+", " ", value)
    return value


def money(value: Optional[str]) -> float:
    """Convierte valor monetario a float"""
    if value in (None, ""):
        return 0.0
    text = str(value).replace("$", "").replace(",", "").strip()
    try:
        return float(text)
    except ValueError:
        return 0.0


def duration_minutes(value: Optional[str]) -> int:
    """Convierte duración string a minutos"""
    if value in (None, ""):
        return 0
    text = str(value)
    hours = re.search(r"(\d+)\s*h", text)
    minutes = re.search(r"(\d+)\s*min", text)
    return (int(hours.group(1)) * 60 if hours else 0) + (int(minutes.group(1)) if minutes else 0)


def parse_date(value: Optional[str]) -> Optional[str]:
    """Parsea fechas en múltiples formatos"""
    if value in (None, ""):
        return None
    text = str(value).strip()
    formats = [
        "%d/%m/%y %H:%M:%S",
        "%d %b %Y, %I:%M%p",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).isoformat()
        except ValueError:
            pass
    return text


def branch_code(center_name: Optional[str]) -> str:
    """Genera código de sucursal"""
    text = str(center_name or "")
    if "Plaza O" in text:
        return "O"
    if "CIMA" in text:
        return "C"
    if "Los Pinos" in text:
        return "P"
    return "X"


def process_row(raw: Dict[str, str]) -> Dict[str, Any]:
    """Procesa una fila del CSV y crea un diccionario con los datos normalizados"""
    # Mapeo de columnas
    row = {target: raw.get(source_col) for source_col, target in RAW_COLUMNS.items()}

    # Datos requeridos
    ref = (row.get("ref_cita") or "").strip()
    staff = (row.get("staff_name") or "").strip()

    # Validar datos mínimos
    if not ref or not staff:
        return None

    # Normalizar y procesar datos
    processed = {
        "ref_cita": ref,
        "client_name": row.get("client_name"),
        "staff_name": staff,
        "staff_normalized_name": normalize_name(staff),
        "resource": row.get("resource"),
        "status": row.get("status"),
        "created_at_source": parse_date(row.get("created_at_source")),
        "scheduled_at": parse_date(row.get("scheduled_at")),
        "cancelled_at": parse_date(row.get("cancelled_at")),
        "category": row.get("category"),
        "service": row.get("service"),
        "duration_original": row.get("duration_original"),
        "duration_minutes": duration_minutes(row.get("duration_original")),
        "time_slot": row.get("time_slot"),
        "created_by": row.get("created_by"),
        "cancelled_by": row.get("cancelled_by"),
        "center_name": row.get("center_name"),
        "branch_code": branch_code(row.get("center_name")),
        "net_sales": money(row.get("net_sales")),
        "cancellation_reason": row.get("cancellation_reason"),
        "surcharges": money(row.get("surcharges")),
        "prepayments": money(row.get("prepayments")),
        "source_file": "all-data",
        "raw_payload": json.dumps(raw, ensure_ascii=False),
        "imported_at": datetime.utcnow().isoformat(),
    }

    return processed


def create_batch(supabase: Any, source: str, file_path: str) -> int:
    """Crea un registro de batch de importación"""
    # Primero, verificar si el batch ya existe
    batches = supabase.table("import_batches").select("*").filter("source", "eq", source).filter("file_name", "eq", file_path).execute()

    if batches.data:
        return batches.data[0]["id"]

    # Crear nuevo batch
    batch = {
        "source": source,
        "file_name": file_path,
        "created_at": datetime.utcnow().isoformat(),
    }
    result = supabase.table("import_batches").insert(batch).execute()
    return result.data[0]["id"]


def fetch_existing_refs(supabase: Any) -> set:
    """Obtiene todos los ref_cita existentes en Supabase con paginación"""
    existing_refs = set()
    page_size = 1000
    offset = 0

    while True:
        response = supabase.table("sales_appointments").select("ref_cita").range(offset, offset + page_size - 1).execute()
        if not response.data:
            break
        existing_refs.update(row["ref_cita"] for row in response.data)
        offset += page_size

    return existing_refs


def import_file(supabase: Any, file_path: str, source: str, force_update: bool = False, dry_run: bool = False):
    """Importa archivo CSV a Supabase usando REST API"""
    file_path = Path(file_path)
    batch_id = create_batch(supabase, source, str(file_path))

    total = 0
    skipped = 0

    if force_update:
        existing_refs = set()
    else:
        print("   Obteniendo citas existentes en Supabase...")
        existing_refs = fetch_existing_refs(supabase)
        print(f"   Existentes en Supabase: {len(existing_refs):,}")

    with file_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        rows_to_insert = []

        for raw in reader:
            total += 1
            processed = process_row(raw)

            if processed:
                if force_update or processed["ref_cita"] not in existing_refs:
                    rows_to_insert.append(processed)
                else:
                    skipped += 1

        inserted = 0
        errors = 0

        if rows_to_insert:
            print(f"   Nuevas a importar: {len(rows_to_insert):,}")
            print(f"   Saltadas (ya existen): {skipped:,}")

            if dry_run:
                print(f"   🔍 DRY RUN — no se escribirán cambios")
                for row in rows_to_insert[:5]:
                    print(f"      Ejemplo: {row['ref_cita']} | {row.get('client_name', '')} | {row.get('staff_name', '')}")
                if len(rows_to_insert) > 5:
                    print(f"      ... y {len(rows_to_insert) - 5} más")
                print(f"\n   Filas en CSV: {total:,}")
                print(f"   Existentes en Supabase: {len(existing_refs):,}")
                print(f"   Nuevas a importar: {len(rows_to_insert):,}")
                print(f"   Saltadas (ya existen): {skipped:,}")
                print(f"   Importadas: 0 (dry run)")
                print(f"   Errores: 0")
                return total, 0, 0

            if force_update:
                print(f"   Procesando {len(rows_to_insert)} citas (upsert)...")
                response = supabase.table("sales_appointments").upsert(rows_to_insert).execute()
            else:
                print(f"   Importando {len(rows_to_insert)} citas nuevas...")
                response = supabase.table("sales_appointments").insert(rows_to_insert).execute()

            if response.data:
                inserted = len(response.data)
        else:
            print(f"   No hay citas nuevas para importar")

        print(f"\n   Filas en CSV: {total:,}")
        print(f"   Existentes en Supabase: {len(existing_refs):,}")
        print(f"   Nuevas a importar: {len(rows_to_insert):,}")
        print(f"   Saltadas (ya existen): {skipped:,}")
        print(f"   Importadas: {inserted:,}")
        print(f"   Errores: {errors}")

        if not dry_run:
            batch_update = {
                "rows_total": total,
                "rows_inserted": inserted,
                "rows_updated": skipped,
            }
            supabase.table("import_batches").update(batch_update).eq("id", batch_id).execute()

    return total, inserted, skipped


def seed_staff(supabase: Any, staff_path: str):
    """Seed de empleados desde archivo JSON"""
    if not staff_path:
        return
    path = Path(staff_path)
    if not path.exists():
        print(f"   ⚠️  Archivo de empleados no encontrado: {staff_path}")
        return

    with path.open(encoding="utf-8") as handle:
        staff = json.load(handle)

    print(f"   📋 Seed de empleados desde {staff_path}")
    for item in staff:
        name = item.get("nombre")
        if not name:
            continue

        normalized = normalize_name(name)
        data = {
            "full_name": name,
            "normalized_name": normalized,
            "email": item.get("contacto"),
            "phone": item.get("telefono"),
            "relationship_type": "mercantil",
            "contract_type": "mercantil",
            "raw_payload": json.dumps(item, ensure_ascii=False),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        # Usar upsert con unique constraint en normalized_name + branch_name
        # Para evitar duplicados
        try:
            supabase.table("people").upsert([data]).execute()
        except Exception as e:
            print(f"   ⚠️  Error al procesar empleado {name}: {e}")


def link_sales_to_people(supabase: Any):
    print("   Enlazando citas con empleados...")
    try:
        supabase.rpc("update_sales_person_id").execute()
        print("   Citas enlazadas correctamente")
    except Exception as e:
        print(f"   No se pudo ejecutar el linking: {e}")
        print("   Ejecuta manualmente en el SQL Editor de Supabase:")
        print("   UPDATE sales_appointments")
        print("   SET person_id = (SELECT people.id FROM people WHERE people.normalized_name = sales_appointments.staff_normalized_name LIMIT 1)")
        print("   WHERE person_id IS NULL;")


def main():
    parser = argparse.ArgumentParser(description="Importar datos de Fresha a Supabase")
    parser.add_argument("--staff", default="/Users/marco/Documents/code/vanity_hq/vanity_payroll/scripts/data/staff.json")
    parser.add_argument("--csv", default="/Users/marco/Documents/code/vanity_hq/vanity_dashboard/all-data.csv")
    parser.add_argument("--source", default="fresha-all-data", help="Nombre del fuente de datos")
    parser.add_argument("--force-update", action="store_true", help="Upsert all rows (same as original behavior)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be imported without writing")
    args = parser.parse_args()

# Crear cliente Supabase
    from supabase import create_client

    # Extraer el proyecto ID desde la configuración CLI
    project_ref = "umzlwcdjxtbdoqiclolo"
    print(f"📍 Project Ref: {project_ref}")

    # Crear URL REST correcta
    supabase_rest_url = f"https://{project_ref}.supabase.co"
    print(f"📍 Supabase REST URL: {supabase_rest_url}")

    supabase_key = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_ANON_KEY')

    if not supabase_key or 'XXX' in supabase_key:
        print("Supabase API keys no estan configuradas")
        print("   Configura SUPABASE_SERVICE_KEY o SUPABASE_ANON_KEY en .env.migration")
        sys.exit(1)

    try:
        supabase = create_client(supabase_rest_url, supabase_key)
        print("✅ Conectado a Supabase")
    except Exception as e:
        print(f"❌ Error conectando a Supabase: {e}")
        sys.exit(1)

    # Seed de empleados
    if Path(args.staff).exists():
        seed_staff(supabase, args.staff)

    # Importar archivo CSV
    print(f"\n📂 Importando archivo {args.csv}")
    if not Path(args.csv).exists():
        print(f"❌ Archivo CSV no encontrado: {args.csv}")
        sys.exit(1)

    totals = import_file(supabase, args.csv, args.source, force_update=args.force_update, dry_run=args.dry_run)

    if not args.dry_run:
        link_sales_to_people(supabase)

    total, inserted, skipped = totals
    print(f"\n{'='*70}")
    print(f"✅ IMPORTACIÓN COMPLETA" if not args.dry_run else f"🔍 DRY RUN COMPLETO")
    print(f"{'='*70}")
    print(f"Total citas: {total:,}")
    print(f"Importadas: {inserted:,}")
    print(f"Saltadas: {skipped:,}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    sys.exit(main())