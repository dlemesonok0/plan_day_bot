from __future__ import annotations

from typing import Optional
import logging

import httpx


logger = logging.getLogger(__name__)

class HuggingFaceLLMClient:
    """Client for calling Hugging Face Inference API models."""

    def __init__(self, *, api_token: str, model: str, timeout: float = 40.0):
        self.api_token = api_token
        self.model = model
        self.timeout = timeout
        self._url = f"https://api-inference.huggingface.co/models/{model}"
        logger.debug("HuggingFaceLLMClient initialized for model=%s", model)

    async def generate(
        self,
        prompt: str,
        *,
        max_new_tokens: int = 700,
        temperature: float = 0.4,
    ) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_token}",
        }
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": max_new_tokens,
                "temperature": temperature,
                "return_full_text": False,
            },
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            logger.debug(
                "Sending request to Hugging Face Inference API (model=%s)", self.model
            )
            response = await client.post(self._url, headers=headers, json=payload)

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code == 410:
                raise ValueError(
                    (
                        f"Модель Hugging Face '{self.model}' более недоступна. "
                        "Обновите переменную окружения HUGGINGFACE_MODEL."
                    )
                ) from exc
            raise

        data = response.json()

        generated: Optional[str] = None
        if isinstance(data, list):
            if data and isinstance(data[0], dict):
                generated = data[0].get("generated_text")
        elif isinstance(data, dict):
            generated = data.get("generated_text")

        if not generated:
            raise ValueError("Empty response from Hugging Face Inference API")
        logger.debug(
            "Received response from Hugging Face Inference API (length=%d)", len(generated)
        )
        return generated.strip()
