import pandas as pd
from pathlib import Path
import csv

BASE_DIR = Path(__file__).resolve().parent
CURATED_DIR = BASE_DIR / "adriana_projects" / "data" / "curated"
CURATED_DIR.mkdir(parents=True, exist_ok=True)

XLSX_FILE = BASE_DIR / "Reporte_Maestro_Produccion_NF_Sanmina_AFL (1) (1).xlsx"

def extract_plan_accion():
    df = pd.read_excel(XLSX_FILE, sheet_name="📋 Plan de Acción")
    mask = df.isin(["Acción"]).any(axis=1)
    if not mask.any():
        print("Acción not found in Plan de Accion")
        return
    start_idx = df[mask].index[0]
    df_plan = df.iloc[start_idx+1:]
    df_plan.columns = df.iloc[start_idx]
    df_plan = df_plan.dropna(subset=['Acción'])
    
    rows = []
    for _, r in df_plan.iterrows():
        prioridad = str(r.get('Prioridad', '')).split(' ')[-1] if ' ' in str(r.get('Prioridad', '')) else r.get('Prioridad', '')
        status = 'pendiente' if r.get('Status', '') == '⬜' else 'completado'
        rows.append({
            'num': r.get('#', ''),
            'accion': r.get('Acción', ''),
            'linea': r.get('Línea', ''),
            'area': r.get('Área', ''),
            'prioridad': prioridad,
            'inicio': r.get('Inicio', ''),
            'fin': r.get('Fin', ''),
            'responsable': r.get('Resp.', ''),
            'recursos': r.get('Recursos', ''),
            'kpi': r.get('KPI', ''),
            'status': status
        })
    
    with open(CURATED_DIR / "plan_accion.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print("plan_accion.csv extracted.")

def extract_demanda():
    df = pd.read_excel(XLSX_FILE, sheet_name="📉 Antes vs Después")
    # Demanda is around row 34. Let's find "Programa" in any column
    mask = df.isin(["Programa"]).any(axis=1)
    if not mask.any():
        return
    start_idx = df[mask].index[0]
    df_demanda = df.iloc[start_idx+1:start_idx+9]
    df_demanda.columns = df.iloc[start_idx]
    
    rows = []
    for _, r in df_demanda.iterrows():
        rows.append({
            'programa': r.get('Programa', ''),
            'part_number': r.get('Part Number', ''),
            'dic': r.get('Dic', ''),
            'ene': r.get('Ene', ''),
            'feb': r.get('Feb', ''),
            'mar': r.get('Mar', ''),
            'abr': r.get('Abr', ''),
            'may': r.get('May', ''),
            'total': r.get('Total', ''),
            'pico': r.get('Pico mes', '')
        })
    
    with open(CURATED_DIR / "demanda_afl.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print("demanda_afl.csv extracted.")

def extract_balanceo():
    df = pd.read_excel(XLSX_FILE, sheet_name="📉 Antes vs Después")
    
    mask = df.isin(["Estación", "Estacion"]).any(axis=1)
    if not mask.any():
        return
    start_nf = df[mask].index[0]
    df_nf = df.iloc[start_nf+1:start_nf+8]
    # To avoid relying on exact column positions, let's just use the known values from the rows.
    # The columns are: nan, nan, Estación, CT Actual, CT Meta, Ahorro (seg), Ahorro %, Intervención, nan, Estación, CT Act, Ops, CT/Op, Meta CT/Op, Ops Meta, Acción
    cols = list(df.iloc[start_nf])
    # The left side is NF, the right side is Sanmina
    
    rows = []
    for i, r in df_nf.iterrows():
        row_vals = list(r)
        # NF is cols 2 to 7 (Estación, CT Actual, CT Meta, Ahorro)
        # We find indices dynamically
        estacion_idx = [j for j, v in enumerate(cols) if str(v).lower() in ('estación', 'estacion')]
        if len(estacion_idx) >= 2:
            nf_est_idx = estacion_idx[0]
            sm_est_idx = estacion_idx[1]
            
            # NF
            ct_actual_nf = row_vals[nf_est_idx+1]
            ct_meta_nf = row_vals[nf_est_idx+2]
            ahorro_nf = row_vals[nf_est_idx+3]
            try:
                if str(ahorro_nf) in ('—', 'nan', ''):
                    ahorro_nf = float(ct_actual_nf) - float(ct_meta_nf)
            except:
                ahorro_nf = 0
            
            if pd.notna(row_vals[nf_est_idx]) and str(row_vals[nf_est_idx]).strip():
                rows.append({
                    'linea': 'NORTHFACE',
                    'estacion': row_vals[nf_est_idx],
                    'ct_actual': ct_actual_nf,
                    'ct_meta': ct_meta_nf,
                    'takt': 2821, # Hardcoded takt as seen in sheet
                    'ahorro_seg': ahorro_nf
                })
            
            # Sanmina
            # Estación, CT Act, Ops, CT/Op, Meta CT/Op, Ops Meta, Acción
            ct_act_sm = row_vals[sm_est_idx+1]
            ct_op_sm = row_vals[sm_est_idx+3]
            meta_ct_op_sm = row_vals[sm_est_idx+4]
            try:
                ahorro_sm = float(ct_op_sm) - float(meta_ct_op_sm)
            except:
                ahorro_sm = 0
                
            if pd.notna(row_vals[sm_est_idx]) and str(row_vals[sm_est_idx]).strip():
                rows.append({
                    'linea': 'SANMINA',
                    'estacion': row_vals[sm_est_idx],
                    'ct_actual': ct_op_sm,
                    'ct_meta': meta_ct_op_sm,
                    'takt': 2217,
                    'ahorro_seg': ahorro_sm
                })
                
    with open(CURATED_DIR / "balanceo_lineas.csv", "w", newline="", encoding="utf-8") as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
    print("balanceo_lineas.csv extracted.")

def extract_desperdicios():
    df = pd.read_excel(XLSX_FILE, sheet_name="📊 Desperdicios & Insights")
    mask = df.isin(["Categoría", "Categoria"]).any(axis=1)
    if not mask.any():
        return
    start_idx = df[mask].index[0]
    df_desp = df.iloc[start_idx+1:start_idx+7]
    df_desp.columns = df.iloc[start_idx]
    
    rows = []
    for _, r in df_desp.iterrows():
        pct = str(r.get('%', ''))
        pct = pct.replace('%', '').strip()
        cat = r.get('Categoría', r.get('Categoria', ''))
        if pd.notna(cat) and str(cat).strip():
            rows.append({
                'categoria': cat,
                'tiempo_seg': r.get('Tiempo (seg)', ''),
                'pct': pct
            })
        
    with open(CURATED_DIR / "desperdicios.csv", "w", newline="", encoding="utf-8") as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
    print("desperdicios.csv extracted.")

def extract_throughput():
    df = pd.read_excel(XLSX_FILE, sheet_name="📊 Desperdicios & Insights")
    mask = df.isin(["Escenario"]).any(axis=1)
    if not mask.any():
        return
    start_idx = df[mask].index[0]
    df_tp = df.iloc[start_idx+1:start_idx+6]
    df_tp.columns = df.iloc[start_idx]
    
    rows = []
    for _, r in df_tp.iterrows():
        esc = r.get('Escenario', '')
        if pd.notna(esc) and str(esc).strip():
            rows.append({
                'etapa': esc,
                'pzas_hr': r.get('Pzas/turno', '')
            })
        
    with open(CURATED_DIR / "throughput_mejoras.csv", "w", newline="", encoding="utf-8") as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
    print("throughput_mejoras.csv extracted.")

def extract_stations():
    df = pd.read_excel(XLSX_FILE, sheet_name="📉 Cuellos & Balanceo")
    
    mask = df.isin(["Estación", "Estacion"]).any(axis=1)
    if not mask.any():
        return
    start_idx = df[mask].index[0]
    df_sm = df.iloc[start_idx+1:start_idx+8]
    cols = list(df.iloc[start_idx])
    
    rows = []
    station_id = 1
    for i, r in df_sm.iterrows():
        row_vals = list(r)
        estacion_idx = [j for j, v in enumerate(cols) if str(v).lower() in ('estación', 'estacion')]
        if len(estacion_idx) >= 2:
            sm_est_idx = estacion_idx[1]
            
            est_name = row_vals[sm_est_idx]
            ops = row_vals[sm_est_idx+1]
            ct_act_sm = row_vals[sm_est_idx+2]
            # action can be derived from status or just leave it empty or map it
            status = row_vals[sm_est_idx+6] if len(row_vals) > sm_est_idx+6 else ""
            
            if pd.notna(est_name) and str(est_name).strip():
                rows.append({
                    'station_id': station_id,
                    'station_name': est_name,
                    'time_seconds': ct_act_sm,
                    'operators': ops,
                    'observations': status,
                    'action': ''
                })
                station_id += 1
                
    with open(BASE_DIR / "data" / "stations.csv", "w", newline="", encoding="utf-8") as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
    print("stations.csv extracted.")

if __name__ == "__main__":
    extract_plan_accion()
    extract_demanda()
    extract_balanceo()
    extract_desperdicios()
    extract_throughput()
    extract_stations()
