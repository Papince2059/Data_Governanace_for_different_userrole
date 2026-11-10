#!/usr/bin/env bash
# ==============================================================================
# Reset Local Environment — Clean Slate Setup
# WARNING: Deletes all local volumes, database containers, and cached OpenFGA state.
# ==============================================================================
set -e

echo "⚠️  WARNING: Resetting local Enterprise Data Governance environment."
echo "   This will remove persistent database volumes and rebuild containers."
read -p "Are you sure you want to proceed? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "Cancelled."
    exit 1
fi

echo "1. Stopping and removing existing containers and volumes..."
docker compose down -v --remove-orphans

echo "2. Cleaning up local generated config..."
rm -f .openfga_config
rm -rf data/uploads/*

echo "3. Starting core infrastructure (PostgreSQL with pgvector + OpenFGA)..."
docker compose up -d postgres openfga

echo "4. Waiting for database and authorization engine to be healthy..."
sleep 8

echo "5. Running master initialization and data seeding..."
python scripts/initialize.py

echo "6. Starting backend and frontend containers..."
docker compose up -d

echo ""
echo "=================================================================="
echo "✓ Local environment reset and initialized successfully!"
echo "  Frontend URL: http://localhost:5173"
echo "  Backend API:  http://localhost:8000"
echo "  OpenFGA:      http://localhost:8080"
echo "=================================================================="

