# Plan Multiagente — BRIS Salud

## Overview

Extender el dashboard BRIS/Kadrix existente para crear un **sistema de gestion medica multiagente** que atiende familias, registra pacientes via wizard, agenda citas, y ofrece opciones inteligentes basadas en padecimientos.

---

## Control de Acceso por Rol

### Dos roles principales:

| Rol | Permisos | Ver |
|-----|----------|-----|
| **Asistente** (recepcionista) | Wizard, citas, datos basicos, triage | Solo datos operativos: nombre, telefono, cita, sintomas reportados. **NO ve expedientes clinicos** |
| **Duenya / Admin** | Todo lo anterior + expedientes completos + Knowledge Base + RAG IA | Expedientes, diagnosticos, tratamientos, historial familiar, analytics, KB |

### Reglas de acceso:

```python
ROLES = {
    "asistente": {
        "ver_expediente": False,
        "ver_diagnostico": False,
        "ver_tratamiento": False,
        "ver_historial_familiar": False,
        "ver_citas": True,
        "ver_paciente_basico": True,
        "wizard_registro": True,
        "triage_inicial": True,
        "cancelar_cita": True,
        "ver_knowledge_base": False,
        "ver_rag_ai": False,
        "ver_reportes": False,
    },
    "duenya": {
        "ver_expediente": True,
        "ver_diagnostico": True,
        "ver_tratamiento": True,
        "ver_historial_familiar": True,
        "ver_citas": True,
        "ver_paciente_basico": True,
        "wizard_registro": True,
        "triage_inicial": True,
        "cancelar_cita": True,
        "ver_knowledge_base": True,
        "ver_rag_ai": True,
        "ver_reportes": True,
        "editar_padecimientos": True,
        "ver_alertas_criticas": True,
    }
}
```

### Decorador de permisos:

```python
# salud/utils/permisos.py

from functools import wraps
from flask import session, redirect, url_for

def requiere_rol(*roles):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            user_role = session.get("role", "asistente")
            if user_role not in roles:
                return redirect(url_for("salud.sin_permiso"))
            return f(*args, **kwargs)
        return wrapped
    return decorator

def puede_ver(campo: str) -> bool:
    user_role = session.get("role", "asistente")
    return ROLES.get(user_role, {}).get(campo, False)

# Uso en templates:
# {% if puede_ver("ver_expediente") %} mostrar expediente {% endif %}
```

### Endpoints protegidos:

| Endpoint | Asistente | Duenya |
|----------|-----------|--------|
| `/salud/` (dashboard) | SI | SI |
| `/salud/wizard/*` | SI | SI |
| `/salud/citas/*` | SI | SI |
| `/salud/buscar` | SI | SI |
| `/salud/paciente/<id>` (perfil basico) | SI | SI |
| `/salud/paciente/<id>/expediente` | **NO** | SI |
| `/salud/familia/<id>` (detalle completo) | **NO** | SI |
| `/salud/diagnostico/opciones/*` | SI (solo opciones) | SI |
| `/salud/seguimiento/*` (notas post-cita) | **NO** | SI |
| `/salud/kb/*` (Knowledge Base) | **NO** | SI |
| `/salud/rag/*` (RAG IA) | **NO** | SI |
| `/salud/reportes/*` | **NO** | SI |

### Modelo visual: lo que ve cada rol

```
ASISTENTE VE:                          DUENYA VE:
+---------------------------+          +---------------------------+
| Dashboard Recepcion       |          | Dashboard Recepcion       |
| - Citas del dia           |          | - Citas del dia           |
| - Buscar paciente         |          | - Buscar paciente         |
| - Agendar cita            |          | - Agendar cita            |
| - Wizard nuevo paciente   |          | - Wizard nuevo paciente   |
|                           |          |                           |
| Perfil Paciente (BASICO): |          | Expediente Paciente       |
| - Nombre, Tel, Email     |          | (COMPLETO):               |
| - Proxima cita            |          | - TODO lo basico +       |
| - Padecimiento reportado  |          | - Diagnosticos            |
| - Estatus cita            |          | - Tratamientos            |
|                           |          | - Antecedentes heredo-fam |
| NO VE:                    |          | - Historial completo      |
| - Diagnosticos clinicos   |          | - Notas del medico        |
| - Tratamientos            |          |                           |
| - Antecedentes            |          | Knowledge Base + RAG IA:  |
| - Notas post-consulta     |          | - Guias clinicas          |
| - KB / RAG                |          | - Busqueda semantica      |
| - Reportes                |          | - Consultas IA            |
+---------------------------+          | - Casos similares         |
                                      | - Roadmap RAG             |
                                      +---------------------------+
```

---

## Arquitectura Multiagente (7 Agentes)

### Agente 1: Recepcion / Triage (`recepcion/`)

**Proposito:** Primer punto de contacto. Determina el camino del paciente.
**Acceso:** Asistente y Duenya

| Funcion | Descripcion |
|---------|-------------|
| Wizard de registro | Formulario multi-paso que recolecta datos del paciente paso a paso |
| Triage inteligente | Clasifica urgencia y tipo de atencion segun sintomas |
| Routing | Envia al paciente al agente correcto (citas, diagnostico, seguimiento) |
| Identificacion | Verifica si el paciente ya existe o es nuevo |

**Endpoints:**
- `GET /salud/` — Dashboard recepcion
- `GET /salud/wizard/` — Wizard paso 1: datos personales
- `POST /salud/wizard/personal` — Guarda datos personales, redirige a paso 2
- `GET /salud/wizard/<id>/historial` — Paso 2: antecedentes (solo asistente: datos basicos; duenya: completo)
- `POST /salud/wizard/<id>/historial` — Guarda historial
- `GET /salud/wizard/<id>/padecimiento` — Paso 3: sintomas/padecimiento actual
- `POST /salud/wizard/<id>/padecimiento` — Guarda padecimiento
- `GET /salud/wizard/<id>/confirmar` — Paso 4: confirmacion y resumen

**Wizard de Registro (4 pasos):**

```
Paso 1: Datos Personales (ASISTENTE y DUENYA)
+-- Nombre completo
+-- Fecha de nacimiento
+-- Sexo
+-- Telefono
+-- Email
+-- Direccion
+-- Pertenece a una familia registrada? -> Si si, vincular

Paso 2: Antecedentes (DUENYA ve todo, ASISTENTE solo alergias criticas*)
+-- Alergias (multi-select + texto libre)
+-- Enfermedades cronicas (solo duenya ve completo)
+-- Medicamentos actuales (solo duenya ve completo)
+-- Antecedentes heredo-familiares (solo duenya)
+-- Cirugias previas (solo duenya)
+-- Habitos (solo duenya)

Paso 3: Padecimiento Actual (ASISTENTE y DUENYA)
+-- Que te trae hoy? (texto libre + categorias sugeridas)
+-- Sintomas principales (multi-select dinamico segun categoria)
+-- Intensidad del dolor (1-10 escala visual)
+-- Tiempo de evolucion (horas/dias/semanas/meses)
+-- Es urgencia? (auto-detectado o manual)
+-- Notas adicionales

Paso 4: Confirmacion y Opciones (ASISTENTE y DUENYA)
+-- Resumen de datos capturados
+-- Opciones recomendadas segun padecimiento (Agente Diagnostico)
+-- Disponibilidad de citas (Agente Citas)
+-- Confirmar -> Crear paciente + Agendar cita

* Asistente ve alergias para seguridad del paciente (no es historial clinico)
```

---

### Agente 2: Paciente / Familia (`paciente/`)

**Proposito:** Gestion del expediente paciente y relaciones familiares.
**Acceso:** Asistente (solo basico), Duenya (completo + KB)

| Funcion | Descripcion | Asistente | Duenya |
|---------|-------------|-----------|--------|
| Perfil paciente | Ver/editar datos | Solo basicos | Completo |
| Grupo familiar | Vincular pacientes | Ver lista | Ver + editar |
| Busqueda | Buscar paciente | Nombre/tel | Nombre/tel/CURP |
| Expediente | Historial completo | **NO** | SI |

**Endpoints:**
- `GET /salud/paciente/<id>` — Perfil basico (ambos roles)
- `GET /salud/paciente/<id>/editar` — Editar datos basicos (ambos)
- `POST /salud/paciente/<id>/editar` — Guardar cambios
- `GET /salud/paciente/<id>/expediente` — **[DUENYA]** Expediente completo
- `GET /salud/familia/<id>` — **[DUENYA]** Vista de grupo familiar completo
- `POST /salud/familia/vincular` — Vincular paciente a familia
- `GET /salud/buscar` — Buscar pacientes

**Modelo de Familia:**
```
salud_familias
+-- id
+-- apellido_principal
+-- direccion_compartida (bool)
+-- telefono_emergencia
+-- notas
+-- created_at

salud_pacientes (extension)
+-- familia_id (FK -> salud_familias)
+-- es_titular (bool -- responsable del grupo)
+-- parentesco (hijo, conyuge, padre, etc.)
```

---

### Agente 3: Citas (`citas/`)

**Proposito:** Programacion, reagendamiento y cancelacion de citas.
**Acceso:** Asistente y Duenya

| Funcion | Descripcion |
|---------|-------------|
| Agendar cita | Crear cita para paciente existente o nuevo |
| Disponibilidad | Mostrar horarios disponibles por medico/especialidad |
| Reagendar | Mover cita existente |
| Cancelar | Cancelar cita con motivo |
| Recordatorios | Notificaciones automaticas |
| Calendario | Vista de calendario por medico/sala |

**Endpoints:**
- `GET /salud/citas/` — Calendario de citas
- `GET /salud/citas/nueva` — Formulario nueva cita
- `POST /salud/citas/nueva` — Crear cita
- `GET /salud/citas/<id>` — Detalle de cita
- `POST /salud/citas/<id>/reagendar` — Reagendar
- `POST /salud/citas/<id>/cancelar` — Cancelar
- `GET /salud/citas/disponibilidad` — API: slots disponibles (JSON)
- `GET /salud/citas/hoy` — Citas del dia

---

### Agente 4: Diagnostico / Padecimiento (`diagnostico/`)

**Proposito:** Motor de opciones inteligentes segun el padecimiento del paciente.
**Acceso:** Asistente (opciones para agendar), Duenya (opciones + diagnostico clinico)

| Funcion | Asistente | Duenya |
|---------|-----------|--------|
| Opciones por padecimiento | SI (para agendar) | SI |
| Diagnostico clinico | **NO** | SI |
| Notas del medico | **NO** | SI |
| Recomendaciones KB | **NO** | SI |

**Endpoints:**
- `GET /salud/diagnostico/opciones/<padecimiento_id>` — Opciones para un padecimiento (ambos)
- `GET /salud/diagnostico/triage` — Evaluacion de triage (ambos)
- `POST /salud/diagnostico/triage` — Resultado de triage
- `GET /salud/api/padecimientos` — Catalogo de padecimientos (JSON)
- `GET /salud/api/padecimientos/<id>/opciones` — Opciones por padecimiento (JSON)
- `GET /salud/api/sintomas` — Lista de sintomas (JSON, filtrable)
- `POST /salud/diagnostico/nota/<cita_id>` — **[DUENYA]** Nota de diagnostico clinico

---

### Agente 5: Seguimiento (`seguimiento/`)

**Proposito:** Post-cita, recordatorios, seguimiento de tratamientos.
**Acceso:** Solo Duenya (contiene informacion clinica)

| Funcion | Descripcion |
|---------|-------------|
| Recordatorios | Notificaciones antes de citas |
| Post-cita | Nota post-consulta, causas, tratamiento |
| Tratamiento | Seguimiento de medicamentos, proxima cita |
| Alertas | Senales de advertencia segun condicion |

**Endpoints:**
- `GET /salud/seguimiento/` — **[DUENYA]** Dashboard seguimiento
- `GET /salud/seguimiento/<paciente_id>` — **[DUENYA]** Seguimiento por paciente
- `POST /salud/seguimiento/<cita_id>/nota` — **[DUENYA]** Agregar nota post-consulta
- `GET /salud/seguimiento/alertas` — **[DUENYA]** Alertas activas
- `POST /salud/seguimiento/<paciente_id>/recordatorio` — Programar recordatorio

---

### Agente 6: Reportes / Analytics (`reportes/`)

**Proposito:** Estadisticas, reportes, dashboards gerenciales (extiende analytics existente).
**Acceso:** Solo Duenya

| Funcion | Descripcion |
|---------|-------------|
| Citas por dia/semana/mes | Graficas de ocupacion |
| Pacientes nuevos vs recurrentes | Tendencias |
| Padecimientos mas comunes | Epidemiologia |
| Tiempos de espera | Eficiencia |
| Familiar | Estadisticas por grupo familiar |

**Endpoints:**
- `GET /salud/reportes/` — **[DUENYA]** Dashboard general
- `GET /salud/api/reportes/citas` — API datos de citas
- `GET /salud/api/reportes/padecimientos` — API datos de padecimientos
- `GET /salud/api/reportes/pacientes` — API datos de pacientes

---

### Agente 7: Knowledge Base + RAG IA (`kb_rag/`)

**Proposito:** Base de conocimiento medico consultable con IA que aprende de los expedientes.
**Acceso:** Exclusivo rol `duenya`.

| Funcion | Descripcion |
|---------|-------------|
| Guias clinicas | Protocolos de atencion por padecimiento (subidos por duenya) |
| Notas clinicas | Experiencia acumulada de consultas (diagnosticos, tratamientos efectivos) |
| Casos similares | Busqueda semantica de pacientes con padecimientos similares |
| Roadmap RAG | Evolucion gradual: KB estatica -> embeddings -> RAG completo |

**Endpoints:**
- `GET /salud/kb/` — **[DUENYA]** Dashboard Knowledge Base
- `GET /salud/kb/guias/` — Listar guias clinicas
- `POST /salud/kb/guias/upload` — Subir guia clinica (PDF, DOCX)
- `GET /salud/kb/guias/<id>` — Ver guia
- `DELETE /salud/kb/guias/<id>` — Eliminar guia
- `GET /salud/kb/casos_similares/<padecimiento_id>` — Casos similares a un padecimiento
- `GET /salud/rag/` — **[DUENYA]** Interfaz de consulta RAG
- `POST /salud/rag/query` — Consulta en lenguaje natural
- `GET /salud/rag/roadmap` — Estado del roadmap RAG (Fase 1/2/3)
- `GET /salud/api/kb/search?q=` — API busqueda semantica

**Roadmap RAG:**

```
FASE 1: KB Estatica (implementar primero)
+-- Duenya sube guias clinicas (PDF, DOCX)
+-- Busqueda por texto completo (LIKE / FULLTEXT)
+-- Vinculacion guias <-> padecimientos
+-- Vista de casos similares por padecimiento
+-- Sin IA, solo consulta manual

FASE 2: Embeddings (implementar segundo)
+-- Integrar sentence-transformers (all-MiniLM-L6-v2)
+-- Vectorizar documentos al subir
+-- Vectorizar notas clinicas de expedientes
+-- Almacenar embeddings en salud_kb_embeddings
+-- Busqueda semantica con cosine similarity
+-- Recuperar chunks relevantes dado un padecimiento
+-- ChromaDB o FAISS como vector store

FASE 3: RAG Completo
+-- Integrar LLM (local: Ollama/Llama, o API)
+-- Pipeline: pregunta -> retrieval -> contexto -> generacion
+-- Consultas en lenguaje natural sobre expedientes
+-- "Pacientes con dolor abdominal similares en el ultimo mes"
+-- "Que tratamiento funciono mejor para diabetes tipo 2"
+-- Logging de consultas en salud_rag_consultas
+-- Dashboard de metricas RAG
```

---

## Schema MySQL -- Modulo Salud

```sql
-- ============================================================
-- Schema: Salud -- Sistema de Gestion Medica Multiagente
-- ============================================================

-- Roles extendidos (reutiliza kadrix_users con campo role)
-- Los roles existentes: admin, manager, technician, operator, viewer
-- Agregar: asistente, duenya
ALTER TABLE kadrix_users MODIFY COLUMN role ENUM(
    'admin', 'manager', 'technician', 'operator', 'viewer',
    'asistente', 'duenya'
) DEFAULT 'asistente';

-- Familias
CREATE TABLE salud_familias (
    id INT AUTO_INCREMENT PRIMARY KEY,
    apellido_principal VARCHAR(100) NOT NULL,
    direccion TEXT,
    telefono_emergencia VARCHAR(20),
    correo_comun VARCHAR(255),
    notas TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Pacientes
CREATE TABLE salud_pacientes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    familia_id INT,
    es_titular BOOLEAN DEFAULT FALSE,
    parentesco VARCHAR(50),
    nombre VARCHAR(200) NOT NULL,
    apellido_paterno VARCHAR(100) NOT NULL,
    apellido_materno VARCHAR(100),
    fecha_nacimiento DATE,
    sexo ENUM('masculino', 'femenino', 'otro'),
    curp VARCHAR(18),
    telefono VARCHAR(20),
    email VARCHAR(255),
    direccion TEXT,
    alergias JSON,
    enfermedades_cronicas JSON,
    medicamentos_actuales JSON,
    antecedentes_heredofamiliares JSON,
    cirugias_previas JSON,
    habitos JSON,
    notas_generales TEXT,
    activo BOOLEAN DEFAULT TRUE,
    creado_por INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (familia_id) REFERENCES salud_familias(id) ON DELETE SET NULL,
    INDEX idx_nombre (nombre, apellido_paterno),
    INDEX idx_familia (familia_id)
);

-- Padecimientos / Catalogo
CREATE TABLE salud_padecimientos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(50) UNIQUE NOT NULL,
    nombre VARCHAR(200) NOT NULL,
    categoria VARCHAR(100),
    urgencia_base TINYINT DEFAULT 1,
    especialidades JSON,
    estudios_recomendados JSON,
    preguntas_triage JSON,
    flags_rojo JSON,
    descripcion TEXT,
    activo BOOLEAN DEFAULT TRUE
);

-- Sintomas
CREATE TABLE salud_sintomas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(50) UNIQUE NOT NULL,
    nombre VARCHAR(200) NOT NULL,
    categoria VARCHAR(100),
    padecimientos_relacionados JSON,
    activo BOOLEAN DEFAULT TRUE
);

-- Medicos
CREATE TABLE salud_medicos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(200) NOT NULL,
    especialidad VARCHAR(100),
    cedula VARCHAR(50),
    telefono VARCHAR(20),
    email VARCHAR(255),
    activo BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Consultorios / Salas
CREATE TABLE salud_consultorios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(20) UNIQUE NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    tipo ENUM('consulta', 'urgencias', 'procedimiento', 'laboratorio', 'imagenologia'),
    capacidad INT DEFAULT 1,
    activo BOOLEAN DEFAULT TRUE
);

-- Horarios de medicos
CREATE TABLE salud_horarios_medico (
    id INT AUTO_INCREMENT PRIMARY KEY,
    medico_id INT NOT NULL,
    consultorio_id INT NOT NULL,
    dia_semana TINYINT NOT NULL,
    hora_inicio TIME NOT NULL,
    hora_fin TIME NOT NULL,
    duracion_cita_min INT DEFAULT 30,
    activo BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (medico_id) REFERENCES salud_medicos(id),
    FOREIGN KEY (consultorio_id) REFERENCES salud_consultorios(id)
);

-- Citas
CREATE TABLE salud_citas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    paciente_id INT NOT NULL,
    medico_id INT NOT NULL,
    consultorio_id INT NOT NULL,
    padecimiento_id INT,
    fecha DATE NOT NULL,
    hora_inicio TIME NOT NULL,
    hora_fin TIME NOT NULL,
    duracion_min INT DEFAULT 30,
    tipo ENUM('primera_vez', 'seguimiento', 'urgencia', 'procedimiento', 'preventivo') DEFAULT 'primera_vez',
    status ENUM('agendada', 'confirmada', 'en_curso', 'completada', 'cancelada', 'no_asistio') DEFAULT 'agendada',
    motivacion TEXT,
    sintomas_reportados JSON,
    urgencia_calculada TINYINT DEFAULT 1,
    notas_previas TEXT,
    notas_posterior TEXT,
    diagnostico TEXT,
    tratamiento JSON,
    proxima_cita_sugerida DATE,
    cancelado_motivo VARCHAR(200),
    creado_por INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (paciente_id) REFERENCES salud_pacientes(id),
    FOREIGN KEY (medico_id) REFERENCES salud_medicos(id),
    FOREIGN KEY (consultorio_id) REFERENCES salud_consultorios(id),
    FOREIGN KEY (padecimiento_id) REFERENCES salud_padecimientos(id),
    INDEX idx_fecha (fecha, hora_inicio),
    INDEX idx_paciente (paciente_id),
    INDEX idx_medico (medico_id, fecha),
    INDEX idx_status (status)
);

-- Seguimiento post-cita
CREATE TABLE salud_seguimientos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cita_id INT NOT NULL,
    paciente_id INT NOT NULL,
    tipo ENUM('recordatorio_cita', 'seguimiento_tratamiento', 'alerta', 'nota_libre') DEFAULT 'nota_libre',
    contenido TEXT NOT NULL,
    fecha_seguimiento DATE,
    completado BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cita_id) REFERENCES salud_citas(id),
    FOREIGN KEY (paciente_id) REFERENCES salud_pacientes(id)
);

-- Historial de padecimientos por paciente
CREATE TABLE salud_paciente_padecimientos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    paciente_id INT NOT NULL,
    padecimiento_id INT NOT NULL,
    status ENUM('activo', 'resuelto', 'cronico', 'recurrente') DEFAULT 'activo',
    fecha_inicio DATE,
    fecha_resolucion DATE,
    notas TEXT,
    FOREIGN KEY (paciente_id) REFERENCES salud_pacientes(id),
    FOREIGN KEY (padecimiento_id) REFERENCES salud_padecimientos(id)
);

-- Triage (evaluacion de urgencia)
CREATE TABLE salud_triage (
    id INT AUTO_INCREMENT PRIMARY KEY,
    paciente_id INT NOT NULL,
    cita_id INT,
    nivel ENUM('verde', 'amarillo', 'naranja', 'rojo') DEFAULT 'verde',
    sintomas JSON,
    respuestas_triage JSON,
    puntuacion INT DEFAULT 0,
    recomendacion TEXT,
    evaluado_por INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paciente_id) REFERENCES salud_pacientes(id),
    FOREIGN KEY (cita_id) REFERENCES salud_citas(id)
);

-- Knowledge Base: Documentos y guias
CREATE TABLE salud_kb_documentos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    titulo VARCHAR(300) NOT NULL,
    tipo ENUM('guia_clinica', 'protocolo', 'nota_experiencia', 'articulo', 'otro'),
    padecimiento_id INT,
    contenido TEXT NOT NULL,
    archivo_path VARCHAR(500),
    subido_por INT NOT NULL,
    etiquetas JSON,
    version INT DEFAULT 1,
    activo BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (padecimiento_id) REFERENCES salud_padecimientos(id),
    INDEX idx_tipo (tipo),
    INDEX idx_padecimiento (padecimiento_id)
);

-- Knowledge Base: Embeddings (Fase 2+)
CREATE TABLE salud_kb_embeddings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    documento_id INT NOT NULL,
    chunk_text TEXT NOT NULL,
    chunk_index INT NOT NULL,
    embedding BLOB,
    modelo_embedding VARCHAR(100) DEFAULT 'sentence-transformers/all-MiniLM-L6-v2',
    metadata JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (documento_id) REFERENCES salud_kb_documentos(id) ON DELETE CASCADE,
    INDEX idx_documento (documento_id)
);

-- RAG: Consultas historicas
CREATE TABLE salud_rag_consultas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    consultado_por INT NOT NULL,
    pregunta TEXT NOT NULL,
    contexto_recuperado JSON,
    respuesta TEXT,
    confianza FLOAT,
    modelo_llm VARCHAR(100),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (consultado_por) REFERENCES kadrix_users(id)
);

-- RAG: Config
CREATE TABLE salud_rag_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    fase ENUM('fase1_kb_estatica', 'fase2_embeddings', 'fase3_rag_completo') DEFAULT 'fase1_kb_estatica',
    modelo_embedding VARCHAR(200),
    modelo_llm VARCHAR(200),
    config JSON,
    activo BOOLEAN DEFAULT TRUE,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Vista: Citas del dia
CREATE VIEW v_citas_hoy AS
SELECT c.*, p.nombre AS paciente_nombre, p.apellido_paterno, p.apellido_materno,
       m.nombre AS medico_nombre, m.especialidad,
       con.nombre AS consultorio_nombre,
       pad.nombre AS padecimiento_nombre
FROM salud_citas c
JOIN salud_pacientes p ON c.paciente_id = p.id
JOIN salud_medicos m ON c.medico_id = m.id
JOIN salud_consultorios con ON c.consultorio_id = con.id
LEFT JOIN salud_padecimientos pad ON c.padecimiento_id = pad.id
WHERE c.fecha = CURDATE()
ORDER BY c.hora_inicio;

-- Vista: Proximas citas
CREATE VIEW v_proximas_citas AS
SELECT c.*, p.nombre AS paciente_nombre, p.apellido_paterno,
       m.nombre AS medico_nombre, m.especialidad,
       pad.nombre AS padecimiento_nombre
FROM salud_citas c
JOIN salud_pacientes p ON c.paciente_id = p.id
JOIN salud_medicos m ON c.medico_id = m.id
LEFT JOIN salud_padecimientos pad ON c.padecimiento_id = pad.id
WHERE c.fecha >= CURDATE() AND c.status IN ('agendada', 'confirmada')
ORDER BY c.fecha, c.hora_inicio;

-- Vista: Pacientes por familia
CREATE VIEW v_familia_pacientes AS
SELECT f.*, p.id AS paciente_id, p.nombre, p.apellido_paterno, p.parentesco,
       p.fecha_nacimiento, p.sexo
FROM salud_familias f
JOIN salud_pacientes p ON p.familia_id = f.id
WHERE p.activo = TRUE
ORDER BY f.apellido_principal, p.es_titular DESC;

-- Vista: Expediente completo (solo duenya)
CREATE VIEW v_expediente_completo AS
SELECT p.*,
       GROUP_CONCAT(DISTINCT pad.nombre) AS padecimientos_activos,
       (SELECT COUNT(*) FROM salud_citas c WHERE c.paciente_id = p.id) AS total_citas,
       (SELECT COUNT(*) FROM salud_citas c WHERE c.paciente_id = p.id AND c.status = 'completada') AS citas_completadas,
       (SELECT MAX(c.fecha) FROM salud_citas c WHERE c.paciente_id = p.id AND c.status IN ('agendada','confirmada')) AS proxima_cita
FROM salud_pacientes p
LEFT JOIN salud_paciente_padecimientos pp ON p.id = pp.paciente_id AND pp.status = 'activo'
LEFT JOIN salud_padecimientos pad ON pp.padecimiento_id = pad.id
WHERE p.activo = TRUE
GROUP BY p.id;

-- Seed data: Padecimientos comunes
INSERT INTO salud_padecimientos (codigo, nombre, categoria, urgencia_base, especialidades, estudios_recomendados, preguntas_triage, flags_rojo) VALUES
('dolor_cabeza', 'Cefalea / Dolor de cabeza', 'consulta', 2, '["medicina_general", "neurologia"]', '["biometria_hematica", "tomografia"]', '["Es el peor dolor de cabeza de tu vida?", "Tienes fiebre?", "Tienes rigidez en el cuello?"]', '["peor_dolor", "fiebre_alta", "rigidez_cuello"]'),
('dolor_pecho', 'Dolor en el pecho', 'urgencias', 5, '["urgencias", "cardiologia"]', '["ecg", "troponinas", "rayos_x"]', '["El dolor se irradia al brazo izquierdo?", "Tienes dificultad para respirar?"]', '["irradia_brazo", "disnea"]'),
('diabetes_seguimiento', 'Seguimiento de Diabetes', 'cronico', 1, '["medicina_general", "endocrinologia"]', '["glucosa_ayunas", "hemoglobina_glicosilada", "perfil_lipidico"]', '["Ha tenido hipoglucemias recientes?", "Ha notado cambios en la vision?"]', '["hipoglucemia_severa", "vision_borrosa"]'),
('hipertension_seguimiento', 'Seguimiento de Hipertension', 'cronico', 1, '["medicina_general", "cardiologia"]', '["presion_arterial", "electrocardiograma", "perfil_lipidico"]', '["Ha tenido cefalea intensa?", "Ha notado vision borrosa?"]', '["cefalea_intensa", "vision_borrosa", "dolor_pecho"]'),
('infeccion_respiratoria', 'Infeccion respiratoria', 'consulta', 2, '["medicina_general", "neumologia"]', '["biometria_hematica", "rayos_x_torax"]', '["Tienes fiebre?", "Tienes dificultad para respirar?", "Tienes tos con flema?"]', '["fiebre_alta", "disnea", "hemoptisis"]'),
('dolor_abdominal', 'Dolor abdominal', 'consulta', 3, '["medicina_general", "gastroenterologia"]', '["biometria_hematica", "quimica_sanguinea", "ultrasonido"]', '["El dolor es localizado o generalizado?", "Tienes nausea o vomito?"]', '["dolor_localizado", "vomito", "fiebre"]'),
('chequeo_general', 'Chequeo general / Preventivo', 'preventivo', 1, '["medicina_general"]', '["biometria_hematica", "quimica_sanguinea", "examen_orina"]', '[]', '[]'),
('lesion_muscular', 'Lesion muscular / Esqueletica', 'consulta', 2, '["medicina_general", "ortopedia"]', '["rayos_x", "resonancia"]', '["Hay inflamacion visible?", "Puedes mover la extremidad?"]', '["inflamacion_severa", "imposibilidad_mover"]');

-- Seed data: Medicos
INSERT INTO salud_medicos (nombre, especialidad, cedula, telefono, email) VALUES
('Dr. Carlos Mendoza', 'medicina_general', '12345678', '555-0101', 'cmendoza@bris.local'),
('Dra. Maria Elena Vazquez', 'cardiologia', '23456789', '555-0102', 'mevazquez@bris.local'),
('Dr. Roberto Sanchez', 'neurologia', '34567890', '555-0103', 'rsanchez@bris.local'),
('Dra. Ana Luisa Garcia', 'endocrinologia', '45678901', '555-0104', 'algarcia@bris.local'),
('Dr. Fernando Lopez', 'ortopedia', '56789012', '555-0105', 'flopez@bris.local');

-- Seed data: Consultorios
INSERT INTO salud_consultorios (codigo, nombre, tipo, capacidad) VALUES
('C1', 'Consultorio 1', 'consulta', 1),
('C2', 'Consultorio 2', 'consulta', 1),
('C3', 'Consultorio 3', 'consulta', 1),
('URG', 'Urgencias', 'urgencias', 3),
('LAB', 'Laboratorio', 'laboratorio', 2),
('IMG', 'Imagenologia', 'imagenologia', 2);

-- Seed data: RAG config (inicia en Fase 1)
INSERT INTO salud_rag_config (fase, modelo_embedding, modelo_llm, config) VALUES
('fase1_kb_estatica', NULL, NULL, '{"disponible": true, "busqueda": "fulltext"}');
```

---

## Estructura de Archivos

```
bris_dash/
+-- salud/
|   +-- __init__.py                 # Blueprint registration (prefijo /salud/)
|   +-- db.py                       # Reutiliza kadrix/db.py para MySQL
|   +-- auth.py                     # Login, roles, permisos
|   +-- agentes/
|   |   +-- __init__.py
|   |   +-- recepcion.py            # Agente 1: Recepcion y Wizard
|   |   +-- paciente.py             # Agente 2: Paciente y Familia
|   |   +-- citas.py                # Agente 3: Citas
|   |   +-- diagnostico.py          # Agente 4: Diagnostico y Opciones
|   |   +-- seguimiento.py          # Agente 5: Seguimiento (SOLO DUENYA)
|   |   +-- reportes.py             # Agente 6: Reportes (SOLO DUENYA)
|   |   +-- kb_rag.py               # Agente 7: Knowledge Base + RAG (SOLO DUENYA)
|   +-- forms/
|   |   +-- __init__.py
|   |   +-- wizard.py               # WTForms para wizard multi-paso
|   |   +-- paciente.py             # Formularios de paciente
|   |   +-- cita.py                 # Formularios de cita
|   |   +-- triage.py               # Formulario de triage
|   +-- utils/
|       +-- __init__.py
|       +-- permisos.py             # Decoradores de rol y permisos
|       +-- padecimientos.py        # Catalogo y logica de opciones
|       +-- triage.py               # Algoritmo de triage
|       +-- disponibilidad.py      # Calculo de slots disponibles
+-- templates/
|   +-- salud/
|       +-- base.html                # Layout con sidebar diferenciado por rol
|       +-- sin_permiso.html         # Pagina de acceso denegado
|       +-- recepcion/
|       |   +-- dashboard.html
|       |   +-- wizard/
|       |       +-- paso1_personal.html
|       |       +-- paso2_historial.html
|       |       +-- paso3_padecimiento.html
|       |       +-- paso4_confirmar.html
|       +-- paciente/
|       |   +-- perfil.html         # Basico (ambos) / Completo (duenya)
|       |   +-- editar.html
|       |   +-- expediente.html     # SOLO DUENYA
|       |   +-- buscar.html
|       +-- familia/
|       |   +-- detalle.html        # SOLO DUENYA
|       |   +-- vincular.html
|       +-- citas/
|       |   +-- calendario.html
|       |   +-- nueva.html
|       |   +-- detalle.html
|       |   +-- hoy.html
|       +-- diagnostico/
|       |   +-- opciones.html
|       |   +-- triage.html
|       +-- seguimiento/             # SOLO DUENYA
|       |   +-- dashboard.html
|       |   +-- paciente.html
|       |   +-- alertas.html
|       +-- reportes/               # SOLO DUENYA
|       |   +-- dashboard.html
|       +-- kb/                      # SOLO DUENYA
|       |   +-- dashboard.html
|       |   +-- guias.html
|       |   +-- guia_detalle.html
|       +-- rag/                     # SOLO DUENYA
|           +-- consulta.html
|           +-- roadmap.html
+-- static/
|   +-- salud/
|       +-- css/
|       |   +-- salud.css
|       +-- js/
|           +-- wizard.js
|           +-- triage.js
|           +-- citas.js
|           +-- opciones.js
|           +-- rag.js               # Consultas RAG (Fase 3)
+-- data/
|   +-- salud/
|       +-- padecimientos.json
|       +-- sintomas.json
|       +-- especialidades.json
+-- scripts/
    +-- load_salud_schema.py
+-- docker-compose.yml
```

---

## Flujo de Interaccion Multiagente (con roles)

```
PACIENTE LLEGA
      |
      v
+----------------------------------+
|  AGENTE RECEPCION                |
|  (Asistente o Duenya)            |
|  - Ya estas registrado?          |
|  - No -> Wizard 4 pasos          |
|  - Si -> Buscar paciente         |
+----------+-----------------------+
           |
           v
+----------------------------------+     +----------------------------------+
|  AGENTE DIAGNOSTICO              |     |  AGENTE PACIENTE                 |
|  (Ambos roles)                   |     |  (Duenya ve expediente COMPLETO) |
|  - Cual es tu padecimiento?      |     |  (Asistente ve SOLO datos basicos)|
|  - Triage (sintomas)             |     |  - Nombre, telefono, cita        |
|  - Opciones dinamicas            |     |  - NO ve diagnostico/tratamiento  |
|    segun padecimiento            |     +----------+-----------------------+
+----------+-----------------------+                |
           |                                        |
           v                                        v
+----------------------------------+     +----------------------------------+
|  OPCIONES PRESENTADAS            |     |  Agendar cita?                   |
|  - Especialista                  |     |                                  |
|  - Estudios a realizar           |----->  AGENTE CITAS                  |
|  - Urgencia calculada            |     |  - Disponibilidad                |
|  - Proximos pasos                |     |  - Agendar/Reagendar             |
+----------+-----------------------+     |  - Confirmacion                 |
           |                            +----------+-----------------------+
           |                                        |
           |           +----------------------------+
           |           |                            |
           v           v                            v
+----------------------------------+     +----------------------------------+
|  AGENTE SEGUIMIENTO              |     |  CITA CONFIRMADA                 |
|  (SOLO DUENYA)                   |     |  - Email / SMS                   |
|  - Recordatorios                 |     |  - Notas del medico (duenya)     |
|  - Post-consulta                 |     |  - Proxima cita                  |
|  - Alertas                       |     +----------------------------------+
|  - Tratamiento                   |
+----------+-----------------------+
           |
           v
+----------------------------------+
|  AGENTE KB + RAG                 |
|  (SOLO DUENYA)                   |
|  - Guias clinicas                |
|  - Casos similares               |
|  - Consultas IA (Fase 3)         |
|  - Expedientes como contexto     |
+----------------------------------+
```

---

## Opciones Dinamicas por Padecimiento

**Solo se muestran opciones relevantes segun el padecimiento del paciente.**

La duena ve opciones PLUS recomendaciones de la KB/RAG. La asistente solo ve opciones basicas para agendar.

```python
# salud/agentes/diagnostico.py

def get_opciones_por_padecimiento(padecimiento_codigo: str, rol: str = "asistente"):
    """Retorna opciones filtradas por rol y padecimiento."""
    base = PADECIMIENTO_OPCIONES.get(padecimiento_codigo, {})

    opciones_asistente = {
        "especialistas_disponibles": base.get("especialistas_disponibles", []),
        "urgencia_calculada": base.get("urgencia_base", 1),
        "estudios_sugeridos": base.get("estudios_sugeridos", []),
    }

    opciones_duenya = {
        **opciones_asistente,
        "preguntas_triage": base.get("preguntas_triage", []),
        "flags_triage": base.get("flags_triage", {}),
        "recomendaciones_kb": _buscar_en_kb(padecimiento_codigo),
        "casos_similares": _buscar_casos_similares(padecimiento_codigo),
        "guias_clinicas": _buscar_guias(padecimiento_codigo),
    }

    return opciones_duenya if rol == "duenya" else opciones_asistente
```

---

## Integracion con Kadrix Existente

| Componente Kadrix | Componente Salud | Relacion |
|--------------------|-------------------|----------|
| `kadrix_users` | Reutilizado + roles extendidos | `asistente`, `duenya` agregados al ENUM |
| `kadrix_boards` | Tablero de citas | Kanban para seguimiento de citas |
| `kadrix_tasks` | Tareas de seguimiento | Tareas post-consulta |
| `kadrix_activities` | Actividades medicas | Registro de consultas |
| `kadrix_fixtures` | Consultorios | Equipamiento por sala |
| ROI Analytics | Reportes salud (duenya) | Extender dashboard |
| Base.html | Extendido | Sidebar diferenciado por rol |

### Sidebar por rol:

```
ASISTENTE SIDEBAR:              DUENYA SIDEBAR:
+-----------------------+      +-----------------------+
| Recepcion             |      | Recepcion             |
| Buscar Paciente       |      | Buscar Paciente       |
| Agendar Cita          |      | Agendar Cita          |
| Citas del Dia         |      | Citas del Dia         |
| Nuevo Paciente        |      | Nuevo Paciente        |
|                       |      |-----------------------|
|                       |      | Expedientes           |
|                       |      | Familias              |
|                       |      | Seguimiento           |
|                       |      | Diagnosticos          |
|                       |      |-----------------------|
|                       |      | Knowledge Base        |
|                       |      | Consultas RAG         |
|                       |      | Reportes              |
|                       |      |-----------------------|
|                       |      | Kadrix (existente)    |
+-----------------------+      +-----------------------+
```

---

## Prioridades de Implementacion

| Fase | Componente | Tiempo estimado |
|------|-------------|-----------------|
| **1** | Schema MySQL + seed data + permisos | 1 dia |
| **2** | Auth + roles (asistente/duenya) | 1 dia |
| **3** | Agente Recepcion (Wizard) | 2 dias |
| **4** | Agente Paciente/Familia (con permisos) | 1.5 dias |
| **5** | Agente Citas | 2 dias |
| **6** | Agente Diagnostico (opciones dinamicas) | 2 dias |
| **7** | Agente Seguimiento (duenya) | 1 dia |
| **8** | Agente Reportes (duenya) | 1 dia |
| **9** | Agente KB estatica (Fase 1 RAG) | 1.5 dias |
| **10** | Integracion UI + Sidebar por rol | 1 dia |
| **11** | Testing + ajustes | 1 dia |
| **Total** | | **~15 dias** |

### Roadmap KB/RAG:

| Fase RAG | Descripcion | Tiempo |
|----------|-------------|--------|
| **Fase 1** | KB estatica: subir guias, busqueda fulltext, vinculacion padecimientos | Incluido en Fase 9 |
| **Fase 2** | Embeddings: sentence-transformers, vector store, busqueda semantica | +3 dias |
| **Fase 3** | RAG completo: LLM integration, consultas NL, dashboard metricas | +5 dias |

---

## Notas Tecnicas

- **Reutiliza** `kadrix/db.py` para conexion MySQL (ya maneja fallback graceful)
- **Extiende** `base.html` con navbar seccion "Salud" diferenciado por rol
- **JavaScript**: Wizard multi-paso con validacion en cada paso, sin recarga completa
- **APIs JSON**: Todos los agentes exponen APIs para futuro frontend React/Vue
- **Triage automatico**: Puntuacion basada en flags del catalogo de padecimientos
- **Familias**: Vinculacion por `familia_id`, permisos de titulares para ver expedientes de dependientes
- **Horarios**: Matriz medico x dia x hora para calculo de disponibilidad
- **Permisos**: Decoradores `@requiere_rol("duenya")` y helper `puede_ver()` en templates
- **KB Fase 1**: Almacenamiento de documentos en `data/salud/kb/`, busqueda FULLTEXT MySQL
- **KB Fase 2**: ChromaDB local o FAISS para embeddings
- **KB Fase 3**: Ollama (local) o API (OpenAI) para generacion