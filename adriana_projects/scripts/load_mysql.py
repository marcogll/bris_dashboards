import csv
import json
import os
from pathlib import Path

import mysql.connector


ROOT = Path(__file__).resolve().parents[2]
CURATED_DIR = ROOT / "adriana_projects" / "data" / "curated"
SCHEMA_FILE = ROOT / "adriana_projects" / "mysql" / "init" / "01_schema.sql"

TABLE_FILES = [
    ("source_sheets", "source_sheets.csv"),
    ("raw_rows", "raw_rows.csv"),
    ("parts", "parts.csv"),
    ("bom_items", "bom_items.csv"),
    ("pfep_items", "pfep_items.csv"),
    ("work_center_operations", "work_center_operations.csv"),
    ("station_materials", "station_materials.csv"),
    ("kanban_notifications", "kanban_notifications.csv"),
]


def empty_to_none(value):
    return None if value == "" else value


def connect():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "bris_user"),
        password=os.getenv("MYSQL_PASSWORD", "bris_password"),
        database=os.getenv("MYSQL_DATABASE", "bris_adriana"),
    )


def load_table(cursor, table: str, csv_name: str) -> int:
    path = CURATED_DIR / csv_name
    if not path.exists():
        return 0

    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        columns = reader.fieldnames or []
        placeholders = ", ".join(["%s"] * len(columns))
        column_sql = ", ".join(f"`{column}`" for column in columns)
        update_sql = ", ".join(f"`{column}` = VALUES(`{column}`)" for column in columns)
        sql = f"INSERT INTO `{table}` ({column_sql}) VALUES ({placeholders})"
        if table == "parts":
            sql += f" ON DUPLICATE KEY UPDATE {update_sql}"

        count = 0
        for row in reader:
            values = []
            for column in columns:
                value = empty_to_none(row[column])
                if table == "raw_rows" and column == "row_json" and value:
                    value = json.dumps(json.loads(value), ensure_ascii=False)
                values.append(value)
            cursor.execute(sql, values)
            count += 1
    return count


def truncate_tables(cursor):
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
    for table, _ in reversed(TABLE_FILES):
        cursor.execute(f"TRUNCATE TABLE `{table}`")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")


def apply_schema(connection):
    statements = []
    current = []
    for line in SCHEMA_FILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        current.append(line)
        if stripped.endswith(";"):
            statements.append("\n".join(current).rstrip(";"))
            current = []

    cursor = connection.cursor()
    for statement in statements:
        cursor.execute(statement)
    connection.commit()
    cursor.close()


def main():
    connection = connect()
    apply_schema(connection)
    cursor = connection.cursor()
    truncate_tables(cursor)
    loaded = {}
    for table, csv_name in TABLE_FILES:
        loaded[table] = load_table(cursor, table, csv_name)
    connection.commit()
    cursor.close()
    connection.close()
    print(json.dumps(loaded, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
