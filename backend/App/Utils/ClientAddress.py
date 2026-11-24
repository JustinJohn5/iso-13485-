"""按明确配置的信任链解析客户端 IP。"""
from __future__ import annotations

from ipaddress import IPv4Address, IPv6Address, ip_address, ip_network
from typing import Iterable


def resolve_client_ip(peer_address: str | None, forwarded_for: str | None,
                      trusted_proxy_cidrs: Iterable[str]) -> str:
    """只有 TCP 对端属于可信代理时才使用 X-Forwarded-For。"""
    peer = _parse_address(peer_address)
    if peer is None:
        return "unknown"
    networks = _parse_networks(trusted_proxy_cidrs)
    if not forwarded_for or not _is_trusted(peer, networks):
        return str(peer)
    if len(forwarded_for) > 1024:
        return str(peer)

    forwarded = [_parse_address(value.strip()) for value in forwarded_for.split(",")]
    if not forwarded or len(forwarded) > 20 or any(value is None for value in forwarded):
        return str(peer)

    chain = [*forwarded, peer]
    for address in reversed(chain):
        if not _is_trusted(address, networks):
            return str(address)
    return str(forwarded[0])


def rate_limit_address(address: str) -> str:
    """IPv6 按 /64 聚合来源，避免单个客户端轮换临时地址绕过配额。"""
    parsed = _parse_address(address)
    if parsed is None:
        return "unknown"
    if isinstance(parsed, IPv6Address):
        return str(ip_network(f"{parsed}/64", strict=False).network_address)
    return str(parsed)


def _parse_address(value: str | None) -> IPv4Address | IPv6Address | None:
    try:
        return ip_address(value) if value else None
    except ValueError:
        return None


def _parse_networks(values: Iterable[str]):
    networks = []
    for value in values:
        if value.strip():
            networks.append(ip_network(value.strip(), strict=False))
    return networks


def _is_trusted(address: IPv4Address | IPv6Address, networks) -> bool:
    return any(address.version == network.version and address in network for network in networks)
