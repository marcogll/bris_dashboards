# Statement of Work (SOW) — Sistema de Gestión Operativa "Cadrex"

**Proyecto:** Implementación de Dashboard de Producción, Gestión de Tareas y Control de Herramentales.  
**Cliente:** Adriana — Gerencia de Producción (Cadrex).  
**Proveedor:** Marco — Consultoría de Sistemas y Operaciones (Soul:23).  
**Fecha:** Mayo 2026

---

## 1. Propósito y Alcance del Proyecto

Este documento define el alcance para la configuración, despliegue y capacitación de un sistema de gestión visual en la nube (Dashboard Cadrex). El sistema está diseñado para erradicar el seguimiento manual ("micromanagement") de actividades, digitalizar el control de mantenimiento de *fixtures* y centralizar las iniciativas de mejora continua para las líneas de ensamble Northface, Sanmina y Kantishna.

El alcance incluye la configuración del software, alojamiento temporal en servidor privado por los primeros dos meses, estructuración de flujos de trabajo (Kanban) y vinculación con los planes de acción de ingeniería.

---

## 2. Entregables Principales

1. **Entorno de Trabajo Digital (Workspace):** Despliegue de la plataforma accesible vía web con cuentas de usuario para la Gerencia (Adriana) y su equipo directo.

2. **Tableros de Flujo de Trabajo (Kanban Boards):**
   - Tablero operativo diario: Tareas recurrentes, asignación de responsables y fechas límite (*Due dates*).
   - Tablero de Proyectos de Mejora: Seguimiento a las iniciativas del Plan de Acción (ej. *Fixture para gaskets base Est. 4*, *Shadow boards Est. 4 Northface*).

3. **Módulo de Control de Fixtures:** Base de datos visual y seguimiento de estado (Disponible, Reparación, PM) para herramentales críticos (ej. remachadoras SK41H, SG-2973, pistola de torque).

4. **Documentación y Capacitación:** Entrega de manual de uso rápido y sesión de capacitación en piso para el uso de atajos del sistema (ej. creación de tareas con tecla rápida "C") y actualización de estatus (*In Progress*, *Testing*, *Done*).

---

## 3. KPIs y Métricas de Éxito del Proyecto

El éxito de la adopción del sistema se medirá por su capacidad para impactar positivamente los siguientes indicadores clave (KPIs) extraídos del Reporte Maestro de Producción:

- **Reducción de Tiempo Muerto (Downtime):** Bajar de los niveles actuales a la meta de **≤ 30 min/turno**, eliminando tiempos muertos por "Fixture Dañado" o "Traslado de herramienta" (como los 859s perdidos en Northface).
- **Eficiencia Operativa y Cycle Time (CT):** Proveer visibilidad en tiempo real para apoyar la reducción del CT en cuellos de botella (ej. Reducir los 77.5 min de Sanmina para igualar el Takt de 36.9 min).
- **OEE (Efectividad General del Equipo):** Apoyar con gestión estructurada para alcanzar la meta de **≥ 85%**.
- **First Pass Yield (FPY):** Asegurar mediante checklists y tareas digitales vinculadas a calidad que se logre la meta de **≥ 95%**.

---

## 4. Cronograma de Implementación (Hitos)

| Fase | Hito | Descripción | Tiempo Estimado |
|------|------|-------------|-----------------|
| **Fase 1** | **MVP y Adopción** | Configuración de servidor, creación de usuarios, estructuración de tableros Kanban y capacitación inicial del equipo. | Mes 1 |
| **Fase 2** | **Trazabilidad de Piso** | Integración del catálogo de fixtures, configuración de alertas visuales de fallas y despliegue del flujo de mantenimiento. | Mes 2 al 3 |
| **Fase 3** | **Dashboards KPIs** | Vinculación del cumplimiento de tareas en Cadrex con el reporte de métricas de piso (Producción Diaria, Scrap, Retrabajos). | Mes 4 al 6 |

---

## 5. Responsabilidades

**Por parte del Proveedor (Marco / Soul:23):**
- Garantizar el correcto funcionamiento de la plataforma en el servidor de *staging* durante la prueba piloto de 2 meses.
- Brindar soporte técnico para ajustes de flujos de trabajo en los tableros de acuerdo con la retroalimentación del equipo.

**Por parte del Cliente (Adriana / Cadrex):**
- Asegurar que el equipo utilice la plataforma como única fuente de verdad para reportar avances operativos ("Si no está en el sistema, no se está trabajando").
- Proveer información técnica actualizada en caso de cambios en los herramentales o en el Layout de las líneas.

---

## 6. Acuerdos Comerciales

*(Añadir aquí las condiciones de pago, facturación y honorarios acordados, vinculados al presupuesto global del plan de mejora y los $77,520 USD de ahorro proyectado anual).*

---

## Firmas de Aceptación

| Rol | Nombre | Firma | Fecha |
|-----|--------|-------|-------|
| Gerente de Producción, Cadrex | Adriana | ___________________ | _______ |
| Consultor de Procesos Estratégicos, Soul:23 | Marco | ___________________ | _______ |
