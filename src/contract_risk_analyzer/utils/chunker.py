from __future__ import annotations

from typing import List

import tiktoken


def chunk_section(text: str, max_tokens: int = 1500) -> List[str]:
    """
    Split text into overlapping token chunks.

    - max_tokens: maximum tokens per chunk
    - overlap: 100 tokens
    """
    if max_tokens <= 0:
        raise ValueError("max_tokens must be > 0")

    overlap = 100
    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text or "")

    if len(tokens) <= max_tokens:
        return [text or ""]

    step = max(1, max_tokens - overlap)
    chunks: List[str] = []

    start = 0
    n = len(tokens)
    while start < n:
        end = min(n, start + max_tokens)
        chunk_tokens = tokens[start:end]
        chunks.append(enc.decode(chunk_tokens))
        if end >= n:
            break
        start += step

    return chunks

