import socket
import unittest

from egress_proxy import canonical_hosts, checked_target, parse_connect


class EgressTests(unittest.TestCase):
    def resolver(self, *ips):
        return lambda *a, **k: [
            (
                socket.AF_INET6 if ":" in ip else socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                (ip, 443, 0, 0) if ":" in ip else (ip, 443),
            )
            for ip in ips
        ]

    def test_public_address_is_returned_numeric_not_hostname(self):
        target = checked_target("example.org:443", ["example.org"], self.resolver("93.184.216.34"))
        self.assertEqual(target[3], ("93.184.216.34", 443))

        def json_resolver(*a, **k):
            return [[2, 1, 6, "", ["93.184.216.34", 443]]]

        self.assertEqual(
            checked_target("example.org:443", ["example.org"], json_resolver)[3],
            ("93.184.216.34", 443),
        )

    def test_every_private_and_mixed_answer_refused(self):
        for ip in (
            "127.0.0.1",
            "10.1.1.1",
            "172.17.0.1",
            "192.168.1.1",
            "169.254.169.254",
            "100.64.0.1",
            "0.0.0.0",
            "224.1.1.1",
            "::1",
            "fc00::1",
            "fe80::1",
            "::ffff:93.184.216.34",
            "2002:7f00:1::1",
            "2002:0a00:1::1",
            "2001:0:4136:e378:8000:63bf:3fff:fdd2",
        ):
            with self.subTest(ip=ip), self.assertRaises(ValueError):
                checked_target(
                    "example.org:443", ["example.org"], self.resolver("93.184.216.34", ip)
                )

    def test_authority_refusals_never_resolve(self):
        def fail(*a, **k):
            self.fail("resolver was reached")

        for authority in (
            "example.org:80",
            "example.org.:443",
            "EXAMPLE.ORG:443",
            "example.org.evil.test:443",
            "127.0.0.1:443",
            "[::1]:443",
            "user@example.org:443",
            "example.org:443/path",
            "example.org:0443",
        ):
            with self.subTest(authority=authority), self.assertRaises(ValueError):
                checked_target(authority, ["example.org"], fail)

    def test_canonical_allowlist(self):
        for hosts in (
            [],
            ["example.org", "example.org"],
            ["*.example.org"],
            ["localhost"],
            ["127.0.0.1"],
            ["example.org."],
            ["EXAMPLE.ORG"],
        ):
            with self.subTest(hosts=hosts), self.assertRaises(ValueError):
                canonical_hosts(hosts)

    def test_connect_framing_and_headers(self):
        good = b"CONNECT example.org:443 HTTP/1.1\r\nHost: example.org:443\r\nProxy-Connection: keep-alive\r\n\r\n"
        self.assertEqual(parse_connect(good, ["example.org"]), "example.org:443")
        for bad in (
            good + b"TLS",
            good.replace(b"CONNECT", b"GET"),
            good.replace(b"Host:", b"X-Host:"),
            good.replace(b"Host: example.org:443", b"Host: evil.test:443"),
            good.replace(b"\r\n\r\n", b"\r\nHost: example.org:443\r\n\r\n"),
            good.replace(b"HTTP/1.1", b"HTTP/1.0"),
            b"x" * 8193,
        ):
            with self.subTest(bad=bad[:80]), self.assertRaises(ValueError):
                parse_connect(bad, ["example.org"])


if __name__ == "__main__":
    unittest.main()
