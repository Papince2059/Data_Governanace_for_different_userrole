"""
OpenFGA client wrapper.
Communicates with OpenFGA using the official SDK.
Implements fail-closed security: if OpenFGA is unreachable, raise AuthorizationServiceUnavailableError.
"""
import asyncio
from typing import Optional

import httpx

from src.core.config import get_settings
from src.core.exceptions import AuthorizationServiceUnavailableError
from src.core.logging import get_logger

logger = get_logger(__name__)


class OpenFGAClient:
    """
    Async OpenFGA client.
    Uses the OpenFGA REST API directly via httpx (more reliable than SDK for async).
    """

    def __init__(self, api_url: str, store_id: str, auth_model_id: str, timeout: int = 10):
        self.api_url = api_url.rstrip("/")
        self.store_id = store_id
        self.auth_model_id = auth_model_id
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=f"{self.api_url}/stores/{self.store_id}",
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def check(self, user: str, relation: str, object: str) -> bool:
        """
        Check if user has relation to object.
        Raises AuthorizationServiceUnavailableError if OpenFGA is unreachable.
        Returns False (not True) on any error — fail closed.
        """
        client = await self._get_client()
        payload = {
            "tuple_key": {
                "user": user,
                "relation": relation,
                "object": object,
            },
            "authorization_model_id": self.auth_model_id,
        }
        try:
            resp = await client.post("/check", json=payload)
            resp.raise_for_status()
            allowed: bool = resp.json().get("allowed", False)
            logger.debug(
                "openfga_check",
                user=user,
                relation=relation,
                object=object,
                allowed=allowed,
            )
            return allowed
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            logger.error(
                "openfga_unreachable",
                user=user,
                relation=relation,
                object=object,
                error=str(exc),
            )
            raise AuthorizationServiceUnavailableError(
                "OpenFGA is unreachable. Failing closed — access denied."
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.error(
                "openfga_check_http_error",
                user=user,
                relation=relation,
                object=object,
                status_code=exc.response.status_code,
                error=str(exc),
            )
            return False
        except Exception as exc:
            logger.error(
                "openfga_check_unexpected_error",
                user=user,
                relation=relation,
                object=object,
                error=str(exc),
            )
            return False

    async def list_objects(self, user: str, relation: str, object_type: str) -> list[str]:
        """
        List all objects of type that user has relation to.
        Used for pre-retrieval ACL filtering.
        Raises AuthorizationServiceUnavailableError if OpenFGA is unreachable.
        Returns empty list (not all objects) on any error — fail closed.
        """
        client = await self._get_client()
        payload = {
            "user": user,
            "relation": relation,
            "type": object_type,
            "authorization_model_id": self.auth_model_id,
        }
        try:
            resp = await client.post("/list-objects", json=payload)
            resp.raise_for_status()
            objects: list[str] = resp.json().get("objects", [])
            logger.debug(
                "openfga_list_objects",
                user=user,
                relation=relation,
                object_type=object_type,
                count=len(objects),
            )
            return objects
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            logger.error(
                "openfga_list_objects_unreachable",
                user=user,
                relation=relation,
                object_type=object_type,
                error=str(exc),
            )
            raise AuthorizationServiceUnavailableError(
                "OpenFGA is unreachable. Failing closed — returning empty object list."
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.error(
                "openfga_list_objects_http_error",
                user=user,
                relation=relation,
                object_type=object_type,
                status_code=exc.response.status_code,
                error=str(exc),
            )
            return []
        except Exception as exc:
            logger.error(
                "openfga_list_objects_unexpected_error",
                user=user,
                relation=relation,
                object_type=object_type,
                error=str(exc),
            )
            return []

    async def write_tuple(self, user: str, relation: str, object: str) -> None:
        """Write a relationship tuple to OpenFGA."""
        client = await self._get_client()
        payload = {
            "writes": {
                "tuple_keys": [
                    {"user": user, "relation": relation, "object": object}
                ]
            },
            "authorization_model_id": self.auth_model_id,
        }
        try:
            resp = await client.post("/write", json=payload)
            resp.raise_for_status()
            logger.info(
                "openfga_tuple_written",
                user=user,
                relation=relation,
                object=object,
            )
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            logger.error(
                "openfga_write_tuple_unreachable",
                user=user,
                relation=relation,
                object=object,
                error=str(exc),
            )
            raise AuthorizationServiceUnavailableError(
                "OpenFGA is unreachable. Cannot write tuple."
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.error(
                "openfga_write_tuple_http_error",
                user=user,
                relation=relation,
                object=object,
                status_code=exc.response.status_code,
                response_body=exc.response.text,
                error=str(exc),
            )
            raise

    async def delete_tuple(self, user: str, relation: str, object: str) -> None:
        """Delete a relationship tuple from OpenFGA."""
        client = await self._get_client()
        payload = {
            "deletes": {
                "tuple_keys": [
                    {"user": user, "relation": relation, "object": object}
                ]
            },
            "authorization_model_id": self.auth_model_id,
        }
        try:
            resp = await client.post("/write", json=payload)
            resp.raise_for_status()
            logger.info(
                "openfga_tuple_deleted",
                user=user,
                relation=relation,
                object=object,
            )
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            logger.error(
                "openfga_delete_tuple_unreachable",
                user=user,
                relation=relation,
                object=object,
                error=str(exc),
            )
            raise AuthorizationServiceUnavailableError(
                "OpenFGA is unreachable. Cannot delete tuple."
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.error(
                "openfga_delete_tuple_http_error",
                user=user,
                relation=relation,
                object=object,
                status_code=exc.response.status_code,
                response_body=exc.response.text,
                error=str(exc),
            )
            raise

    async def write_tuples_batch(self, tuples: list[dict]) -> None:
        """Write multiple tuples in batches of 100 (OpenFGA limit)."""
        batch_size = 100
        client = await self._get_client()
        for i in range(0, len(tuples), batch_size):
            batch = tuples[i : i + batch_size]
            tuple_keys = [
                {"user": t["user"], "relation": t["relation"], "object": t["object"]}
                for t in batch
            ]
            payload = {
                "writes": {"tuple_keys": tuple_keys},
                "authorization_model_id": self.auth_model_id,
            }
            try:
                resp = await client.post("/write", json=payload)
                resp.raise_for_status()
                logger.info(
                    "openfga_batch_written",
                    batch_index=i // batch_size,
                    count=len(batch),
                )
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                logger.error(
                    "openfga_batch_write_unreachable",
                    batch_index=i // batch_size,
                    error=str(exc),
                )
                raise AuthorizationServiceUnavailableError(
                    "OpenFGA is unreachable. Cannot write tuple batch."
                ) from exc
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "openfga_batch_write_http_error",
                    batch_index=i // batch_size,
                    status_code=exc.response.status_code,
                    response_body=exc.response.text,
                    error=str(exc),
                )
                raise

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def health_check(self) -> bool:
        """Check if OpenFGA is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.api_url}/stores/{self.store_id}")
                return resp.status_code == 200
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            logger.warning("openfga_health_check_failed", error=str(exc))
            return False
        except Exception as exc:
            logger.warning("openfga_health_check_unexpected_error", error=str(exc))
            return False
