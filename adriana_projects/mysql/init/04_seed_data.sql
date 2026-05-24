-- ============================================================
-- Kadrix — Seed Data: Lineas, estaciones, baseline, mejoras
-- Datos reales extraidos de balanceo_lineas.csv
-- ============================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ------------------------------------------------------------
-- Lineas
-- ------------------------------------------------------------
INSERT INTO kadrix_lines (code, name, description, takt_seconds, target_pieces_per_shift) VALUES
('NORTHFACE', 'Northface Rack Assembly', 'Linea ensamble de gabinetes Northface', 2821.00, 18),
('SANMINA', 'Sanmina Rack Assembly', 'Linea ensamble de gabinetes Sanmina', 2217.00, 18);

-- ------------------------------------------------------------
-- Estaciones NORTHFACE
-- ------------------------------------------------------------
INSERT INTO kadrix_stations (line_id, code, name, description, operators_default) VALUES
((SELECT id FROM kadrix_lines WHERE code='NORTHFACE'), 'EST-1', 'Est1 Fab Sub', 'Fabricacion subconjunto', 3),
((SELECT id FROM kadrix_lines WHERE code='NORTHFACE'), 'EST-2', 'Est2 Fab Caja', 'Fabricacion caja', 1),
((SELECT id FROM kadrix_lines WHERE code='NORTHFACE'), 'EST-3', 'Est3 Fab Tapa', 'Fabricacion tapa', 1),
((SELECT id FROM kadrix_lines WHERE code='NORTHFACE'), 'EST-4', 'Est4 Sub H', 'Subconjunto H', 1),
((SELECT id FROM kadrix_lines WHERE code='NORTHFACE'), 'EST-5', 'Est5 Sub H Tapa', 'Subconjunto H + Tapa', 1),
((SELECT id FROM kadrix_lines WHERE code='NORTHFACE'), 'EST-6', 'Est6 Ensamble', 'Ensamble final', 1),
((SELECT id FROM kadrix_lines WHERE code='NORTHFACE'), 'EST-7', 'Est7 Integracion', 'Integracion y test', 1);

-- ------------------------------------------------------------
-- Estaciones SANMINA
-- ------------------------------------------------------------
INSERT INTO kadrix_stations (line_id, code, name, description, operators_default) VALUES
((SELECT id FROM kadrix_lines WHERE code='SANMINA'), 'EST-1', 'Est1 Cables', 'Ruteo de cables', 3),
((SELECT id FROM kadrix_lines WHERE code='SANMINA'), 'EST-2', 'Est2 Tapa', 'Colocacion de tapa', 1),
((SELECT id FROM kadrix_lines WHERE code='SANMINA'), 'EST-3', 'Est3 Gasket', 'Colocacion de gasket', 1),
((SELECT id FROM kadrix_lines WHERE code='SANMINA'), 'EST-4', 'Est4 Sub H', 'Subconjunto H', 1),
((SELECT id FROM kadrix_lines WHERE code='SANMINA'), 'EST-5', 'Est5 Sub H Tapa', 'Subconjunto H + Tapa', 1),
((SELECT id FROM kadrix_lines WHERE code='SANMINA'), 'EST-6', 'Est6 Ruteo', 'Ruteo de cables avanzado', 1),
((SELECT id FROM kadrix_lines WHERE code='SANMINA'), 'EST-7', 'Est7 Integracion', 'Integracion final', 1);

-- ------------------------------------------------------------
-- Baseline NORTHFACE (CT actual antes de mejoras)
-- ------------------------------------------------------------
INSERT INTO kadrix_baseline_metrics (line_id, station_id, metric_type, value, unit, measurement_date, notes) VALUES
((SELECT id FROM kadrix_lines WHERE code='NORTHFACE'), (SELECT id FROM kadrix_stations WHERE line_id=(SELECT id FROM kadrix_lines WHERE code='NORTHFACE') AND code='EST-1'), 'cycle_time', 2065, 'seconds', '2026-05-01', 'CT actual medido mayo 2026'),
((SELECT id FROM kadrix_lines WHERE code='NORTHFACE'), (SELECT id FROM kadrix_stations WHERE line_id=(SELECT id FROM kadrix_lines WHERE code='NORTHFACE') AND code='EST-2'), 'cycle_time', 1685, 'seconds', '2026-05-01', NULL),
((SELECT id FROM kadrix_lines WHERE code='NORTHFACE'), (SELECT id FROM kadrix_stations WHERE line_id=(SELECT id FROM kadrix_lines WHERE code='NORTHFACE') AND code='EST-3'), 'cycle_time', 2978, 'seconds', '2026-05-01', 'Cuello de botella potencial'),
((SELECT id FROM kadrix_lines WHERE code='NORTHFACE'), (SELECT id FROM kadrix_stations WHERE line_id=(SELECT id FROM kadrix_lines WHERE code='NORTHFACE') AND code='EST-4'), 'cycle_time', 3953, 'seconds', '2026-05-01', 'MAYOR CUELLO DE BOTELLA'),
((SELECT id FROM kadrix_lines WHERE code='NORTHFACE'), (SELECT id FROM kadrix_stations WHERE line_id=(SELECT id FROM kadrix_lines WHERE code='NORTHFACE') AND code='EST-5'), 'cycle_time', 876, 'seconds', '2026-05-01', NULL),
((SELECT id FROM kadrix_lines WHERE code='NORTHFACE'), (SELECT id FROM kadrix_stations WHERE line_id=(SELECT id FROM kadrix_lines WHERE code='NORTHFACE') AND code='EST-6'), 'cycle_time', 4923, 'seconds', '2026-05-01', 'Ensamble supera takt 75%'),
((SELECT id FROM kadrix_lines WHERE code='NORTHFACE'), (SELECT id FROM kadrix_stations WHERE line_id=(SELECT id FROM kadrix_lines WHERE code='NORTHFACE') AND code='EST-7'), 'cycle_time', 3571, 'seconds', '2026-05-01', NULL);

-- ------------------------------------------------------------
-- Baseline SANMINA
-- ------------------------------------------------------------
INSERT INTO kadrix_baseline_metrics (line_id, station_id, metric_type, value, unit, measurement_date, notes) VALUES
((SELECT id FROM kadrix_lines WHERE code='SANMINA'), (SELECT id FROM kadrix_stations WHERE line_id=(SELECT id FROM kadrix_lines WHERE code='SANMINA') AND code='EST-1'), 'cycle_time', 29, 'seconds', '2026-05-01', NULL),
((SELECT id FROM kadrix_lines WHERE code='SANMINA'), (SELECT id FROM kadrix_stations WHERE line_id=(SELECT id FROM kadrix_lines WHERE code='SANMINA') AND code='EST-2'), 'cycle_time', 494, 'seconds', '2026-05-01', NULL),
((SELECT id FROM kadrix_lines WHERE code='SANMINA'), (SELECT id FROM kadrix_stations WHERE line_id=(SELECT id FROM kadrix_lines WHERE code='SANMINA') AND code='EST-3'), 'cycle_time', 50, 'seconds', '2026-05-01', NULL),
((SELECT id FROM kadrix_lines WHERE code='SANMINA'), (SELECT id FROM kadrix_stations WHERE line_id=(SELECT id FROM kadrix_lines WHERE code='SANMINA') AND code='EST-4'), 'cycle_time', 300, 'seconds', '2026-05-01', NULL),
((SELECT id FROM kadrix_lines WHERE code='SANMINA'), (SELECT id FROM kadrix_stations WHERE line_id=(SELECT id FROM kadrix_lines WHERE code='SANMINA') AND code='EST-5'), 'cycle_time', 84, 'seconds', '2026-05-01', NULL),
((SELECT id FROM kadrix_lines WHERE code='SANMINA'), (SELECT id FROM kadrix_stations WHERE line_id=(SELECT id FROM kadrix_lines WHERE code='SANMINA') AND code='EST-6'), 'cycle_time', 1410, 'seconds', '2026-05-01', 'Cuello Sanmina'),
((SELECT id FROM kadrix_lines WHERE code='SANMINA'), (SELECT id FROM kadrix_stations WHERE line_id=(SELECT id FROM kadrix_lines WHERE code='SANMINA') AND code='EST-7'), 'cycle_time', 150, 'seconds', '2026-05-01', NULL);

-- ------------------------------------------------------------
-- Baseline desperdicios NORTHFACE Est.7
-- ------------------------------------------------------------
INSERT INTO kadrix_baseline_metrics (line_id, metric_type, value, unit, measurement_date, notes) VALUES
((SELECT id FROM kadrix_lines WHERE code='NORTHFACE'), NULL, 'cycle_time', 4483, 'seconds', '2026-05-01', 'CT total Est.7 incluyendo desperdicios'),
((SELECT id FROM kadrix_lines WHERE code='NORTHFACE'), NULL, 'downtime', 2417, 'seconds', '2026-05-01', 'Tiempo perdido: esperas, caminatas, retrabajo');

-- ------------------------------------------------------------
-- Proyectos de mejora con ROI ($15K budget)
-- ------------------------------------------------------------
INSERT INTO kadrix_improvements (line_id, station_id, title, category, description, investment_usd, implementation_cost_usd, status, priority, start_date, end_date, expected_savings_usd_annual, expected_time_saved_sec, expected_quality_improvement_pct, justification) VALUES
((SELECT id FROM kadrix_lines WHERE code='NORTHFACE'), (SELECT id FROM kadrix_stations WHERE line_id=(SELECT id FROM kadrix_lines WHERE code='NORTHFACE') AND code='EST-4'), 'Shadow board Est.4', '5s', 'Organizacion visual de herramientas en estacion 4 para reducir caminatas', 1200.00, 300.00, 'proposed', 'high', '2026-06-01', '2026-06-14', 15440.00, 416, 5.00, 'Reduccion de 416 segundos en caminatas = +1.1 pzs/turno. ROI 10x en 1 año.'),
((SELECT id FROM kadrix_lines WHERE code='NORTHFACE'), (SELECT id FROM kadrix_stations WHERE line_id=(SELECT id FROM kadrix_lines WHERE code='NORTHFACE') AND code='EST-6'), 'Fixture anti-retrabajo remaches', 'fixture', 'Diseño y fabricacion de fixture que elimina retrabajo de remaches en Est.6', 3500.00, 800.00, 'proposed', 'high', '2026-06-15', '2026-07-15', 22160.00, 293, 8.00, 'Elimina 293s de retrabajo. Impacto directo en FPY y scrap.'),
((SELECT id FROM kadrix_lines WHERE code='NORTHFACE'), (SELECT id FROM kadrix_stations WHERE line_id=(SELECT id FROM kadrix_lines WHERE code='NORTHFACE') AND code='EST-4'), 'QA dedicado linea NF', 'quality', 'Asignacion de inspector QA dedicado para eliminar esperas', 0.00, 0.00, 'proposed', 'high', '2026-05-24', '2026-05-31', 12500.00, 633, 3.00, 'Elimina 633s de espera QA. Requiere reasignacion de personal, no inversion directa.'),
((SELECT id FROM kadrix_lines WHERE code='NORTHFACE'), NULL, 'Lift assist / conveyor gabinetes', 'ergonomic', 'Sistema de asistencia para manejo de gabinetes pesados', 4500.00, 1200.00, 'proposed', 'medium', '2026-07-05', '2026-09-13', 18500.00, 0, 0.00, 'Mejora ergonomia y reduce riesgo de lesion. Dificil de cuantificar en segundos pero evita costos de incapacidad.'),
((SELECT id FROM kadrix_lines WHERE code='NORTHFACE'), (SELECT id FROM kadrix_stations WHERE line_id=(SELECT id FROM kadrix_lines WHERE code='NORTHFACE') AND code='EST-6'), 'Operador adicional Est.6', 'other', 'Agregar 1 operador a Est.6 para reducir CT de 4923s a ~1641s', 0.00, 0.00, 'proposed', 'high', '2026-05-31', '2026-06-07', 18000.00, 3282, 0.00, 'Reasignacion de personal existente. Divide CT entre 3 operadores. Impacto masivo en throughput.'),
((SELECT id FROM kadrix_lines WHERE code='NORTHFACE'), (SELECT id FROM kadrix_stations WHERE line_id=(SELECT id FROM kadrix_lines WHERE code='NORTHFACE') AND code='EST-7'), 'Fixture alineacion PCA Est.7', 'fixture', 'Fixture de precision para alineacion de PCA en estacion 7', 2800.00, 600.00, 'proposed', 'medium', '2026-06-21', '2026-08-02', 9800.00, 0, 12.00, 'Mejora FPY Est.7. Reduce scrap y retrabajo.'),
((SELECT id FROM kadrix_lines WHERE code='NORTHFACE'), NULL, 'PM preventivo remachadoras', 'other', 'Check-list semanal de mantenimiento preventivo para remachadoras', 0.00, 200.00, 'proposed', 'high', '2026-05-31', '2026-06-07', 8500.00, 0, 0.00, 'Evita averias que causan 1906s de downtime. Costo bajo, impacto alto.'),
((SELECT id FROM kadrix_lines WHERE code='SANMINA'), (SELECT id FROM kadrix_stations WHERE line_id=(SELECT id FROM kadrix_lines WHERE code='SANMINA') AND code='EST-6'), 'WI visual ruteo cables Est.6', 'training', 'Work instructions visuales para ruteo de cables', 800.00, 400.00, 'proposed', 'high', '2026-05-24', '2026-06-07', 11200.00, 470, 6.00, 'Reduce CT de 1410s a 940s. Mejora FPY y reduce variacion operador.'),
((SELECT id FROM kadrix_lines WHERE code='SANMINA'), (SELECT id FROM kadrix_stations WHERE line_id=(SELECT id FROM kadrix_lines WHERE code='SANMINA') AND code='EST-4'), 'Fixture gaskets base Est.4', 'fixture', 'Fixture automatizado para colocacion de gaskets', 3200.00, 700.00, 'proposed', 'high', '2026-05-24', '2026-06-14', 18900.00, 650, 10.00, 'Reduce CT Est.4 de 300s a meta de 250s. Elimina variacion operador.');

SET FOREIGN_KEY_CHECKS = 1;
