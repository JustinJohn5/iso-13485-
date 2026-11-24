"""客户端地址解析只信任显式配置的反向代理。"""

import pytest


@pytest.mark.parametrize(
    ("peer", "forwarded_for", "trusted_proxies", "expected"),
    [
        ("203.0.113.9", "198.51.100.4", [], "203.0.113.9"),
        ("10.0.0.8", "198.51.100.4, 10.0.0.7", ["10.0.0.0/24"], "198.51.100.4"),
        ("10.0.0.8", "not-an-ip", ["10.0.0.0/24"], "10.0.0.8"),
    ],
)
def test_resolve_client_ip_trusts_only_configured_proxy_chain(peer, forwarded_for, trusted_proxies, expected):
    from App.Utils.ClientAddress import resolve_client_ip

    assert resolve_client_ip(peer, forwarded_for, trusted_proxies) == expected
