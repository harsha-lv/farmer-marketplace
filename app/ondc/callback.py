import ipaddress
import socket
from urllib.parse import urlparse

import httpx


class CallbackError(Exception):
    """The buyer application did not accept on_search."""


def callback_url(bap_uri: str) -> str:
    parsed = urlparse(bap_uri.strip())
    if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
        raise CallbackError("bap uri must be an http url")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addresses = _addresses(parsed.hostname, port)
    except socket.gaierror as exc:
        raise CallbackError("bap uri host did not resolve") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise CallbackError("bap uri must be a public host")
    return f"{parsed.scheme}://{parsed.netloc}/on_search"


class BecknCallback:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    async def on_search(self, bap_uri: str, payload: dict) -> None:
        url = callback_url(bap_uri)
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=30.0) as client:
                response = await client.post(url, json=payload)
        except httpx.HTTPError as exc:
            raise CallbackError("on_search callback failed") from exc
        if response.status_code >= 400:
            raise CallbackError(f"on_search callback returned {response.status_code}")


def _addresses(host: str, port: int) -> list[str]:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        infos = socket.getaddrinfo(host, port)
        return [info[4][0] for info in infos]
    return [host]
