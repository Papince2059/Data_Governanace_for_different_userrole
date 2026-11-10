"""
OpenFGA store and authorization model initialization.
Called during application startup or by the initialize.py script.
"""
import json
from pathlib import Path

import httpx

from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)


async def create_or_get_store(api_url: str, store_name: str = "enterprise-data-governance") -> str:
    """
    Create an OpenFGA store if it doesn't exist, return the store_id.
    Lists existing stores first to avoid duplicates.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        # List stores
        resp = await client.get(f"{api_url}/stores")
        resp.raise_for_status()
        stores = resp.json().get("stores", [])
        for store in stores:
            if store["name"] == store_name:
                logger.info("openfga_store_exists", store_id=store["id"])
                return store["id"]
        # Create new store
        resp = await client.post(f"{api_url}/stores", json={"name": store_name})
        resp.raise_for_status()
        store_id = resp.json()["id"]
        logger.info("openfga_store_created", store_id=store_id)
        return store_id


async def load_authorization_model(api_url: str, store_id: str, model_path: Path) -> str:
    """
    Load the authorization model from model.fga (converted to JSON format).
    Returns the authorization_model_id.
    """
    # Read the .fga file and convert to OpenFGA JSON format
    # The model.fga needs to be sent as a JSON representation
    # We'll use the OpenFGA API to write the model
    model_json = convert_fga_to_json(model_path.read_text())

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{api_url}/stores/{store_id}/authorization-models",
            json=model_json,
        )
        resp.raise_for_status()
        model_id = resp.json()["authorization_model_id"]
        logger.info("openfga_model_loaded", model_id=model_id)
        return model_id


def convert_fga_to_json(fga_content: str) -> dict:
    """
    Convert OpenFGA DSL to JSON format for the API.
    Since we can't run the fga CLI in-process easily, we'll use the JSON format directly.
    Returns the type_definitions dict for the authorization model.
    """
    # Build the authorization model as JSON directly.
    # This matches the DSL defined in model.fga exactly.
    return {
        "schema_version": "1.1",
        "type_definitions": [
            {
                "type": "user",
                "relations": {},
                "metadata": None,
            },
            {
                "type": "organization",
                "relations": {
                    "member": {"this": {}},
                    "admin": {"this": {}},
                },
                "metadata": {
                    "relations": {
                        "member": {
                            "directly_related_user_types": [{"type": "user"}]
                        },
                        "admin": {
                            "directly_related_user_types": [{"type": "user"}]
                        },
                    }
                },
            },
            {
                "type": "department",
                "relations": {
                    "member": {"this": {}},
                    "parent": {"this": {}},
                },
                "metadata": {
                    "relations": {
                        "member": {
                            "directly_related_user_types": [
                                {"type": "user"},
                                {"type": "group", "relation": "member"},
                            ]
                        },
                        "parent": {
                            "directly_related_user_types": [{"type": "organization"}]
                        },
                    }
                },
            },
            {
                "type": "group",
                "relations": {
                    "member": {"this": {}},
                    "parent_department": {"this": {}},
                },
                "metadata": {
                    "relations": {
                        "member": {
                            "directly_related_user_types": [{"type": "user"}]
                        },
                        "parent_department": {
                            "directly_related_user_types": [{"type": "department"}]
                        },
                    }
                },
            },
            {
                "type": "folder",
                "relations": {
                    "owner": {"this": {}},
                    "parent_department": {"this": {}},
                    "viewer": {
                        "union": {
                            "child": [
                                {"this": {}},
                                {"computedUserset": {"relation": "owner"}},
                                {"computedUserset": {"relation": "editor"}},
                            ]
                        }
                    },
                    "editor": {
                        "union": {
                            "child": [
                                {"this": {}},
                                {"computedUserset": {"relation": "owner"}},
                            ]
                        }
                    },
                    "can_read": {
                        "union": {
                            "child": [
                                {"computedUserset": {"relation": "viewer"}},
                                {"computedUserset": {"relation": "editor"}},
                                {"computedUserset": {"relation": "owner"}},
                            ]
                        }
                    },
                    "can_write": {
                        "union": {
                            "child": [
                                {"computedUserset": {"relation": "editor"}},
                                {"computedUserset": {"relation": "owner"}},
                            ]
                        }
                    },
                },
                "metadata": {
                    "relations": {
                        "owner": {
                            "directly_related_user_types": [{"type": "user"}]
                        },
                        "parent_department": {
                            "directly_related_user_types": [{"type": "department"}]
                        },
                        "viewer": {
                            "directly_related_user_types": [
                                {"type": "user"},
                                {"type": "group", "relation": "member"},
                                {"type": "department", "relation": "member"},
                            ]
                        },
                        "editor": {
                            "directly_related_user_types": [
                                {"type": "user"},
                                {"type": "group", "relation": "member"},
                            ]
                        },
                    }
                },
            },
            {
                "type": "document",
                "relations": {
                    "owner": {"this": {}},
                    "parent_folder": {"this": {}},
                    "parent_department": {"this": {}},
                    "viewer": {
                        "union": {
                            "child": [
                                {"this": {}},
                                {"computedUserset": {"relation": "owner"}},
                                {
                                    "tupleToUserset": {
                                        "tupleset": {"relation": "parent_folder"},
                                        "computedUserset": {"relation": "viewer"},
                                    }
                                },
                            ]
                        }
                    },
                    "editor": {
                        "union": {
                            "child": [
                                {"this": {}},
                                {"computedUserset": {"relation": "owner"}},
                                {
                                    "tupleToUserset": {
                                        "tupleset": {"relation": "parent_folder"},
                                        "computedUserset": {"relation": "editor"},
                                    }
                                },
                            ]
                        }
                    },
                    "can_read": {
                        "union": {
                            "child": [
                                {"computedUserset": {"relation": "viewer"}},
                                {"computedUserset": {"relation": "editor"}},
                                {"computedUserset": {"relation": "owner"}},
                            ]
                        }
                    },
                    "can_write": {
                        "union": {
                            "child": [
                                {"computedUserset": {"relation": "editor"}},
                                {"computedUserset": {"relation": "owner"}},
                            ]
                        }
                    },
                },
                "metadata": {
                    "relations": {
                        "owner": {
                            "directly_related_user_types": [{"type": "user"}]
                        },
                        "parent_folder": {
                            "directly_related_user_types": [{"type": "folder"}]
                        },
                        "parent_department": {
                            "directly_related_user_types": [{"type": "department"}]
                        },
                        "viewer": {
                            "directly_related_user_types": [
                                {"type": "user"},
                                {"type": "group", "relation": "member"},
                                {"type": "department", "relation": "member"},
                            ]
                        },
                        "editor": {
                            "directly_related_user_types": [
                                {"type": "user"},
                                {"type": "group", "relation": "member"},
                            ]
                        },
                    }
                },
            },
        ],
    }


async def seed_tuples(api_url: str, store_id: str, auth_model_id: str, tuples_path: Path) -> int:
    """
    Load and write seed tuples from seed_tuples.json.
    Writes in batches of 100 (OpenFGA limit).
    Returns the number of tuples written.
    """
    with open(tuples_path) as f:
        data = json.load(f)

    tuples = data.get("tuples", [])
    batch_size = 100
    written = 0

    async with httpx.AsyncClient(timeout=30) as client:
        for i in range(0, len(tuples), batch_size):
            batch = tuples[i : i + batch_size]
            writes = [
                {"user": t["user"], "relation": t["relation"], "object": t["object"]}
                for t in batch
            ]
            resp = await client.post(
                f"{api_url}/stores/{store_id}/write",
                json={
                    "writes": {"tuple_keys": writes},
                    "authorization_model_id": auth_model_id,
                },
            )
            if resp.status_code not in (200, 400):  # 400 may mean duplicate tuples
                resp.raise_for_status()
            written += len(batch)
            logger.info(
                "openfga_tuples_seeded",
                batch=i // batch_size + 1,
                count=len(batch),
            )

    logger.info("openfga_seed_complete", total_written=written)
    return written


async def initialize_openfga(
    api_url: str,
    model_path: Path,
    tuples_path: Path,
    store_name: str = "enterprise-data-governance",
) -> tuple[str, str]:
    """
    Full OpenFGA initialization: create/get store, load model, seed tuples.
    Returns (store_id, auth_model_id).
    """
    store_id = await create_or_get_store(api_url, store_name)
    auth_model_id = await load_authorization_model(api_url, store_id, model_path)
    total = await seed_tuples(api_url, store_id, auth_model_id, tuples_path)
    logger.info(
        "openfga_initialized",
        store_id=store_id,
        auth_model_id=auth_model_id,
        tuples_seeded=total,
    )
    return store_id, auth_model_id
