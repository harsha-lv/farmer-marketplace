import ipaddress
import json
import socket
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from app.ondc.auth.signing import get_platform_signer


class CallbackError(Exception):
    """The buyer application did not accept the callback."""


def callback_url(bap_uri: str, action: str = "on_search") -> str:
    parsed = urlparse(bap_uri.strip())
    if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
        raise CallbackError("bap uri must be an http url")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addresses = _addresses(parsed.hostname, port)
    except socket.gaierror as exc:
        raise CallbackError("bap uri host did not resolve") from exc

    settings = get_settings()
    if settings.environment == "production":
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                raise CallbackError("bap uri must be a public host")
    return f"{parsed.scheme}://{parsed.netloc}/{action}"


class BecknCallback:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    async def on_search(self, bap_uri: str, payload: dict) -> None:
        await self.send(bap_uri, "on_search", payload)

    async def send(self, bap_uri: str, action: str, payload: dict) -> None:
        url = callback_url(bap_uri, action)
        body_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": get_platform_signer().sign_request(body_bytes),
        }
        try:
            from app.common.http_client import SafeAsyncClient

            _settings = get_settings()
            allow_priv = (_settings.environment != "production") or (self._transport is not None)
            async with SafeAsyncClient(
                transport=self._transport,
                allow_private=allow_priv,
                settings=_settings,
            ) as client:
                response = await client.post(url, content=body_bytes, headers=headers)
        except Exception as exc:
            raise CallbackError(f"{action} callback failed: {exc}") from exc
        if response.status_code >= 400:
            raise CallbackError(f"{action} callback returned {response.status_code}")


def _addresses(host: str, port: int) -> list[str]:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        infos = socket.getaddrinfo(host, port)
        return [info[4][0] for info in infos]
    return [host]
