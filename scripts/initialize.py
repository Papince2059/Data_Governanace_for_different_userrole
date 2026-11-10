"""
Master Initialization Script for Enterprise Data Governance System.
Orchestrates:
  1. Service health polling (PostgreSQL + OpenFGA)
  2. Database schema migrations via Alembic
  3. OpenFGA store creation and authorization model compilation/upload
  4. OpenFGA relationship tuple seeding
  5. Relational data, document content, chunking, and embedding seeding
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import httpx

# Ensure project root and backend are in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from src.infrastructure.openfga.setup import (
    create_or_get_store,
    load_authorization_model,
    seed_tuples,
)

from src.core.config import get_settings

settings = get_settings()
OPENFGA_API_URL = os.getenv("OPENFGA_API_URL", settings.OPENFGA_API_URL)
DATABASE_URL = os.getenv("DATABASE_URL", settings.DATABASE_URL)


async def wait_for_postgres(database_url: str, max_retries: int = 30) -> None:
    """Wait for PostgreSQL to become ready for connections."""
    import asyncpg
    clean_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    print(f"Waiting for PostgreSQL ({clean_url.split('@')[-1]})...")

    for i in range(max_retries):
        try:
            conn = await asyncpg.connect(clean_url)
            await conn.close()
            print("✓ PostgreSQL is ready and accepting connections.")
            return
        except Exception:
            await asyncio.sleep(2)
            print(f"  ...waiting for PostgreSQL ({i+1}/{max_retries})")

    raise RuntimeError("Timed out waiting for PostgreSQL container.")


async def wait_for_openfga(api_url: str, max_retries: int = 30) -> None:
    """Wait for OpenFGA HTTP endpoint to respond healthy."""
    print(f"Waiting for OpenFGA at {api_url}...")
    async with httpx.AsyncClient(timeout=5) as client:
        for i in range(max_retries):
            try:
                resp = await client.get(f"{api_url}/healthz")
                if resp.status_code == 200:
                    print("✓ OpenFGA is ready and healthy.")
                    return
            except Exception:
                pass
            await asyncio.sleep(2)
            print(f"  ...waiting for OpenFGA ({i+1}/{max_retries})")

    raise RuntimeError("Timed out waiting for OpenFGA container.")


def run_alembic_migrations():
    """Run Alembic database schema migrations."""
    print("\nRunning Alembic migrations...")
    backend_dir = PROJECT_ROOT / "backend"
    env = {**os.environ, "DATABASE_URL": DATABASE_URL}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(backend_dir),
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        print(f"Alembic stdout: {result.stdout}")
        print(f"Alembic stderr: {result.stderr}")
        raise RuntimeError(f"Alembic migrations failed with code {result.returncode}")
    print("✓ Alembic migrations applied successfully.")


async def main():
    print("================================================================")
    print(" Enterprise Data Governance — Master Initialization")
    print("================================================================")

    # 1. Health checks
    await wait_for_postgres(DATABASE_URL)
    await wait_for_openfga(OPENFGA_API_URL)

    # 2. Run migrations
    try:
        run_alembic_migrations()
    except Exception as e:
        print(f"Notice during migration run: {e}. Checking if tables already exist...")

    # 3. OpenFGA Store Setup
    print("\nSetting up OpenFGA Store...")
    store_id = await create_or_get_store(OPENFGA_API_URL, "enterprise-data-governance")
    print(f"✓ OpenFGA Store ID: {store_id}")

    # 4. Compile & Load Authorization Model
    print("\nLoading OpenFGA Authorization Model from openfga/model.fga...")
    model_path = PROJECT_ROOT / "openfga" / "model.fga"
    auth_model_id = await load_authorization_model(OPENFGA_API_URL, store_id, model_path)
    print(f"✓ OpenFGA Authorization Model ID: {auth_model_id}")

    # Save IDs to .openfga_config
    config_file = PROJECT_ROOT / ".openfga_config"
    with open(config_file, "w") as f:
        json.dump({"store_id": store_id, "auth_model_id": auth_model_id}, f, indent=2)
    print(f"✓ Saved OpenFGA config to {config_file}")

    # 5. Seed OpenFGA Relationship Tuples
    print("\nSeeding OpenFGA relationship tuples from openfga/seed_tuples.json...")
    seed_tuples_path = PROJECT_ROOT / "openfga" / "seed_tuples.json"
    tuples_count = await seed_tuples(OPENFGA_API_URL, store_id, auth_model_id, seed_tuples_path)
    print(f"✓ Seeded {tuples_count} OpenFGA relationship tuples.")

    # 6. Seed Relational Data & Documents & Embeddings
    print("\nSeeding PostgreSQL with synthetic documents and vector embeddings...")
    from scripts.seed_data import seed_database
    await seed_database(DATABASE_URL)

    print("\n================================================================")
    print("✓ INITIALIZATION COMPLETE!")
    print(f"  PostgreSQL: {DATABASE_URL}")
    print(f"  OpenFGA Store ID: {store_id}")
    print(f"  OpenFGA Model ID: {auth_model_id}")
    print("================================================================")


if __name__ == "__main__":
    asyncio.run(main())

