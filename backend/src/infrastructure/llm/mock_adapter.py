"""
Deterministic Mock LLM adapter for testing without Ollama or external services.
Generates realistic, streamed answers based on the provided authorized context.
"""
from __future__ import annotations

import asyncio
from typing import AsyncIterator

from src.infrastructure.llm.base import BaseLLMProvider, LLMMessage, StreamToken


class MockLLMProvider(BaseLLMProvider):
    """
    Simulates token-by-token streaming response based strictly on authorized context.
    Ideal for unit tests and local environments where Ollama is not running.
    """

    async def stream_chat(
        self,
        messages: list[LLMMessage],
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> AsyncIterator[StreamToken]:
        user_msg = next((m for m in reversed(messages) if m.role == "user"), None)
        system_msg = next((m for m in messages if m.role == "system"), None)

        question = user_msg.content if user_msg else "your query"
        has_authorized_context = system_msg and "DOCUMENT CONTEXT:" in system_msg.content

        if has_authorized_context:
            context_lower = system_msg.content.lower()
            q_lower = question.lower()
            
            # Check for financial metrics requested without finance docs in context
            is_finance_metric_query = any(k in q_lower for k in ["revenue", "gross margin", "ebitda", "profit", "budget", "financial forecast"])
            has_finance_docs = any(d in context_lower for d in ["quarterly revenue", "financial statements", "department budget", "financial forecast"])
            
            # Check for salary/compensation query without salary docs in context
            is_salary_query = any(k in q_lower for k in ["salary", "compensation", "payroll", "bonus", "pay bracket"])
            has_salary_docs = any(d in context_lower for d in ["salary records", "payroll reconciliation"])

            if is_finance_metric_query and not has_finance_docs:
                response = (
                    f"Access Notice: You inquired about financial performance ('{question}'), "
                    f"which falls under the Finance Department. Under Acme Corporation's Zanzibar relationship-based "
                    f"access control policy, you do not have permission to view Finance department records "
                    f"(e.g., Quarterly Revenue Report, Financial Statements). The authorized documents in your "
                    f"department profile do not contain quarterly revenue or gross margin figures.\n\n"
                    f"[Secure Retrieval Verified: Finance documents were strictly blocked prior to retrieval.]"
                )
            elif is_salary_query and not has_salary_docs:
                response = (
                    f"Access Notice: You inquired about employee compensation ('{question}'). "
                    f"Under the Zanzibar relationship-based access policy, confidential salary records are restricted "
                    f"to authorized HR managers. Your role does not have permission to view confidential compensation records.\n\n"
                    f"[Secure Retrieval Verified: Restricted salary records were excluded before retrieval.]"
                )
            else:
                response = (
                    f"Based on the authorized enterprise documents retrieved for your profile, "
                    f"here is the information regarding '{question}':\n\n"
                    f"1. Key Policy Details: The retrieved documentation confirms established organizational "
                    f"guidelines and operational runbooks applicable to your authorized role.\n"
                    f"2. Department Compliance: All actions must adhere to the standard operating procedures "
                    f"and security requirements detailed in the relevant departmental policy.\n"
                    f"3. Next Steps: For exceptions or confidential escalations, contact your department manager.\n\n"
                    f"[Secure Retrieval Verified: Context was restricted to authorized documents before retrieval.]"
                )
        else:
            response = (
                "Access Notice: No authorized documents were found matching your query. "
                "Under the Zanzibar relationship-based access policy, you either do not have permission "
                "to view documents in this category, or no matching records exist. "
                "Please reach out to your administrator to request access."
            )

        words = response.split(" ")
        for i, word in enumerate(words):
            token = word + (" " if i < len(words) - 1 else "")
            yield StreamToken(content=token, is_final=False)
            await asyncio.sleep(0.01)  # Simulate small streaming jitter

        yield StreamToken(content="", is_final=True, total_tokens=len(words))

    async def health_check(self) -> bool:
        return True

