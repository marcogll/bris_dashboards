# Plan Multiagente — BRIS Salud

## Overview

Extender el dashboard BRIS/Kadrix existente para crear un **sistema de gestión médica multiagente** que atiende familias, registra pacientes via wizard, agenda citas, y ofrece opciones inteligentes basadas en padecimientos.

---

## Arquitectura Multiagente

### Agente 1: Recepción / Triage (`recepcion/`)

**Propósito:** Primer punto de contacto. Determina el camino del paciente.

| Función | Descripción |
|---------|-------------|
| Wizard de registro | Formulario multi-paso que recolecta datos del paciente paso a paso |
| Triage inteligente | Clasifica urgencia y tipo de atención según síntomas |
| Routing | Envía al paciente al agente correcto (citas, diagnóstico, seguimiento) |
| Identificación | Verifica si el paciente ya existe o es nuevo |

**Endpoints:**
- `GET /salud/` — Dashboard recepción
- `GET /salud/wizard/` — Wizard paso 1: datos personales
- `POST /salud/wizard/personal` — Guarda datos personales, redirige a paso 2
- `GET /salud/wizard/<id>/historial` — Paso 2: antecedentes
- `POST /salud/wizard/<id>/historial` — Guarda historial, redirige a paso 3
- `GET /salud/wizard/<id>/padecimiento` — Paso 3: síntomas/padecimiento actual
- `POST /salud/wizard/<id>/padecimiento` — Guarda padecimiento, redirige a opciones
- `GET /salud/wizard/<id>/confirmar` — Paso 4: confirmación y resumen

**Wizard de Registro (4 pasos):**

```
Paso 1: Datos Personales
├── Nombre completo
├── Fecha de nacimiento
├── Sexo
├── Teléfono
├── Email
├── Dirección
└── ¿Pertenece a una familia registrada? → Si sí, vincular

Paso 2: Antecedentes
├── Alergias (multi-select + texto libre)
├── Enfermedades crónicas (multi-select + texto libre)
├── Medicamentos actuales (multi-select + texto libre)
├── Antecedentes heredo-familiares (diabetes, hipertensión, cáncer, etc.)
├── Cirugías previas
└── Hábitos (tabaco, alcohol, ejercicio)

Paso 3: Padecimiento Actual
├── ¿Qué te trae hoy? (texto libre + categorías sugeridas)
├── Síntomas principales (multi-select dinámico según categoría)
├── Intensidad del dolor (1-10 escala visual)
├── Tiempo de evolución (horas/días/semanas/meses)
├── ¿Es urgencia? (auto-detectado o manual)
└── Notas adicionales

Paso 4: Confirmación y Opciones
├── Resumen de datos capturados
├── Opciones recomendadas según padecimiento (Agente Diagnóstico)
├── Disponibilidad de citas (Agente Citas)
└── Confirmar → Crear paciente + Agendar cita
```

---

### Agente 2: Paciente / Familia (`paciente/`)

**Propósito:** Gestión del expediente paciente y relaciones familiares.

| Función | Descripción |
|---------|-------------|
| Perfil paciente | Ver/editar datos personales, historial, alergias |
| Grupo familiar | Vincular pacientes en familias, historial heredo-familiar compartido |
| Búsqueda | Buscar paciente por nombre, teléfono, ID |
| Expediente | Historial completo de citas, diagnósticos, tratamientos |

**Endpoints:**
- `GET /salud/paciente/<id>` — Perfil del paciente
- `GET /salud/paciente/<id>/editar` — Editar datos
- `POST /salud/paciente/<id>/editar` — Guardar cambios
- `GET /salud/paciente/<id>/expediente` — Expediente completo
- `GET /salud/familia/<id>` — Vista de grupo familiar
- `POST /salud/familia/vincular` — Vincular paciente a familia
- `GET /salud/buscar` — Buscar pacientes

**Modelo de Familia:**
```
salud_familias
├── id
├── apellido_principal
├── direccion_compartida (bool)
├── telefono_emergencia
├── notas
└── created_at

salud_pacientes (extension)
├── familia_id (FK → salud_familias)
├── es_titular (bool — responsable del grupo)
└── parentesco (hijo, conyuge, padre, etc.)
```

---

### Agente 3: Citas (`citas/`)

**Propósito:** Programación, reagendamiento y cancelación de citas.

| Función | Descripción |
|---------|-------------|
| Agendar cita | Crear cita para paciente existente o nuevo |
| Disponibilidad | Mostrar horarios disponibles por médico/especialidad |
| Reagendar | Mover cita existente |
| Cancelar | Cancelar cita con motivo |
| Recordatorios | Notificaciones automáticas |
| Calendario | Vista de calendario por médico/sala |

**Endpoints:**
- `GET /salud/citas/` — Calendario de citas
- `GET /salud/citas/nueva` — Formulario nueva cita
- `POST /salud/citas/nueva` — Crear cita
- `GET /salud/citas/<id>` — Detalle de cita
- `POST /salud/citas/<id>/reagendar` — Reagendar
- `POST /salud/citas/<id>/cancelar` — Cancelar
- `GET /salud/citas/disponibilidad` — API: slots disponibles (JSON)
- `GET /salud/citas/hoy` — Citas del día

---

### Agente 4: Diagnóstico / Padecimiento (`diagnostico/`)

**Propósito:** Motor de opciones inteligentes según el padecimiento del paciente.

| Función | Descripción |
|---------|-------------|
| Catálogo de padecimientos | Base de datos de condiciones médicas con especialidades |
| Opciones dinámicas | Según padecimiento, muestra especialistas, estudios, tratamientos |
| Triage automático | Clasifica urgencia según síntomas |
| Recomendaciones | Sugiere próximos pasos basados en historial |
| Flujos clínicos | Rutas predefinidas para condiciones comunes |

**Endpoints:**
- `GET /salud/diagnostico/opciones/<padecimiento_id>` — Opciones para un padecimiento
- `GET /salud/diagnostico/triage` — Evaluación de triage
- `POST /salud/diagnostico/triage` — Resultado de triage
- `GET /salud/api/padecimientos` — Catálogo de padecimientos (JSON)
- `GET /salud/api/padecimientos/<id>/opciones` — Opciones por padecimiento (JSON)
- `GET /salud/api/sintomas` — Lista de síntomas (JSON, filtrable)

**Lógica de opciones dinámicas:**

```python
PADECIMIENTO_OPCIONES = {
    "dolor_cabeza": {
        "urgencia_base": 2,
        "especialidades": ["medicina_general", "neurologia"],
        "estudios": ["biometria_hematica", "tomografia"],
        "preguntas_triage": [
            "¿Es el peor dolor de cabeza de tu vida?",
            "¿Tienes fiebre?",
            "¿Tienes rigidez en el cuello?",
        ],
        "flags_rojo": ["peor_dolor", "fiebre_alta", "rigidez_cuello"],  → urgencia alta
    },
    "dolor_pecho": {
        "urgencia_base": 4,
        "especialidades": ["urgencias", "cardiologia"],
        "estudios": ["ecg", "troponinas", "rayos_x"],
        "preguntas_triage": [
            "¿El dolor se irradia al brazo izquierdo?",
            "¿Tienes dificultad para respirar?",
        ],
        "flags_rojo": ["irradia_brazo", "disnea"],
    },
    "diabetes_seguimiento": {
        "urgencia_base": 1,
        "especialidades": ["medicina_general", "endocrinologia"],
        "estudios": ["glucosa_ayunas", "hemoglobina_glicosilada", "perfil_lipidico"],
        "preguntas_triage": [
            "¿Ha tenidohipoglucemiasrecientes?",
            "¿Ha notadocambios en la visión?",
        ],
        "flags_rojo": ["hipoglucemia_severa", "vision_borrosa"],
    },
    # ... más padecimientos
}
```

---

### Agente 5: Seguimiento (`seguimiento/`)

**Propósito:** Post-cita, recordatorios, seguimiento de tratamientos.

| Función | Descripción |
|---------|-------------|
| Recordatorios | Notificaciones antes de citas |
| Post-cita | Nota post-consulta, causas, tratamiento |
| Tratamiento | Seguimiento de medicamentos, próxima cita |
| Alertas | Señales de advertencia según condición |

**Endpoints:**
- `GET /salud/seguimiento/` — Dashboard seguimiento
- `GET /salud/seguimiento/<paciente_id>` — Seguimiento por paciente
- `POST /salud/seguimiento/<cita_id>/nota` — Agregar nota post-consulta
- `GET /salud/seguimiento/alertas` — Alertas activas
- `POST /salud/seguimiento/<paciente_id>/recordatorio` — Programar recordatorio

---

### Agente 6: Reportes / Analytics (`reportes/`)

**Propósito:** Estadísticas, reportes, dashboards gerenciales (extiende analytics existente).

| Función | Descripción |
|---------|-------------|
| Citas por día/semana/mes | Gráficas de ocupación |
| Pacientes nuevos vs recurrentes | Tendencias |
| Padecimientos más comunes | Epidemiología |
| Tiempos de espera | Eficiencia |
| Familiar | Estadísticas por grupo familiar |

**Endpoints:**
- `GET /salud/reportes/` — Dashboard general
- `GET /salud/api/reportes/citas` — API datos de citas
- `GET /salud/api/reportes/padecimientos` — API datos de padecimientos
- `GET /salud/api/reportes/pacientes` — API datos de pacientes

---

## Schema MySQL — Módulo Salud

```sql
-- ============================================================
-- Schema: Salud — Sistema de Gestión Médica Multiagente
-- ============================================================

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
    parentesco VARCHAR(50),  -- hijo, conyuge, padre, madre, hermano, etc.
    nombre VARCHAR(200) NOT NULL,
    apellido_paterno VARCHAR(100) NOT NULL,
    apellido_materno VARCHAR(100),
    fecha_nacimiento DATE,
    sexo ENUM('masculino', 'femenino', 'otro'),
    curp VARCHAR(18),
    telefono VARCHAR(20),
    email VARCHAR(255),
    direccion TEXT,
    alergias JSON,           -- ["penicilina", "latex", ...]
    enfermedades_cronicas JSON,  -- ["diabetes", "hipertension", ...]
    medicamentos_actuales JSON,   -- ["metformina 500mg", ...]
    antecedentes_heredofamiliares JSON,  -- {"diabetes": true, "cancer": false, ...}
    cirugias_previas JSON,    -- ["apendicectomia 2018", ...]
    habitos JSON,             -- {"tabaco": false, "alcohol": "ocasional", "ejercicio": "3x_semana"}
    notas_generales TEXT,
    activo BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (familia_id) REFERENCES salud_familias(id) ON DELETE SET NULL,
    INDEX idx_nombre (nombre, apellido_paterno),
    INDEX idx_familia (familia_id)
);

-- Padecimientos / Catálogo
CREATE TABLE salud_padecimientos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(50) UNIQUE NOT NULL,  -- 'dolor_cabeza', 'diabetes_seguimiento', etc.
    nombre VARCHAR(200) NOT NULL,
    categoria VARCHAR(100),     -- 'urgencias', 'cronico', 'consulta', 'preventivo'
    urgencia_base TINYINT DEFAULT 1,  -- 1-5 (1=bajo, 5=critico)
    especialidades JSON,       -- ["medicina_general", "neurologia"]
    estudios_recomendados JSON,  -- ["biometria_hematica", ...]
    preguntas_triage JSON,     -- ["¿Tienes fiebra?", ...]
    flags_rojo JSON,           -- ["fiebre_alta", "rigidez_cuello"]
    descripcion TEXT,
    activo BOOLEAN DEFAULT TRUE
);

-- Síntomas
CREATE TABLE salud_sintomas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(50) UNIQUE NOT NULL,
    nombre VARCHAR(200) NOT NULL,
    categoria VARCHAR(100),
    padraciones_relacionadas JSON,  -- ["dolor_cabeza", ...]
    activo BOOLEAN DEFAULT TRUE
);

-- Médicos
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

-- Horarios de médicos
CREATE TABLE salud_horarios_medico (
    id INT AUTO_INCREMENT PRIMARY KEY,
    medico_id INT NOT NULL,
    consultorio_id INT NOT NULL,
    dia_semana TINYINT NOT NULL,  -- 1=Lun ... 7=Dom
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
    motivacion TEXT,         -- Razón de la cita (texto libre)
    sintomas_reportados JSON,  -- ["cefalea", "fiebre", ...]
    urgencia_calculada TINYINT DEFAULT 1,  -- Calculada por Agente Diagnóstico
    notas_previas TEXT,         -- Notas antes de la cita
    notas_posterior TEXT,        -- Notas después de la cita
    diagnostico TEXT,            -- Diagnóstico del médico
    tratamiento JSON,           -- {"medicamentos": [...], "indicaciones": "...", "reposo": "3 dias"}
    proxima_cita_sugerida DATE, -- Fecha sugerida para próxima cita
    cancelado_motivo VARCHAR(200),
    creado_por INT,             -- FK → kadrix_users.id (quien agendó)
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

-- Triage (evaluación de urgencia)
CREATE TABLE salud_triage (
    id INT AUTO_INCREMENT PRIMARY KEY,
    paciente_id INT NOT NULL,
    cita_id INT,
    nivel ENUM('verde', 'amarillo', 'naranja', 'rojo') DEFAULT 'verde',
    sintomas JSON,
    respuestas_triage JSON,
    puntuacion INT DEFAULT 0,
    recomendacion TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paciente_id) REFERENCES salud_pacientes(id),
    FOREIGN KEY (cita_id) REFERENCES salud_citas(id)
);

-- Vista: Citas del día
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

-- Vista: Próximas citas por paciente
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

-- Seed data: Padecimientos comunes
INSERT INTO salud_padecimientos (codigo, nombre, categoria, urgencia_base, especialidades, estudios_recomendados, preguntas_triage, flags_rojo) VALUES
('dolor_cabeza', 'Cefalea / Dolor de cabeza', 'consulta', 2, '["medicina_general", "neurologia"]', '["biometria_hematica", "tomografia"]', '["¿Es el peor dolor de cabeza de tu vida?", "¿Tienes fiebre?", "¿Tienes rigidez en el cuello?"]', '["peor_dolor", "fiebre_alta", "rigidez_cuello"]'),
('dolor_pecho', 'Dolor en el pecho', 'urgencias', 5, '["urgencias", "cardiologia"]', '["ecg", "troponinas", "rayos_x"]', '["¿El dolor se irradia al brazo izquierdo?", "¿Tienes dificultad para respirar?"]', '["irradia_brazo", "disnea"]'),
('diabetes_seguimiento', 'Seguimiento de Diabetes', 'cronico', 1, '["medicina_general", "endocrinologia"]', '["glucosa_ayunas", "hemoglobina_glicosilada", "perfil_lipidico"]', '["¿Ha tenido hipoglucemias recientes?", "¿Ha notado cambios en la visión?"]', '["hipoglucemia_severa", "vision_borrosa"]'),
('hipertension_seguimiento', 'Seguimiento de Hipertensión', 'cronico', 1, '["medicina_general", "cardiologia"]', '["presion_arterial", "electrocardiograma", "perfil_lipidico"]', '["¿Ha tenido cefalea intensa?", "¿Ha notado visión borrosa?"]', '["cefalea_intensa", "vision_borrosa", "dolor_pecho"]'),
('infeccion_respiratoria', 'Infección respiratoria', 'consulta', 2, '["medicina_general", "neumologia"]', '["biometria_hematica", "rayos_x_torax"]', '["¿Tienes fiebre?", "¿Tienes dificultad para respirar?", "¿Tienes tos con flema?"]', '["fiebre_alta", "disnea", "hemoptisis"]'),
('dolor_abdominal', 'Dolor abdominal', 'consulta', 3, '["medicina_general", "gastroenterologia"]', '["biometria_hematica", "quimica_sanguinea", "ultrasonido"]', '["¿El dolor es localizado o generalizado?", "¿Tienes náusea o vómito?"]', '["dolor_localizado", "vomito", "fiebre"]'),
('chequeo_general', 'Chequeo general / Preventivo', 'preventivo', 1, '["medicina_general"]', '["biometria_hematica", "quimica_sanguinea", "examen_orina"]', '[]', '[]'),
('lesion_muscular', 'Lesión muscular / Esquelética', 'consulta', 2, '["medicina_general", "ortopedia"]', '["rayos_x", "resonancia"]', '["¿Hay inflamación visible?", "¿Puedes mover la extremidad?"]', '["inflamacion_severa", "imposibilidad_mover"]');

-- Seed data: Médicos
INSERT INTO salud_medicos (nombre, especialidad, cedula, telefono, email) VALUES
('Dr. Carlos Mendoza', 'medicina_general', '12345678', '555-0101', 'cmendoza@bris.local'),
('Dra. María Elena Vázquez', 'cardiologia', '23456789', '555-0102', 'mevazquez@bris.local'),
('Dr. Roberto Sánchez', 'neurologia', '34567890', '555-0103', 'rsanchez@bris.local'),
('Dra. Ana Luisa García', 'endocrinologia', '45678901', '555-0104', 'algarcia@bris.local'),
('Dr. Fernando López', 'ortopedia', '56789012', '555-0105', 'flopez@bris.local');

-- Seed data: Consultorios
INSERT INTO salud_consultorios (codigo, nombre, tipo, capacidad) VALUES
('C1', 'Consultorio 1', 'consulta', 1),
('C2', 'Consultorio 2', 'consulta', 1),
('C3', 'Consultorio 3', 'consulta', 1),
('URG', 'Urgencias', 'urgencias', 3),
('LAB', 'Laboratorio', 'laboratorio', 2),
('IMG', 'Imagenología', 'imagenologia', 2);
```

---

## Estructura de Archivos

```
bris_dash/
├── salud/                          # Nuevo módulo multiagente
│   ├── __init__.py                 # Blueprint registration (prefijo /salud/)
│   ├── db.py                       # Reutiliza kadrix/db.py para MySQL
│   ├── agentes/
│   │   ├── __init__.py
│   │   ├── recepcion.py            # Agente 1: Recepción y Wizard
│   │   ├── paciente.py             # Agente 2: Paciente y Familia
│   │   ├── citas.py                # Agente 3: Citas
│   │   ├── diagnostico.py          # Agente 4: Diagnóstico y Opciones
│   │   ├── seguimiento.py          # Agente 5: Seguimiento
│   │   └── reportes.py             # Agente 6: Reportes y Analytics
│   ├── forms/
│   │   ├── __init__.py
│   │   ├── wizard.py               # WTForms para wizard multi-paso
│   │   ├── paciente.py             # Formularios de paciente
│   │   ├── cita.py                 # Formularios de cita
│   │   └── triage.py               # Formulario de triage
│   └── utils/
│       ├── __init__.py
│       ├── padecimientos.py        # Catálogo y lógica de opciones
│       ├── triage.py               # Algoritmo de triage
│       └── disponibilidad.py      # Cálculo de slots disponibles
├── templates/
│   └── salud/
│       ├── base.html                # Layout base con sidebar de salud
│       ├── recepcion/
│       │   ├── dashboard.html       # Dashboard recepción
│       │   └── wizard/
│       │       ├── paso1_personal.html
│       │       ├── paso2_historial.html
│       │       ├── paso3_padecimiento.html
│       │       └── paso4_confirmar.html
│       ├── paciente/
│       │   ├── perfil.html
│       │   ├── editar.html
│       │   ├── expediente.html
│       │   └── buscar.html
│       ├── familia/
│       │   ├── detalle.html
│       │   └── vincular.html
│       ├── citas/
│       │   ├── calendario.html
│       │   ├── nueva.html
│       │   ├── detalle.html
│       │   └── hoy.html
│       ├── diagnostico/
│       │   ├── opciones.html
│       │   └── triage.html
│       ├── seguimiento/
│       │   ├── dashboard.html
│       │   ├── paciente.html
│       │   └── alertas.html
│       └── reportes/
│           └── dashboard.html
├── static/
│   └── salud/
│       ├── css/
│       │   └── salud.css            # Estilos específicos de salud
│       └── js/
│           ├── wizard.js            # Lógica del wizard (validation, steps)
│           ├── triage.js            # Lógica de triage dinámico
│           ├── citas.js             # Calendario y disponibilidad
│           └── opciones.js          # Opciones dinámicas por padecimiento
├── data/
│   └── salud/
│       ├── padecimientos.json       # Catálogo de padecimientos (fallback)
│       ├── sintomas.json            # Catálogo de síntomas
│       └── especialidades.json      # Catálogo de especialidades
├── scripts/
│   └── load_salud_schema.py         # Script para cargar schema MySQL
└── docker-compose.yml               # Agregar servicio de salud
```

---

## Flujo de Interacción Multiagente

```
┌─────────────────────────────────────────────────────────────────┐
│                    PACIENTE LLEGA                               │
└─────────────┬───────────────────────────────────────────────────┘
              │
              ▼
┌──────────────────────────┐
│  AGENTE RECEPCIÓN        │  ¿Ya estás registrado?
│  - Wizard de Registro    │──── No ──→ Wizard 4 pasos
│  - Identificación        │                │
│  - Triage inicial        │──── Sí ──→ Buscar paciente
└──────────┬───────────────┘                │
           │                                │
           ▼                                ▼
┌──────────────────────────┐    ┌───────────────────────┐
│  AGENTE DIAGNÓSTICO      │    │  AGENTE PACIENTE      │
│  - ¿Cuál es tu           │    │  - Mostrar expediente  │
│    padecimiento?         │    │  - Historial familiar  │
│  - Triage (síntomas)     │    │  - Citas previas      │
│  - Opciones dinámicas    │    └───────────┬───────────┘
│    según padecimiento    │                │
└──────────┬───────────────┘                │
           │                                │
           ▼                                ▼
┌──────────────────────────┐    ┌───────────────────────┐
│  OPCIONES PRESENTADAS    │    │  ¿Agendar cita?       │
│  - Especialista          │    │                         │
│  - Estudios a realizar   │─────→ AGENTE CITAS          │
│  - Urgencia calculada    │    │  - Disponibilidad      │
│  - Próximos pasos        │    │  - Agendar/Reagendar   │
└──────────┬───────────────┘    │  - Confirmación        │
           │                    └───────────┬───────────┘
           │                                │
           ▼                                ▼
┌──────────────────────────┐    ┌───────────────────────┐
│  AGENTE SEGUIMIENTO      │    │  CITA CONFIRMADA       │
│  - Recordatorios         │    │  - Email / SMS         │
│  - Post-consulta         │    │  - Notas del médico    │
│  - Alertas               │    │  - Próxima cita        │
│  - Tratamiento           │    └───────────────────────┘
└──────────────────────────┘
```

---

## Opciones Dinámicas por Padecimiento

La característica principal: **solo se muestran opciones relevantes según el padecimiento del paciente**.

```python
# salud/agentes/diagnostico.py

PADACIMIENTO = {
    "dolor_cabeza": {
        "categorias_sintomas": [
            {"grupo": "Tipo de dolor", "opciones": ["Pulsátil", "Opresivo", "Punzante", "Sordo"]},
            {"grupo": "Localización", "opciones": ["Frontal", "Temporal", "Occipital", "Generalizada"]},
            {"grupo": "Asociados", "opciones": ["Náusea", "Fotofobia", "Vértigo", "Mareo"]},
        ],
        "especialistas_disponibles": [
            {"especialidad": "Medicina General", "urgencia": "baja", "espera": "1-2 días"},
            {"especialidad": "Neurología", "urgencia": "media", "espera": "3-5 días"},
            {"especialidad": "Urgencias", "urgencia": "alta", "espera": "inmediata"},
        ],
        "estudios_sugeridos": [
            {"estudio": "Biometría hemática", "requerido": True, "duracion": "30 min"},
            {"estudio": "Tomografía cerebral", "requerido": False, "condicion": "si_dolor_severo"},
        ],
        "preguntas_obligatorias": [
            "¿Es el peor dolor de cabeza de tu vida?",
            "¿Tienes fiebre?",
            "¿Tienes rigidez en el cuello?",
        ],
        "flags_triage": {
            "rojo": ["peor_dolor", "fiebre_alta", "rigidez_cuello", "perdida_conocimiento"],
            "naranja": ["vomito", "vision_borrosa", "confusion"],
            "amarillo": ["dolor_severo", "empeorando"],
            "verde": ["dolor_leve", "sin_otros_sintomas"],
        }
    },
    # ... más padecimientos se cargan dinámicamente
}
```

---

## Integración con Kadrix Existente

| Componente Kadrix | Componente Salud | Relación |
|--------------------|-------------------|----------|
| `kadrix_users` | Reutilizado | Usuarios del sistema (médicos, recepcionistas, admins) |
| `kadrix_boards` | Tablero de citas | Kanban para seguimiento de citas |
| `kadrix_tasks` | Tareas de seguimiento | Tareas post-consulta |
| `kadrix_activities` | Actividades médicas | Registro de consultas |
| `kadrix_fixtures` | Consultorios | Equipamiento por sala |
| ROI Analytics | Reportes salud | Extender dashboard |
| Base.html | Extendido | Sidebar con sección "Salud" |

---

## Prioridades de Implementación

| Fase | Componente | Tiempo estimado |
|------|-------------|-----------------|
| **1** | Schema MySQL +
 seed data | 1 día |
| **2** | Agente Recepción (Wizard) | 2 días |
| **3** | Agente Paciente/Familia | 1.5 días |
| **4** | Agente Citas | 2 días |
| **5** | Agente Diagnóstico (opciones dinámicas) | 2 días |
| **6** | Agente Seguimiento | 1 día |
| **7** | Agente Reportes | 1 día |
| **8** | Integración UI + Sidebar | 1 día |
| **9** | Testing + ajustes | 1 día |
| **Total** | | **~12.5 días** |

---

## Notas Técnicas

- **Reutiliza** `kadrix/db.py` para conexión MySQL (ya maneja fallback graceful)
- **Extiende** `base.html` con navbar sección "Salud" 
- **JavaScript**: Wizard multi-paso con validación en cada paso, sin recarga completa
- **APIs JSON**: Todos los agentes exponen APIs para futuro frontend React/Vue
- **Triage automático**: Puntuación basada en flags del catálogo de padecimientos
- **Familias**: Vinculación por `familia_id`, permisos de titulares para ver expedientes de dependientes
- **Horarios**: Matriz médico × día × hora para cálculo de disponibilidad