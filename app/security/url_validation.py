"""Hard validation for tool endpoint URLs (never trust the model for this)."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from app.constants import BLOCKED_IPV4_NETWORKS, BLOCKED_TOOL_HOSTNAMES

_BLOCKED_NETWORKS = tuple(ipaddress.ip_network(n) for n in BLOCKED_IPV4_NETWORKS)


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
        return True
    if ip.is_multicast or ip.is_unspecified:
        return True
    if isinstance(ip, ipaddress.IPv4Address):
        return any(ip in net for net in _BLOCKED_NETWORKS)
    # Block IPv6 unique-local and site-local equivalents already covered by is_private.
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return _is_blocked_ip(ip.ipv4_mapped)
    return False


def validate_tool_endpoint_url(url: str) -> str:
    """Raise ValueError unless URL is a public HTTPS endpoint."""
    if not isinstance(url, str) or not url.strip():
        raise ValueError("Tool endpoint must be a non-empty HTTPS URL")

    parsed = urlparse(url.strip())
    if parsed.scheme.lower() != "https":
        raise ValueError("Tool endpoint must use HTTPS")
    if not parsed.hostname:
        raise ValueError("Tool endpoint must include a hostname")
    if parsed.username or parsed.password:
        raise ValueError("Tool endpoint must not include credentials")

    host = parsed.hostname.lower().rstrip(".")
    if host in BLOCKED_TOOL_HOSTNAMES:
        raise ValueError(f"Tool endpoint hostname is blocked: {host}")
    if host.endswith(".localhost") or host.endswith(".local"):
        raise ValueError(f"Tool endpoint hostname is blocked: {host}")

    # Literal IP in hostname
    try:
        literal_ip = ipaddress.ip_address(host)
    except ValueError:
        literal_ip = None
    if literal_ip is not None and _is_blocked_ip(literal_ip):
        raise ValueError(f"Tool endpoint IP is not publicly routable: {host}")

    # DNS resolution check (SSRF hardening). Fail closed on resolution errors.
    resolve_port = parsed.port or 443
    try:
        addrinfos = socket.getaddrinfo(host, resolve_port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"Tool endpoint hostname could not be resolved: {host}") from exc

    if not addrinfos:
        raise ValueError(f"Tool endpoint hostname resolved to no addresses: {host}")

    for info in addrinfos:
        ip_str = info[4][0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError as exc:
            raise ValueError(f"Invalid resolved address for tool endpoint: {ip_str}") from exc
        if _is_blocked_ip(ip_obj):
            raise ValueError(
                f"Tool endpoint resolves to a non-public address ({ip_str}); blocked"
            )

    return url.strip()
