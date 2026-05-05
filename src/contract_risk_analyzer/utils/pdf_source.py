from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from typing import Iterator
from urllib.parse import urlparse

import httpx


MAX_PDF_BYTES = 50 * 1024 * 1024
DOWNLOAD_TIMEOUT_SECONDS = 60.0


def _validate_source(file_path: str | None, pdf_url: str | None) -> None:
    if bool(file_path) == bool(pdf_url):
        raise ValueError("Provide exactly one of file_path or pdf_url.")


def _validate_pdf_url(pdf_url: str) -> None:
    parsed = urlparse(pdf_url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("pdf_url must use http or https.")
    if not parsed.netloc:
        raise ValueError("pdf_url must include a hostname.")


def _download_pdf(pdf_url: str) -> str:
    _validate_pdf_url(pdf_url)

    fd, path = tempfile.mkstemp(prefix="contract-risk-", suffix=".pdf")
    bytes_written = 0

    try:
        with os.fdopen(fd, "wb") as out:
            with httpx.stream(
                "GET",
                pdf_url,
                follow_redirects=True,
                timeout=DOWNLOAD_TIMEOUT_SECONDS,
            ) as response:
                response.raise_for_status()
                for chunk in response.iter_bytes():
                    if not chunk:
                        continue
                    bytes_written += len(chunk)
                    if bytes_written > MAX_PDF_BYTES:
                        raise ValueError(
                            f"PDF exceeds maximum size of {MAX_PDF_BYTES // (1024 * 1024)} MB."
                        )
                    out.write(chunk)
        return path
    except Exception:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        raise


@contextmanager
def pdf_path_from_source(
    file_path: str | None = None,
    pdf_url: str | None = None,
) -> Iterator[str]:
    """
    Yield a local PDF path for either an existing file path or a remote PDF URL.

    Remote PDFs are downloaded to a temporary file and removed when the caller exits
    the context. Local file paths are yielded unchanged.
    """
    _validate_source(file_path, pdf_url)

    if file_path:
        yield file_path
        return

    assert pdf_url is not None
    temp_path = _download_pdf(pdf_url)
    try:
        yield temp_path
    finally:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass
