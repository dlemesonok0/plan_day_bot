from __future__ import annotations

from typing import Optional
import logging
import asyncio

from openai import OpenAI
from openai import APIStatusError

logger = logging.getLogger(__name__)


class HuggingFaceLLMClient:
    """Client for calling Hugging Face via OpenAI-compatible Router API."""

    def __init__(self, *, api_token: str, model: str, timeout: float = 40.0):
        self.api_token = api_token
        self.model = model
        self.timeout = timeout

        self._client = OpenAI(
            base_url="https://router.huggingface.co/v1",
            api_key=self.api_token,
        )
        logger.debug(
            "HuggingFaceLLMClient (router) initialized for model=%s", self.model
        )

    async def generate(
        self,
        prompt: str,
        *,
        max_new_tokens: int = 700,
        temperature: float = 0.4,
    ) -> str:
        """
        Генерирует текст с помощью router.huggingface.co в OpenAI-формате.
        Интерфейс сохранён таким же, как раньше.
        """

        logger.debug(
            "Sending request to HF Router API (model=%s)", self.model
        )

        def _call_openai():
            return self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                # max_tokens=max_new_tokens,
                # temperature=temperature,
            )

        try:
            completion = await asyncio.to_thread(_call_openai)
        except APIStatusError as exc:
            status_code = exc.status_code
            logger.error(
                "HF Router error status=%s details=%s",
                status_code,
                getattr(exc, "response", None),
            )
            if status_code == 410:
                raise ValueError(
                    (
                        f"Модель Hugging Face '{self.model}' более недоступна. "
                        "Обновите переменную окружения HUGGINGFACE_MODEL."
                    )
                ) from exc
            raise
        except Exception as exc:
            logger.exception("HF Router call failed")
            raise

        generated: Optional[str] = None
        if completion.choices:
            msg = completion.choices[0].message
            generated = msg.content

        if not generated:
            raise ValueError("Empty response from Hugging Face Router API")

        text = generated.strip()
        logger.debug(
            "Received response from HF Router API (length=%d)", len(text)
        )
        return text
