"""OpenAI LLM provider implementation."""

import os
from typing import List, Optional

import openai
from pydantic import SecretStr

from coding_agent.application.ports.llm_port import LLMPort, Message, Response
from coding_agent.utils.errors import LLMError


class OpenAIClient(LLMPort):
    """OpenAI API client implementation."""

    def __init__(
        self,
        api_key: SecretStr,
        model: str = "gpt-4o",
        temperature: float = 0.1,
        max_tokens: int = 2000,
        timeout: float = 30.0,
    ):
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout = timeout
        self._api_key = api_key

        # Initialize client
        try:
            self._client = openai.AsyncOpenAI(
                api_key=api_key.get_secret_value() if api_key else os.getenv("OPENAI_API_KEY"),
                timeout=timeout,
            )
        except Exception as e:
            raise LLMError(
                f"Failed to initialize OpenAI client: {e}",
                response=str(e),
            )

    async def complete(self, messages: List[Message]) -> Response:
        """Send messages and get completion.

        Args:
            messages: List of messages

        Returns:
            Response from OpenAI

        Raises:
            LLMError: If request fails
        """
        try:
            openai_messages = [
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ]

            result = await self._client.chat.completions.create(
                model=self._model,
                messages=openai_messages,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )

            return Response(
                content=result.choices[0].message.content or "",
                usage={
                    "prompt_tokens": result.usage.prompt_tokens if result.usage else 0,
                    "completion_tokens": result.usage.completion_tokens if result.usage else 0,
                    "total_tokens": result.usage.total_tokens if result.usage else 0,
                },
                model=result.model,
                finish_reason=result.choices[0].finish_reason,
            )

        except openai.APIError as e:
            raise LLMError(
                f"OpenAI API error: {e.message}",
                status_code=e.status_code if hasattr(e, "status_code") else None,
                response=str(e),
            )
        except Exception as e:
            raise LLMError(f"Unexpected error calling OpenAI: {e}", response=str(e))

    def count_tokens(self, text: str) -> int:
        """Estimate token count.

        Args:
            text: Text to count

        Returns:
            Estimated token count
        """
        # Rough estimate: 1 token ~ 4 characters
        return len(text) // 4

    async def health_check(self) -> bool:
        """Check if OpenAI is accessible.

        Returns:
            True if healthy
        """
        try:
            # Simple check - just list models
            await self._client.models.list()
            return True
        except Exception:
            return False
