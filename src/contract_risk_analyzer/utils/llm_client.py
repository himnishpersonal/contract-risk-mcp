from __future__ import annotations

import random
import time
from typing import Type, TypeVar

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def _sleep_with_jitter(seconds: float) -> None:
    time.sleep(seconds + random.uniform(0, 0.2 * seconds))


def call_llm(system_prompt: str, user_prompt: str, response_schema: Type[T]) -> T:
    """
    Call GPT-4o and parse a structured response into the given Pydantic schema.

    Uses OpenAI Python SDK directly (no LangChain). Retries rate limits with
    exponential backoff (max 3 attempts).
    """
    load_dotenv()

    client = OpenAI()

    last_err: Exception | None = None
    for attempt in range(3):
        try:
            response = client.beta.chat.completions.parse(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=response_schema,
            )
            return response.choices[0].message.parsed
        except Exception as e:
            last_err = e
            msg = str(e)
            if ("429" in msg or "rate limit" in msg.lower()) and attempt < 2:
                _sleep_with_jitter(2**attempt)
                continue
            else:
                raise

    # Unreachable, but keeps typing happy.
    raise last_err  # type: ignore[misc]

