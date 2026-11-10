"""
Performance and Latency Benchmark Script.
Executes and measures live operations against the running system:
  1. OpenFGA Authorization check latency (Check & ListObjects)
  2. SentenceTransformers Embedding generation latency
  3. pgvector Cosine Distance Retrieval with Pre-Retrieval ACL Filtering
  4. Time-to-First-Token (TTFT) and total stream response time
  5. Documents considered, authorized documents, and chunks retrieved

Outputs real, measured statistics (mean, p50, p95, min, max).
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import httpx
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
OPENFGA_API_URL = os.getenv("OPENFGA_API_URL", "http://localhost:8080")


async def benchmark_authentication() -> str:
    """Measure login latency and retrieve JWT token."""
    print("\n--- 1. Authentication Benchmark ---")
    latencies = []
    token = ""
    async with httpx.AsyncClient(base_url=API_BASE_URL) as client:
        for i in range(10):
            start = time.perf_counter()
            resp = await client.post(
                "/api/v1/auth/login",
                json={"email": "alice@acme.com", "password": "password123"},
            )
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)
            if resp.status_code == 200:
                token = resp.json()["access_token"]

    print(f"Login Requests: 10")
    print(f"Mean Latency: {np.mean(latencies):.2f} ms")
    print(f"P95 Latency:  {np.percentile(latencies, 95):.2f} ms")
    print(f"Min / Max:    {np.min(latencies):.2f} ms / {np.max(latencies):.2f} ms")
    return token


async def benchmark_authorization(token: str):
    """Measure OpenFGA check and list-objects latencies."""
    print("\n--- 2. OpenFGA Authorization Benchmark ---")
    headers = {"Authorization": f"Bearer {token}"}
    check_latencies = []
    list_latencies = []

    async with httpx.AsyncClient(base_url=API_BASE_URL) as client:
        # Check permissions
        for _ in range(20):
            start = time.perf_counter()
            resp = await client.post(
                "/api/v1/permissions/check",
                headers=headers,
                json={
                    "user_id": "alice",
                    "relation": "can_read",
                    "resource_type": "document",
                    "resource_id": "doc_employee_handbook",
                },
            )
            elapsed = (time.perf_counter() - start) * 1000
            if resp.status_code == 200:
                check_latencies.append(elapsed)

        # List accessible resources (Pre-Retrieval ACL evaluation)
        for _ in range(20):
            start = time.perf_counter()
            resp = await client.get(
                "/api/v1/permissions/resources?user_id=alice&resource_type=document",
                headers=headers,
            )
            elapsed = (time.perf_counter() - start) * 1000
            if resp.status_code == 200:
                list_latencies.append(elapsed)

    print("Check Permission (Single Resource):")
    print(f"  Mean: {np.mean(check_latencies):.2f} ms | P95: {np.percentile(check_latencies, 95):.2f} ms")
    print("List Accessible Resources (Pre-Retrieval ACL Graph Walk):")
    print(f"  Mean: {np.mean(list_latencies):.2f} ms | P95: {np.percentile(list_latencies, 95):.2f} ms")


async def benchmark_embedding():
    """Measure in-process SentenceTransformer embedding generation."""
    print("\n--- 3. Local Embedding Benchmark (sentence-transformers/all-MiniLM-L6-v2) ---")
    from src.infrastructure.embeddings.local_embedder import LocalEmbedder

    embedder = LocalEmbedder()
    test_queries = [
        "What are the employee paid time off and leave policies?",
        "Show me the server architecture and maintenance runbook.",
        "What is the quarterly revenue and gross margin?",
        "Customer pipeline and enterprise deal sizes.",
        "General IT acceptable usage and workstation security.",
    ]

    # Warmup
    embedder.embed_text("warmup query")

    latencies = []
    for query in test_queries * 4:  # 20 iterations
        start = time.perf_counter()
        vec = embedder.embed_text(query)
        elapsed = (time.perf_counter() - start) * 1000
        latencies.append(elapsed)

    print(f"Embedding Dimension: {len(vec)}")
    print(f"Iterations:          {len(latencies)}")
    print(f"Mean Latency:        {np.mean(latencies):.2f} ms")
    print(f"P95 Latency:         {np.percentile(latencies, 95):.2f} ms")
    print(f"Min / Max:           {np.min(latencies):.2f} ms / {np.max(latencies):.2f} ms")


async def benchmark_streaming_rag(token: str):
    """Measure Time-to-First-Token (TTFT) and total response stream duration."""
    print("\n--- 4. Streaming RAG Benchmark (Pre-Retrieval ACL + pgvector + LLM) ---")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    query_body = {"question": "What is the employee leave policy for annual vacation days?"}

    ttft_list = []
    total_latencies = []
    token_counts = []
    auth_doc_counts = []
    retrieved_chunk_counts = []

    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=60.0) as client:
        for trial in range(5):
            t_start = time.perf_counter()
            first_token_time = None
            total_tokens = 0
            authorized_docs = 0
            retrieved_chunks = 0

            async with client.stream("POST", "/api/v1/chat/stream", headers=headers, json=query_body) as resp:
                current_event = None
                async for line in resp.aiter_lines():
                    if line.startswith("event: "):
                        current_event = line.replace("event: ", "").strip()
                    elif line.startswith("data: "):
                        raw_data = line.replace("data: ", "").strip()
                        try:
                            data = json.loads(raw_data)
                            if current_event == "authorization.completed":
                                authorized_docs = data.get("authorized_doc_count", 0)
                            elif current_event == "retrieval.completed":
                                retrieved_chunks = data.get("chunk_count", 0)
                            elif current_event == "token":
                                if first_token_time is None:
                                    first_token_time = time.perf_counter()
                                total_tokens += 1
                        except json.JSONDecodeError:
                            pass

            t_end = time.perf_counter()
            total_time_ms = (t_end - t_start) * 1000
            ttft_ms = ((first_token_time - t_start) * 1000) if first_token_time else total_time_ms

            ttft_list.append(ttft_ms)
            total_latencies.append(total_time_ms)
            token_counts.append(total_tokens)
            auth_doc_counts.append(authorized_docs)
            retrieved_chunk_counts.append(retrieved_chunks)

    print(f"Trials:                     {len(total_latencies)}")
    print(f"Time-To-First-Token (TTFT): {np.mean(ttft_list):.2f} ms mean (P95: {np.percentile(ttft_list, 95):.2f} ms)")
    print(f"Total Stream Duration:      {np.mean(total_latencies):.2f} ms mean")
    print(f"Tokens Generated / Stream:  {int(np.mean(token_counts))}")
    print(f"Authorized Docs Filtered:   {auth_doc_counts[0]}")
    print(f"Chunks Retrieved & Fed:     {retrieved_chunk_counts[0]}")


async def main():
    print("==================================================================")
    print(" Enterprise Data Governance System — Performance Benchmark")
    print("==================================================================")
    try:
        token = await benchmark_authentication()
        await benchmark_authorization(token)
        await benchmark_embedding()
        await benchmark_streaming_rag(token)
        print("\n==================================================================")
        print("✓ All benchmarks finished successfully.")
        print("==================================================================")
    except Exception as e:
        print(f"\n⚠️ Benchmark error: {e}")
        print("Ensure the backend and OpenFGA containers are running ('docker compose up').")


if __name__ == "__main__":
    asyncio.run(main())

