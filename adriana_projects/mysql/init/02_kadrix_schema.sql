-- ============================================================
-- Sistema Kadrix — Schema completo
-- Gestión de proyectos, Kanban, fixtures y mantenimiento
-- ============================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ------------------------------------------------------------
-- 1. Usuarios
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `kadrix_users`;
CREATE TABLE `kadrix_users` (
  `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  `username` VARCHAR(50) NOT NULL,
  `name` VARCHAR(100) NOT NULL,
  `email` VARCHAR(100) NOT NULL,
  `role` ENUM('admin', 'manager', 'technician', 'operator', 'viewer') NOT NULL DEFAULT 'viewer',
  `password_hash` VARCHAR(255) NOT NULL,
  `active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY `uk_kadrix_users_username` (`username`),
  UNIQUE KEY `uk_kadrix_users_email` (`email`),
  KEY `idx_kadrix_users_role` (`role`),
  KEY `idx_kadrix_users_active` (`active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 2. Tableros Kanban
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `kadrix_boards`;
CREATE TABLE `kadrix_boards` (
  `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  `name` VARCHAR(100) NOT NULL,
  `description` TEXT,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY `idx_kadrix_boards_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 3. Columnas de tablero (estados del Kanban)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `kadrix_columns`;
CREATE TABLE `kadrix_columns` (
  `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  `board_id` INT UNSIGNED NOT NULL,
  `name` VARCHAR(50) NOT NULL,
  `position` INT UNSIGNED NOT NULL DEFAULT 0,
  `color` VARCHAR(7) DEFAULT NULL COMMENT 'Hex color, e.g. #3498db',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY `idx_kadrix_columns_board_position` (`board_id`, `position`),
  CONSTRAINT `fk_kadrix_columns_board`
    FOREIGN KEY (`board_id`) REFERENCES `kadrix_boards` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 4. Tareas / tarjetas del Kanban
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `kadrix_tasks`;
CREATE TABLE `kadrix_tasks` (
  `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  `board_id` INT UNSIGNED NOT NULL,
  `column_id` INT UNSIGNED NOT NULL,
  `title` VARCHAR(200) NOT NULL,
  `description` TEXT,
  `assigned_to` INT UNSIGNED DEFAULT NULL,
  `priority` ENUM('low', 'medium', 'high', 'critical') NOT NULL DEFAULT 'medium',
  `due_date` DATE DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `created_by` INT UNSIGNED DEFAULT NULL,
  KEY `idx_kadrix_tasks_board_column` (`board_id`, `column_id`),
  KEY `idx_kadrix_tasks_assigned` (`assigned_to`),
  KEY `idx_kadrix_tasks_priority` (`priority`),
  KEY `idx_kadrix_tasks_due_date` (`due_date`),
  KEY `idx_kadrix_tasks_created_by` (`created_by`),
  CONSTRAINT `fk_kadrix_tasks_board`
    FOREIGN KEY (`board_id`) REFERENCES `kadrix_boards` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_kadrix_tasks_column`
    FOREIGN KEY (`column_id`) REFERENCES `kadrix_columns` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_kadrix_tasks_assigned_to`
    FOREIGN KEY (`assigned_to`) REFERENCES `kadrix_users` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_kadrix_tasks_created_by`
    FOREIGN KEY (`created_by`) REFERENCES `kadrix_users` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 5. Comentarios en tareas
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `kadrix_task_comments`;
CREATE TABLE `kadrix_task_comments` (
  `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  `task_id` INT UNSIGNED NOT NULL,
  `user_id` INT UNSIGNED NOT NULL,
  `comment` TEXT NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY `idx_kadrix_task_comments_task` (`task_id`),
  KEY `idx_kadrix_task_comments_user` (`user_id`),
  KEY `idx_kadrix_task_comments_created` (`created_at`),
  CONSTRAINT `fk_kadrix_task_comments_task`
    FOREIGN KEY (`task_id`) REFERENCES `kadrix_tasks` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_kadrix_task_comments_user`
    FOREIGN KEY (`user_id`) REFERENCES `kadrix_users` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 6. Catálogo de fixtures
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `kadrix_fixtures`;
CREATE TABLE `kadrix_fixtures` (
  `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  `code` VARCHAR(50) NOT NULL,
  `name` VARCHAR(150) NOT NULL,
  `line` VARCHAR(50) DEFAULT NULL COMMENT 'Línea de producción',
  `station` VARCHAR(50) DEFAULT NULL COMMENT 'Estación de trabajo',
  `status` ENUM('active', 'inactive', 'maintenance', 'retired') NOT NULL DEFAULT 'active',
  `location` VARCHAR(100) DEFAULT NULL,
  `notes` TEXT,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY `uk_kadrix_fixtures_code` (`code`),
  KEY `idx_kadrix_fixtures_status` (`status`),
  KEY `idx_kadrix_fixtures_line` (`line`),
  KEY `idx_kadrix_fixtures_station` (`station`),
  KEY `idx_kadrix_fixtures_line_station` (`line`, `station`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 7. Historial de mantenimiento de fixtures
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `kadrix_fixture_maintenance`;
CREATE TABLE `kadrix_fixture_maintenance` (
  `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  `fixture_id` INT UNSIGNED NOT NULL,
  `type` ENUM('preventive', 'corrective', 'predictive', 'calibration', 'upgrade') NOT NULL,
  `description` TEXT NOT NULL,
  `started_at` DATETIME NOT NULL,
  `completed_at` DATETIME DEFAULT NULL,
  `technician` INT UNSIGNED DEFAULT NULL COMMENT 'Referencia a kadrix_users.id',
  `status` ENUM('scheduled', 'in_progress', 'completed', 'cancelled', 'on_hold') NOT NULL DEFAULT 'scheduled',
  `downtime_minutes` INT UNSIGNED DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY `idx_kadrix_fixture_maintenance_fixture` (`fixture_id`),
  KEY `idx_kadrix_fixture_maintenance_status` (`status`),
  KEY `idx_kadrix_fixture_maintenance_type` (`type`),
  KEY `idx_kadrix_fixture_maintenance_dates` (`started_at`, `completed_at`),
  KEY `idx_kadrix_fixture_maintenance_technician` (`technician`),
  CONSTRAINT `fk_kadrix_fixture_maintenance_fixture`
    FOREIGN KEY (`fixture_id`) REFERENCES `kadrix_fixtures` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_kadrix_fixture_maintenance_technician`
    FOREIGN KEY (`technician`) REFERENCES `kadrix_users` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 8. Proyectos de mejora continua
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `kadrix_projects`;
CREATE TABLE `kadrix_projects` (
  `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  `name` VARCHAR(150) NOT NULL,
  `description` TEXT,
  `objective` TEXT,
  `budget` DECIMAL(15,2) DEFAULT NULL,
  `status` ENUM('draft', 'active', 'on_hold', 'completed', 'cancelled') NOT NULL DEFAULT 'draft',
  `start_date` DATE DEFAULT NULL,
  `end_date` DATE DEFAULT NULL,
  `roi_expected` DECIMAL(5,2) DEFAULT NULL COMMENT 'ROI esperado en porcentaje',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY `idx_kadrix_projects_status` (`status`),
  KEY `idx_kadrix_projects_dates` (`start_date`, `end_date`),
  KEY `idx_kadrix_projects_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 9. Relación proyectos ↔ tareas
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `kadrix_project_tasks`;
CREATE TABLE `kadrix_project_tasks` (
  `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  `project_id` INT UNSIGNED NOT NULL,
  `task_id` INT UNSIGNED NOT NULL,
  UNIQUE KEY `uk_kadrix_project_tasks` (`project_id`, `task_id`),
  KEY `idx_kadrix_project_tasks_task` (`task_id`),
  CONSTRAINT `fk_kadrix_project_tasks_project`
    FOREIGN KEY (`project_id`) REFERENCES `kadrix_projects` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_kadrix_project_tasks_task`
    FOREIGN KEY (`task_id`) REFERENCES `kadrix_tasks` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 10. Registro de actividades diarias
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `kadrix_activities`;
CREATE TABLE `kadrix_activities` (
  `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  `user_id` INT UNSIGNED NOT NULL,
  `activity_type` ENUM('task_created', 'task_updated', 'task_moved', 'task_completed',
                       'comment_added', 'fixture_maintenance', 'fixture_status_change',
                       'project_created', 'project_updated', 'login', 'other') NOT NULL,
  `description` TEXT NOT NULL,
  `related_fixture_id` INT UNSIGNED DEFAULT NULL,
  `related_task_id` INT UNSIGNED DEFAULT NULL,
  `duration_minutes` INT UNSIGNED DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY `idx_kadrix_activities_user` (`user_id`),
  KEY `idx_kadrix_activities_type` (`activity_type`),
  KEY `idx_kadrix_activities_created` (`created_at`),
  KEY `idx_kadrix_activities_related_fixture` (`related_fixture_id`),
  KEY `idx_kadrix_activities_related_task` (`related_task_id`),
  CONSTRAINT `fk_kadrix_activities_user`
    FOREIGN KEY (`user_id`) REFERENCES `kadrix_users` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_kadrix_activities_fixture`
    FOREIGN KEY (`related_fixture_id`) REFERENCES `kadrix_fixtures` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_kadrix_activities_task`
    FOREIGN KEY (`related_task_id`) REFERENCES `kadrix_tasks` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;
