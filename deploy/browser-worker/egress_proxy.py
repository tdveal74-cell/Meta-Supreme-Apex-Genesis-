"""Candidate HTTPS CONNECT proxy. Dedicated browser network only, no public listener.

Every target is an exact configured DNS hostname on port 443. Resolve all
addresses, reject the whole answer if any address is not globally routable, then
connect a checked numeric address. No resolver runs after validation. Redirects
and subresources need a new independently checked CONNECT. There is no HTTP
forwarding, DNS forwarding, arbitrary port, environment proxy or retry path.
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
import select
import socket
import socketserver
import subprocess
import sys
import threading
import time

HOST = re.compile(
    r"(?=.{1,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?\Z"
)
MAX_HEADER = 8192
MAX_TUNNEL_BYTES = 32 * 1024 * 1024


def private_ipv4(value):
    try:
        ip = ipaddress.ip_address(value)
        return ip.version == 4 and any(
            ip in ipaddress.ip_network(cidr)
            for cidr in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
        )
    except ValueError:
        return False


def canonical_hosts(raw):
    if not isinstance(raw, (list, tuple)) or not 1 <= len(raw) <= 20:
        raise ValueError("bounded public hosts required")
    result = tuple(raw)
    if len(set(result)) != len(result) or any(
        not isinstance(x, str) or not HOST.fullmatch(x) for x in result
    ):
        raise ValueError("canonical DNS hosts required")
    return result


def bounded_resolver(host, port, **kwargs):
    # Kill the isolated resolver process on timeout; no blocked resolver thread
    # survives to exhaust proxy slots. argv is data, never shell source.
    program = "import socket,json,sys; a=socket.getaddrinfo(sys.argv[1],443,type=socket.SOCK_STREAM); assert 0<len(a)<=32; print(json.dumps(a))"
    result = subprocess.run(
        [sys.executable, "-I", "-c", program, host],
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    )
    if len(result.stdout) > 16384:
        raise ValueError("DNS answer oversized")
    return json.loads(result.stdout)


def checked_target(authority, allowed_hosts, resolver=bounded_resolver):
    hosts = canonical_hosts(allowed_hosts)
    if not isinstance(authority, str) or authority.count(":") != 1:
        raise ValueError("HTTPS target required")
    host, port = authority.split(":")
    if host not in hosts or port != "443":
        raise ValueError("target refused")
    answers = resolver(host, 443, type=socket.SOCK_STREAM)
    if not answers or len(answers) > 32:
        raise ValueError("bounded DNS answer required")
    checked = []
    for family, kind, protocol, _name, address in answers:
        if family not in (socket.AF_INET, socket.AF_INET6) or kind != socket.SOCK_STREAM:
            raise ValueError("address family refused")
        ip = ipaddress.ip_address(address[0])
        if not ip.is_global or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
            raise ValueError("non-public DNS answer refused")
        if family == socket.AF_INET6 and (
            ip.ipv4_mapped is not None
            or ip.sixtofour is not None
            or ip.teredo is not None
            or address[3] != 0
        ):
            raise ValueError("mapped or scoped IPv6 refused")
        checked.append((family, kind, protocol, tuple(address)))
    return checked[0]


def parse_connect(raw, hosts):
    if len(raw) > MAX_HEADER or not raw.endswith(b"\r\n\r\n") or b"\x00" in raw:
        raise ValueError("bounded header required")
    lines = raw.decode("ascii").split("\r\n")
    parts = lines[0].split(" ")
    if len(parts) != 3 or parts[0] != "CONNECT" or parts[2] != "HTTP/1.1":
        raise ValueError("CONNECT required")
    authority = parts[1]
    if authority not in tuple(host + ":443" for host in canonical_hosts(hosts)):
        raise ValueError("target refused")
    seen = set()
    for line in lines[1:-2]:
        name, sep, value = line.partition(":")
        if not sep or not re.fullmatch(r"[A-Za-z-]+", name) or name.lower() in seen:
            raise ValueError("header refused")
        seen.add(name.lower())
        if name.lower() not in {"host", "proxy-connection", "user-agent"}:
            raise ValueError("header refused")
        if name.lower() == "host" and value.strip() != authority:
            raise ValueError("authority mismatch")
    if "host" not in seen:
        raise ValueError("Host required")
    return authority


class ConnectProxy(socketserver.ThreadingTCPServer):
    allow_reuse_address = False
    daemon_threads = True
    request_queue_size = 16

    def __init__(self, address, hosts):
        self.hosts = canonical_hosts(hosts)
        self.slots = threading.BoundedSemaphore(16)
        super().__init__(address, ConnectHandler)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


class ConnectHandler(socketserver.BaseRequestHandler):
    def handle(self):
        upstream = None
        established = False
        deadline = time.monotonic() + 30
        try:
            self.request.settimeout(5)
            raw = b""
            while not raw.endswith(b"\r\n\r\n"):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ValueError("header deadline exceeded")
                self.request.settimeout(min(5, remaining))
                chunk = self.request.recv(min(1024, MAX_HEADER + 1 - len(raw)))
                if not chunk:
                    return
                raw += chunk
                if len(raw) > MAX_HEADER:
                    raise ValueError("header too large")
            authority = parse_connect(raw, self.server.hosts)
            if time.monotonic() >= deadline:
                raise ValueError("header deadline exceeded")
            family, kind, protocol, address = checked_target(authority, self.server.hosts)
            if time.monotonic() >= deadline:
                raise ValueError("DNS deadline exceeded")
            upstream = socket.socket(family, kind, protocol)
            upstream.settimeout(min(10, max(0.01, deadline - time.monotonic())))
            upstream.connect(address)
            if time.monotonic() >= deadline:
                raise ValueError("connect deadline exceeded")
            self.request.settimeout(max(0.01, deadline - time.monotonic()))
            self.request.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            established = True
            total = 0
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return
                ready, _, _ = select.select([self.request, upstream], [], [], min(15, remaining))
                if not ready:
                    return
                for source in ready:
                    chunk = source.recv(65536)
                    if not chunk:
                        return
                    total += len(chunk)
                    if total > MAX_TUNNEL_BYTES:
                        return
                    (upstream if source is self.request else self.request).sendall(chunk)
        except (ValueError, UnicodeError, OSError, subprocess.SubprocessError):
            if not established:
                try:
                    self.request.sendall(
                        b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
                    )
                except OSError:
                    pass
        finally:
            if upstream is not None:
                upstream.close()


if __name__ == "__main__":
    if os.environ.get("DEVON_EGRESS_PROXY_ENABLED") != "1":
        raise SystemExit("proxy disabled")
    # Private interface is assigned by the isolated test/deployment network.
    address = os.environ.get("DEVON_EGRESS_BIND", "")
    if not private_ipv4(address):
        raise SystemExit("private dedicated interface required")
    with ConnectProxy(
        (address, 3128), os.environ.get("DEVON_BROWSER_ALLOWED_HOSTS", "").split(",")
    ) as server:
        server.serve_forever(poll_interval=0.25)
