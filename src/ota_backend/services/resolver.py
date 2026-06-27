from __future__ import annotations

import ipaddress
import json
import re
import socket
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, Protocol
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
    def head(
        self,
        url: str,
        *,
        timeout: float,
        pinned_ip: str | None = ...,
    ) -> tuple[int, str | None]: ...


OPLUS_DOWNLOAD_CHECK_HEADERS = {
    "User-Agent": "okhttp/3.14.9",
    "userId": "oplus-ota|16000015",
}

OPLUS_INTERMEDIATE_MARKERS = ("downloadCheck", "servlet/download")
OPLUS_DIRECT_CDN_HEADERS = {"User-Agent": "curl/8.0.1"}
OPLUS_CN_COST_AUTO_PREFIX = "gauss-compotacostauto-cn."
OPLUS_CN_COST_MANUAL_PREFIX = "gauss-componentotacostmanual-cn."


class HttpxResolverTransport:
    def head(
        self,
        url: str,
        *,
        timeout: float,
        pinned_ip: str | None = None,
    ) -> tuple[int, str | None]:
        if _is_oplus_intermediate_url(url):
            response = self._send(
                "GET",
                url,
                headers=OPLUS_DOWNLOAD_CHECK_HEADERS,
                timeout=timeout,
                pinned_ip=pinned_ip,
            )
            if 300 <= response.status_code < 400:
                return response.status_code, response.headers.get("location")
            if response.status_code == 200:
                location = _extract_oplus_download_location(response)
                if location:
                    return 302, location
            return response.status_code, response.headers.get("location")

        response = self._send(
            "HEAD",
            url,
            headers=(
                OPLUS_DIRECT_CDN_HEADERS if _is_oplus_browser_blocked_direct_url(url) else None
            ),
            timeout=timeout,
            pinned_ip=pinned_ip,
        )
        return response.status_code, response.headers.get("location")

    @staticmethod
    def _send(
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None,
        timeout: float,
        pinned_ip: str | None,
    ) -> httpx.Response:
        if pinned_ip is None:
            # Preserve the simple, monkey-patchable httpx.get/head behavior for
            # local development and existing unit tests.
            if method == "GET":
                return httpx.get(
                    url,
                    headers=headers,
                    follow_redirects=False,
                    timeout=timeout,
                )
            return httpx.head(
                url,
                headers=headers,
                follow_redirects=False,
                timeout=timeout,
            )
        return _send_with_pinned_ip(
            method,
            url,
            headers=headers,
            timeout=timeout,
            pinned_ip=pinned_ip,
        )


def _send_with_pinned_ip(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None,
    timeout: float,
    pinned_ip: str,
) -> httpx.Response:
    """Send an HTTP request to an explicitly validated IP address.

    The URL hostname is rewritten to the pinned IP literal, while the original
    hostname is preserved in the Host header and in the TLS SNI/cert
    verification name. This closes the TOCTOU window between DNS validation
    and the actual TCP connect, so a rebind that suddenly maps the hostname
    to a private/internal IP cannot redirect the resolver.
    """

    parsed = urlsplit(url)
    hostname = (parsed.hostname or "").rstrip(".").lower()
    if not hostname:
        raise ResolverError("VALIDATION_ERROR", "A valid HTTP(S) URL is required.")
    port = parsed.port
    pinned_netloc = pinned_ip + (f":{port}" if port else "")
    pinned_url = urlunsplit((parsed.scheme, pinned_netloc, parsed.path or "/", parsed.query, ""))
    final_headers = dict(headers or {})
    final_headers["Host"] = hostname
    request_obj = httpx.Request(
        method,
        pinned_url,
        headers=final_headers,
        extensions={"sni_hostname": hostname},
    )
    with httpx.Client(timeout=timeout) as client:
        return client.send(request_obj, follow_redirects=False)


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
        # Per-resolve DNS cache. Reused for every hop so a hostname is
        # resolved (and validated) exactly once, and the same IP is reused
        # for the actual TCP connect via pinned-IP transport. This closes the
        # DNS rebind window between safety validation and the HTTP fetch.
        dns_cache: dict[str, list[str]] = {}
        try:
            original = self._validated_safe_url(value, dns_cache=dns_cache)
            stored_input = original
            current = self._component_link_transform(original)
            current = self._validated_safe_url(current, dns_cache=dns_cache)
            normalized_legacy_auto = _is_oplus_cn_cost_auto_url(original)
            for hop in range(self._max_redirects + 1):
                pinned_ip = self._pinned_ip_for(current, dns_cache=dns_cache)
                status_code, location = self._transport.head(
                    current,
                    timeout=self._timeout_seconds,
                    pinned_ip=pinned_ip,
                )
                if 300 <= status_code < 400 and location:
                    if hop >= self._max_redirects:
                        raise ResolverError("RESOLVE_FAILED", "Too many resolver redirects.")
                    current = self._validated_safe_url(
                        urljoin(current, location), dns_cache=dns_cache
                    )
                    continue
                if 200 <= status_code < 300:
                    # If the final URL still contains intermediate servlet endpoints,
                    # it means the OPlus server did not redirect, indicating an expired token.
                    if _is_oplus_intermediate_url(current):
                        raise ResolverError(
                            "RESOLVE_FAILED",
                            "The OTA link has expired or the signature is invalid"
                            " (upstream error 2306).",
                        )
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
                if normalized_legacy_auto:
                    raise ResolverError(
                        "RESOLVE_FAILED",
                        "This legacy auto CDN link is no longer available after "
                        "manual-host normalization. Use a fresh downloadCheck link "
                        "or rerun the OTA query.",
                    )
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

    def _validated_safe_url(
        self,
        value: str,
        *,
        dns_cache: dict[str, list[str]] | None = None,
    ) -> str:
        parsed = urlsplit(value.strip())
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            raise ResolverError("VALIDATION_ERROR", "A valid HTTP(S) URL is required.")
        if parsed.username or parsed.password:
            raise ResolverError("VALIDATION_ERROR", "URL credentials are not allowed.")
        if parsed.port not in {None, 80, 443}:
            raise ResolverError(
                "RESOLVE_BLOCKED_HOST", "This URL port is not allowed.", status="blocked"
            )
        hostname = parsed.hostname.rstrip(".").lower()
        if not any(
            hostname == suffix or hostname.endswith("." + suffix)
            for suffix in self._allowed_suffixes
        ):
            raise ResolverError(
                "RESOLVE_BLOCKED_HOST", "This host is not allowed.", status="blocked"
            )
        if dns_cache is not None and hostname in dns_cache:
            addresses = dns_cache[hostname]
        else:
            addresses = self._dns_resolver(hostname)
            if dns_cache is not None:
                dns_cache[hostname] = addresses
        if not addresses:
            raise ResolverError("RESOLVE_FAILED", "Host resolution failed.")
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if not ip.is_global:
                raise ResolverError(
                    "RESOLVE_BLOCKED_HOST", "This host is not allowed.", status="blocked"
                )
        netloc = hostname
        if parsed.port:
            netloc += f":{parsed.port}"
        return urlunsplit((parsed.scheme.lower(), netloc, parsed.path or "/", parsed.query, ""))

    def _pinned_ip_for(
        self,
        url: str,
        *,
        dns_cache: dict[str, list[str]],
    ) -> str | None:
        parsed = urlsplit(url)
        hostname = (parsed.hostname or "").rstrip(".").lower()
        if not hostname:
            return None
        addresses = dns_cache.get(hostname)
        if not addresses:
            return None
        # Prefer the first validated address. All addresses passed the
        # is_global check above, so any is safe to use.
        return addresses[0]

    @staticmethod
    def _component_link_transform(value: str) -> str:
        parsed = urlsplit(value)
        hostname = parsed.hostname or ""
        if hostname.startswith(OPLUS_CN_COST_AUTO_PREFIX):
            hostname = OPLUS_CN_COST_MANUAL_PREFIX + hostname.removeprefix(
                OPLUS_CN_COST_AUTO_PREFIX
            )
        elif not hostname.startswith(OPLUS_CN_COST_MANUAL_PREFIX):
            hostname = hostname.replace("componentotacostmanual", "opexcostmanual")
        netloc = hostname + (f":{parsed.port}" if parsed.port else "")
        return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, ""))

    @staticmethod
    def _default_dns_resolver(hostname: str) -> list[str]:
        try:
            return sorted(
                {
                    # entry[4] is a sockaddr tuple; for AF_INET the first
                    # element is an IPv4 string, for AF_INET6 it is also a
                    # string. Coerce defensively to satisfy strict typing.
                    str(entry[4][0])
                    for entry in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
                }
            )
        except socket.gaierror:
            return []


def _is_oplus_intermediate_url(value: str) -> bool:
    return any(marker in value for marker in OPLUS_INTERMEDIATE_MARKERS)


def _is_oplus_browser_blocked_direct_url(value: str) -> bool:
    parsed = urlsplit(value)
    hostname = parsed.hostname or ""
    return hostname.startswith(OPLUS_CN_COST_MANUAL_PREFIX)


def _is_oplus_cn_cost_auto_url(value: str) -> bool:
    parsed = urlsplit(value)
    hostname = parsed.hostname or ""
    return hostname.startswith(OPLUS_CN_COST_AUTO_PREFIX)


def _extract_oplus_download_location(response: httpx.Response) -> str | None:
    try:
        payload = response.json()
    except json.JSONDecodeError:
        payload = None

    if isinstance(payload, dict):
        _raise_for_oplus_error(payload)
        for candidate in _iter_structured_url_candidates(payload):
            if _looks_like_download_location(candidate):
                return candidate

    for candidate in _iter_text_url_candidates(response.text):
        if _looks_like_download_location(candidate):
            return candidate
    return None


def _raise_for_oplus_error(payload: dict[str, Any]) -> None:
    response_code = payload.get("responseCode")
    err_msg = str(payload.get("errMsg") or "")
    if response_code == 2306 or str(response_code) == "2306" or "[2306]" in err_msg:
        raise ResolverError(
            "RESOLVE_FAILED",
            "The OTA link has expired or the signature is invalid (upstream error 2306).",
        )


def _iter_structured_url_candidates(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        normalized = _normalize_candidate_url(value)
        if normalized:
            yield normalized
        return

    if isinstance(value, list):
        for item in value:
            yield from _iter_structured_url_candidates(item)
        return

    if not isinstance(value, dict):
        return

    preferred_keys = (
        "downloadUrl",
        "download_url",
        "manualUrl",
        "manual_url",
        "panelUrl",
        "panel_url",
        "url",
        "link",
        "href",
    )
    for key in preferred_keys:
        if key in value:
            yield from _iter_structured_url_candidates(value[key])
    for key, item in value.items():
        if key not in preferred_keys:
            yield from _iter_structured_url_candidates(item)


def _iter_text_url_candidates(value: str) -> Iterable[str]:
    for match in re.finditer(r"https?:\\/\\/[^\"'\\s<>]+|https?://[^\"'\\s<>]+", value):
        normalized = _normalize_candidate_url(match.group(0))
        if normalized:
            yield normalized


def _normalize_candidate_url(value: str) -> str | None:
    candidate = value.strip().replace("\\/", "/")
    if not candidate.lower().startswith(("http://", "https://")):
        return None
    return candidate


def _looks_like_download_location(value: str) -> bool:
    lower_value = value.lower()
    return (
        ".zip" in lower_value
        or ".ozip" in lower_value
        or "downloadcheck" in lower_value
        or "servlet/download" in lower_value
    )
