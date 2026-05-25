#!/bin/bash
set -e

echo "Running Django migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput 2>&1 | tail -1

echo "Starting server..."
exec "$@"