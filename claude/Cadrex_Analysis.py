#!/usr/bin/env python3
"""
CADREX Data & Dashboard Hub — Script de Análisis de Producción
Gerencia de Producción · Adriana Ramos · Planta Saltillo
Mayo 2026
"""

import json
import math
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime

# ── Paleta Catppuccin Latte (para terminales con color ANSI) ──────────────────
class Color:
    BLUE   = "\033[94m"
    GREEN  = "\033[92m"
    RED    = "\033[91m"
    YELLOW = "\033[93m"
    CYAN   = "\033[96m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    RESET  = "\033[0m"

# ── Modelos de datos ──────────────────────────────────────────────────────────

@dataclass
class Estacion:
    id: str
    ct_seg: float
    takt_seg: float
    operador: str = ""
    downtime_seg_evento: Optional[float] = None
    causa_downtime: str = ""
    flex_disponibilidad_pct: Optional[float] = None
    cubre_estaciones: list = field(default_factory=list)

    @property
    def pct_takt(self) -> float:
        return round((self.ct_seg / self.takt_seg) * 100, 1) if self.takt_seg else 0

    @property
    def delta_ct(self) -> float:
        return round(self.ct_seg - self.takt_seg, 1)

    @property
    def estado(self) -> str:
        if self.pct_takt > 100:
            return "CRITICO"
        if self.flex_disponibilidad_pct and self.flex_disponibilidad_pct > 50:
            return "FLEX"
        return "OK"

    @property
    def tiempo_libre_seg(self) -> float:
        return max(0, self.takt_seg - self.ct_seg)

    def resumen(self) -> dict:
        return {
            "id": self.id,
            "operador": self.operador,
            "ct_seg": self.ct_seg,
            "takt_seg": self.takt_seg,
            "delta_ct": self.delta_ct,
            "pct_takt": self.pct_takt,
            "estado": self.estado,
        }


@dataclass
class Linea:
    id: str
    nombre: str
    takt_seg: float
    num_operadores: int
    oee_pct: float
    turno_min: int = 480
    precio_unitario_usd: float = 120.0
    estaciones: list[Estacion] = field(default_factory=list)

    @property
    def tiempo_turno_seg(self) -> float:
        return self.turno_min * 60

    @property
    def capacidad_teorica_pzas(self) -> float:
        return round(self.tiempo_turno_seg / self.takt_seg, 2)

    @property
    def capacidad_real_pzas(self) -> float:
        return round(self.capacidad_teorica_pzas * (self.oee_pct / 100), 2)

    @property
    def ct_bottleneck(self) -> Optional[float]:
        cts = [e.ct_seg for e in self.estaciones]
        return max(cts) if cts else None

    @property
    def estacion_bottleneck(self) -> Optional[str]:
        if not self.estaciones:
            return None
        return max(self.estaciones, key=lambda e: e.ct_seg).id

    @property
    def estaciones_criticas(self) -> list[Estacion]:
        return [e for e in self.estaciones if e.pct_takt > 100]

    @property
    def estaciones_flex(self) -> list[Estacion]:
        return [e for e in self.estaciones if e.estado == "FLEX"]

    @property
    def eficiencia_promedio_pct(self) -> float:
        if not self.estaciones:
            return 0.0
        return round(sum(e.pct_takt for e in self.estaciones) / len(self.estaciones), 1)

    @property
    def valor_por_turno_usd(self) -> float:
        return round(self.capacidad_real_pzas * self.precio_unitario_usd, 2)

    def resumen(self) -> dict:
        return {
            "linea": self.nombre,
            "takt_seg": self.takt_seg,
            "operadores": self.num_operadores,
            "oee_pct": self.oee_pct,
            "capacidad_teorica": self.capacidad_teorica_pzas,
            "capacidad_real": self.capacidad_real_pzas,
            "bottleneck_estacion": self.estacion_bottleneck,
            "bottleneck_ct_seg": self.ct_bottleneck,
            "eficiencia_promedio_pct": self.eficiencia_promedio_pct,
            "valor_turno_usd": self.valor_por_turno_usd,
        }


@dataclass
class Fase:
    numero: int
    nombre: str
    periodo: str
    inversion_usd: float
    beneficio_usd: float
    actividades: list[dict] = field(default_factory=list)

    @property
    def roi_neto_usd(self) -> float:
        return self.beneficio_usd - self.inversion_usd

    @property
    def roi_pct(self) -> float:
        if self.inversion_usd == 0:
            return float('inf')
        return round((self.roi_neto_usd / self.inversion_usd) * 100, 1)


# ── Datos de producción ───────────────────────────────────────────────────────

def cargar_lineas() -> list[Linea]:
    nf = Linea(
        id="NF", nombre="Northface", takt_seg=2821,
        num_operadores=9, oee_pct=68.0,
        estaciones=[
            Estacion("Est1", 820,  2821, "Op-1"),
            Estacion("Est2", 1240, 2821, "Op-2"),
            Estacion("Est3", 1650, 2821, "Op-3"),
            Estacion("Est4", 2100, 2821, "Op-4", downtime_seg_evento=1906, causa_downtime="Falla SK41H"),
            Estacion("Est5", 876,  2821, "Op-5", flex_disponibilidad_pct=69.0, cubre_estaciones=["Est3","Est6"]),
            Estacion("Est6", 4923, 2821, "Op-6"),
            Estacion("Est7", 1180, 2821, "Op-7"),
            Estacion("Est8", 940,  2821, "Op-8"),
            Estacion("Est9", 680,  2821, "Op-9"),
        ]
    )
    san = Linea(
        id="SAN", nombre="Sanmina", takt_seg=2217,
        num_operadores=8, oee_pct=72.0,
        estaciones=[
            Estacion("Est1", 650,  2217, "Op-A"),
            Estacion("Est2", 980,  2217, "Op-B"),
            Estacion("Est3", 50,   2217, "Op-E", flex_disponibilidad_pct=97.7, cubre_estaciones=["Est4","Est6"]),
            Estacion("Est4", 1420, 2217, "Op-C"),
            Estacion("Est5", 770,  2217, "Op-D"),
            Estacion("Est6", 2820, 2217, "Op-F"),
            Estacion("Est7", 1050, 2217, "Op-G"),
            Estacion("Est8", 810,  2217, "Op-H"),
            Estacion("Est9", 590,  2217, "Op-I"),
        ]
    )
    kan = Linea(id="KAN", nombre="Kantishna", takt_seg=2217, num_operadores=7, oee_pct=74.0)
    afl = Linea(id="AFL", nombre="AFL",       takt_seg=2821, num_operadores=6, oee_pct=71.0)
    return [nf, san, kan, afl]


def cargar_fases() -> list[Fase]:
    return [
        Fase(1, "Inmediato",    "0-30 días",  0,     18000,
             [{"id":"F1-01","actividad":"Cantado PN×PN en todas las líneas"},
              {"id":"F1-02","actividad":"Flex-Op: Op-5 → Est3 y Est6 NF"},
              {"id":"F1-03","actividad":"WIP ≤ 3 pzas (señalética)"},
              {"id":"F1-04","actividad":"MP herramental SK41H Est4 NF"},
              {"id":"F1-05","actividad":"Capacitación supervisores Dashboard+Bot"},
              {"id":"F1-06","actividad":"Andon visual Est6 cuando CT > Takt"}]),
        Fase(2, "Corto Plazo",  "1-3 meses",  8000,  35000,
             [{"id":"F2-01","actividad":"Shadow boards herramental"},
              {"id":"F2-02","actividad":"Certificar ops en 2+ estaciones"},
              {"id":"F2-03","actividad":"Balanceo SAN: Est6 → Est4/5"},
              {"id":"F2-04","actividad":"First Article Inspection x modelo"},
              {"id":"F2-05","actividad":"Reuniones diarias KPIs"},
              {"id":"F2-06","actividad":"Bot → Dashboard tiempo real"}]),
        Fase(3, "Mediano Plazo","3-6 meses",  25000, 77520,
             [{"id":"F3-01","actividad":"Rediseño layout Est6 NF"},
              {"id":"F3-02","actividad":"Automatización parcial subensamble (cobot)"},
              {"id":"F3-03","actividad":"OEE ≥ 85% todas las líneas"},
              {"id":"F3-04","actividad":"AFL: cantado completo certificado"},
              {"id":"F3-05","actividad":"Estándar de trabajo 4 líneas"},
              {"id":"F3-06","actividad":"Revisión formal ROI — Q3 2026"}]),
    ]


# ── Funciones de análisis ─────────────────────────────────────────────────────

def calcular_perdida_por_bottleneck(linea: Linea) -> dict:
    if not linea.estaciones:
        return {}
    bn = max(linea.estaciones, key=lambda e: e.ct_seg)
    pzas_perdidas_turno = (bn.ct_seg - linea.takt_seg) / linea.takt_seg * linea.capacidad_real_pzas
    valor_perdido_turno = pzas_perdidas_turno * linea.precio_unitario_usd
    return {
        "linea": linea.nombre,
        "estacion_bottleneck": bn.id,
        "ct_seg": bn.ct_seg,
        "takt_seg": linea.takt_seg,
        "exceso_seg": bn.delta_ct,
        "pct_takt": bn.pct_takt,
        "pzas_perdidas_por_turno": round(pzas_perdidas_turno, 2),
        "valor_perdido_por_turno_usd": round(valor_perdido_turno, 2),
        "valor_perdido_por_anio_usd": round(valor_perdido_turno * 240, 2),
    }


def calcular_oportunidad_flex(linea: Linea) -> list[dict]:
    resultados = []
    for est in linea.estaciones:
        if est.estado == "FLEX" and est.cubre_estaciones:
            tiempo_disponible = est.takt_seg - est.ct_seg
            pzas_adicionales_posibles = tiempo_disponible / linea.takt_seg
            resultados.append({
                "linea": linea.nombre,
                "operador": est.operador,
                "estacion_base": est.id,
                "ct_seg": est.ct_seg,
                "tiempo_libre_seg": round(tiempo_disponible, 0),
                "disponibilidad_pct": round((tiempo_disponible / linea.takt_seg) * 100, 1),
                "cubre_estaciones": est.cubre_estaciones,
                "capacidad_adicional_pzas": round(pzas_adicionales_posibles, 2),
            })
    return resultados


def calcular_roi_acumulado(fases: list[Fase]) -> list[dict]:
    acumulado_inv = 0
    acumulado_ben = 0
    resultado = []
    for f in fases:
        acumulado_inv += f.inversion_usd
        acumulado_ben += f.beneficio_usd
        resultado.append({
            "fase": f.numero,
            "nombre": f.nombre,
            "inversion_acumulada_usd": acumulado_inv,
            "beneficio_acumulado_usd": acumulado_ben,
            "roi_neto_acumulado_usd": acumulado_ben - acumulado_inv,
            "roi_pct": round(((acumulado_ben - acumulado_inv) / acumulado_inv * 100) if acumulado_inv > 0 else float('inf'), 1),
        })
    return resultado


def calcular_impacto_cantado(lineas: list[Linea], error_rate_actual_pct: float = 3.5) -> dict:
    total_material_events = sum(len(l.estaciones) * 3 for l in lineas)
    errores_actuales = round(total_material_events * error_rate_actual_pct / 100, 1)
    costo_por_error_usd = 120 * 0.15
    ahorro_anual_usd = round(errores_actuales * costo_por_error_usd * 240, 2)
    return {
        "eventos_material_por_turno": total_material_events,
        "tasa_error_actual_pct": error_rate_actual_pct,
        "errores_por_turno": errores_actuales,
        "costo_por_error_usd": costo_por_error_usd,
        "ahorro_anual_con_cantado_usd": ahorro_anual_usd,
    }


def calcular_eficiencia_global(lineas: list[Linea]) -> dict:
    oee_promedio = sum(l.oee_pct for l in lineas) / len(lineas)
    valor_total_turno = sum(l.valor_por_turno_usd for l in lineas)
    capacidad_total_teorica = sum(l.capacidad_teorica_pzas for l in lineas if l.estaciones)
    capacidad_total_real = sum(l.capacidad_real_pzas for l in lineas if l.estaciones)
    return {
        "oee_promedio_pct": round(oee_promedio, 1),
        "oee_meta_pct": 85.0,
        "gap_oee_pct": round(85.0 - oee_promedio, 1),
        "valor_total_por_turno_usd": round(valor_total_turno, 2),
        "valor_potencial_oee85_usd": round(valor_total_turno * (85 / oee_promedio), 2),
        "capacidad_teorica_total_pzas": round(capacidad_total_teorica, 2),
        "capacidad_real_total_pzas": round(capacidad_total_real, 2),
        "incremento_potencial_pct": round((85 / oee_promedio - 1) * 100, 1),
    }


# ── Reportes a consola ────────────────────────────────────────────────────────

def print_header(titulo: str):
    print(f"\n{Color.BOLD}{Color.BLUE}{'═'*70}{Color.RESET}")
    print(f"{Color.BOLD}{Color.BLUE}  {titulo}{Color.RESET}")
    print(f"{Color.BOLD}{Color.BLUE}{'═'*70}{Color.RESET}")


def print_section(titulo: str):
    print(f"\n{Color.BOLD}{Color.CYAN}  ▶ {titulo}{Color.RESET}")
    print(f"{Color.DIM}  {'─'*60}{Color.RESET}")


def print_linea_detalle(linea: Linea):
    print_section(f"{linea.nombre} ({linea.id})  —  Takt: {linea.takt_seg:,} seg  |  OEE: {linea.oee_pct}%")
    if not linea.estaciones:
        print(f"    {Color.DIM}Sin datos de estaciones disponibles{Color.RESET}")
        return

    print(f"    {'Estación':<8} {'Operador':<8} {'CT (seg)':>9} {'Takt (seg)':>11} {'% Takt':>8} {'Delta CT':>9} {'Estado':<10}")
    print(f"    {'─'*8} {'─'*8} {'─'*9} {'─'*11} {'─'*8} {'─'*9} {'─'*10}")

    for est in linea.estaciones:
        color = Color.RED if est.estado == "CRITICO" else (Color.GREEN if est.estado == "FLEX" else "")
        delta_str = f"+{est.delta_ct:,.0f}" if est.delta_ct >= 0 else f"{est.delta_ct:,.0f}"
        bar_filled = min(int(est.pct_takt / 10), 17)
        bar = "█" * bar_filled + "░" * (17 - bar_filled)
        print(f"    {color}{est.id:<8} {est.operador:<8} {est.ct_seg:>9,.0f} {est.takt_seg:>11,.0f} "
              f"{est.pct_takt:>7.1f}% {delta_str:>9} {est.estado:<10}{Color.RESET}")

    print(f"\n    {Color.DIM}Capacidad teórica: {linea.capacidad_teorica_pzas} pzas/turno  |  "
          f"Capacidad real (OEE): {linea.capacidad_real_pzas} pzas/turno  |  "
          f"Valor/turno: ${linea.valor_por_turno_usd:,.0f} USD{Color.RESET}")


def print_gap_analysis(lineas: list[Linea]):
    print_section("GAP ANALYSIS — Cuellos de Botella")
    for linea in lineas:
        for est in linea.estaciones_criticas:
            print(f"\n    {Color.RED}{Color.BOLD}🔴 {linea.nombre} — {est.id}{Color.RESET}")
            print(f"    CT Real:  {est.ct_seg:>7,.0f} seg")
            print(f"    Takt:     {est.takt_seg:>7,.0f} seg")
            print(f"    Exceso:   {est.delta_ct:>+7,.0f} seg  ({est.pct_takt:.1f}% del Takt)")
            perdida = calcular_perdida_por_bottleneck(linea)
            print(f"    Pérdida est.:  ${perdida.get('valor_perdido_por_turno_usd', 0):>8,.0f} USD/turno")
            print(f"    Pérdida anual: ${perdida.get('valor_perdido_por_anio_usd', 0):>8,.0f} USD/año")

    print_section("OPORTUNIDADES FLEX")
    for linea in lineas:
        for r in calcular_oportunidad_flex(linea):
            print(f"\n    {Color.GREEN}{Color.BOLD}★ {r['linea']} — {r['operador']} ({r['estacion_base']}){Color.RESET}")
            print(f"    CT: {r['ct_seg']} seg  |  Libre: {r['tiempo_libre_seg']:.0f} seg ({r['disponibilidad_pct']}%)")
            print(f"    Cubre: {', '.join(r['cubre_estaciones'])}")


def print_roi(fases: list[Fase]):
    print_section("ROI — Retorno Sobre Inversión")
    roi_data = calcular_roi_acumulado(fases)

    print(f"\n    {'Fase':<20} {'Inversión':>12} {'Beneficio':>12} {'ROI Neto':>12} {'ROI %':>8}")
    print(f"    {'─'*20} {'─'*12} {'─'*12} {'─'*12} {'─'*8}")
    for fase in fases:
        roi_str = f"{fase.roi_pct:.0f}%" if fase.roi_pct != float('inf') else "∞"
        print(f"    {fase.nombre:<20} ${fase.inversion_usd:>10,.0f} ${fase.beneficio_usd:>10,.0f} "
              f"${fase.roi_neto_usd:>10,.0f} {roi_str:>8}")
    print(f"    {'─'*20} {'─'*12} {'─'*12} {'─'*12} {'─'*8}")
    total_inv = sum(f.inversion_usd for f in fases)
    total_ben = sum(f.beneficio_usd for f in fases)
    total_neto = total_ben - total_inv
    total_pct = round((total_neto / total_inv) * 100, 1) if total_inv > 0 else float('inf')
    print(f"    {Color.BOLD}{'TOTAL':<20} ${total_inv:>10,.0f} ${total_ben:>10,.0f} "
          f"${total_neto:>10,.0f} {total_pct:.0f}%{Color.RESET}")


def print_eficiencia(lineas: list[Linea]):
    print_section("EFICIENCIA GLOBAL")
    ef = calcular_eficiencia_global(lineas)
    print(f"\n    OEE Promedio actual:   {ef['oee_promedio_pct']}%")
    print(f"    OEE Meta (Fase 3):     {ef['oee_meta_pct']}%")
    print(f"    Gap OEE:               {ef['gap_oee_pct']} puntos porcentuales")
    print(f"    Valor actual/turno:    ${ef['valor_total_por_turno_usd']:,.0f} USD")
    print(f"    Valor potencial OEE85: ${ef['valor_potencial_oee85_usd']:,.0f} USD")
    print(f"    Incremento potencial:  +{ef['incremento_potencial_pct']}%")

    print_section("IMPACTO DEL CANTADO")
    cant = calcular_impacto_cantado(lineas)
    print(f"\n    Eventos de material/turno:     {cant['eventos_material_por_turno']}")
    print(f"    Tasa de error actual:          {cant['tasa_error_actual_pct']}%")
    print(f"    Errores estimados/turno:       {cant['errores_por_turno']}")
    print(f"    Costo por error:               ${cant['costo_por_error_usd']:.2f} USD")
    print(f"    {Color.GREEN}Ahorro anual con cantado:      ${cant['ahorro_anual_con_cantado_usd']:,.0f} USD{Color.RESET}")


# ── Exportación ───────────────────────────────────────────────────────────────

def exportar_json(lineas: list[Linea], fases: list[Fase], ruta: str = "Cadrex_Analysis_Output.json"):
    datos = {
        "generado": datetime.now().isoformat(),
        "responsable": "Adriana Ramos — Gerencia de Producción",
        "planta": "Saltillo",
        "resumen_lineas": [l.resumen() for l in lineas],
        "gaps": [calcular_perdida_por_bottleneck(l) for l in lineas if l.estaciones],
        "flex_ops": [r for l in lineas for r in calcular_oportunidad_flex(l)],
        "roi_acumulado": calcular_roi_acumulado(fases),
        "eficiencia_global": calcular_eficiencia_global(lineas),
        "impacto_cantado": calcular_impacto_cantado(lineas),
        "estaciones_detalle": {
            l.nombre: [asdict(e) for e in l.estaciones]
            for l in lineas if l.estaciones
        }
    }
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n  {Color.GREEN}✓ JSON exportado: {ruta}{Color.RESET}")
    return datos


def exportar_csv(lineas: list[Linea], ruta: str = "Cadrex_Estaciones.csv"):
    import csv
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Línea","Takt_Seg","OEE_Pct","Estación","Operador",
                         "CT_Seg","Delta_CT","Pct_Takt","Estado","Tiempo_Libre_Seg"])
        for linea in lineas:
            for est in linea.estaciones:
                writer.writerow([
                    linea.nombre, linea.takt_seg, linea.oee_pct,
                    est.id, est.operador, est.ct_seg,
                    est.delta_ct, est.pct_takt, est.estado, est.tiempo_libre_seg
                ])
    print(f"  {Color.GREEN}✓ CSV exportado: {ruta}{Color.RESET}")


def exportar_reporte_texto(lineas: list[Linea], fases: list[Fase], ruta: str = "Cadrex_KPI_Report.txt"):
    ef = calcular_eficiencia_global(lineas)
    roi = calcular_roi_acumulado(fases)
    cant = calcular_impacto_cantado(lineas)
    lineas_con_est = [l for l in lineas if l.estaciones]

    with open(ruta, "w", encoding="utf-8") as f:
        f.write("CADREX DATA & DASHBOARD HUB — KPI REPORT\n")
        f.write(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"Responsable: Adriana Ramos — Gerencia de Producción · Planta Saltillo\n")
        f.write("=" * 70 + "\n\n")

        f.write("RESUMEN EJECUTIVO\n")
        f.write("-" * 40 + "\n")
        f.write(f"OEE Promedio:          {ef['oee_promedio_pct']}%  (Meta: 85%)\n")
        f.write(f"Valor total/turno:     ${ef['valor_total_por_turno_usd']:,.0f} USD\n")
        f.write(f"Valor potencial OEE85: ${ef['valor_potencial_oee85_usd']:,.0f} USD\n")
        f.write(f"Ahorro cantado/año:    ${cant['ahorro_anual_con_cantado_usd']:,.0f} USD\n\n")

        f.write("CUELLOS DE BOTELLA IDENTIFICADOS\n")
        f.write("-" * 40 + "\n")
        for linea in lineas_con_est:
            for est in linea.estaciones_criticas:
                f.write(f"  [{linea.nombre}] {est.id}: {est.ct_seg:,} seg = {est.pct_takt}% Takt  (exceso: +{est.delta_ct:,.0f} seg)\n")
        f.write("\n")

        f.write("ROI POR FASE\n")
        f.write("-" * 40 + "\n")
        for r in roi:
            pct_str = f"{r['roi_pct']}%" if r['roi_pct'] != float('inf') else "inf"
            f.write(f"  Fase {r['fase']} — {r['nombre']:<14}: "
                    f"Inv. ${r['inversion_acumulada_usd']:>7,.0f}  |  "
                    f"Ben. ${r['beneficio_acumulado_usd']:>7,.0f}  |  "
                    f"Neto ${r['roi_neto_acumulado_usd']:>7,.0f}  ({pct_str})\n")
        f.write("\n")

        f.write("PLAN DE ACCIÓN\n")
        f.write("-" * 40 + "\n")
        for fase in fases:
            f.write(f"\n  FASE {fase.numero} — {fase.nombre} ({fase.periodo})\n")
            for act in fase.actividades:
                f.write(f"    [{act['id']}] {act['actividad']}\n")

    print(f"  {Color.GREEN}✓ Reporte texto exportado: {ruta}{Color.RESET}")


# ── Punto de entrada ──────────────────────────────────────────────────────────

def main():
    print_header("CADREX DATA & DASHBOARD HUB — Análisis de Producción")
    print(f"  Planta Saltillo · Adriana Ramos — Gerencia de Producción")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    lineas = cargar_lineas()
    fases  = cargar_fases()

    # ── Detalle por línea ─────────────────────────────────────────────────────
    print_header("ESTADO ACTUAL POR LÍNEA")
    for linea in lineas:
        print_linea_detalle(linea)

    # ── Gap analysis ──────────────────────────────────────────────────────────
    print_header("GAP ANALYSIS & OPORTUNIDADES")
    print_gap_analysis(lineas)

    # ── Eficiencia global ─────────────────────────────────────────────────────
    print_header("MÉTRICAS GLOBALES & IMPACTO CANTADO")
    print_eficiencia(lineas)

    # ── ROI ───────────────────────────────────────────────────────────────────
    print_header("PLAN DE ACCIÓN & ROI")
    print_roi(fases)

    # ── Exports ───────────────────────────────────────────────────────────────
    print_header("EXPORTACIONES")
    exportar_json(lineas, fases)
    exportar_csv(lineas)
    exportar_reporte_texto(lineas, fases)

    print(f"\n{Color.BOLD}{Color.GREEN}  ✓ Análisis completo. Todos los archivos generados.{Color.RESET}\n")


if __name__ == "__main__":
    main()
