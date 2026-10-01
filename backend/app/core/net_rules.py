"""Network-level SSRF rules (pure): which IPs and hosts the worker may download from."""

import ipaddress

# Where YouTube serves media bytes, plus its own hosts (redirects may pass through them).
MEDIA_HOST_SUFFIX = ".googlevideo.com"
MEDIA_EXACT_HOSTS = frozenset({"youtube.com", "www.youtube.com", "m.youtube.com"})


def unwrap_ipv4(ip: ipaddress.IPv4Address | ipaddress.IPv6Address):
    """IPv6 forms that carry an IPv4 address are judged by that IPv4 address."""
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:  # ::ffff:10.0.0.1
            return ip.ipv4_mapped
        if ip.sixtofour is not None:  # 2002:0a00:0001::/48 → 10.0.0.1
            return ip.sixtofour
        if ip.teredo is not None:  # 2001:0::/32 → (server, client)
            return ip.teredo[1]
    return ip


def is_public_ip(value: str) -> bool:
    """True only for globally routable unicast addresses.

    `is_global` already excludes private, loopback, link-local (incl. 169.254.169.254
    cloud metadata), CGNAT 100.64/10, reserved, unspecified and documentation ranges.
    """
    try:
        ip = unwrap_ipv4(ipaddress.ip_address(value.split("%", 1)[0]))  # drop IPv6 zone id
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and int(ip) >> 32 == 0:
        return False  # ::/96 (incl. deprecated ::a.b.c.d IPv4-compatible form, ::, ::1)
    return ip.is_global and not ip.is_multicast


def is_allowed_media_host(host: str) -> bool:
    host = host.lower().rstrip(".")
    return host in MEDIA_EXACT_HOSTS or (
        host.endswith(MEDIA_HOST_SUFFIX) and len(host) > len(MEDIA_HOST_SUFFIX)
    )
