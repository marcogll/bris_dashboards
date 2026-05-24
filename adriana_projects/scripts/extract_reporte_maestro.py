#!/usr/bin/env python3
"""
Extractor del Reporte Maestro de Producción NF/Sanmina/AFL.
Lee el Excel maestro y genera/actualiza todos los CSVs curados.
"""

import json
import logging
import sys
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("extract_reporte_maestro")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAW_FILE = BASE_DIR / "data" / "raw" / "Reporte_Maestro_Produccion_NF_Sanmina_AFL (1) (1).xlsx"
CURATED_DIR = BASE_DIR / "adriana_projects" / "data" / "curated"
FALLBACKS_DIR = BASE_DIR / "data" / "fallbacks"


def save_csv(df: pd.DataFrame, name: str) -> None:
    path = CURATED_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")
    logger.info("Guardado %s (%d filas)", path.name, len(df))


def save_json(data: list[dict], name: str) -> None:
    path = FALLBACKS_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Guardado fallback %s", path.name)


def extract_kpis_unificados(xl: pd.ExcelFile) -> pd.DataFrame:
    df = xl.parse("📈 KPIs Unificados", header=1)
    df = df.iloc[1:].reset_index(drop=True)
    df = df.iloc[:, 1:].copy()
    df.columns = [
        "kpi", "northface_actual", "northface_meta",
        "sanmina_actual", "sanmina_meta",
        "afl_actual", "afl_meta", "status", "accion"
    ]
    return df.dropna(subset=["kpi"]).reset_index(drop=True)


def extract_cuellos_balanceo(xl: pd.ExcelFile) -> pd.DataFrame:
    df = xl.parse("📉 Cuellos & Balanceo", header=3)
    # Tabla NORTHFACE: cols 1-6 (col 0 es vacia)
    nf = df.iloc[:, 1:7].copy()
    nf.columns = ["estacion", "ct_actual", "takt", "delta", "pct_utilizacion", "status"]
    nf = nf.dropna(subset=["estacion"])
    nf["linea"] = "NORTHFACE"
    nf["status"] = nf["status"].astype(str).str.strip()

    # Tabla SANMINA: cols 8-14 (col 7 es vacia)
    sm = df.iloc[:, 8:15].copy()
    sm.columns = ["estacion", "ops", "ct_actual", "takt", "ct_op", "pct_takt", "status"]
    sm = sm.dropna(subset=["estacion"])
    sm["linea"] = "SANMINA"
    sm["status"] = sm["status"].astype(str).str.strip()

    # Unificar
    nf["ops"] = None
    nf["ct_op"] = None
    nf["pct_takt"] = None
    sm["delta"] = None
    sm["pct_utilizacion"] = None
    cols = ["linea", "estacion", "ct_actual", "takt", "delta", "pct_utilizacion", "status", "ops", "ct_op", "pct_takt"]
    return pd.concat([nf[cols], sm[cols]], ignore_index=True)


def extract_desperdicios(xl: pd.ExcelFile) -> pd.DataFrame:
    df = xl.parse("📊 Desperdicios & Insights", header=3)
    df = df.iloc[:, 1:6].copy()  # col 0 es vacia
    df.columns = ["categoria", "tiempo_seg", "pct", "causa_raiz", "accion"]
    # Solo filas donde pct contenga % (las primeras 6 categorias)
    df = df[df["pct"].astype(str).str.contains("%", na=False)].reset_index(drop=True)
    df["pct"] = df["pct"].astype(str).str.replace("%", "").astype(float)
    df["tiempo_seg"] = pd.to_numeric(df["tiempo_seg"], errors="coerce").fillna(0)
    return df


def extract_antes_despues(xl: pd.ExcelFile) -> pd.DataFrame:
    df = xl.parse("📉 Antes vs Después", header=3)
    nf = df.iloc[:, 0:6].copy()
    nf.columns = ["estacion", "ct_actual", "ct_meta", "ahorro_seg", "ahorro_pct", "intervencion"]
    nf = nf.dropna(subset=["estacion"])
    nf["linea"] = "NORTHFACE"

    sm = df.iloc[:, 7:13].copy()
    sm.columns = ["estacion", "ops", "ct_actual", "ct_op", "ops_meta", "accion"]
    sm = sm.dropna(subset=["estacion"])
    sm["linea"] = "SANMINA"

    nf_out = nf[["linea", "estacion", "ct_actual", "ct_meta", "ahorro_seg", "intervencion"]].copy()
    nf_out["ops"] = None
    nf_out["accion_sm"] = None

    sm_out = sm[["linea", "estacion", "ct_actual"]].copy()
    sm_out["ct_meta"] = None
    sm_out["ahorro_seg"] = None
    sm_out["intervencion"] = sm["accion"]
    sm_out["ops"] = sm["ops"]
    sm_out["accion_sm"] = sm["accion"]

    cols = ["linea", "estacion", "ct_actual", "ct_meta", "ahorro_seg", "intervencion", "ops", "accion_sm"]
    return pd.concat([nf_out[cols], sm_out[cols]], ignore_index=True)


def extract_plan_accion(xl: pd.ExcelFile) -> pd.DataFrame:
    df = xl.parse("📋 Plan de Acción", header=1)
    df = df.iloc[:, 1:].copy()  # quitar Unnamed: 0
    df.columns = ["num", "accion", "linea", "area", "prioridad", "inicio", "fin", "responsable", "recursos", "kpi", "status"]
    df = df.dropna(subset=["num"]).reset_index(drop=True)
    df["prioridad"] = df["prioridad"].astype(str).str.replace("🔴 ", "").str.replace("🟠 ", "").str.replace("🟢 ", "").str.strip()
    df["status"] = df["status"].astype(str).str.replace("⬜", "pendiente").str.replace("✅", "completado").str.strip()
    df["num"] = pd.to_numeric(df["num"], errors="coerce").fillna(0).astype(int)
    return df


def extract_herramental(xl: pd.ExcelFile) -> pd.DataFrame:
    df = xl.parse("🔩 Herramental", header=1)
    df = df.iloc[:, 1:].copy()
    df.columns = ["linea", "estacion", "herramienta", "especificacion", "uso", "torque_config", "cantidad", "tipo", "observaciones"]
    return df.dropna(subset=["linea"]).reset_index(drop=True)


def extract_layout_racks(xl: pd.ExcelFile) -> pd.DataFrame:
    df = xl.parse("📐 Layout Racks", header=1)
    df = df.iloc[1:, 1:].reset_index(drop=True)  # saltar fila titulo + col vacia
    df.columns = ["workstation", "rack_id", "cart_id", "tipo_bin", "num_partes", "numero_parte", "proceso", "peso", "operador", "estacion_nf"]
    return df.dropna(subset=["workstation"]).reset_index(drop=True)


def extract_etiquetas_bins(xl: pd.ExcelFile) -> pd.DataFrame:
    df = xl.parse("🏷️ Etiquetas Bins", header=1)
    df = df.iloc[:, 1:6].copy()  # solo primeras 5 cols de datos
    df.columns = ["tipo_bin", "nombre", "contenido", "ubicacion", "material"]
    return df.dropna(subset=["tipo_bin"]).reset_index(drop=True)


def extract_flujo_proceso(xl: pd.ExcelFile) -> pd.DataFrame:
    df = xl.parse("🔄 Flujo de Proceso", header=1)
    df = df.iloc[:, 1:].copy()
    df.columns = ["northface", "nf_obs", "sanmina", "sm_obs", "kantishna", "kn_obs"]
    return df.dropna(how="all").reset_index(drop=True)


def extract_estaciones_nf(xl: pd.ExcelFile) -> pd.DataFrame:
    df = xl.parse("🔧 Estaciones NF", header=1)
    df = df.iloc[:, 1:].copy()
    df.columns = ["num", "actividad", "op", "bec_s", "work_s", "caminata_s", "espera_s", "total_s", "herramental_pn"]
    return df.dropna(subset=["actividad"]).reset_index(drop=True)


def extract_estaciones_sanmina(xl: pd.ExcelFile) -> pd.DataFrame:
    df = xl.parse("🔧 Estaciones Sanmina", header=1)
    df = df.iloc[:, 1:].copy()
    df.columns = ["num", "actividad", "op", "material_pn", "herramental", "ct_seg", "ct_min", "pzas_hr", "observaciones", "accion"]
    return df.dropna(subset=["actividad"]).reset_index(drop=True)


def extract_dashboard_resumen(xl: pd.ExcelFile) -> pd.DataFrame:
    df = xl.parse("📊 Dashboard", header=3)
    df = df.dropna(how="all").reset_index(drop=True)
    return df


def main() -> int:
    if not RAW_FILE.exists():
        logger.error("No encontrado: %s", RAW_FILE)
        return 1

    logger.info("Leyendo %s ...", RAW_FILE.name)
    xl = pd.ExcelFile(RAW_FILE)
    logger.info("Hojas encontradas: %s", xl.sheet_names)

    save_csv(extract_kpis_unificados(xl), "kpis_unificados.csv")
    save_csv(extract_cuellos_balanceo(xl), "balanceo_lineas.csv")
    save_csv(extract_desperdicios(xl), "desperdicios.csv")
    save_csv(extract_antes_despues(xl), "balanceo_antes_despues.csv")
    save_csv(extract_plan_accion(xl), "plan_accion.csv")
    save_csv(extract_herramental(xl), "herramental.csv")
    save_csv(extract_layout_racks(xl), "layout_racks.csv")
    for name, extractor in [
        ("etiquetas_bins.csv", extract_etiquetas_bins),
        ("flujo_proceso.csv", extract_flujo_proceso),
        ("estaciones_nf.csv", extract_estaciones_nf),
        ("estaciones_sanmina.csv", extract_estaciones_sanmina),
        ("dashboard_resumen.csv", extract_dashboard_resumen),
    ]:
        try:
            save_csv(extractor(xl), name)
        except Exception as exc:
            logger.warning("No se pudo extraer %s: %s", name, exc)

    # Fallbacks JSON de los principales
    desperdicios = extract_desperdicios(xl)
    plan = extract_plan_accion(xl)
    save_json(desperdicios.to_dict("records"), "desperdicios.json")
    save_json(plan.to_dict("records"), "plan_accion.json")

    logger.info("Extraction completa. Archivos en %s", CURATED_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
