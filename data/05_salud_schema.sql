-- ============================================================
-- Schema: Salud — Sistema de Gestion Medica Multiagente
-- Base de datos: bris_adriana (misma DB que Kadrix)
-- ============================================================

-- Extender roles de usuario
ALTER TABLE kadrix_users MODIFY COLUMN role ENUM(
    'admin', 'manager', 'technician', 'operator', 'viewer',
    'asistente', 'duenya'
) DEFAULT 'asistente';

-- ============================================================
-- Familias
-- ============================================================
CREATE TABLE IF NOT EXISTS salud_familias (
    id INT AUTO_INCREMENT PRIMARY KEY,
    apellido_principal VARCHAR(100) NOT NULL,
    direccion TEXT,
    telefono_emergencia VARCHAR(20),
    correo_comun VARCHAR(255),
    notas TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- Pacientes
-- ============================================================
CREATE TABLE IF NOT EXISTS salud_pacientes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    familia_id INT,
    es_titular BOOLEAN DEFAULT FALSE,
    parentesco VARCHAR(50) COMMENT 'hijo, conyuge, padre, madre, hermano, etc.',
    nombre VARCHAR(200) NOT NULL,
    apellido_paterno VARCHAR(100) NOT NULL,
    apellido_materno VARCHAR(100),
    fecha_nacimiento DATE,
    sexo ENUM('masculino', 'femenino', 'otro'),
    curp VARCHAR(18),
    telefono VARCHAR(20),
    email VARCHAR(255),
    direccion TEXT,
    alergias JSON COMMENT '["penicilina", "latex", ...]',
    enfermedades_cronicas JSON COMMENT '["diabetes", "hipertension", ...]',
    medicamentos_actuales JSON COMMENT '["metformina 500mg", ...]',
    antecedentes_heredofamiliares JSON COMMENT '{"diabetes": true, "cancer": false, ...}',
    cirugias_previas JSON COMMENT '["apendicectomia 2018", ...]',
    habitos JSON COMMENT '{"tabaco": false, "alcohol": "ocasional", "ejercicio": "3x_semana"}',
    notas_generales TEXT,
    activo BOOLEAN DEFAULT TRUE,
    creado_por INT COMMENT 'FK kadrix_users.id',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (familia_id) REFERENCES salud_familias(id) ON DELETE SET NULL,
    INDEX idx_nombre (nombre, apellido_paterno),
    INDEX idx_familia (familia_id),
    INDEX idx_telefono (telefono)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- Padecimientos / Catalogo
-- ============================================================
CREATE TABLE IF NOT EXISTS salud_padecimientos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(50) UNIQUE NOT NULL,
    nombre VARCHAR(200) NOT NULL,
    categoria ENUM('urgencias', 'cronico', 'consulta', 'preventivo') DEFAULT 'consulta',
    urgencia_base TINYINT DEFAULT 1 COMMENT '1=bajo, 5=critico',
    especialidades JSON COMMENT '["medicina_general", "neurologia"]',
    estudios_recomendados JSON COMMENT '["biometria_hematica", ...]',
    preguntas_triage JSON COMMENT '["Tienes fiebre?", ...]',
    flags_rojo JSON COMMENT '["fiebre_alta", "rigidez_cuello"]',
    descripcion TEXT,
    activo BOOLEAN DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- Sintomas
-- ============================================================
CREATE TABLE IF NOT EXISTS salud_sintomas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(50) UNIQUE NOT NULL,
    nombre VARCHAR(200) NOT NULL,
    categoria VARCHAR(100),
    padecimientos_relacionados JSON,
    activo BOOLEAN DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- Medicos
-- ============================================================
CREATE TABLE IF NOT EXISTS salud_medicos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(200) NOT NULL,
    especialidad VARCHAR(100),
    cedula VARCHAR(50),
    telefono VARCHAR(20),
    email VARCHAR(255),
    activo BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- Consultorios / Salas
-- ============================================================
CREATE TABLE IF NOT EXISTS salud_consultorios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(20) UNIQUE NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    tipo ENUM('consulta', 'urgencias', 'procedimiento', 'laboratorio', 'imagenologia') DEFAULT 'consulta',
    capacidad INT DEFAULT 1,
    activo BOOLEAN DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- Horarios de medicos
-- ============================================================
CREATE TABLE IF NOT EXISTS salud_horarios_medico (
    id INT AUTO_INCREMENT PRIMARY KEY,
    medico_id INT NOT NULL,
    consultorio_id INT NOT NULL,
    dia_semana TINYINT NOT NULL COMMENT '1=Lun ... 7=Dom',
    hora_inicio TIME NOT NULL,
    hora_fin TIME NOT NULL,
    duracion_cita_min INT DEFAULT 30,
    activo BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (medico_id) REFERENCES salud_medicos(id),
    FOREIGN KEY (consultorio_id) REFERENCES salud_consultorios(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- Citas
-- ============================================================
CREATE TABLE IF NOT EXISTS salud_citas (
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
    creado_por INT COMMENT 'FK kadrix_users.id',
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- Seguimiento post-cita
-- ============================================================
CREATE TABLE IF NOT EXISTS salud_seguimientos (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- Historial de padecimientos por paciente
-- ============================================================
CREATE TABLE IF NOT EXISTS salud_paciente_padecimientos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    paciente_id INT NOT NULL,
    padecimiento_id INT NOT NULL,
    status ENUM('activo', 'resuelto', 'cronico', 'recurrente') DEFAULT 'activo',
    fecha_inicio DATE,
    fecha_resolucion DATE,
    notas TEXT,
    FOREIGN KEY (paciente_id) REFERENCES salud_pacientes(id),
    FOREIGN KEY (padecimiento_id) REFERENCES salud_padecimientos(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- Triage (evaluacion de urgencia)
-- ============================================================
CREATE TABLE IF NOT EXISTS salud_triage (
    id INT AUTO_INCREMENT PRIMARY KEY,
    paciente_id INT NOT NULL,
    cita_id INT,
    nivel ENUM('verde', 'amarillo', 'naranja', 'rojo') DEFAULT 'verde',
    sintomas JSON,
    respuestas_triage JSON,
    puntuacion INT DEFAULT 0,
    recomendacion TEXT,
    evaluado_por INT COMMENT 'FK kadrix_users.id',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paciente_id) REFERENCES salud_pacientes(id),
    FOREIGN KEY (cita_id) REFERENCES salud_citas(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- Knowledge Base: Documentos y guias
-- ============================================================
CREATE TABLE IF NOT EXISTS salud_kb_documentos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    titulo VARCHAR(300) NOT NULL,
    tipo ENUM('guia_clinica', 'protocolo', 'nota_experiencia', 'articulo', 'otro') DEFAULT 'otro',
    padecimiento_id INT,
    contenido TEXT NOT NULL,
    archivo_path VARCHAR(500),
    subido_por INT NOT NULL COMMENT 'FK kadrix_users.id (debe ser duenya)',
    etiquetas JSON,
    version INT DEFAULT 1,
    activo BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (padecimiento_id) REFERENCES salud_padecimientos(id),
    INDEX idx_tipo (tipo),
    INDEX idx_padecimiento (padecimiento_id),
    FULLTEXT idx_busqueda (titulo, contenido)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- Knowledge Base: Embeddings (Fase 2+)
-- ============================================================
CREATE TABLE IF NOT EXISTS salud_kb_embeddings (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- RAG: Consultas historicas
-- ============================================================
CREATE TABLE IF NOT EXISTS salud_rag_consultas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    consultado_por INT NOT NULL COMMENT 'FK kadrix_users.id',
    pregunta TEXT NOT NULL,
    contexto_recuperado JSON,
    respuesta TEXT,
    confianza FLOAT,
    modelo_llm VARCHAR(100),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (consultado_por) REFERENCES kadrix_users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- RAG: Config
-- ============================================================
CREATE TABLE IF NOT EXISTS salud_rag_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    fase ENUM('fase1_kb_estatica', 'fase2_embeddings', 'fase3_rag_completo') DEFAULT 'fase1_kb_estatica',
    modelo_embedding VARCHAR(200),
    modelo_llm VARCHAR(200),
    config JSON,
    activo BOOLEAN DEFAULT TRUE,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- Vistas
-- ============================================================

CREATE OR REPLACE VIEW v_citas_hoy AS
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

CREATE OR REPLACE VIEW v_proximas_citas AS
SELECT c.*, p.nombre AS paciente_nombre, p.apellido_paterno,
       m.nombre AS medico_nombre, m.especialidad,
       pad.nombre AS padecimiento_nombre
FROM salud_citas c
JOIN salud_pacientes p ON c.paciente_id = p.id
JOIN salud_medicos m ON c.medico_id = m.id
LEFT JOIN salud_padecimientos pad ON c.padecimiento_id = pad.id
WHERE c.fecha >= CURDATE() AND c.status IN ('agendada', 'confirmada')
ORDER BY c.fecha, c.hora_inicio;

CREATE OR REPLACE VIEW v_familia_pacientes AS
SELECT f.*, p.id AS paciente_id, p.nombre, p.apellido_paterno, p.parentesco,
       p.fecha_nacimiento, p.sexo
FROM salud_familias f
JOIN salud_pacientes p ON p.familia_id = f.id
WHERE p.activo = TRUE
ORDER BY f.apellido_principal, p.es_titular DESC;

-- ============================================================
-- Seed data
-- ============================================================

INSERT IGNORE INTO salud_padecimientos (codigo, nombre, categoria, urgencia_base, especialidades, estudios_recomendados, preguntas_triage, flags_rojo) VALUES
('dolor_cabeza', 'Cefalea / Dolor de cabeza', 'consulta', 2, '["medicina_general", "neurologia"]', '["biometria_hematica", "tomografia"]', '["¿Es el peor dolor de cabeza de tu vida?", "¿Tienes fiebre?", "¿Tienes rigidez en el cuello?"]', '["peor_dolor", "fiebre_alta", "rigidez_cuello"]'),
('dolor_pecho', 'Dolor en el pecho', 'urgencias', 5, '["urgencias", "cardiologia"]', '["ecg", "troponinas", "rayos_x"]', '["¿El dolor se irradia al brazo izquierdo?", "¿Tienes dificultad para respirar?"]', '["irradia_brazo", "disnea"]'),
('diabetes_seguimiento', 'Seguimiento de Diabetes', 'cronico', 1, '["medicina_general", "endocrinologia"]', '["glucosa_ayunas", "hemoglobina_glicosilada", "perfil_lipidico"]', '["¿Ha tenido hipoglucemias recientes?", "¿Ha notado cambios en la visión?"]', '["hipoglucemia_severa", "vision_borrosa"]'),
('hipertension_seguimiento', 'Seguimiento de Hipertensión', 'cronico', 1, '["medicina_general", "cardiologia"]', '["presion_arterial", "electrocardiograma", "perfil_lipidico"]', '["¿Ha tenido cefalea intensa?", "¿Ha notado visión borrosa?"]', '["cefalea_intensa", "vision_borrosa", "dolor_pecho"]'),
('infeccion_respiratoria', 'Infección respiratoria', 'consulta', 2, '["medicina_general", "neumologia"]', '["biometria_hematica", "rayos_x_torax"]', '["¿Tienes fiebre?", "¿Tienes dificultad para respirar?", "¿Tienes tos con flema?"]', '["fiebre_alta", "disnea", "hemoptisis"]'),
('dolor_abdominal', 'Dolor abdominal', 'consulta', 3, '["medicina_general", "gastroenterologia"]', '["biometria_hematica", "quimica_sanguinea", "ultrasonido"]', '["¿El dolor es localizado o generalizado?", "¿Tienes náusea o vómito?"]', '["dolor_localizado", "vomito", "fiebre"]'),
('chequeo_general', 'Chequeo general / Preventivo', 'preventivo', 1, '["medicina_general"]', '["biometria_hematica", "quimica_sanguinea", "examen_orina"]', '[]', '[]'),
('lesion_muscular', 'Lesión muscular / Esquelética', 'consulta', 2, '["medicina_general", "ortopedia"]', '["rayos_x", "resonancia"]', '["¿Hay inflamación visible?", "¿Puedes mover la extremidad?"]', '["inflamacion_severa", "imposibilidad_mover"]');

INSERT IGNORE INTO salud_medicos (nombre, especialidad, cedula, telefono, email) VALUES
('Dr. Carlos Mendoza', 'medicina_general', '12345678', '555-0101', 'cmendoza@bris.local'),
('Dra. María Elena Vázquez', 'cardiologia', '23456789', '555-0102', 'mevazquez@bris.local'),
('Dr. Roberto Sánchez', 'neurologia', '34567890', '555-0103', 'rsanchez@bris.local'),
('Dra. Ana Luisa García', 'endocrinologia', '45678901', '555-0104', 'algarcia@bris.local'),
('Dr. Fernando López', 'ortopedia', '56789012', '555-0105', 'flopez@bris.local');

INSERT IGNORE INTO salud_consultorios (codigo, nombre, tipo, capacidad) VALUES
('C1', 'Consultorio 1', 'consulta', 1),
('C2', 'Consultorio 2', 'consulta', 1),
('C3', 'Consultorio 3', 'consulta', 1),
('URG', 'Urgencias', 'urgencias', 3),
('LAB', 'Laboratorio', 'laboratorio', 2),
('IMG', 'Imagenología', 'imagenologia', 2);

INSERT IGNORE INTO salud_horarios_medico (medico_id, consultorio_id, dia_semana, hora_inicio, hora_fin, duracion_cita_min) VALUES
(1, 1, 1, '09:00:00', '14:00:00', 30),
(1, 1, 2, '09:00:00', '14:00:00', 30),
(1, 1, 3, '09:00:00', '14:00:00', 30),
(1, 1, 4, '09:00:00', '14:00:00', 30),
(1, 1, 5, '09:00:00', '14:00:00', 30),
(2, 2, 1, '10:00:00', '15:00:00', 45),
(2, 2, 3, '10:00:00', '15:00:00', 45),
(2, 2, 5, '10:00:00', '15:00:00', 45),
(3, 3, 2, '09:00:00', '13:00:00', 40),
(3, 3, 4, '09:00:00', '13:00:00', 40),
(4, 1, 2, '15:00:00', '19:00:00', 30),
(4, 1, 4, '15:00:00', '19:00:00', 30),
(5, 2, 1, '15:00:00', '19:00:00', 30),
(5, 2, 3, '15:00:00', '19:00:00', 30),
(5, 2, 5, '15:00:00', '19:00:00', 30);

INSERT IGNORE INTO salud_rag_config (fase, modelo_embedding, modelo_llm, config) VALUES
('fase1_kb_estatica', NULL, NULL, '{"disponible": true, "busqueda": "fulltext"}');