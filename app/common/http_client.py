"""SSRF-Hardened Outbound HTTP Client.

Guarantees:
  - Scheme Validation: Strictly blocks file://, gopher://, ftp://, data://; only http:// and https:// allowed.
  - IP & DNS Target Hardening:
      * Blocks RFC 1918 Private ranges: 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16
      * Blocks Loopback targets: 127.0.0.0/8, ::1, localhost
      * Blocks Link-Local targets: 169.254.0.0/16, fe80::/10
      * Blocks Cloud Metadata Service: 169.254.169.254
      * Blocks IPv6 Unique Local Addresses (ULA): fc00::/7
      * Blocks Reserved, Multicast, Unspecified (0.0.0.0, ::/128, 224.0.0.0/4, 240.0.0.0/4)
  - Redirect Hop Hardening: Re-validates every redirect hop against SSRF rules before following.
  - Timeouts: Connect, read, write, and pool timeouts driven by settings with sane defaults.
"""

import ipaddress
import logging
import socket
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from app.config import Settings, get_settings
from app.errors import AppError

logger = logging.getLogger("app.common.http_client")

# Prohibited CIDR blocks
PROHIBITED_IPV4_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),         # Broadcast / Current network
    ipaddress.ip_network("10.0.0.0/8"),        # RFC 1918
    ipaddress.ip_network("127.0.0.0/8"),       # Loopback
    ipaddress.ip_network("169.254.0.0/16"),     # Link-local & Cloud metadata (includes 169.254.169.254)
    ipaddress.ip_network("172.16.0.0/12"),      # RFC 1918
    ipaddress.ip_network("192.168.0.0/16"),     # RFC 1918
    ipaddress.ip_network("224.0.0.0/4"),       # Multicast
    ipaddress.ip_network("240.0.0.0/4"),       # Reserved
]

PROHIBITED_IPV6_NETWORKS = [
    ipaddress.ip_network("::1/128"),           # Loopback
    ipaddress.ip_network("::/128"),            # Unspecified
    ipaddress.ip_network("fc00::/7"),          # IPv6 Unique Local Address (ULA)
    ipaddress.ip_network("fe80::/10"),         # Link-local
    ipaddress.ip_network("ff00::/8"),          # Multicast
]

CLOUD_METADATA_IP = ipaddress.ip_address("169.254.169.254")


class SSRFBlockedError(AppError):
    """Raised when an outbound HTTP request targets a prohibited or internal IP/scheme."""

    def __init__(self, detail: str) -> None:
        super().__init__(
            status_code=403,
            title="SSRF Request Blocked",
            detail=detail,
        )


def is_ip_prohibited(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> tuple[bool, str]:
    """Check if an IP address belongs to any prohibited private, loopback, or metadata subnet."""
    if ip == CLOUD_METADATA_IP:
        return True, "Cloud instance metadata service (169.254.169.254) is prohibited"

    if ip.is_loopback:
        return True, f"Loopback address ({ip}) is prohibited"

    if ip.is_link_local:
        return True, f"Link-local address ({ip}) is prohibited"

    if ip.is_private:
        return True, f"Private / RFC1918 / ULA address ({ip}) is prohibited"

    if ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        return True, f"Multicast/reserved/unspecified address ({ip}) is prohibited"

    if isinstance(ip, ipaddress.IPv4Address):
        for net in PROHIBITED_IPV4_NETWORKS:
            if ip in net:
                return True, f"Address {ip} belongs to prohibited IPv4 network {net}"
    elif isinstance(ip, ipaddress.IPv6Address):
        for net in PROHIBITED_IPV6_NETWORKS:
            if ip in net:
                return True, f"Address {ip} belongs to prohibited IPv6 network {net}"

    return False, ""


def validate_url_and_resolve(url: str, *, allow_private: bool = False) -> str:
    """Validate URL scheme and resolve host to ensure it does not target prohibited networks.

    Returns the normalized URL if valid, or raises SSRFBlockedError.
    """
    clean_url = str(url).strip()
    if not clean_url:
        raise SSRFBlockedError("URL cannot be empty")

    parsed = urlparse(clean_url)
    scheme = (parsed.scheme or "").lower()

    if scheme not in ("http", "https"):
        raise SSRFBlockedError(
            f"Prohibited URL scheme '{scheme}'. Only HTTP and HTTPS protocols are permitted (file:// and others blocked)."
        )

    host = parsed.hostname
    if not host:
        raise SSRFBlockedError("URL host is missing or invalid")

    # If host is an IP literal
    try:
        ip = ipaddress.ip_address(host)
        if not allow_private:
            prohibited, reason = is_ip_prohibited(ip)
            if prohibited:
                raise SSRFBlockedError(f"Target host {host} is blocked: {reason}")
        return clean_url
    except ValueError:
        pass  # Host is a domain name, proceed to DNS resolution

    # Resolve domain via DNS
    port = parsed.port or (443 if scheme == "https" else 80)
    try:
        addr_info = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise SSRFBlockedError(f"DNS resolution failed for host '{host}': {exc}") from exc

    if not addr_info:
        raise SSRFBlockedError(f"Could not resolve host '{host}' to any IP address")

    if not allow_private:
        for entry in addr_info:
            sockaddr = entry[4]
            ip_str = sockaddr[0]
            try:
                ip_obj = ipaddress.ip_address(ip_str)
                prohibited, reason = is_ip_prohibited(ip_obj)
                if prohibited:
                    logger.warning("SSRF blocked: host '%s' resolves to prohibited IP %s (%s)", host, ip_str, reason)
                    raise SSRFBlockedError(f"Host '{host}' resolves to prohibited IP {ip_str}: {reason}")
            except ValueError:
                continue

    return clean_url


class SafeAsyncClient:
    """Async HTTP client wrapper providing SSRF protection, redirect hop re-validation, and settings-tuned timeouts."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float | httpx.Timeout | None = None,
        allow_private: bool | None = None,
        max_redirects: int | None = None,
        **client_kwargs: Any,
    ) -> None:
        self.settings = settings or get_settings()
        self.allow_private = (
            allow_private
            if allow_private is not None
            else getattr(self.settings, "http_ssrf_allow_private", False)
        )
        self.max_redirects = (
            max_redirects
            if max_redirects is not None
            else getattr(self.settings, "http_max_redirects", 5)
        )

        if timeout is None:
            self.timeout = httpx.Timeout(
                connect=getattr(self.settings, "http_connect_timeout_seconds", 5.0),
                read=getattr(self.settings, "http_read_timeout_seconds", 15.0),
                write=getattr(self.settings, "http_write_timeout_seconds", 10.0),
                pool=getattr(self.settings, "http_pool_timeout_seconds", 5.0),
            )
        elif isinstance(timeout, (int, float)):
            self.timeout = httpx.Timeout(timeout)
        else:
            self.timeout = timeout

        self._transport = transport
        self._client_kwargs = client_kwargs
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "SafeAsyncClient":
        self._client = httpx.AsyncClient(
            transport=self._transport,
            timeout=self.timeout,
            follow_redirects=False,  # Redirects are manually handled and re-validated
            **self._client_kwargs,
        )
        await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._client:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)
            self._client = None

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        data: Any = None,
        json: Any = None,
        content: Any = None,
        timeout: float | httpx.Timeout | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Execute request with pre-validation and hop-by-hop redirect verification."""
        current_url = validate_url_and_resolve(url, allow_private=self.allow_private)
        req_headers = dict(headers or {})
        req_timeout = timeout or self.timeout

        own_client = False
        client = self._client
        if client is None:
            own_client = True
            client = httpx.AsyncClient(
                transport=self._transport,
                timeout=req_timeout,
                follow_redirects=False,
                **self._client_kwargs,
            )
            await client.__aenter__()

        try:
            redirects_count = 0
            current_method = method
            current_data = data
            current_json = json
            current_content = content

            while True:
                response = await client.request(
                    current_method,
                    current_url,
                    headers=req_headers,
                    params=params if redirects_count == 0 else None,
                    data=current_data,
                    json=current_json,
                    content=current_content,
                    timeout=req_timeout,
                    **kwargs,
                )

                if response.is_redirect and "location" in response.headers:
                    redirects_count += 1
                    if redirects_count > self.max_redirects:
                        raise SSRFBlockedError(f"Exceeded maximum allowed redirects ({self.max_redirects})")

                    location = response.headers["location"]
                    target_url = urljoin(current_url, location)

                    # Re-validate the redirect destination hop
                    current_url = validate_url_and_resolve(target_url, allow_private=self.allow_private)
                    logger.debug("Redirect hop %d -> validated %s", redirects_count, current_url)

                    # 303 or 301/302 from POST switches to GET
                    if response.status_code in (301, 302, 303):
                        current_method = "GET"
                        current_data = None
                        current_json = None
                        current_content = None

                    continue

                return response
        finally:
            if own_client:
                await client.__aexit__(None, None, None)

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("PUT", url, **kwargs)

    async def patch(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("PATCH", url, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("DELETE", url, **kwargs)
