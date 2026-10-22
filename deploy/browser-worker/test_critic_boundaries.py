import socketserver
import threading
import unittest
from unittest.mock import patch

import egress_proxy as proxy


class Boundaries(unittest.TestCase):
    def test_proxy_bind_is_only_rfc1918_ipv4(self):
        for value in (
            "::",
            "0.0.0.0",
            "127.0.0.2",
            "8.8.8.8",
            "169.254.1.1",
            "100.64.0.1",
            "999.1.1.1",
        ):
            with self.subTest(value=value):
                self.assertFalse(proxy.private_ipv4(value))
        for value in ("10.0.0.2", "172.16.0.2", "172.31.255.254", "192.168.4.2"):
            self.assertTrue(proxy.private_ipv4(value))

    def test_header_obeys_absolute_deadline_without_dns_or_connection(self):
        class FakeSocket:
            def __init__(self):
                self.recv_count = 0
                self.sent = b""

            def settimeout(self, timeout):
                pass

            def recv(self, n):
                self.recv_count += 1
                return b"CONNECT example.org:443 HTTP/1.1\r\nHost: example.org:443\r\n\r\n"

            def sendall(self, value):
                self.sent += value

        handler = proxy.ConnectHandler.__new__(proxy.ConnectHandler)
        handler.request = FakeSocket()
        handler.server = type("Server", (), {"hosts": ["example.org"]})()
        with (
            patch.object(proxy.time, "monotonic", side_effect=[0, 31]),
            patch.object(proxy, "checked_target", side_effect=AssertionError("DNS after deadline")),
        ):
            handler.handle()
        self.assertEqual(handler.request.recv_count, 0)
        self.assertIn(b"403 Forbidden", handler.request.sent)

    def test_concurrency_cap_rejects_seventeenth_without_thread(self):
        server = proxy.ConnectProxy.__new__(proxy.ConnectProxy)
        server.slots = threading.BoundedSemaphore(16)
        started = []
        refused = []
        server.shutdown_request = lambda request: refused.append(request)
        with patch.object(
            socketserver.ThreadingTCPServer,
            "process_request",
            lambda self, request, address: started.append(request),
        ):
            for i in range(17):
                server.process_request(i, ("fixture", i))
        self.assertEqual(started, list(range(16)))
        self.assertEqual(refused, [16])


if __name__ == "__main__":
    unittest.main()
