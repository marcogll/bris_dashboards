-- ============================================================
-- Kadrix — Telegram & Basecamp Sync Schema
-- ============================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ------------------------------------------------------------
-- 1. Agregar telegram_chat_id a usuarios
-- ------------------------------------------------------------
ALTER TABLE kadrix_users
  ADD COLUMN telegram_chat_id BIGINT DEFAULT NULL,
  ADD UNIQUE KEY uk_telegram_chat (telegram_chat_id);

-- ------------------------------------------------------------
-- 2. Sesiones/historial de Telegram
-- ------------------------------------------------------------
DROP TABLE IF EXISTS kadrix_telegram_sessions;
CREATE TABLE kadrix_telegram_sessions (
  `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  `user_id` INT UNSIGNED NOT NULL,
  `chat_id` BIGINT NOT NULL,
  `active` TINYINT(1) DEFAULT 1,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY `uk_chat` (`chat_id`),
  KEY `idx_user` (`user_id`),
  CONSTRAINT `fk_telegram_sessions_user`
    FOREIGN KEY (`user_id`) REFERENCES `kadrix_users` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 3. Sync con Basecamp/Fizzy
-- ------------------------------------------------------------
DROP TABLE IF EXISTS kadrix_basecamp_sync;
CREATE TABLE kadrix_basecamp_sync (
  `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  `kadrix_task_id` INT UNSIGNED NOT NULL,
  `basecamp_todo_id` VARCHAR(100) NOT NULL,
  `basecamp_project_id` VARCHAR(100) DEFAULT NULL,
  `last_sync_at` DATETIME DEFAULT NULL,
  `sync_direction` ENUM('bidirectional', 'to_basecamp', 'to_kadrix') DEFAULT 'bidirectional',
  UNIQUE KEY `uk_kadrix_task` (`kadrix_task_id`),
  KEY `idx_basecamp` (`basecamp_todo_id`),
  CONSTRAINT `fk_basecamp_sync_task`
    FOREIGN KEY (`kadrix_task_id`) REFERENCES `kadrix_tasks` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 4. Seed: usuario bot/telegram placeholder (opcional)
-- ------------------------------------------------------------
-- El bot no es un usuario real, pero podríamos querer
-- asignar tareas creadas por Telegram a un usuario "bot"
-- INSERT INTO kadrix_users (username, name, email, role, password_hash, active)
-- VALUES ('telegram_bot', 'Bri Bot', 'bot@cadrex.local', 'viewer', '', 1);

SET FOREIGN_KEY_CHECKS = 1;
