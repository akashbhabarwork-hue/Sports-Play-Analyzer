import pytest

from app.core.net_rules import is_allowed_media_host, is_public_ip


@pytest.mark.parametrize(
    "addr",
    [
        "127.0.0.1", "127.255.255.254", "10.0.0.1", "172.16.0.1", "172.31.255.255",
        "192.168.1.1", "169.254.169.254", "100.64.0.1", "0.0.0.0", "255.255.255.255",
        "224.0.0.1", "192.0.2.1", "198.18.0.1",
        "::1", "::", "fc00::1", "fd12:3456::1", "fe80::1", "fe80::1%eth0", "ff02::1",
        "::ffff:10.0.0.1", "::ffff:127.0.0.1", "::ffff:169.254.169.254",
        "2002:a00:1::1",  # 6to4 wrapping 10.0.0.1
        "2002:a9fe:a9fe::1",  # 6to4 wrapping 169.254.169.254
        "2001:0:4136:e378:8000:63bf:f5ff:fffe",  # Teredo
        "::8.8.8.8",  # deprecated IPv4-compatible form
        "2001:db8::1",  # documentation
        "not-an-ip", "", "1.2.3", "8.8.8.8.8",
    ],
)  # fmt: skip
def test_net_rules_block_non_public_ips(addr):
    assert is_public_ip(addr) is False


@pytest.mark.parametrize(
    "addr", ["8.8.8.8", "142.250.72.14", "172.217.0.1", "2607:f8b0:4004:800::200e"]
)
def test_net_rules_allow_public_ips(addr):
    assert is_public_ip(addr) is True


@pytest.mark.parametrize(
    ("host", "allowed"),
    [
        ("rr3---sn-abc.googlevideo.com", True),
        ("RR1---SN-X.GOOGLEVIDEO.COM.", True),
        ("www.youtube.com", True),
        ("googlevideo.com", False),
        (".googlevideo.com", False),
        ("evilgooglevideo.com", False),
        ("googlevideo.com.evil.io", False),
        ("youtu.be", False),
        ("169.254.169.254", False),
        ("localhost", False),
    ],
)
def test_net_rules_media_host_allowlist(host, allowed):
    assert is_allowed_media_host(host) is allowed


@pytest.mark.parametrize(
    ("v6", "v4"),
    [
        ("::ffff:10.0.0.1", "10.0.0.1"),
        ("2002:a9fe:a9fe::1", "169.254.169.254"),
        ("2001:0:4136:e378:8000:63bf:3fff:fdd2", "192.0.2.45"),  # RFC 4380 example
    ],
)
def test_net_rules_unwrap_ipv4_inside_ipv6(v6, v4):
    # Defence in depth: older Python patch releases misjudged some of these ranges
    # (CVE-2024-4032), so the embedded IPv4 address is what gets judged.
    import ipaddress

    from app.core.net_rules import unwrap_ipv4

    assert unwrap_ipv4(ipaddress.ip_address(v6)) == ipaddress.ip_address(v4)
