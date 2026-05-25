#!/usr/bin/env python3
"""
Seed users into kadrix_users from a CSV/JSON list.
Usage:
    python scripts/seed_users.py users.csv

CSV format (no header required):
    username, "Full Name", email@domain.com, role, plain_password

Roles: admin, manager, technician, operator, viewer
"""
import csv
import json
import sys
import os
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from werkzeug.security import generate_password_hash
from kadrix.db import execute, query


def seed_from_csv(csv_path: str):
    path = Path(csv_path)
    if not path.exists():
        print(f"❌ File not found: {csv_path}")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        count = 0
        for row in reader:
            if not row or row[0].startswith("#"):
                continue
            if len(row) < 5:
                print(f"⚠️  Skipping malformed row: {row}")
                continue
            username = row[0].strip().lower()
            name = row[1].strip()
            email = row[2].strip()
            role = row[3].strip().lower()
            password = row[4].strip()

            if role not in ("admin", "manager", "technician", "operator", "viewer"):
                print(f"⚠️  Invalid role '{role}' for {username}, defaulting to 'viewer'")
                role = "viewer"

            pw_hash = generate_password_hash(password)

            existing = query("SELECT id FROM kadrix_users WHERE username = %s", (username,))
            if existing:
                execute(
                    "UPDATE kadrix_users SET name=%s, email=%s, role=%s, password_hash=%s, active=1 WHERE username=%s",
                    (name, email, role, pw_hash, username),
                )
                print(f"🔄 Updated: {username} ({role})")
            else:
                execute(
                    "INSERT INTO kadrix_users (username, name, email, role, password_hash, active) VALUES (%s, %s, %s, %s, %s, 1)",
                    (username, name, email, role, pw_hash),
                )
                print(f"✅ Created: {username} ({role})")
            count += 1

    print(f"\n🎉 Done. {count} users processed.")


def seed_from_json(json_path: str):
    path = Path(json_path)
    if not path.exists():
        print(f"❌ File not found: {json_path}")
        sys.exit(1)

    data = json.loads(path.read_text(encoding="utf-8"))
    count = 0
    for username, info in data.items():
        username = username.strip().lower()
        name = info.get("display_name", username)
        email = info.get("email", f"{username}@cadrex.local")
        role = info.get("role", "viewer")
        password = info.get("password_plain", "")

        if not password:
            print(f"⚠️  No plain password for {username}, skipping")
            continue

        pw_hash = generate_password_hash(password)
        existing = query("SELECT id FROM kadrix_users WHERE username = %s", (username,))
        if existing:
            execute(
                "UPDATE kadrix_users SET name=%s, email=%s, role=%s, password_hash=%s, active=1 WHERE username=%s",
                (name, email, role, pw_hash, username),
            )
            print(f"🔄 Updated: {username} ({role})")
        else:
            execute(
                "INSERT INTO kadrix_users (username, name, email, role, password_hash, active) VALUES (%s, %s, %s, %s, %s, 1)",
                (username, name, email, role, pw_hash),
            )
            print(f"✅ Created: {username} ({role})")
        count += 1

    print(f"\n🎉 Done. {count} users processed.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/seed_users.py <users.csv|users.json>")
        print("")
        print("CSV format (no header):")
        print('  username, "Full Name", email@domain.com, role, plain_password')
        print("")
        print("JSON format:")
        print('  { "username": { "display_name": "...", "email": "...", "role": "...", "password_plain": "..." } }')
        sys.exit(1)

    file_path = sys.argv[1]
    if file_path.endswith(".json"):
        seed_from_json(file_path)
    else:
        seed_from_csv(file_path)
