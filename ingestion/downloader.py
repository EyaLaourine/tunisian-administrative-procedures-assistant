"""Polite, size-capped downloader restricted to allow-listed official domains."""

import logging
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

log = logging.getLogger(__name__)


class DownloadError(Exception):
    pass


@dataclass
class DownloadResult:
    data: bytes
    final_url: str
    status_code: int
    content_type: str | None
    last_modified: str | None


class Downloader:
    def __init__(self, client: httpx.Client, allowed_domains: list[str], max_bytes: int, default_delay: float):
        self._client = client
        self._allowed = set(allowed_domains)
        self._max_bytes = max_bytes
        self._default_delay = default_delay
        self._last_request_at: dict[str, float] = {}

    def _respect_delay(self, host: str, crawl_delay: float | None) -> None:
        delay = max(self._default_delay, crawl_delay or 0.0)
        last = self._last_request_at.get(host)
        if last is not None:
            wait = delay - (time.monotonic() - last)
            if wait > 0:
                time.sleep(wait)
        self._last_request_at[host] = time.monotonic()

    def fetch(self, url: str, crawl_delay: float | None = None) -> DownloadResult:
        host = urlsplit(url).hostname or ""
        if host not in self._allowed:
            raise DownloadError(f"host not allow-listed: {host}")
        self._respect_delay(host, crawl_delay)
        try:
            with self._client.stream("GET", url) as resp:
                final_host = resp.url.host
                if final_host not in self._allowed:
                    raise DownloadError(f"redirected to non-allow-listed host: {final_host}")
                if resp.status_code != 200:
                    raise DownloadError(f"HTTP {resp.status_code}")
                declared = resp.headers.get("content-length")
                if declared and declared.isdigit() and int(declared) > self._max_bytes:
                    raise DownloadError(f"file too large: {declared} bytes")
                chunks: list[bytes] = []
                total = 0
                for chunk in resp.iter_bytes():
                    total += len(chunk)
                    if total > self._max_bytes:
                        raise DownloadError(f"file exceeds {self._max_bytes} bytes")
                    chunks.append(chunk)
                return DownloadResult(
                    data=b"".join(chunks),
                    final_url=str(resp.url),
                    status_code=resp.status_code,
                    content_type=resp.headers.get("content-type"),
                    last_modified=resp.headers.get("last-modified"),
                )
        except httpx.HTTPError as exc:
            raise DownloadError(f"{type(exc).__name__}: {exc}") from exc
