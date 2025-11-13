from __future__ import annotations

from typing import Optional

import httpx


class HuggingFaceLLMClient:
    """Client for calling Hugging Face Inference API models."""

    def __init__(self, *, api_token: str, model: str, timeout: float = 40.0):
        self.api_token = api_token
        self.model = model
        self.timeout = timeout
        self._url = f"https://api-inference.huggingface.co/models/{model}"

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
            response = await client.post(self._url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        generated: Optional[str] = None
        if isinstance(data, list):
            if data and isinstance(data[0], dict):
                generated = data[0].get("generated_text")
        elif isinstance(data, dict):
            generated = data.get("generated_text")

        if not generated:
            raise ValueError("Empty response from Hugging Face Inference API")
        return generated.strip()
