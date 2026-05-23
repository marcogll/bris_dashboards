import csv
import json
import re
from pathlib import Path
from typing import Iterable

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "adriana_projects" / "data"
RAW_DIR = OUT_DIR / "raw_csv"
CURATED_DIR = OUT_DIR / "curated"


def slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    return re.sub(r"_+", "_", value).strip("_") or "sheet"


def clean_cell(value):
    if pd.isna(value):
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value).strip()


def clean_number(value):
    value = clean_cell(value).replace(",", "")
    if not value:
        return ""
    try:
        return float(value)
    except ValueError:
        return ""


def normalize_column(value: str, fallback: str) -> str:
    value = clean_cell(value)
    if not value:
        value = fallback
    value = value.replace("\n", " ")
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value.lower()).strip("_")
    return value or fallback


def unique_columns(columns: Iterable[str]) -> list[str]:
    seen = {}
    result = []
    for index, col in enumerate(columns):
        base = normalize_column(col, f"column_{index + 1}")
        count = seen.get(base, 0)
        seen[base] = count + 1
        result.append(base if count == 0 else f"{base}_{count + 1}")
    return result


def detect_header_row(df: pd.DataFrame, keywords: set[str] | None = None) -> int:
    keywords = keywords or set()
    best_row = 0
    best_score = -1
    for idx in range(min(15, len(df))):
        row = [clean_cell(value).lower() for value in df.iloc[idx].tolist()]
        non_empty = sum(bool(value) for value in row)
        hits = sum(any(keyword in value for keyword in keywords) for value in row)
        score = hits * 10 + non_empty
        if score > best_score:
            best_row = idx
            best_score = score
    return best_row


def dataframe_with_header(file: Path, sheet: str, keywords: set[str]) -> pd.DataFrame:
    raw = pd.read_excel(file, sheet_name=sheet, header=None)
    if raw.empty:
        return pd.DataFrame()
    header_row = detect_header_row(raw, keywords)
    data = raw.iloc[header_row + 1 :].copy()
    data.columns = unique_columns(raw.iloc[header_row].tolist())
    data = data.dropna(how="all")
    data = data.fillna("")
    return data


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def get(row: pd.Series, *names: str):
    for name in names:
        if name in row and clean_cell(row[name]):
            return row[name]
    return ""


def export_raw_sheet(file: Path, sheet: str, df: pd.DataFrame) -> dict:
    raw_name = f"{slug(file.stem)}__{slug(sheet)}.csv"
    raw_path = RAW_DIR / raw_name
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(raw_path, index=False, header=False, encoding="utf-8")
    non_empty_rows = int(df.dropna(how="all").shape[0])
    return {
        "source_file": file.name,
        "sheet_name": sheet,
        "raw_csv": str(raw_path.relative_to(ROOT)),
        "row_count": non_empty_rows,
        "column_count": int(df.shape[1]),
    }


def build() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    CURATED_DIR.mkdir(parents=True, exist_ok=True)

    manifest = []
    raw_rows = []
    bom_rows = []
    pfep_rows = []
    work_center_rows = []
    station_rows = []
    kanban_rows = []
    part_numbers = {}

    files = sorted(ROOT.glob("*.xls*"))
    for file in files:
        xl = pd.ExcelFile(file)
        for sheet in xl.sheet_names:
            raw = pd.read_excel(file, sheet_name=sheet, header=None)
            if raw.empty:
                continue

            manifest.append(export_raw_sheet(file, sheet, raw))
            for row_index, row in raw.fillna("").iterrows():
                values = [clean_cell(value) for value in row.tolist()]
                if any(values):
                    raw_rows.append(
                        {
                            "source_file": file.name,
                            "sheet_name": sheet,
                            "row_number": row_index + 1,
                            "row_json": json.dumps(values, ensure_ascii=False),
                        }
                    )

            sheet_key = sheet.lower().strip()

            if sheet_key == "bom":
                df = dataframe_with_header(
                    file,
                    sheet,
                    {"parent", "component", "description", "req", "vendor", "lead"},
                )
                for _, row in df.iterrows():
                    component = clean_cell(get(row, "component"))
                    parent = clean_cell(get(row, "parent"))
                    if not component and not parent:
                        continue
                    description = clean_cell(get(row, "description1", "description_11"))
                    bom_rows.append(
                        {
                            "source_file": file.name,
                            "sheet_name": sheet,
                            "level_code": clean_cell(get(row, "level")),
                            "parent_part": parent,
                            "backlog": clean_number(get(row, "backlog")),
                            "component_part": component,
                            "status": clean_cell(get(row, "status")),
                            "process_initial": clean_cell(get(row, "proceso_inicial")),
                            "description": description,
                            "required_qty": clean_number(get(row, "req")),
                            "uom": clean_cell(get(row, "u_m")),
                            "on_hand": clean_number(get(row, "on_hand")),
                            "on_order": clean_number(get(row, "on_ord")),
                            "committed": clean_number(get(row, "comm")),
                            "available": clean_number(get(row, "avail")),
                            "lead_time_days": clean_number(get(row, "lead_time")),
                            "vendor_name": clean_cell(get(row, "vendor_name")),
                            "program": clean_cell(get(row, "programa")),
                        }
                    )
                    if component:
                        part_numbers.setdefault(component, description)

            if sheet_key in {"plan for every part", "pfep"}:
                df = dataframe_with_header(
                    file,
                    sheet,
                    {"model", "operator", "station", "component", "quantity", "cart", "bin"},
                )
                for _, row in df.iterrows():
                    component = clean_cell(get(row, "component", "sub_component"))
                    if not component:
                        continue
                    pfep_rows.append(
                        {
                            "source_file": file.name,
                            "sheet_name": sheet,
                            "model": clean_cell(get(row, "model", "part")),
                            "operator_no": clean_number(get(row, "operator")),
                            "station_no": clean_number(get(row, "station")),
                            "cart": clean_cell(get(row, "cart", "cart_id")),
                            "bin_location": clean_cell(get(row, "bin", "bin_location")),
                            "step_no": clean_cell(get(row, "step", "sop_step")),
                            "component_part": component,
                            "quantity": clean_number(get(row, "quantity")),
                            "process_route": clean_cell(get(row, "process_route")),
                            "width": clean_number(get(row, "widht", "width")),
                            "depth": clean_number(get(row, "depth")),
                            "height": clean_number(get(row, "height")),
                            "volume": clean_number(get(row, "in3", "volume")),
                            "storage": clean_cell(get(row, "storage", "container_type")),
                            "bin_model": clean_cell(get(row, "bin_model", "part_size_class")),
                            "bin_capacity": clean_number(get(row, "bin_capacity", "cointainer_capacity")),
                            "batch_size": clean_number(get(row, "batch_size", "batch_size_in_days")),
                            "days_of_stock": clean_number(get(row, "days_of_stock")),
                            "required_bins": clean_number(get(row, "required_bins")),
                            "assembled_using": clean_cell(get(row, "assembled_using", "criteria")),
                            "tool_used": clean_cell(get(row, "tool_used_to_assemble")),
                        }
                    )
                    part_numbers.setdefault(component, "")

            if sheet_key in {"assy wc", "assy_wc"}:
                df = dataframe_with_header(
                    file,
                    sheet,
                    {"process", "parent", "work", "standard", "crew", "description"},
                )
                for _, row in df.iterrows():
                    process_sheet = clean_cell(get(row, "process_sheet_number"))
                    work_center = clean_cell(get(row, "work_center_vendor"))
                    if not process_sheet and not work_center:
                        continue
                    work_center_rows.append(
                        {
                            "source_file": file.name,
                            "sheet_name": sheet,
                            "process_sheet_number": process_sheet,
                            "end_item_part": clean_cell(get(row, "enditempartnumber")),
                            "parent_part": clean_cell(get(row, "parent")),
                            "work_center": work_center,
                            "step_number": clean_cell(get(row, "step_number")),
                            "run_setup": clean_cell(get(row, "run_setup")),
                            "operation_code": clean_cell(get(row, "operation_code")),
                            "component_part": clean_cell(get(row, "component_part_number")),
                            "description": clean_cell(get(row, "description_11", "description")),
                            "standard_rate": clean_number(get(row, "standard_rate")),
                            "lead_time": clean_number(get(row, "lead_time")),
                            "crew_size": clean_number(get(row, "crew_size")),
                        }
                    )

            if "est." in sheet_key or "northface" in file.stem.lower() or "north face" in file.stem.lower():
                df = dataframe_with_header(
                    file,
                    sheet,
                    {"pasos", "numeros", "parte", "unidades", "rack", "herramental"},
                )
                for _, row in df.iterrows():
                    part = clean_cell(get(row, "np_involucrados", "numeros_de_parte", "component"))
                    step = clean_cell(get(row, "pasos", "pasos_7_24", "step"))
                    if not part and not step:
                        continue
                    station_rows.append(
                        {
                            "source_file": file.name,
                            "sheet_name": sheet,
                            "station_name": sheet,
                            "step": step,
                            "rack_location": clean_cell(get(row, "lugar_en_el_rack")),
                            "part_number": part,
                            "units": clean_number(get(row, "unidades", "quantity")),
                            "total_pieces": clean_number(get(row, "piezas_totales_por_20")),
                            "class_code": clean_cell(get(row, "clase_a_b_c")),
                            "tooling": clean_cell(get(row, "herramental", "tool_used_to_assemble")),
                            "notes": clean_cell(get(row, "2_surtir_el_material_por_orden_en_el_rack_requerido_para_el_requerimiento_del_dia")),
                        }
                    )
                    if part:
                        part_numbers.setdefault(part, "")

            if sheet_key == "notificacion":
                df = dataframe_with_header(file, sheet, {"p", "left", "owner"})
                for _, row in df.iterrows():
                    part = clean_cell(get(row, "p_number"))
                    if not part:
                        continue
                    kanban_rows.append(
                        {
                            "source_file": file.name,
                            "sheet_name": sheet,
                            "part_number": part,
                            "days_left": clean_number(get(row, "left")),
                            "owner": clean_cell(get(row, "owner")),
                        }
                    )
                    part_numbers.setdefault(part, "")

    write_csv(CURATED_DIR / "source_sheets.csv", manifest, ["source_file", "sheet_name", "raw_csv", "row_count", "column_count"])
    write_csv(CURATED_DIR / "raw_rows.csv", raw_rows, ["source_file", "sheet_name", "row_number", "row_json"])
    write_csv(CURATED_DIR / "bom_items.csv", bom_rows, [
        "source_file", "sheet_name", "level_code", "parent_part", "backlog", "component_part", "status",
        "process_initial", "description", "required_qty", "uom", "on_hand", "on_order", "committed",
        "available", "lead_time_days", "vendor_name", "program",
    ])
    write_csv(CURATED_DIR / "pfep_items.csv", pfep_rows, [
        "source_file", "sheet_name", "model", "operator_no", "station_no", "cart", "bin_location", "step_no",
        "component_part", "quantity", "process_route", "width", "depth", "height", "volume", "storage",
        "bin_model", "bin_capacity", "batch_size", "days_of_stock", "required_bins", "assembled_using", "tool_used",
    ])
    write_csv(CURATED_DIR / "work_center_operations.csv", work_center_rows, [
        "source_file", "sheet_name", "process_sheet_number", "end_item_part", "parent_part", "work_center",
        "step_number", "run_setup", "operation_code", "component_part", "description", "standard_rate",
        "lead_time", "crew_size",
    ])
    write_csv(CURATED_DIR / "station_materials.csv", station_rows, [
        "source_file", "sheet_name", "station_name", "step", "rack_location", "part_number", "units",
        "total_pieces", "class_code", "tooling", "notes",
    ])
    write_csv(CURATED_DIR / "kanban_notifications.csv", kanban_rows, ["source_file", "sheet_name", "part_number", "days_left", "owner"])
    write_csv(
        CURATED_DIR / "parts.csv",
        [{"part_number": part, "description": description} for part, description in sorted(part_numbers.items())],
        ["part_number", "description"],
    )

    summary = {
        "source_sheets": len(manifest),
        "raw_rows": len(raw_rows),
        "parts": len(part_numbers),
        "bom_items": len(bom_rows),
        "pfep_items": len(pfep_rows),
        "work_center_operations": len(work_center_rows),
        "station_materials": len(station_rows),
        "kanban_notifications": len(kanban_rows),
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    build()
