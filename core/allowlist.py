"""SSRF guard: only hosts listed in `config/sources.yaml` may be fetched (CLAUDE.md rule 7)."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

from core.config import SourcesConfig, load_sources


class DisallowedURL(ValueError):
    pass


def check_url(url: str, sources: SourcesConfig | None = None) -> str:
    """Return the URL unchanged if it is allowed, else raise :class:`DisallowedURL`.

    Rules: https only, no credentials in the URL, no explicit port other than 443,
    no IP literals, and the host must be listed exactly or end with a listed suffix.
    """
    src = sources or load_sources()
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise DisallowedURL(f"only https URLs may be fetched: {url!r}")
    if parts.username or parts.password:
        raise DisallowedURL("credentials in URLs are not allowed")
    host = (parts.hostname or "").lower().rstrip(".")
    if not host:
        raise DisallowedURL(f"URL has no host: {url!r}")
    try:
        port = parts.port
    except ValueError as exc:
        raise DisallowedURL(f"bad port in {url!r}") from exc
    if port not in (None, 443):
        raise DisallowedURL(f"non-standard port in {url!r}")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise DisallowedURL(f"IP-literal hosts are not allowed: {host}")
    if host in {h.lower() for h in src.hosts}:
        return url
    for suffix in src.suffixes:
        s = suffix.lower()
        if s.startswith(".") and host.endswith(s) and len(host) > len(s):
            return url
    raise DisallowedURL(f"host {host!r} is not in config/sources.yaml")


def is_allowed(url: str, sources: SourcesConfig | None = None) -> bool:
    try:
        check_url(url, sources)
    except DisallowedURL:
        return False
    return True
