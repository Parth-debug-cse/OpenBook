from __future__ import annotations
import ipaddress
import re
import socket
from typing import Tuple
from urllib.parse import urlparse

import httpx
import trafilatura
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound


_YT_PATTERN = re.compile(
    r"(?:youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_\-]{11})"
)
_ALLOWED_SCHEMES = {"http", "https"}
_FETCH_TIMEOUT_SECONDS = 10.0


def _extract_video_id(url: str) -> str | None:
    m = _YT_PATTERN.search(url)
    return m.group(1) if m else None


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError("Only http and https URLs are allowed.")
    if not parsed.hostname:
        raise ValueError("URL must include a hostname.")

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addr_infos = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise ValueError(f"Could not resolve URL hostname: {parsed.hostname}") from e

    hosts = {info[4][0] for info in addr_infos}
    for host in hosts:
        try:
            ip = ipaddress.ip_address(host)
        except ValueError as e:
            raise ValueError(f"Invalid resolved address for URL hostname: {host}") from e
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise ValueError("URL resolves to a blocked private, local, link-local, reserved, or multicast address.")


def scrape_youtube(url: str) -> Tuple[str, str]:
    video_id = _extract_video_id(url)
    if not video_id:
        raise ValueError(f"Cannot parse YouTube video ID from URL: {url}")

    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
    except (TranscriptsDisabled, NoTranscriptFound) as e:
        raise ValueError(f"No transcript available for {url}: {e}") from e

    text = " ".join(entry["text"] for entry in transcript_list)
    title = f"YouTube: {video_id}"
    return text, title


def scrape_web(url: str) -> Tuple[str, str]:
    _validate_url(url)
    try:
        response = httpx.get(
            url,
            follow_redirects=True,
            timeout=_FETCH_TIMEOUT_SECONDS,
            headers={"User-Agent": "OpenBook/1.0 (+https://localhost)"},
        )
        response.raise_for_status()
    except httpx.HTTPError as e:
        raise ValueError(f"Could not download page: {e}") from e

    text = trafilatura.extract(
        response.text,
        include_comments=False,
        include_tables=True,
        no_fallback=False,
    )
    if not text or len(text.strip()) < 50:
        raise ValueError(f"No usable text extracted from: {url}")

    return text.strip(), url


def scrape(url: str) -> Tuple[str, str]:
    if _extract_video_id(url):
        return scrape_youtube(url)
    return scrape_web(url)
