CREATE DATABASE IF NOT EXISTS bris_adriana CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE bris_adriana;

CREATE TABLE IF NOT EXISTS source_sheets (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  source_file VARCHAR(255) NOT NULL,
  sheet_name VARCHAR(255) NOT NULL,
  raw_csv VARCHAR(500) NOT NULL,
  row_count INT NOT NULL DEFAULT 0,
  column_count INT NOT NULL DEFAULT 0,
  imported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_source_sheet (source_file, sheet_name)
);

CREATE TABLE IF NOT EXISTS raw_rows (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  source_file VARCHAR(255) NOT NULL,
  sheet_name VARCHAR(255) NOT NULL,
  `row_number` INT NOT NULL,
  row_json JSON NOT NULL,
  imported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_raw_source (source_file, sheet_name),
  KEY idx_raw_row_number (`row_number`)
);

CREATE TABLE IF NOT EXISTS parts (
  part_number VARCHAR(120) NOT NULL PRIMARY KEY,
  description TEXT NULL,
  imported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bom_items (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  source_file VARCHAR(255) NOT NULL,
  sheet_name VARCHAR(255) NOT NULL,
  level_code VARCHAR(80) NULL,
  parent_part VARCHAR(120) NULL,
  backlog DECIMAL(14,4) NULL,
  component_part VARCHAR(120) NULL,
  status VARCHAR(80) NULL,
  process_initial VARCHAR(120) NULL,
  description TEXT NULL,
  required_qty DECIMAL(14,4) NULL,
  uom VARCHAR(40) NULL,
  on_hand DECIMAL(14,4) NULL,
  on_order DECIMAL(14,4) NULL,
  committed DECIMAL(14,4) NULL,
  available DECIMAL(14,4) NULL,
  lead_time_days DECIMAL(14,4) NULL,
  vendor_name VARCHAR(255) NULL,
  program VARCHAR(255) NULL,
  imported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_bom_parent (parent_part),
  KEY idx_bom_component (component_part),
  KEY idx_bom_vendor (vendor_name),
  KEY idx_bom_lead_time (lead_time_days)
);

CREATE TABLE IF NOT EXISTS pfep_items (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  source_file VARCHAR(255) NOT NULL,
  sheet_name VARCHAR(255) NOT NULL,
  model VARCHAR(160) NULL,
  operator_no DECIMAL(10,2) NULL,
  station_no DECIMAL(10,2) NULL,
  cart VARCHAR(120) NULL,
  bin_location VARCHAR(120) NULL,
  step_no VARCHAR(80) NULL,
  component_part VARCHAR(120) NULL,
  quantity DECIMAL(14,4) NULL,
  process_route VARCHAR(255) NULL,
  width DECIMAL(14,4) NULL,
  depth DECIMAL(14,4) NULL,
  height DECIMAL(14,4) NULL,
  volume DECIMAL(14,4) NULL,
  storage VARCHAR(120) NULL,
  bin_model VARCHAR(120) NULL,
  bin_capacity DECIMAL(14,4) NULL,
  batch_size DECIMAL(14,4) NULL,
  days_of_stock DECIMAL(14,4) NULL,
  required_bins DECIMAL(14,4) NULL,
  assembled_using TEXT NULL,
  tool_used VARCHAR(255) NULL,
  imported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_pfep_component (component_part),
  KEY idx_pfep_station (station_no),
  KEY idx_pfep_cart (cart),
  KEY idx_pfep_route (process_route)
);

CREATE TABLE IF NOT EXISTS work_center_operations (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  source_file VARCHAR(255) NOT NULL,
  sheet_name VARCHAR(255) NOT NULL,
  process_sheet_number VARCHAR(120) NULL,
  end_item_part VARCHAR(120) NULL,
  parent_part VARCHAR(120) NULL,
  work_center VARCHAR(120) NULL,
  step_number VARCHAR(80) NULL,
  run_setup VARCHAR(40) NULL,
  operation_code VARCHAR(80) NULL,
  component_part VARCHAR(120) NULL,
  description TEXT NULL,
  standard_rate DECIMAL(14,4) NULL,
  lead_time DECIMAL(14,4) NULL,
  crew_size DECIMAL(14,4) NULL,
  imported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_wc_process (process_sheet_number),
  KEY idx_wc_parent (parent_part),
  KEY idx_wc_work_center (work_center),
  KEY idx_wc_rate (standard_rate)
);

CREATE TABLE IF NOT EXISTS station_materials (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  source_file VARCHAR(255) NOT NULL,
  sheet_name VARCHAR(255) NOT NULL,
  station_name VARCHAR(255) NULL,
  step VARCHAR(120) NULL,
  rack_location VARCHAR(120) NULL,
  part_number VARCHAR(120) NULL,
  units DECIMAL(14,4) NULL,
  total_pieces DECIMAL(14,4) NULL,
  class_code VARCHAR(80) NULL,
  tooling TEXT NULL,
  notes TEXT NULL,
  imported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_station_part (part_number),
  KEY idx_station_name (station_name),
  KEY idx_station_step (step)
);

CREATE TABLE IF NOT EXISTS kanban_notifications (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  source_file VARCHAR(255) NOT NULL,
  sheet_name VARCHAR(255) NOT NULL,
  part_number VARCHAR(120) NOT NULL,
  days_left DECIMAL(14,4) NULL,
  owner VARCHAR(120) NULL,
  imported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_kanban_part (part_number),
  KEY idx_kanban_owner (owner),
  KEY idx_kanban_days_left (days_left)
);

CREATE OR REPLACE VIEW v_material_shortages AS
SELECT
  component_part,
  description,
  vendor_name,
  program,
  SUM(COALESCE(required_qty, 0)) AS total_required_qty,
  MIN(available) AS min_available,
  MAX(lead_time_days) AS max_lead_time_days,
  COUNT(*) AS bom_lines
FROM bom_items
WHERE component_part IS NOT NULL AND component_part <> ''
GROUP BY component_part, description, vendor_name, program
HAVING min_available < total_required_qty OR max_lead_time_days >= 70;

CREATE OR REPLACE VIEW v_station_load AS
SELECT
  station_name,
  COUNT(*) AS material_lines,
  SUM(COALESCE(units, 0)) AS total_units,
  SUM(COALESCE(total_pieces, 0)) AS total_pieces,
  COUNT(DISTINCT part_number) AS distinct_parts
FROM station_materials
GROUP BY station_name;

CREATE OR REPLACE VIEW v_work_center_bottlenecks AS
SELECT
  work_center,
  COUNT(*) AS operations,
  SUM(COALESCE(standard_rate, 0)) AS total_standard_rate,
  AVG(NULLIF(crew_size, 0)) AS avg_crew_size,
  MAX(standard_rate) AS max_standard_rate
FROM work_center_operations
WHERE work_center IS NOT NULL AND work_center <> ''
GROUP BY work_center
ORDER BY total_standard_rate DESC;
