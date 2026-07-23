#!/usr/bin/env bash
# Render.com build script for Django backend
set -o errexit

echo "=== Building LoL Roster Challenge Backend ==="

pip install --upgrade pip
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --noinput

echo "=== Build complete ==="
