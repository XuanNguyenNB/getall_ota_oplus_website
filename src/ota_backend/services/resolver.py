from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Callable, Protocol
from urllib.parse import urljoin, urlsplit, urlunsplit
from uuid import uuid4

import httpx

from ota_backend.domain.models import ResolveRequest, utc_now
from ota_backend.repositories.interfaces import ResolverRepository


class ResolverError(Exception):
    def __init__(self, code: str, message: str, *, status: str = "failed") -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


@dataclass(frozen=True)
class ResolverResult:
    input_url: str
    resolved_url: str


class ResolverTransport(Protocol):
    def head(self, url: str, *, timeout: float) -> tuple[int, str | None]:
        ...


class HttpxResolverTransport:
    def head(self, url: str, *, timeout: float) -> tuple[int, str | None]:
        response = httpx.head(url, follow_redirects=False, timeout=timeout)
        return response.status_code, response.headers.get("location")


class ResolverService:
    def __init__(
        self,
        *,
        repository: ResolverRepository,
        allowed_suffixes: tuple[str, ...],
        timeout_seconds: float,
        max_redirects: int,
        transport: ResolverTransport | None = None,
        dns_resolver: Callable[[str], list[str]] | None = None,
    ) -> None:
        self._repository = repository
        self._allowed_suffixes = allowed_suffixes
        self._timeout_seconds = timeout_seconds
        self._max_redirects = max_redirects
        self._transport = transport or HttpxResolverTransport()
        self._dns_resolver = dns_resolver or self._default_dns_resolver

    def resolve(self, value: str, *, source: str = "web") -> ResolverResult:
        stored_input: str | None = None
        try:
            original = self._validated_safe_url(value)
            stored_input = original
            current = self._component_link_transform(original)
            current = self._validated_safe_url(current)
            for hop in range(self._max_redirects + 1):
                status_code, location = self._transport.head(
                    current, timeout=self._timeout_seconds
                )
                if 300 <= status_code < 400 and location:
                    if hop >= self._max_redirects:
                        raise ResolverError("RESOLVE_FAILED", "Too many resolver redirects.")
                    current = self._validated_safe_url(urljoin(current, location))
                    continue
                if 200 <= status_code < 300:
                    result = ResolverResult(input_url=original, resolved_url=current)
                    self._repository.record(
                        ResolveRequest(
                            id=uuid4(),
                            source=source,  # type: ignore[arg-type]
                            status="success",
                            created_at=utc_now(),
                            input_url=original,
                            resolved_url=current,
                        )
                    )
                    return result
                raise ResolverError("RESOLVE_FAILED", "The resolver upstream rejected this URL.")
            raise ResolverError("RESOLVE_FAILED", "Resolver did not reach a final URL.")
        except ResolverError as exc:
            self._repository.record(
                ResolveRequest(
                    id=uuid4(),
                    source=source,  # type: ignore[arg-type]
                    status=exc.status,  # type: ignore[arg-type]
                    created_at=utc_now(),
                    input_url=stored_input,
                    error_code=exc.code,
                    error_message=exc.message,
                )
            )
            raise

    def _validated_safe_url(self, value: str) -> str:
        parsed = urlsplit(value.strip())
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            raise ResolverError("VALIDATION_ERROR", "A valid HTTP(S) URL is required.")
        if parsed.username or parsed.password:
            raise ResolverError("VALIDATION_ERROR", "URL credentials are not allowed.")
        if parsed.port not in {None, 80, 443}:
            raise ResolverError("RESOLVE_BLOCKED_HOST", "This URL port is not allowed.", status="blocked")
        hostname = parsed.hostname.rstrip(".").lower()
        if not any(
            hostname == suffix or hostname.endswith("." + suffix)
            for suffix in self._allowed_suffixes
        ):
            raise ResolverError("RESOLVE_BLOCKED_HOST", "This host is not allowed.", status="blocked")
        addresses = self._dns_resolver(hostname)
        if not addresses:
            raise ResolverError("RESOLVE_FAILED", "Host resolution failed.")
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if not ip.is_global:
                raise ResolverError("RESOLVE_BLOCKED_HOST", "This host is not allowed.", status="blocked")
        netloc = hostname
        if parsed.port:
            netloc += f":{parsed.port}"
        return urlunsplit((parsed.scheme.lower(), netloc, parsed.path or "/", parsed.query, ""))

    @staticmethod
    def _component_link_transform(value: str) -> str:
        parsed = urlsplit(value)
        hostname = (parsed.hostname or "").replace("componentotacostmanual", "opexcostmanual")
        netloc = hostname + (f":{parsed.port}" if parsed.port else "")
        return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, ""))

    @staticmethod
    def _default_dns_resolver(hostname: str) -> list[str]:
        try:
            return sorted(
                {
                    entry[4][0]
                    for entry in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
                }
            )
        except socket.gaierror:
            return []
