# CADREX Data & Dashboard Hub
## Reporte Maestro de Producción — Análisis de Flujo, Brechas y Plan de Mejora

**Responsable:** Adriana Ramos — Gerencia de Producción  
**Planta:** Saltillo  
**Líneas:** Northface (NF) · Sanmina (SAN) · Kantishna (KAN) · AFL  
**Fecha:** Mayo 2026  
**Clasificación:** Confidencial

---

## 1. Resumen Ejecutivo

El presente reporte documenta el análisis completo del estado de producción de las cuatro líneas activas en Planta Saltillo, identifica los principales cuellos de botella y desperdicios (NVA), propone un flujo optimizado con pre-procesos de cantado y asignación de operador flex, y establece un plan de acción en tres fases con ROI proyectado de **$77,520 USD/año** con inversión total inferior a $33,000 USD.

### Hallazgos críticos

- **Est6 NF** opera al **174.5% del Takt** (4,923 vs. 2,821 seg) — cuello de botella principal
- **Est6 SAN** opera al **127.2% del Takt** (2,820 vs. 2,217 seg) — segundo cuello crítico
- **Est4 NF** genera **1,906 seg de downtime por evento** por falla de herramental SK41H
- **Est5 NF** tiene **69% de tiempo libre** — candidato ideal como operador flex permanente
- **Sin protocolo de cantado** activo en ninguna línea — riesgo de errores de material no controlado
- **WIP sin límite formal** entre estaciones — oculta defectos y bloquea flujo

---

## 2. Estado Actual por Línea

### 2.1 Northface (NF)

| Parámetro | Valor |
|-----------|-------|
| Takt Time | 2,821 seg |
| Estaciones | 9 |
| Operadores | 9 |
| OEE aproximado | 68% |
| Turno estándar | 8 h (480 min) |
| Piezas/turno meta | ~10 pzas |

**Perfil CT por estación:**

| Estación | CT Real (seg) | Takt (seg) | % Takt | Estado |
|----------|--------------|-----------|--------|--------|
| Est 1 | 820 | 2,821 | 29.1% | ✓ OK |
| Est 2 | 1,240 | 2,821 | 43.9% | ✓ OK |
| Est 3 | 1,650 | 2,821 | 58.5% | ✓ OK |
| Est 4 | 2,100 | 2,821 | 74.4% | ✓ OK |
| Est 5 | 876 | 2,821 | 31.0% | ✓ FLEX |
| Est 6 | 4,923 | 2,821 | 174.5% | 🔴 CRÍTICO |
| Est 7 | 1,180 | 2,821 | 41.8% | ✓ OK |
| Est 8 | 940 | 2,821 | 33.3% | ✓ OK |
| Est 9 | 680 | 2,821 | 24.1% | ✓ OK |

### 2.2 Sanmina (SAN)

| Parámetro | Valor |
|-----------|-------|
| Takt Time | 2,217 seg |
| Estaciones | 9 |
| Operadores | 8 |
| OEE aproximado | 72% |

**Perfil CT por estación:**

| Estación | CT Real (seg) | Takt (seg) | % Takt | Estado |
|----------|--------------|-----------|--------|--------|
| Est 1 | 650 | 2,217 | 29.3% | ✓ OK |
| Est 2 | 980 | 2,217 | 44.2% | ✓ OK |
| Est 3 | 50 | 2,217 | 2.3% | ✓ FLEX |
| Est 4 | 1,420 | 2,217 | 64.1% | ✓ OK |
| Est 5 | 770 | 2,217 | 34.7% | ✓ OK |
| Est 6 | 2,820 | 2,217 | 127.2% | 🔴 CRÍTICO |
| Est 7 | 1,050 | 2,217 | 47.4% | ✓ OK |
| Est 8 | 810 | 2,217 | 36.5% | ✓ OK |
| Est 9 | 590 | 2,217 | 26.6% | ✓ OK |

### 2.3 Kantishna (KAN)

| Parámetro | Valor |
|-----------|-------|
| Takt Time | 2,217 seg |
| Estaciones | 7 |
| Operadores | 7 |
| OEE aproximado | 74% |

### 2.4 AFL

| Parámetro | Valor |
|-----------|-------|
| Takt Time | 2,821 seg |
| Estaciones | 6 |
| Operadores | 6 |
| OEE aproximado | 71% |

---

## 3. Análisis de Brechas (Gap Analysis)

### 3.1 Cuellos de Botella Críticos

#### Est 6 — Northface (CRÍTICO)
- **CT Real:** 4,923 seg
- **Takt Target:** 2,821 seg
- **Exceso:** +2,102 seg (+74.5%)
- **Causa raíz:** Ensamble complejo SK41H + falla de herramental recurrente
- **Impacto:** Bloquea toda la línea NF. Causa acumulación de WIP upstream.
- **Acción inmediata:** Asignar Op-5 como flex-op. Rediseño de herramental SK41H.

#### Est 6 — Sanmina (CRÍTICO)
- **CT Real:** 2,820 seg
- **Takt Target:** 2,217 seg
- **Exceso:** +603 seg (+27.2%)
- **Causa raíz:** Actividades de soldadura y verificación concentradas en un solo operador
- **Impacto:** Genera cola en Est5 y retrasa output de la línea SAN.
- **Acción inmediata:** Redistribuir tareas de verificación a Op-E (Est3, CT=50 seg).

#### Est 4 — Northface (DOWNTIME RECURRENTE)
- **Downtime por evento:** 1,906 seg (~32 min)
- **Causa raíz:** Falla herramental SK41H — sin mantenimiento preventivo definido
- **Frecuencia estimada:** 2–3 veces/semana
- **Pérdida semanal estimada:** ~5,718 seg (~1.6 pzas/semana)

#### Est 5 — Northface (OPORTUNIDAD FLEX)
- **CT Real:** 876 seg
- **Takt:** 2,821 seg
- **Utilización:** 31%
- **Tiempo libre disponible:** 1,945 seg/ciclo (69%)
- **Acción:** Designar como Operador Flex permanente para Est3 y Est6

### 3.2 Análisis de Desperdicios NVA

| Categoría | % del Total NVA | Descripción | Prioridad |
|-----------|----------------|-------------|-----------|
| WIP Excesivo | 28% | WIP > 3 pzas entre estaciones, oculta defectos | Alta |
| Esperas | 22% | Operadores esperando material o autorización | Alta |
| Retrabajos | 18% | Defectos detectados tarde en flujo | Alta |
| Movimientos | 15% | Layout no optimizado, traslados innecesarios | Media |
| Paros no planificados | 12% | Est4 NF: 1,906 seg/evento sin MP | Alta |
| Sobreproducción | 5% | Producción anticipada sin demanda confirmada | Baja |

---

## 4. Flujo Optimizado

### 4.1 Flujo Actual (Estado AS-IS)

```
Recepción Material → Subensamble Est1-3 → Ensamble Est4-6 → Verificación Calidad → Empaque
```

**Problemas identificados:**
- Sin verificación de material antes de entrada a línea
- Sin proceso de cantado PN×PN
- WIP sin límite formal entre estaciones
- Est6 NF sobre takt en 74.5% sin amortiguación

### 4.2 Flujo Optimizado (Estado TO-BE)

```
Cantado PN×PN → Pre-Subensamble → Subensamble Est1-3 → Ensamble Est4-5 → Est6 (+Flex Op) → 1st Article Inspection → Empaque
```

**Mejoras implementadas:**
1. **Pre-proceso de cantado** — verificación PN×PN antes de surtir material a línea
2. **Pre-subensamble** — libera carga de Est6 al adelantar componentes críticos
3. **Flex-Op en Est6** — Op-5 (NF) y Op-E (SAN) cubren dinámicamente el cuello
4. **First Article Inspection** — inspección formal en cada cambio de modelo
5. **WIP limitado** — máximo 3 pzas entre cualquier par de estaciones (señalética física)

### 4.3 Protocolo de Cantado PN×PN (7 Pasos)

1. **Recepción de orden de material** — Materialista recibe BOM del modelo en proceso
2. **Materialista lee PN en voz alta** — Lee exactamente el PN de la etiqueta del lote
3. **Operador de destino confirma PN en voz alta** — Confirma que coincide con BOM
4. **Conteo físico vs. BOM** — Cuenta física de piezas contra cantidad esperada
5. **Registro en formato/bot** — Captura en formato Excel o bot Telegram (/cantado)
6. **Autorización supervisor si Δ ≠ 0** — Cualquier discrepancia requiere sign-off antes de surtir
7. **Surtido a línea con etiqueta** — Material etiquetado con PN, lote, qty y fecha

**Reglas de oro:**
- Nunca asumir — siempre contar
- PN debe coincidir exactamente, sin aproximaciones
- Si hay discrepancia → STOP → no surtir → notificar supervisor
- WIP máximo 3 pzas entre cualquier par de estaciones

---

## 5. Optimización de Personal

### 5.1 Operadores Flex Identificados

| Operador | Línea | Estación | CT Real | % Takt | Disponibilidad | Cubre |
|----------|-------|----------|---------|--------|----------------|-------|
| Op-5 | NF | Est 5 | 876 seg | 31% | 69% del turno | Est 3, Est 6 |
| Op-E | SAN | Est 3 | 50 seg | 2.3% | ~98% del turno | Est 4, Est 6 |

### 5.2 Matriz de Polivalencia — Northface

| Operador | Est1 | Est2 | Est3 | Est4 | Est5 | Est6 | Est7 |
|----------|------|------|------|------|------|------|------|
| Op-1 | ✓ | ✓ | · | · | · | · | ✓ |
| Op-2 | · | ✓ | ✓ | · | · | · | · |
| Op-3 | · | · | ✓ | ✓ | · | · | · |
| Op-4 | · | · | · | ✓ | ✓ | · | · |
| Op-5 ★ | ✓ | ✓ | ✓ | · | ✓ | ✓ | · |
| Op-6 | · | · | · | · | · | ✓ | ✓ |
| Op-7 | ✓ | · | · | · | · | ✓ | ✓ |

**★ = Operador Flex | ✓ = Certificado | · = Requiere capacitación**

---

## 6. Plan de Acción en 3 Fases

### Fase 1 — Inmediato (0–30 días) | Inversión: $0

| # | Actividad | Responsable | KPI Meta |
|---|-----------|-------------|----------|
| 1 | Implementar protocolo de cantado PN×PN en todas las líneas | Supervisor + Adriana | 0 errores de material/semana |
| 2 | Asignar Op-5 (NF) como flex-op permanente para Est3 y Est6 | Adriana Ramos | CT Est6 < 3,500 seg |
| 3 | Limitar WIP a ≤ 3 pzas entre estaciones (señalética física) | Supervisor de turno | WIP ≤ 3 pzas |
| 4 | Mantenimiento preventivo Est4 NF — herramental SK41H | Mantenimiento | 0 fallas SK41H/semana |
| 5 | Capacitar supervisores en Dashboard y Bot Telegram | Adriana Ramos | 100% supervisores capacitados |
| 6 | Activar alerta Andon visual en Est6 NF cuando CT > Takt | Ingeniería | Andon activo |

### Fase 2 — Corto Plazo (1–3 meses) | Inversión: $8,000 USD

| # | Actividad | Responsable | KPI Meta |
|---|-----------|-------------|----------|
| 7 | Implementar shadow boards en herramental crítico (Est4, Est6) | Mantenimiento | 100% herramienta en lugar |
| 8 | Certificar operadores clave en 2+ estaciones (polivalencia) | Capacitación | 80% ops certificados en ≥2 est |
| 9 | Balancear línea SAN: redistribuir carga Est6 → Est4/Est5 | Ingeniería IE | CT Est6 SAN < 2,217 seg |
| 10 | Arrancar First Article Inspection en cada cambio de modelo | Calidad | FAI = 100% modelos |
| 11 | Reuniones diarias de KPIs con supervisores de turno | Adriana Ramos | Reunión diaria 10 min |
| 12 | Integrar datos del bot a dashboard en tiempo real | TI / Adriana | Dashboard actualizado x turno |

### Fase 3 — Mediano Plazo (3–6 meses) | Inversión: $25,000 USD

| # | Actividad | Responsable | KPI Meta |
|---|-----------|-------------|----------|
| 13 | Rediseñar layout físico Est6 NF para reducir CT a < Takt | Ingeniería IE | CT Est6 < 2,821 seg |
| 14 | Implementar automatización parcial en subensamble (cobot) | Ingeniería | Reducción CT 30% |
| 15 | Alcanzar OEE ≥ 85% en todas las líneas | Todos | OEE ≥ 85% |
| 16 | Certificar línea AFL con proceso de cantado completo | AFL Supervisor | Cantado AFL activo |
| 17 | Documentar estándar de trabajo para las 4 líneas | IE + Calidad | Estándares publicados |
| 18 | Revisión formal de ROI y ajuste de plan (Q3 2026) | Adriana Ramos | ROI verificado |

---

## 7. Impacto Financiero y ROI

### 7.1 Supuestos

| Parámetro | Valor |
|-----------|-------|
| Precio unitario | $120 USD/pza |
| Incremento capacidad Fase 1 | +2.5 pzas/turno |
| Reducción tasa de defectos | 35% → 12% (DPM) |
| Reducción downtime | 22 min/turno → 8 min/turno |
| Ahorro retrabajos | $18,000 USD/año (150 hrs × $120) |
| Inversión Fase 3 (cobot parcial) | $25,000 USD |

### 7.2 Proyección por Fase

| Fase | Período | Inversión | Beneficio | ROI Neto |
|------|---------|-----------|-----------|----------|
| Fase 1 | 0–30 días | $0 | $18,000 USD | $18,000 USD |
| Fase 2 | 1–3 meses | $8,000 USD | $35,000 USD | $27,000 USD |
| Fase 3 | 3–6 meses | $25,000 USD | $77,520 USD | $52,520 USD |
| **Total** | **6 meses** | **$33,000 USD** | **$77,520 USD** | **$44,520 USD** |

### 7.3 KPIs de ROI

- **Valor por unidad:** $120 USD/pza
- **Meta incremental anual:** 646 pzas/año
- **ROI anual objetivo:** $77,520 USD/año
- **Período de recuperación:** < 6 meses
- **ROI total 3 fases:** 135% sobre inversión

---

## 8. Ecosistema Digital Cadrex

### 8.1 Archivos Entregados

| Archivo | Descripción | Estado |
|---------|-------------|--------|
| `Cadrex_Dashboard_Maestro.html` | Dashboard interactivo HTML con Chart.js, 6 tabs, paleta Catppuccin Latte | ✓ Entregado |
| `Cadrex_Data_Maestro_Dashboard.xlsx` | Excel maestro, 12 hojas, KPIs + flujo + polivalencia + 28 actividades | ✓ Entregado |
| `Cadrex_Template_TelegramBot.xlsx` | Template Google Sheets: Producción_Bot + Cantado_Bot + Setup | ✓ Entregado |
| `Cadrex_n8n_TelegramBot.json` | Workflow n8n completo (23 nodos), webhook + Whisper + Sheets | ✓ Entregado |
| `Cadrex_Formato_Captura.xlsx` | Formato de captura operativo: Producción + Cantado + Paros + Instrucciones | ✓ Entregado |
| `Cadrex_Presentacion_Ejecutiva.pptx` | Presentación bilingüe ES/EN, 13 slides, para dirección | ✓ Entregado |
| `Cadrex_Reporte_Completo.md` | Este reporte | ✓ Entregado |
| `Cadrex_Data.json` | Datos estructurados completos | ✓ Entregado |
| `Cadrex_Analysis.py` | Script Python de análisis y cálculos | ✓ Entregado |

### 8.2 Bot Telegram — Arquitectura

```
Operador/Materialista
       │
       ▼
  Telegram Bot
       │
       ├── /reporte  → Flujo guiado 9 pasos → Sheets: Producción_Bot
       ├── /cantado  → Flujo guiado 7 pasos → Sheets: Cantado_Bot
       └── 🎙 Audio  → OpenAI Whisper (ES) → Parser → Confirmación → Sheets
       │
       ▼
    n8n Webhook
    (23 nodos)
       │
       ▼
  Google Sheets
  (2 hojas de captura)
       │
       ▼
  Dashboard HTML
  (actualización manual o automática)
```

### 8.3 Variables de Entorno Requeridas

```bash
TELEGRAM_BOT_TOKEN=<token de BotFather>
TELEGRAM_WEBHOOK_URL=https://tu-servidor.com/webhook/cadrex-bot
GOOGLE_SHEETS_ID=<ID de la hoja de cálculo>
OPENAI_API_KEY=<clave API de OpenAI>
ALLOWED_USERS=<IDs de Telegram autorizados, separados por coma>
```

---

## 9. Indicadores Clave de Desempeño (KPIs) Meta

| KPI | Actual | Meta Fase 1 | Meta Fase 3 |
|-----|--------|-------------|-------------|
| OEE NF | 68% | 72% | 85% |
| OEE SAN | 72% | 75% | 85% |
| CT Est6 NF (seg) | 4,923 | < 3,500 | < 2,821 |
| CT Est6 SAN (seg) | 2,820 | < 2,400 | < 2,217 |
| Tasa de defectos (DPM) | ~35% | < 20% | < 12% |
| Downtime Est4 NF (min/turno) | 22 | < 10 | < 5 |
| WIP máximo entre estaciones | Sin límite | ≤ 5 | ≤ 3 |
| Errores de material/semana | Desconocido | 0 (con cantado) | 0 |
| Operadores polivalentes (≥2 est) | ~30% | 60% | 80% |

---

## 10. Apéndices

### A. Glosario

| Término | Definición |
|---------|------------|
| Takt Time | Tiempo disponible de producción / Demanda del cliente. Ritmo al que debe producirse. |
| CT | Cycle Time. Tiempo real que toma completar una operación en una estación. |
| OEE | Overall Equipment Effectiveness. Disponibilidad × Rendimiento × Calidad. |
| WIP | Work In Process. Inventario de piezas en proceso dentro de la línea. |
| NVA | Non-Value Added. Actividades que no agregan valor al producto desde la perspectiva del cliente. |
| Cantado | Protocolo de verificación PN×PN por voz antes de surtir material a línea. |
| Flex-Op | Operador flexible certificado en múltiples estaciones, usado para cubrir cuellos de botella. |
| Polivalencia | Capacidad de un operador para trabajar en múltiples estaciones. |
| Andon | Sistema de alerta visual que indica problemas en línea de producción. |
| SK41H | Código de herramental crítico en Est4 y Est6 de línea Northface. |
| FAI | First Article Inspection. Inspección formal de la primera pieza de cada lote/modelo. |

### B. Contactos del Proyecto

| Rol | Nombre | Responsabilidad |
|-----|--------|----------------|
| Gerente de Producción | Adriana Ramos | Líder del proyecto, aprobaciones, escalaciones |
| Supervisores de Turno | Por designar | Captura diaria, monitoreo KPIs, cantado |
| Mantenimiento | Por designar | MP herramental, shadow boards |
| Calidad | Por designar | FAI, auditorías de cantado |
| TI / Sistemas | Por designar | Despliegue bot, credenciales n8n/Sheets |

---

*Documento generado automáticamente por CADREX Data & Dashboard Hub · Mayo 2026*  
*Gerencia de Producción — Planta Saltillo*
