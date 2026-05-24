-- ============================================================
-- Sistema Kadrix — Analytics & ROI Justification Schema
-- Justificacion de inversion $15K USD en mejoras
-- ============================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ------------------------------------------------------------
-- 1. Lineas de produccion
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `kadrix_lines`;
CREATE TABLE `kadrix_lines` (
  `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  `code` VARCHAR(20) NOT NULL COMMENT 'Ej: NORTHFACE, SANMINA, SKYLINE',
  `name` VARCHAR(100) NOT NULL,
  `description` TEXT,
  `takt_seconds` DECIMAL(10,2) DEFAULT NULL,
  `target_pieces_per_shift` INT UNSIGNED DEFAULT NULL,
  `active` TINYINT(1) NOT NULL DEFAULT 1,
  UNIQUE KEY `uk_kadrix_lines_code` (`code`),
  KEY `idx_kadrix_lines_active` (`active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 2. Estaciones por linea
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `kadrix_stations`;
CREATE TABLE `kadrix_stations` (
  `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  `line_id` INT UNSIGNED NOT NULL,
  `code` VARCHAR(20) NOT NULL COMMENT 'Ej: EST-1, EST-2',
  `name` VARCHAR(100) NOT NULL,
  `description` TEXT,
  `operators_default` INT UNSIGNED DEFAULT 1,
  `active` TINYINT(1) NOT NULL DEFAULT 1,
  UNIQUE KEY `uk_kadrix_stations_line_code` (`line_id`, `code`),
  KEY `idx_kadrix_stations_line` (`line_id`),
  CONSTRAINT `fk_kadrix_stations_line`
    FOREIGN KEY (`line_id`) REFERENCES `kadrix_lines` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 3. Metricas base (antes de mejora) — ingreso manual
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `kadrix_baseline_metrics`;
CREATE TABLE `kadrix_baseline_metrics` (
  `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  `line_id` INT UNSIGNED NOT NULL,
  `station_id` INT UNSIGNED DEFAULT NULL,
  `metric_type` ENUM('cycle_time','downtime','scrap_rate','fp_y','oee','rework_time','walk_time','inspection_time') NOT NULL,
  `value` DECIMAL(12,4) NOT NULL,
  `unit` VARCHAR(20) DEFAULT 'seconds' COMMENT 'seconds, minutes, percent, pieces, usd',
  `measurement_date` DATE NOT NULL,
  `measured_by` VARCHAR(100) DEFAULT NULL,
  `notes` TEXT,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY `idx_kadrix_baseline_line` (`line_id`),
  KEY `idx_kadrix_baseline_station` (`station_id`),
  KEY `idx_kadrix_baseline_type` (`metric_type`),
  KEY `idx_kadrix_baseline_date` (`measurement_date`),
  CONSTRAINT `fk_kadrix_baseline_line`
    FOREIGN KEY (`line_id`) REFERENCES `kadrix_lines` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_kadrix_baseline_station`
    FOREIGN KEY (`station_id`) REFERENCES `kadrix_stations` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 4. Proyectos de mejora con ROI
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `kadrix_improvements`;
CREATE TABLE `kadrix_improvements` (
  `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  `project_id` INT UNSIGNED DEFAULT NULL,
  `line_id` INT UNSIGNED DEFAULT NULL,
  `station_id` INT UNSIGNED DEFAULT NULL,
  `title` VARCHAR(200) NOT NULL COMMENT 'Ej: Fixture anti-retrabajo remaches',
  `category` ENUM('fixture','ergonomic','layout','quality','5s','kitting','automation','training','other') NOT NULL DEFAULT 'other',
  `description` TEXT,
  `investment_usd` DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT 'Costo de la mejora en USD',
  `implementation_cost_usd` DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT 'Mano de obra/material extra',
  `status` ENUM('proposed','approved','in_progress','implemented','cancelled') NOT NULL DEFAULT 'proposed',
  `priority` ENUM('low','medium','high','critical') NOT NULL DEFAULT 'medium',
  `start_date` DATE DEFAULT NULL,
  `end_date` DATE DEFAULT NULL,
  `expected_savings_usd_annual` DECIMAL(12,2) DEFAULT NULL COMMENT 'Ahorro anual proyectado USD',
  `expected_time_saved_sec` INT UNSIGNED DEFAULT NULL COMMENT 'Segundos ahorrados por ciclo',
  `expected_quality_improvement_pct` DECIMAL(5,2) DEFAULT NULL,
  `actual_savings_usd_annual` DECIMAL(12,2) DEFAULT NULL,
  `actual_time_saved_sec` INT UNSIGNED DEFAULT NULL,
  `actual_roi_pct` DECIMAL(6,2) DEFAULT NULL,
  `justification` TEXT COMMENT 'Justificacion escrita para aprobacion',
  `created_by` INT UNSIGNED DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY `idx_kadrix_improvements_line` (`line_id`),
  KEY `idx_kadrix_improvements_status` (`status`),
  KEY `idx_kadrix_improvements_category` (`category`),
  KEY `idx_kadrix_improvements_project` (`project_id`),
  KEY `idx_kadrix_improvements_priority` (`priority`),
  CONSTRAINT `fk_kadrix_improvements_line`
    FOREIGN KEY (`line_id`) REFERENCES `kadrix_lines` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_kadrix_improvements_station`
    FOREIGN KEY (`station_id`) REFERENCES `kadrix_stations` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_kadrix_improvements_project`
    FOREIGN KEY (`project_id`) REFERENCES `kadrix_projects` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_kadrix_improvements_created_by`
    FOREIGN KEY (`created_by`) REFERENCES `kadrix_users` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 5. Resultados post-implementacion (tracking mensual)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `kadrix_improvement_results`;
CREATE TABLE `kadrix_improvement_results` (
  `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  `improvement_id` INT UNSIGNED NOT NULL,
  `measurement_month` DATE NOT NULL COMMENT 'Primer dia del mes',
  `line_id` INT UNSIGNED NOT NULL,
  `station_id` INT UNSIGNED DEFAULT NULL,
  `cycle_time_seconds` DECIMAL(10,2) DEFAULT NULL,
  `pieces_per_shift` INT UNSIGNED DEFAULT NULL,
  `scrap_rate_pct` DECIMAL(6,2) DEFAULT NULL,
  `fp_y_pct` DECIMAL(6,2) DEFAULT NULL,
  `downtime_minutes` INT UNSIGNED DEFAULT NULL,
  `rework_minutes` INT UNSIGNED DEFAULT NULL,
  `walk_time_seconds` INT UNSIGNED DEFAULT NULL,
  `cost_per_piece_usd` DECIMAL(10,4) DEFAULT NULL,
  `notes` TEXT,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY `uk_kadrix_results_improvement_month` (`improvement_id`, `measurement_month`),
  KEY `idx_kadrix_results_line` (`line_id`),
  KEY `idx_kadrix_results_station` (`station_id`),
  KEY `idx_kadrix_results_month` (`measurement_month`),
  CONSTRAINT `fk_kadrix_results_improvement`
    FOREIGN KEY (`improvement_id`) REFERENCES `kadrix_improvements` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_kadrix_results_line`
    FOREIGN KEY (`line_id`) REFERENCES `kadrix_lines` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_kadrix_results_station`
    FOREIGN KEY (`station_id`) REFERENCES `kadrix_stations` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 6. Budget tracking (control del presupuesto $15K)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `kadrix_budget_tracking`;
CREATE TABLE `kadrix_budget_tracking` (
  `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  `improvement_id` INT UNSIGNED NOT NULL,
  `expense_date` DATE NOT NULL,
  `concept` VARCHAR(200) NOT NULL COMMENT 'Ej: Compra fixture SG-2973, Diseño CAD',
  `category` ENUM('hardware','software','consulting','materials','labor','training','other') NOT NULL DEFAULT 'other',
  `amount_usd` DECIMAL(10,2) NOT NULL,
  `invoice_ref` VARCHAR(100) DEFAULT NULL,
  `approved_by` INT UNSIGNED DEFAULT NULL,
  `notes` TEXT,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY `idx_kadrix_budget_improvement` (`improvement_id`),
  KEY `idx_kadrix_budget_date` (`expense_date`),
  KEY `idx_kadrix_budget_category` (`category`),
  CONSTRAINT `fk_kadrix_budget_improvement`
    FOREIGN KEY (`improvement_id`) REFERENCES `kadrix_improvements` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_kadrix_budget_approved_by`
    FOREIGN KEY (`approved_by`) REFERENCES `kadrix_users` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;
